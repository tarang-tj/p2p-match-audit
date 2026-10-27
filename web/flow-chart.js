/* Document-flow chart: one lane per document type, one mark per event,
   and a line through each receipt -> invoice -> clearing the matcher paired. */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const LANES = [
    { step: "VINV", label: "Vendor invoice date", color: "--vinv" },
    { step: "PO", label: "Purchase order", color: "--po" },
    { step: "GR", label: "Goods receipt", color: "--gr" },
    { step: "IR", label: "Invoice", color: "--ir" },
    { step: "CLR", label: "Cleared", color: "--clr" },
  ];
  const LANE_OF = { VINV: "VINV", PO: "PO", GR: "GR", xGR: "GR", IR: "IR", xIR: "IR", UNBLOCK: "IR", CLR: "CLR" };

  function el(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  }

  function fmtDate(ms) {
    return new Date(ms).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "Europe/Amsterdam" });
  }

  function render(container, example, opts) {
    const narrow = (opts && opts.narrow) || container.clientWidth < 560;
    const W = narrow ? 560 : 960, left = narrow ? 104 : 150, right = 24, top = 18, laneH = narrow ? 40 : 46;
    const H = top + LANES.length * laneH + 34;
    const css = getComputedStyle(document.documentElement);
    const color = (v) => css.getPropertyValue(v).trim();
    const times = example.events.map((e) => Date.parse(e.t));
    let t0 = Math.min(...times), t1 = Math.max(...times);
    if (t1 - t0 < 864e5) { t0 -= 432e5; t1 += 432e5; }
    const pad = (t1 - t0) * 0.03;
    const x = (t) => left + ((t - (t0 - pad)) / (t1 - t0 + 2 * pad)) * (W - left - right);
    const y = (step) => top + LANES.findIndex((l) => l.step === LANE_OF[step]) * laneH + laneH / 2;

    container.textContent = "";
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
      "aria-label": `${example.title}: ${example.events.length} events from ${fmtDate(t0)} to ${fmtDate(t1)}` }, container);
    svg.dataset.events = String(example.events.length);
    svg.dataset.pairs = String(example.pairs.length);

    LANES.forEach((lane, i) => {
      const cy = top + i * laneH + laneH / 2;
      el("line", { x1: left, x2: W - right, y1: cy, y2: cy, class: "axis" }, svg);
      const label = el("text", { x: left - 10, y: cy + 4, "text-anchor": "end", class: "lane-label" }, svg);
      label.textContent = narrow ? lane.label.replace("Vendor invoice date", "Vendor inv.") : lane.label;
    });

    for (const p of example.pairs) {
      const pts = [["GR", p.gr], ["IR", p.ir], ["CLR", p.clear]].filter(([, t]) => t)
        .map(([s, t]) => [x(Date.parse(t)), y(s)]).sort((a, b) => a[1] - b[1]);
      if (pts.length > 1) {
        el("polyline", { points: pts.map((q) => q.join(",")).join(" "), fill: "none",
          stroke: color("--muted"), "stroke-width": 1.4, "stroke-dasharray": "3 3", class: "pair" }, svg);
      }
    }

    for (const ev of example.events) {
      const cx = x(Date.parse(ev.t)), cy = y(ev.step);
      const lane = LANES.find((l) => l.step === LANE_OF[ev.step]);
      const c = color(lane.color);
      let mark;
      if (ev.step.startsWith("x")) {
        mark = el("g", { class: "mark cancel" }, svg);
        el("circle", { cx, cy, r: 7, fill: color("--sheet"), stroke: c, "stroke-width": 2 }, mark);
        el("path", { d: `M${cx - 4},${cy - 4}L${cx + 4},${cy + 4}M${cx + 4},${cy - 4}L${cx - 4},${cy + 4}`,
          stroke: c, "stroke-width": 2 }, mark);
      } else if (ev.step === "UNBLOCK") {
        mark = el("rect", { x: cx - 5, y: cy - 12, width: 10, height: 6, rx: 1, fill: c, class: "mark unblock" }, svg);
      } else {
        mark = el("circle", { cx, cy, r: 6.5, fill: c, class: "mark" }, svg);
      }
      const title = el("title", {}, mark);
      title.textContent = `${ev.step} ${new Date(ev.t).toLocaleString("en-GB", { timeZone: "Europe/Amsterdam" })} (${ev.user})`;
    }

    const ticks = narrow ? 3 : 5;
    for (let i = 0; i <= ticks; i++) {
      const t = t0 + ((t1 - t0) * i) / ticks;
      const tx = el("text", { x: x(t), y: H - 10, "text-anchor": "middle" }, svg);
      tx.textContent = fmtDate(t);
    }
    return svg;
  }

  window.FlowChart = { render };
})();
