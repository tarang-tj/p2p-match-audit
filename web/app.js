/* Page wiring: loads data/site.json and fills each section from it.
   Every number on the page comes from that file; nothing is typed in by hand. */
(function () {
  const fmt = (n) => Number(n).toLocaleString("en-US");
  const $ = (id) => document.getElementById(id);
  const CONTROL_FAMILIES = ["all", "conformance", "purchasing", "rework", "segregation of duties", "process"];
  const TRIP_LABEL = {};
  const esc = (v) => String(v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const day = 864e5;

  function para(parent, html) {
    const p = document.createElement("p");
    p.innerHTML = html;
    parent.appendChild(p);
  }

  function renderHero(site) {
    $("heroItems").textContent = fmt(site.population.items);
    const ex = site.examples.find((e) => e.key === "recurring");
    window.FlowChart.render($("heroFlow"), ex);
    const paid = ex.pairs.filter((p) => p.gr && p.clear);
    const span = Math.round((Math.max(...paid.map((p) => Date.parse(p.clear))) -
      Math.min(...paid.map((p) => Date.parse(p.gr)))) / day);
    const waits = paid.map((p) => (Date.parse(p.clear) - Math.max(Date.parse(p.gr), Date.parse(p.ir))) / day)
      .sort((a, b) => a - b);
    const med = waits[Math.floor(waits.length / 2)];
    $("heroCaption").textContent = `Item ${ex.case_id}, ${ex.spend_area.toLowerCase()}: ` +
      `${paid.length} invoices, each matched to its own receipt and payment. ` +
      `First receipt to last payment spans ${span} days; per invoice, the median wait to payment was ${Math.round(med)} days.`;
  }

  function renderExample(site, key) {
    const ex = site.examples.find((e) => e.key === key);
    document.querySelectorAll("#exampleTabs button").forEach((b) =>
      b.setAttribute("aria-selected", String(b.dataset.key === key)));
    $("exampleTitle").textContent = ex.title;
    $("exampleBlurb").textContent = ex.blurb;
    window.FlowChart.render($("exampleFlow"), ex);
    const dl = $("exampleFacts");
    dl.textContent = "";
    const rows = [["Item", ex.case_id], ["Matching rule", ex.flow], ["Spend area", ex.spend_area],
      ["Controls tripped", ex.tripped.length ? ex.tripped.map((k) => TRIP_LABEL[k] || k).join("; ") : "none"],
      ["Clearings with no open invoice", String(ex.unmatched_clears)]];
    for (const [k, v] of rows) {
      const dt = document.createElement("dt"); dt.textContent = k;
      const dd = document.createElement("dd"); dd.textContent = v;
      if (k === "Controls tripped" && ex.tripped.length) dd.className = "tripped";
      dl.append(dt, dd);
    }
    dl.dataset.case = ex.case_id;
  }

  function renderExamples(site) {
    const tabs = $("exampleTabs");
    for (const ex of site.examples) {
      const b = document.createElement("button");
      b.type = "button"; b.role = "tab"; b.dataset.key = ex.key; b.textContent = ex.title;
      b.addEventListener("click", () => renderExample(site, ex.key));
      tabs.appendChild(b);
    }
    renderExample(site, site.examples[0].key);
  }

  function renderControls(site, family) {
    const body = $("controlsTable").querySelector("tbody");
    body.textContent = "";
    const rows = site.controls.filter((c) => family === "all" || c.family === family);
    const max = Math.max(...site.controls.filter((c) => c.family !== "process").map((c) => c.rate_pct), 1);
    for (const c of rows) {
      const tr = document.createElement("tr");
      tr.dataset.control = c.control;
      const width = Math.min(100, (100 * c.rate_pct) / max);
      tr.innerHTML = `<td>${esc(c.title)}<span class="family">${esc(c.family)}</span></td>` +
        `<td class="num hide-sm">${fmt(c.applicable_items)}</td><td class="num">${fmt(c.exceptions)}</td>` +
        `<td><div class="rate${c.family === "process" ? " process" : ""}"><div class="track"><div class="fill" style="width:${width}%"></div></div>` +
        `<span>${c.exceptions ? c.rate_pct.toFixed(2) + "%" : "none"}</span></div></td>`;
      body.appendChild(tr);
    }
    document.querySelectorAll("#familyFilter button").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.family === family)));
  }

  function renderControlNotes(site) {
    site.controls.forEach((c) => { TRIP_LABEL[c.control] = c.title; });
    const filter = $("familyFilter");
    for (const f of CONTROL_FAMILIES) {
      const b = document.createElement("button");
      b.type = "button"; b.dataset.family = f; b.textContent = f === "all" ? "All controls" : f[0].toUpperCase() + f.slice(1);
      b.addEventListener("click", () => renderControls(site, f));
      filter.appendChild(b);
    }
    renderControls(site, "all");
    const sod = site.sod_concentration, raw = site.sod_including_interface_accounts;
    const iface = Object.keys(site.interface_users);
    const cr = site.controls.find((c) => c.control === "sod_create_and_receive");
    const ic = sod.sod_invoice_and_clear;
    const n = $("sodNote");
    para(n, `<strong>One account is a system, not a person.</strong> ${esc(iface.join(", "))} creates purchase-order items in the same minute ` +
      `as the shopping-cart system in ${(100 * site.interface_users[iface[0]]).toFixed(1)}% of cases, so it is excluded from ` +
      `segregation-of-duties checks. Counting it would raise create-and-receive conflicts from ${fmt(cr.exceptions)} to ${fmt(raw.sod_create_and_receive)}.`);
    const ci = site.controls.find((c) => c.control === "sod_create_and_invoice");
    para(n, `Invoice-and-clear conflicts come from ${ic.distinct_users} people; the busiest is involved in ${ic.top1_share_of_items_pct}% of them. ` +
      (ci.exceptions === 0 ? "No one both created an item and recorded its invoice." :
        `${fmt(ci.exceptions)} items had one person create the item and record its invoice.`));
  }

  function bar(parent, label, sub, days, maxDays, cls) {
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML = `<div class="label">${esc(label)}<small>${esc(sub)}</small></div>` +
      `<div class="bar-track"><div class="bar-fill ${cls || ""}" style="width:${(100 * days) / maxDays}%">${days} d</div></div>`;
    parent.appendChild(row);
  }

  function renderTime(site) {
    const box = $("throughputBars");
    const rows = site.block_effect;
    const max = Math.max(...rows.map((r) => r.ready_to_clear_median_days));
    const label = { "3way_after_gr": "3-way, invoice after GR", "3way_before_gr": "3-way, invoice before GR" };
    for (const r of rows) {
      bar(box, label[r.flow], `${r.blocked ? "item had a payment block removed" : "no block on the item"}, ${fmt(r.cleared_invoices)} invoices`,
        r.ready_to_clear_median_days, max, r.blocked ? "blocked" : "");
    }
    const pr = site.payment_runs, nv = site.naive_vs_matched;
    const n = $("timeNotes");
    para(n, `<strong>Payment looks like a weekly run.</strong> ${pr.weekday_share_pct.Thursday}% of clearings happen on a Thursday, and one account ` +
      `performs ${pr.top_clearing_user_share_pct}% of all clearings, on just ${pr.top_clearing_user_distinct_days} days.`);
    const gap = (flow) => {
      const b = rows.find((r) => r.flow === flow && r.blocked), u = rows.find((r) => r.flow === flow && !r.blocked);
      return (b.ready_to_clear_median_days - u.ready_to_clear_median_days).toFixed(1);
    };
    para(n, `<strong>Invoices on blocked items wait longer.</strong> Where an item had a payment block removed, its invoices clear ` +
      `${gap("3way_after_gr")} days later at the median on invoice-after-GR items and ${gap("3way_before_gr")} days later on invoice-before-GR items. ` +
      "The log does not say why a block was set, so this is an association, not a cause.");
    para(n, `<strong>Matching changes the answer.</strong> On ${fmt(nv.items_with_2plus_cleared_invoices)} items with several paid invoices, ` +
      `first-receipt-to-last-payment gives a median of ${nv.naive_median_days} days; across their ${fmt(nv.invoices_on_those_items)} matched invoices it is ${nv.matched_median_days} days.`);
  }

  function renderData(site) {
    const v = site.data_quality.value_semantics, t = site.data_quality.time_window;
    const n = $("dataNotes");
    para(n, `<strong>Amounts cannot be matched.</strong> The challenge says invoice values on an item add up to the item's worth. ` +
      `In the file, ${v.invoice_events_equal_item_value_pct}% of invoice events repeat the item's value instead, and of ` +
      `${fmt(v.items_with_2plus_invoices)} items with two or more invoices only ${v.of_which_invoices_sum_to_item_value} add up. ` +
      "So matching here uses counts and dates, never amounts.");
    para(n, `<strong>Dates leak outside 2018.</strong> ${fmt(t.events_before_2018)} events predate 2018 (the earliest is ${t.first_event.slice(0, 4)}), ` +
      `and ${fmt(t.po_items_created_outside_2018)} items were created outside the year.`);
    const nu = site.data_quality.users.no_user_by_activity_pct;
    para(n, `<strong>A quarter of events have no user.</strong> ${site.data_quality.users.events_without_user_pct}% are recorded as NONE: ` +
      `${nu["Vendor creates invoice"]}% are vendor invoice dates and ${nu["Record Service Entry Sheet"]}% service entry sheets. ` +
      "People-based checks only see the steps a person keyed.");
    para(n, `Counts reproduce the publisher's figures exactly: ${fmt(site.population.items)} items, ${fmt(site.population.events)} events, ` +
      `${fmt(site.population.purchase_documents)} purchase documents, ${site.population.activities} activity types.`);
  }

  fetch("data/site.json")
    .then((r) => { if (!r.ok) throw new Error(`site.json: HTTP ${r.status}`); return r.json(); })
    .then((site) => {
      renderHero(site);
      renderControlNotes(site);
      renderExamples(site);
      renderTime(site);
      renderData(site);
      document.body.dataset.ready = "true";
    })
    .catch((err) => {
      document.body.dataset.ready = "error";
      $("heroCaption").textContent = `Could not load the audit data (${err.message}). Serve this folder over HTTP, not file://.`;
    });
})();
