"""Gate: the parsed log must match the challenge's published figures exactly,
and the audit outputs must be internally consistent. Exit 1 on any miss.

Published figures (icpmconference.org/2019/?p=302): 76,349 purchase
documents, 251,734 items, 1,595,923 events, 42 activities, 627 users
(607 human, 20 batch).
"""
import json
import sys
from pathlib import Path

import pandas as pd

PUBLISHED = {"items": 251734, "events": 1595923, "purchase_documents": 76349,
             "activities": 42, "human_users": 607, "batch_users": 20}


def main() -> int:
    errors = []
    cases = pd.read_parquet("data/cases.parquet")
    events = pd.read_parquet("data/events.parquet")
    users = events["user"]
    got = {"items": len(cases), "events": len(events),
           "purchase_documents": cases["po_document"].nunique(),
           "activities": events["activity"].nunique(),
           "human_users": users[users.str.startswith("user_")].nunique(),
           "batch_users": users[users.str.startswith("batch_")].nunique()}
    for k, v in PUBLISHED.items():
        if got[k] != v:
            errors.append(f"{k}: parsed {got[k]} != published {v}")
    if cases["case_id"].duplicated().any():
        errors.append("duplicate case ids")
    if set(events["case_id"]) - set(cases["case_id"]):
        errors.append("events reference unknown cases")

    s = json.loads(Path("out/summary.json").read_text())
    flow_total = sum(s["population"]["flow_mix"].values())
    if flow_total != PUBLISHED["items"]:
        errors.append(f"flow mix sums to {flow_total}, not every item exactly once")
    three_way = s["population"]["flow_mix"]["3-way, invoice after GR"] + \
        s["population"]["flow_mix"]["3-way, invoice before GR"]
    for c in s["controls"]:
        if c["exceptions"] > c["applicable_items"]:
            errors.append(f"{c['control']}: exceptions exceed population")
        if c["control"] == "cleared_without_gr" and c["applicable_items"] != three_way:
            errors.append("3-way control denominator is not the 3-way population")
    m = s["matching"]
    if m["invoices_cleared"] > m["invoices_surviving"]:
        errors.append("more cleared invoices than surviving invoices")

    for e in errors:
        print("RECONCILE FAIL:", e)
    if not errors:
        print("reconcile ok:", got)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
