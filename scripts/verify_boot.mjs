// Boot probe: serve web/ over HTTP, open it in headless Chromium at desktop
// and phone widths, and assert the page renders what site.json says.
// Exit 1 on any failed assertion. Screenshots land in test-results/.
import { createServer } from "node:http";
import { readFile, mkdir } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import vm from "node:vm";
import { chromium } from "playwright";

const ROOT = new URL("../web/", import.meta.url).pathname;
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };
const site = JSON.parse(await readFile(join(ROOT, "data/site.json"), "utf8"));
// Expected first-screen numbers: web/audit.js on the sample (tests/test_browser_parity.py ties it to Python).
const sample = JSON.parse(await readFile(join(ROOT, "data/sample.json"), "utf8"));
const actx = vm.createContext({ Intl, Date, Set, Error, Boolean });
vm.runInContext(await readFile(join(ROOT, "audit.js"), "utf8"), actx);
const runRows = actx.P2PAudit.run(sample);
const rules = actx.P2PAudit.tally(runRows).filter((t) => t.family !== "process");
const failed = (r) => rules.some((t) => r.flags[t.key] === true);
const anyN = runRows.filter(failed).length;
const pct = (k, n) => ((100 * k) / n).toFixed(2) + "%";
const failures = [];
const check = (cond, msg) => { if (!cond) failures.push(msg); };
// Hold audit.js to the Python audit's own answer on this sample (written by scripts/build_sample.py).
const exp = sample.expected;
if (anyN !== exp.any_exception) failures.push(`audit.js finds ${anyN} failing items, Python ${exp.any_exception}`);
for (const t of rules) {
  const [app, exc] = exp.controls[t.key];
  if (t.applicable !== app || t.exceptions !== exc) failures.push(`${t.key}: audit.js ${t.exceptions}/${t.applicable}, Python ${exc}/${app}`);
}

const server = createServer(async (req, res) => {
  let path = normalize(decodeURIComponent(new URL(req.url, "http://x").pathname)).replace(/^\/+/, "");
  if (!path || path === "." || path.endsWith("/")) path += "index.html";
  if (path.startsWith("..")) { res.writeHead(403); res.end(); return; }
  try {
    const body = await readFile(join(ROOT, path));
    res.writeHead(200, { "content-type": TYPES[extname(path)] || "application/octet-stream" });
    res.end(body);
  } catch {
    res.writeHead(404); res.end();
  }
}).listen(0);
const url = `http://127.0.0.1:${server.address().port}/`;

const browser = await chromium.launch();
await mkdir("test-results", { recursive: true });
// The phone run uses reduced motion, so both the animated and the instant path are probed.
for (const [name, width, height, motion] of [["desktop", 1440, 900, "no-preference"], ["mobile", 375, 812, "reduce"]]) {
  const page = await browser.newPage({ viewport: { width, height }, reducedMotion: motion });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  // Fonts come from Google; stub them so the probe does not depend on the network.
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.goto(url);
  await page.waitForFunction(() => document.body.dataset.ready, null, { timeout: 15000 });
  const tag = `[${name}]`;
  check(await page.evaluate(() => document.body.dataset.ready) === "true", `${tag} page did not reach ready`);

  await page.waitForFunction(() => ["done", "error"].includes(document.body.dataset.run), null, { timeout: 20000 });
  check(await page.evaluate(() => document.body.dataset.run) === "done", `${tag} in-browser audit did not finish`);
  check(await page.textContent("#runAny") === anyN.toLocaleString("en-US"), `${tag} headline count`);
  check(await page.textContent("#barSampleVal") === pct(anyN, runRows.length), `${tag} sample share`);
  check(await page.textContent("#barFullVal") === pct(site.any_exception, site.population.items), `${tag} full-log share`);
  const ticks = await page.$$eval("#runTicker li", (ls) => ls.map((l) => [l.dataset.control, l.querySelector(".k").textContent,
    l.querySelector(".full").textContent]));
  check(ticks.length === rules.length && rules.length === 13, `${tag} ticker rows ${ticks.length}`);
  rules.forEach((t, i) => {
    const full = site.controls.find((c) => c.control === t.key);
    check(ticks[i] && ticks[i][0] === t.key && ticks[i][1] === t.exceptions.toLocaleString("en-US") &&
      ticks[i][2] === `log ${full.rate_pct.toFixed(2)}%`, `${tag} ticker ${t.key}: ${ticks[i]}`);
  });
  const hit = runRows.findIndex(failed);
  const { cols, cell } = await page.$eval("#runCanvas", (c) => ({ cols: +c.dataset.cols, cell: +c.dataset.cell }));
  await page.click("#runCanvas", { position: { x: (hit % cols) * cell + cell / 2, y: Math.floor(hit / cols) * cell + cell / 2 } });
  check(await page.getAttribute("#runPick", "data-case") === runRows[hit].id, `${tag} cell click picks item ${runRows[hit].id}`);
  check((await page.textContent("#runPick")).includes("failed"), `${tag} picked item lists its failures`);
  check((await page.textContent("#runPick")).includes(`${sample.items[hit][3].toLocaleString("en-US")} events in the log`),
    `${tag} picked item shows its full event count`);
  await page.click("#runFailed");
  check(await page.getAttribute("#runPick", "data-case") === runRows[hit].id, `${tag} keyboard path shows the first failed item`);
  await page.click('#runTicker li[data-control="invoice_cancelled"] button');
  check(await page.getAttribute('#runTicker li[data-control="invoice_cancelled"] button', "aria-pressed") === "true", `${tag} ticker focus`);
  const [fg, bg] = await page.$eval('#runTicker li[data-control="invoice_cancelled"] button', (b) =>
    [getComputedStyle(b.querySelector(".name")).color, getComputedStyle(b).backgroundColor]);
  check(fg !== bg, `${tag} focused check name is readable (${fg} on ${bg})`);

  check(await page.textContent("#heroItems") === site.population.items.toLocaleString("en-US"), `${tag} hero item count`);
  const rec = site.examples.find((e) => e.key === "recurring");
  check(await page.getAttribute("#heroFlow svg", "data-events") === String(rec.events.length), `${tag} hero chart event count`);
  check(await page.locator("#heroFlow .mark").count() === rec.events.length, `${tag} hero marks drawn`);
  check(await page.locator("#heroFlow .pair").count() === rec.pairs.filter((p) => [p.gr, p.ir, p.clear].filter(Boolean).length > 1).length,
    `${tag} hero pair lines`);

  check(await page.locator("#controlsTable tbody tr").count() === site.controls.length, `${tag} all controls listed`);
  await page.click('#familyFilter button[data-family="segregation of duties"]');
  const sod = site.controls.filter((c) => c.family === "segregation of duties").length;
  check(await page.locator("#controlsTable tbody tr").count() === sod, `${tag} family filter`);

  for (const ex of site.examples) {
    await page.click(`#exampleTabs button[data-key="${ex.key}"]`);
    check(await page.getAttribute("#exampleFacts", "data-case") === ex.case_id, `${tag} tab ${ex.key} shows its item`);
    check(await page.getAttribute("#exampleFlow svg", "data-events") === String(ex.events.length), `${tag} tab ${ex.key} chart`);
    check(await page.getAttribute(`#exampleTabs button[data-key="${ex.key}"]`, "aria-selected") === "true", `${tag} tab ${ex.key} selected`);
  }
  check(await page.locator("#throughputBars .bar-row").count() === site.block_effect.length, `${tag} throughput bars`);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(overflow <= 0, `${tag} horizontal overflow ${overflow}px`);
  check(errors.length === 0, `${tag} console/page errors: ${errors.join(" | ")}`);
  await page.click('#familyFilter button[data-family="all"]');
  await page.click('#exampleTabs button[data-key="clean"]');
  await page.screenshot({ path: `test-results/${name}.png`, fullPage: true });
  await page.close();
}
await browser.close();
server.close();

if (failures.length) {
  for (const f of failures) console.error("BOOT FAIL:", f);
  process.exit(1);
}
console.log("boot ok: desktop 1440x900 and mobile 375x812");
