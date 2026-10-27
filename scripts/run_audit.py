"""Run the full audit: parquet in, out/ tables and out/summary.json out.

Usage: PYTHONPATH=src python3 scripts/run_audit.py [--data data] [--out out]
Deterministic: same input gives byte-identical outputs.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from p2p import activities as A
from p2p import data_quality, summarize, variants
from p2p.controls import evaluate
from p2p.features import build_case_facts, role_users
from p2p.matching import match_all, naive_throughput


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--out", type=Path, default=Path("out"))
    args = ap.parse_args()
    cases = pd.read_parquet(args.data / "cases.parquet")
    events = pd.read_parquet(args.data / "events.parquet")

    facts = build_case_facts(cases, events)
    interface = data_quality.interface_users(events)
    roles_all = role_users(events)
    roles = role_users(events, exclude=frozenset(interface))
    flags = evaluate(facts, roles)
    flags_raw = evaluate(facts, roles_all)
    matched = match_all(events, facts)

    args.out.mkdir(parents=True, exist_ok=True)
    controls = summarize.control_table(flags, facts)
    controls.to_csv(args.out / "controls.csv", index=False)
    through = summarize.throughput_table(matched)
    through.to_csv(args.out / "throughput.csv", index=False)

    breakdowns = {}
    for key in ("cleared_without_gr", "after_the_fact_po", "invoice_cancelled",
                "price_change_after_invoice", "invoices_exceed_receipts"):
        for dim in ("vendor", "company", "spend_area"):
            t = summarize.by_dimension(flags, facts, key, dim)
            t.to_csv(args.out / f"by_{dim}_{key}.csv", index=False)
            breakdowns[f"{key}.{dim}"] = t.to_dict(orient="records")

    flow_mix = facts["flow"].value_counts().rename(index=A.FLOW_LABELS)
    summary = {
        "population": {"items": int(len(facts)), "events": int(len(events)),
                       "purchase_documents": int(facts["po_document"].nunique()),
                       "activities": int(events["activity"].nunique()),
                       "flow_mix": {k: int(v) for k, v in flow_mix.items()}},
        "data_quality": {"value_semantics": data_quality.value_semantics(events, facts),
                         "time_window": data_quality.time_window(events, facts),
                         "users": data_quality.users(events)},
        "controls": controls.to_dict(orient="records"),
        "sod_concentration": summarize.sod_concentration(roles, flags),
        "sod_including_interface_accounts": {
            k: int((flags_raw[k] == True).sum())  # noqa: E712
            for k in ("sod_create_and_receive", "sod_create_and_invoice", "sod_invoice_and_clear")},
        "interface_users": interface,
        "payment_runs": data_quality.payment_runs(events),
        "payment_block_by_flow": summarize.by_dimension(
            flags, facts, "payment_block_removed", "flow", min_items=1).to_dict(orient="records"),
        "value_units": {"note": "anonymized by a linear scaling; report shares, not euros",
                        "total_item_value": round(float(facts["po_value_eur"].sum()), 2)},
        "throughput": through.to_dict(orient="records"),
        "block_effect": summarize.block_effect(matched, facts),
        "naive_vs_matched": summarize.naive_vs_matched(matched, naive_throughput(facts)),
        "matching": {"invoices_surviving": int(len(matched)),
                     "invoices_cleared": int(matched["clear"].notna().sum()),
                     "invoices_with_gr": int(matched["gr"].notna().sum()),
                     "items_with_unmatched_clears": int((matched.attrs["unmatched_clears"] > 0).sum()),
                     "unmatched_clears": int(matched.attrs["unmatched_clears"].sum())},
        "variants": variants.coverage(variants.variants(events, facts), facts),
        "breakdowns": breakdowns,
    }
    (args.out / "summary.json").write_text(json.dumps(
        summarize.clean_json(summary), indent=2, sort_keys=True, default=str, allow_nan=False))
    flags.assign(flow=facts["flow"]).to_parquet(args.out / "item_flags.parquet")
    print(controls.to_string(index=False))


if __name__ == "__main__":
    main()
