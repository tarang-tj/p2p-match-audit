/* First screen: run the 13 rule controls on 5,000 real items, in the browser, one control at a time.
   Each item is one cell. A control's exceptions flash, then stay marked; the headline counts items that
   failed at least one check. Every number comes from web/audit.js on web/data/sample.json, or from
   site.json for the full log. Reduced motion: the finished state, no animation. */
(function () {
  const SHORT = {
    ir_before_gr_gr_based: "Invoice before goods receipt",
    cleared_without_gr: "Paid with no goods receipt",
    cleared_before_gr: "Paid before the goods arrived",
    gr_on_2way: "Goods receipt on a 2-way item",
    invoice_on_consignment: "Invoice on a consignment item",
    invoices_exceed_receipts: "More invoices than receipts",
    after_the_fact_po: "Invoice dated before the order",
    price_change_after_invoice: "Price changed after the invoice",
    invoice_cancelled: "Invoice reversed",
    gr_cancelled: "Goods receipt reversed",
    sod_create_and_receive: "One person ordered and received",
    sod_create_and_invoice: "One person ordered and invoiced",
    sod_invoice_and_clear: "One person invoiced and paid",
  };
  const FLOW = { "3way_after_gr": "3-way, invoice after GR", "3way_before_gr": "3-way, invoice before GR",
    "2way": "2-way", consignment: "Consignment" };
  const STEP = 420, FLASH = 260;
  const $ = (id) => document.getElementById(id);
  const fmt = (n) => Number(n).toLocaleString("en-US");
  const pct = (k, n) => (n ? (100 * k) / n : 0).toFixed(2) + "%";

  function start(site, sample, done) {
    const A = window.P2PAudit;
    const rows = A.run(sample);
    const rules = A.tally(rows).filter((t) => t.family !== "process");
    const full = Object.fromEntries(site.controls.map((c) => [c.control, c]));
    const canvas = $("runCanvas"), ctx = canvas.getContext("2d");
    const hits = rows.map(() => 0);            // how many rule controls each item has failed so far
    let focus = null, timer = 0, flashTimer = 0, geo = null, finished = false, picked = -1, nextFailed = 0;

    const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
    function layout() {
      const w = canvas.parentElement.clientWidth, cell = w >= 560 ? Math.min(7, Math.floor(w / 100)) : 5;
      const cols = Math.max(1, Math.min(100, Math.floor(w / cell))), rowsN = Math.ceil(rows.length / cols), dpr = window.devicePixelRatio || 1;
      canvas.width = cols * cell * dpr; canvas.height = rowsN * cell * dpr;
      canvas.style.width = cols * cell + "px"; canvas.style.height = rowsN * cell + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      geo = { cell, cols };
      canvas.dataset.cols = cols; canvas.dataset.cell = cell;
    }
    function paint(flash) {
      const base = css("--rule"), flag = css("--flag"), ink = css("--ink"), { cell, cols } = geo;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      rows.forEach((r, i) => {
        const on = focus ? r.flags[focus] === true : hits[i] > 0;
        ctx.globalAlpha = focus && !on ? 0.35 : 1;
        ctx.fillStyle = flash && flash.has(i) ? ink : on ? flag : base;
        ctx.fillRect((i % cols) * cell, Math.floor(i / cols) * cell, cell - 1, cell - 1);
      });
      ctx.globalAlpha = 1;
      if (picked >= 0) {                      // ring the item described under the grid
        ctx.strokeStyle = ink; ctx.lineWidth = 2;
        ctx.strokeRect((picked % cols) * cell - 2, Math.floor(picked / cols) * cell - 2, cell + 3, cell + 3);
      }
    }
    const anyCount = () => hits.filter((h) => h > 0).length;

    // ticker: one row per rule control, sample count and full-log rate
    const list = $("runTicker");
    list.textContent = "";
    for (const t of rules) {
      const li = document.createElement("li");
      li.dataset.control = t.key;
      li.innerHTML = `<button type="button" aria-pressed="false" aria-disabled="true"><span class="name"></span>` +
        `<span class="k">·</span><span class="full"></span></button>`;
      li.querySelector(".name").textContent = SHORT[t.key] || t.title;
      li.querySelector("button").title = t.title;
      li.querySelector(".full").textContent = `log ${full[t.key].rate_pct.toFixed(2)}%`;
      li.querySelector("button").addEventListener("click", () => {
        if (!finished) return;
        focus = focus === t.key ? null : t.key;
        list.querySelectorAll("button").forEach((b) =>
          b.setAttribute("aria-pressed", String(b.parentElement.dataset.control === focus)));
        paint();
      });
      list.appendChild(li);
    }

    function setCount(n) {
      $("runAny").textContent = fmt(n);
      $("barSample").style.setProperty("--w", (100 * n) / rows.length / 10 + "");
      $("barSampleVal").textContent = pct(n, rows.length);
    }
    function fire(i) {
      const t = rules[i], li = list.children[i];
      const flash = new Set();
      rows.forEach((r, j) => { if (r.flags[t.key] === true) { hits[j]++; flash.add(j); } });
      li.classList.add("fired");
      li.querySelector(".k").textContent = fmt(t.exceptions);
      li.querySelector(".k").title = `${fmt(t.exceptions)} of ${fmt(t.applicable)} sampled items (${pct(t.exceptions, t.applicable)})`;
      setCount(anyCount());
      paint(flash);
      clearTimeout(flashTimer);
      flashTimer = setTimeout(() => paint(), FLASH);
    }
    function finish() {
      finished = true;
      document.body.dataset.run = "done";
      $("runAgain").disabled = false;
      $("runFailed").disabled = false;
      list.querySelectorAll("button").forEach((b) => b.removeAttribute("aria-disabled"));
      $("runStatus").textContent = `Done: ${rules.length} checks on ${fmt(rows.length)} items. Tap a check to see only its items, or tap a cell.`;
    }
    function reset() {
      clearTimeout(timer); clearTimeout(flashTimer); hits.fill(0); focus = null; finished = false; picked = -1;
      $("runFailed").disabled = true;
      document.body.dataset.run = "running";
      list.querySelectorAll("li").forEach((li) => {
        li.classList.remove("fired"); li.querySelector(".k").textContent = "·";
        li.querySelector("button").setAttribute("aria-pressed", "false");
        li.querySelector("button").setAttribute("aria-disabled", "true");
      });
      setCount(0); paint();
    }
    function play() {
      reset();
      $("runAgain").disabled = true;
      $("runStatus").textContent = "Running the checks…";
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
        rules.forEach((_, i) => fire(i)); clearTimeout(flashTimer); paint(); finish(); return;
      }
      let i = 0;
      const next = () => { if (i < rules.length) { fire(i++); timer = setTimeout(next, STEP); } else finish(); };
      timer = setTimeout(next, 500);
    }

    function pick(i) {
      const it = rows[i];
      const failed = rules.filter((t) => it.flags[t.key] === true).map((t) => SHORT[t.key]);
      picked = i;
      $("runPick").textContent = `Item ${it.id} (${FLOW[it.flow]}, ${fmt(it.events)} events in the log): ` +
        (failed.length ? `failed ${failed.join("; ")}.` : "passed every check.");
      $("runPick").dataset.case = it.id;
      paint();
    }
    canvas.addEventListener("click", (ev) => {
      const b = canvas.getBoundingClientRect(), { cell, cols } = geo;
      const c = Math.floor((ev.clientX - b.left) / cell), r = Math.floor((ev.clientY - b.top) / cell);
      const i = r * cols + c;
      if (c < 0 || c >= cols || r < 0 || !rows[i]) return;
      pick(i);
    });
    // keyboard path to the same answer: step through the items that failed (in the focused check, if any)
    $("runFailed").addEventListener("click", () => {
      const bad = rows.map((r, i) => (focus ? r.flags[focus] === true : hits[i] > 0) ? i : -1).filter((i) => i >= 0);
      if (!bad.length) { $("runPick").textContent = "No item failed this check in the sample."; return; }
      pick(bad[nextFailed++ % bad.length]);
    });
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => paint());
    $("runAgain").addEventListener("click", play);
    let rw = 0;
    window.addEventListener("resize", () => { cancelAnimationFrame(rw); rw = requestAnimationFrame(() => { layout(); paint(); }); });

    $("barFull").style.setProperty("--w", (100 * site.any_exception) / site.population.items / 10 + "");
    $("barFullVal").textContent = pct(site.any_exception, site.population.items);
    $("runFullItems").textContent = fmt(site.population.items);
    layout();
    play();
    if (done) done(rows, rules);
  }

  window.HeroRun = { start };
})();
