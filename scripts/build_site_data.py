"""Build web/data/site.json: aggregates from out/summary.json plus a few
real example items (core events, matched pairs, flags) for the explorer.

Only aggregates and a handful of anonymized items are published; the raw
log stays in data/raw. Example picks are deterministic: the first item (by
case id) that fits each story and has a readable number of events.
"""
import json
from pathlib import Path

import pandas as pd

from p2p import activities as A
from p2p.matching import match_case
from p2p.variants import CORE

STORIES = [
    ("clean", "A clean item",
     "Ordered, received, invoiced, paid. Nothing tripped."),
    ("recurring", "Recurring billing",
     "One line item, several receipts and invoices, each paid on its own."),
    ("cleared_without_gr", "Paid with no goods receipt",
     "A 3-way item whose invoice was cleared with no surviving receipt."),
    ("after_the_fact_po", "Invoice before the order",
     "The vendor's invoice is dated before the PO item existed."),
    ("invoice_cancelled", "Invoice reversed and re-entered",
     "An invoice receipt was cancelled and booked again."),
    ("sod_invoice_and_clear", "One person, two roles",
     "The same person recorded the invoice and cleared it."),
]
MAX_EVENTS = 24


def pick(flags: pd.DataFrame, facts_n: pd.Series, story: str, used: set):
    small = facts_n[facts_n <= MAX_EVENTS].index
    f = flags.loc[flags.index.intersection(small)]
    exc_cols = [c for c in flags.columns if c not in ("flow", "payment_block_removed")]
    if story == "clean":
        ok = (f[exc_cols] != True).all(axis=1) & (f["flow"] == A.FLOW_3WAY_BEFORE)  # noqa: E712
        cand = f[ok].index
    elif story == "recurring":
        cand = facts_n.index[(facts_n >= 12) & (facts_n <= MAX_EVENTS)]
    else:
        cand = f.index[f[story] == True]  # noqa: E712
    if story == "recurring":
        return cand
    return next(c for c in sorted(cand) if c not in used)


def main() -> None:
    summary = json.loads(Path("out/summary.json").read_text())
    flags = pd.read_parquet("out/item_flags.parquet")
    cases = pd.read_parquet("data/cases.parquet").set_index("case_id")
    events = pd.read_parquet("data/events.parquet")
    core = events[events["activity"].isin(CORE)]
    n_core = core.groupby("case_id").size()

    examples = []
    used: set = set()
    for key, title, blurb in STORIES:
        cid = pick(flags, n_core, key, used)
        if key == "recurring":
            # among long items, the first whose matching clears >= 3 invoices
            for c in sorted(cid):
                ev = core[core["case_id"] == c].sort_values(["timestamp", "seq"])
                m = match_case(list(zip(ev["timestamp"], ev["activity"])))
                if sum(p["clear"] is not None for p in m["pairs"]) >= 3 and cases.loc[c, "item_category"] \
                        .startswith("3-way"):
                    cid = c
                    break
        used.add(cid)
        ev = core[core["case_id"] == cid].sort_values(["timestamp", "seq"], kind="mergesort")
        m = match_case(list(zip(ev["timestamp"], ev["activity"])))
        row = flags.loc[cid]
        tripped = [c for c in flags.columns if c != "flow" and row[c] == True]  # noqa: E712
        examples.append({
            "key": key, "title": title, "blurb": blurb, "case_id": cid,
            "flow": A.FLOW_LABELS[row["flow"]],
            "spend_area": cases.loc[cid, "spend_area"],
            "vendor": cases.loc[cid, "vendor"],
            "events": [{"t": t.isoformat(), "step": CORE[a], "user": u}
                       for t, a, u in zip(ev["timestamp"], ev["activity"], ev["user"])],
            "pairs": [{k: (v.isoformat() if v is not None else None) for k, v in p.items()}
                      for p in m["pairs"]],
            "unmatched_clears": m["unmatched_clears"],
            "tripped": tripped,
        })

    site = {k: summary[k] for k in ("population", "data_quality", "controls", "sod_concentration",
                                    "sod_including_interface_accounts", "interface_users",
                                    "payment_runs", "payment_block_by_flow", "throughput",
                                    "block_effect", "naive_vs_matched", "matching", "variants")}
    site["examples"] = examples
    out = Path("web/data")
    out.mkdir(parents=True, exist_ok=True)
    (out / "site.json").write_text(json.dumps(site, indent=1, sort_keys=True, default=str, allow_nan=False))
    print("examples:", [(e["key"], e["case_id"], len(e["events"])) for e in examples])


if __name__ == "__main__":
    main()
