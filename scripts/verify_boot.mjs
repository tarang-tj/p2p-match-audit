// Boot probe: serve web/ over HTTP, open it in headless Chromium at desktop
// and phone widths, and assert the page renders what site.json says.
// Exit 1 on any failed assertion. Screenshots land in test-results/.
import { createServer } from "node:http";
import { readFile, mkdir } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { chromium } from "playwright";

const ROOT = new URL("../web/", import.meta.url).pathname;
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json" };
const site = JSON.parse(await readFile(join(ROOT, "data/site.json"), "utf8"));
const failures = [];
const check = (cond, msg) => { if (!cond) failures.push(msg); };

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
for (const [name, width, height] of [["desktop", 1440, 900], ["mobile", 375, 812]]) {
  const page = await browser.newPage({ viewport: { width, height } });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  // Fonts come from Google; stub them so the probe does not depend on the network.
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.goto(url);
  await page.waitForFunction(() => document.body.dataset.ready, null, { timeout: 15000 });
  const tag = `[${name}]`;
  check(await page.evaluate(() => document.body.dataset.ready) === "true", `${tag} page did not reach ready`);

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
