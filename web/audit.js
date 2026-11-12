/* The 14 controls of src/p2p/controls.py, ported to run in the browser on web/data/sample.json.
   Same definitions as docs/controls.md: each control returns true (exception), false (pass)
   or null (does not apply to the item). tests/test_browser_parity.py runs this file under
   Node and requires every flag on every sampled item to equal the Python audit's. */
(function (root) {
  const FLOW = {
    "3-way match, invoice after GR": "3way_after_gr", "3-way match, invoice before GR": "3way_before_gr",
    "2-way match": "2way", "Consignment": "consignment",
  };
  const TRACKED = {
    "Create Purchase Order Item": "po", "Record Goods Receipt": "gr", "Cancel Goods Receipt": "cancel_gr",
    "Record Service Entry Sheet": "ses", "Vendor creates invoice": "vinv", "Record Invoice Receipt": "ir",
    "Cancel Invoice Receipt": "cancel_ir", "Record Subsequent Invoice": "subseq_ir", "Clear Invoice": "clear",
    "Remove Payment Block": "unblock", "Set Payment Block": "block", "Change Price": "chg_price",
    "Change Quantity": "chg_qty", "Delete Purchase Order Item": "delete", "Reactivate Purchase Order Item": "reactivate",
  };
  const ROLE = { po: "creators", gr: "receivers", ir: "invoicers", clear: "clearers" };
  // Vendor invoice dates are recorded as local midnight, so this control compares calendar days in the
  // company's timezone, exactly as features.local_date does.
  const dayFmt = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Amsterdam", year: "numeric", month: "2-digit", day: "2-digit" });
  // formatToParts, not format(): the order of a formatted date string varies across ICU versions.
  const localDay = (min) => {
    const p = Object.fromEntries(dayFmt.formatToParts(new Date(min * 60000)).map((x) => [x.type, x.value]));
    return +p.year * 10000 + +p.month * 100 + +p.day;
  };
  const THREE = ["3way_after_gr", "3way_before_gr"];
  const has = (v) => v !== null;

  // [key, title, family, applies(flow), flag(facts)]
  const CONTROLS = [
    ["ir_before_gr_gr_based", "Invoice recorded before any goods receipt on a GR-based item", "conformance",
      (fl) => fl === "3way_after_gr", (f) => has(f.first.ir) && (!has(f.first.gr) || f.first.ir < f.first.gr)],
    ["cleared_without_gr", "Invoice cleared with no net goods receipt on a 3-way item", "conformance",
      (fl) => THREE.includes(fl), (f) => f.n.clear > 0 && f.net_gr <= 0],
    ["cleared_before_gr", "First invoice cleared before the first goods receipt on a 3-way item", "conformance",
      (fl) => THREE.includes(fl), (f) => has(f.first.clear) && has(f.first.gr) && f.first.clear < f.first.gr],
    ["gr_on_2way", "Goods receipt recorded on a 2-way item", "conformance",
      (fl) => fl === "2way", (f) => f.n.gr > 0],
    ["invoice_on_consignment", "Invoice recorded or cleared on a consignment item", "conformance",
      (fl) => fl === "consignment", (f) => f.n.ir + f.n.clear > 0],
    ["invoices_exceed_receipts", "More net invoices than net goods receipts at the end of the log (3-way)", "conformance",
      (fl) => THREE.includes(fl), (f) => f.net_gr > 0 && f.net_ir > f.net_gr],
    ["after_the_fact_po", "Vendor invoice dated before the PO item was created (local calendar date)", "purchasing",
      () => true, (f) => has(f.first.vinv) && has(f.first.po) && localDay(f.first.vinv) < localDay(f.first.po)],
    ["price_change_after_invoice", "Price changed after an invoice was recorded", "purchasing",
      () => true, (f) => has(f.last.chg_price) && has(f.first.ir) && f.last.chg_price > f.first.ir],
    ["invoice_cancelled", "At least one invoice receipt cancelled", "rework", () => true, (f) => f.n.cancel_ir > 0],
    ["gr_cancelled", "At least one goods receipt cancelled", "rework", () => true, (f) => f.n.cancel_gr > 0],
    ["payment_block_removed", "Payment block removed manually or by batch", "process", () => true, (f) => f.n.unblock > 0],
  ];
  const SOD = [
    ["sod_create_and_receive", "creators", "receivers", "Same person created the PO item and recorded its goods receipt"],
    ["sod_create_and_invoice", "creators", "invoicers", "Same person created the PO item and recorded its invoice"],
    ["sod_invoice_and_clear", "invoicers", "clearers", "Same person recorded the invoice and cleared it for payment"],
  ];
  const KEYS = CONTROLS.map((c) => c[0]).concat(SOD.map((s) => s[0]));
  const META = CONTROLS.map(([key, title, family]) => ({ key, title, family }))
    .concat(SOD.map(([key, , , title]) => ({ key, title, family: "segregation of duties" })));

  function facts(events, sample, iface) {
    const n = {}, first = {}, last = {}, roles = { creators: new Set(), receivers: new Set(), invoicers: new Set(), clearers: new Set() };
    for (const stem of Object.values(TRACKED)) { n[stem] = 0; first[stem] = null; last[stem] = null; }
    for (const [a, t, u] of events) {
      const stem = TRACKED[sample.activities[a]];
      if (!stem) continue;
      n[stem] += 1;
      if (first[stem] === null || t < first[stem]) first[stem] = t;
      if (last[stem] === null || t > last[stem]) last[stem] = t;
      const user = sample.users[u];
      if (ROLE[stem] && user.startsWith("user_") && !iface.has(user)) roles[ROLE[stem]].add(user);
    }
    return { n, first, last, roles, net_gr: n.gr - n.cancel_gr, net_ir: n.ir + n.subseq_ir - n.cancel_ir };
  }

  /* One row per item: { id, flow, flags: {key: true|false|null} }. */
  function run(sample) {
    const iface = new Set(sample.interface_users);
    return sample.items.map(([id, cat, events, logEvents]) => {
      const flow = FLOW[sample.categories[cat]];
      if (!flow) throw new Error(`unknown item category: ${sample.categories[cat]}`);
      const f = facts(events, sample, iface), flags = {};
      for (const [key, , , applies, flag] of CONTROLS) flags[key] = applies(flow) ? Boolean(flag(f)) : null;
      for (const [key, a, b] of SOD) {
        const A = f.roles[a], B = f.roles[b];
        flags[key] = A.size && B.size ? [...A].some((x) => B.has(x)) : null;
      }
      // logEvents: the item's full event count in the log (the sample keeps only control events)
      return { id, flow, flags, events: logEvents ?? events.length };
    });
  }

  /* Per control: items it applies to and exceptions, in KEYS order. */
  function tally(rows) {
    return META.map((m) => {
      let applicable = 0, exceptions = 0;
      for (const r of rows) { const v = r.flags[m.key]; if (v !== null) { applicable++; if (v) exceptions++; } }
      return { ...m, applicable, exceptions };
    });
  }

  const api = { KEYS, META, run, tally };
  if (typeof module === "object" && module.exports) module.exports = api; else root.P2PAudit = api;
})(typeof window !== "undefined" ? window : globalThis);
