"""Build web/data/sample.json: a seeded random 5,000 items from the real log, for the
in-browser audit (web/audit.js).

Only the events the controls read are kept (the tracked activities in features.TRACKED).
Times are UTC epoch minutes (every timestamp in the log is on a whole minute; checked
here). Users are kept only as role keys (user_NNN, batch_NN, NONE), as the publisher
anonymized them. The interface accounts are found on the FULL log
(data_quality.interface_users) and shipped with the sample, because 5,000 items are too
few to detect them.

Before writing, the sample is audited with the Python controls and every flag is checked
against out/item_flags.parquet from the full-log run, so the sample is the same audit,
just fewer items. Usage: PYTHONPATH=src python3 scripts/build_sample.py
"""
import json
from pathlib import Path

import pandas as pd

from p2p.controls import evaluate
from p2p.data_quality import interface_users
from p2p.features import TRACKED, build_case_facts, role_users

N, SEED = 5000, 2019
OUT = Path("web/data/sample.json")


def draw(cases: pd.DataFrame, events: pd.DataFrame):
    ids = cases["case_id"].sample(N, random_state=SEED).sort_values()
    c = cases[cases["case_id"].isin(set(ids))].sort_values("case_id")
    e = events[events["case_id"].isin(set(ids)) & events["activity"].isin(TRACKED)]
    return c, e.sort_values(["case_id", "timestamp", "seq"], kind="mergesort")


def python_flags(c: pd.DataFrame, e: pd.DataFrame, iface) -> pd.DataFrame:
    return evaluate(build_case_facts(c, e), role_users(e, exclude=frozenset(iface)))


def encode(c: pd.DataFrame, e: pd.DataFrame, iface, n_events: pd.Series, flags: pd.DataFrame) -> dict:
    ns = e["timestamp"].astype("int64")
    if (ns % 60_000_000_000).any():
        raise ValueError("a timestamp is not on a whole minute; epoch minutes would lose it")
    acts = sorted(e["activity"].unique())
    users = sorted(e["user"].unique())
    cats = sorted(c["item_category"].unique())
    ai, ui, ci = ({v: i for i, v in enumerate(x)} for x in (acts, users, cats))
    evs = {cid: [] for cid in c["case_id"]}
    for cid, a, t, u in zip(e["case_id"], e["activity"], ns // 60_000_000_000, e["user"]):
        evs[cid].append([ai[a], int(t), ui[u]])
    return {
        "note": f"Seeded random sample ({N:,} of the log's items, seed {SEED}) of BPI Challenge 2019, "
                "CC BY 4.0. Only the events the controls read. Times are UTC epoch minutes.",
        "seed": SEED, "activities": acts, "users": users, "categories": cats,
        "interface_users": list(iface),
        # what the Python audit says about this sample; the browser probe holds the page to it
        "expected": {
            "any_exception": int((flags.drop(columns="payment_block_removed") == True)  # noqa: E712
                                 .any(axis=1).sum()),
            "controls": {k: [int(flags[k].notna().sum()), int((flags[k] == True).sum())]  # noqa: E712
                         for k in flags.columns}},
        # per item: id, category, control events, and the item's full event count in the log
        "items": [[cid, ci[cat], evs[cid], int(n_events[cid])]
                  for cid, cat in zip(c["case_id"], c["item_category"])],
    }


def main() -> None:
    cases = pd.read_parquet("data/cases.parquet")
    events = pd.read_parquet("data/events.parquet")
    iface = sorted(interface_users(events))
    c, e = draw(cases, events)
    mine = python_flags(c, e, iface)
    full = pd.read_parquet("out/item_flags.parquet").drop(columns="flow").loc[mine.index]
    same = (mine.astype(object).where(mine.notna(), "na") == full.astype(object).where(full.notna(), "na"))
    if not same.all().all():
        bad = same.columns[~same.all()].tolist()
        raise SystemExit(f"sample flags differ from the full-log audit on: {bad}")
    n_events = events[events["case_id"].isin(set(c["case_id"]))].groupby("case_id").size()
    OUT.write_text(json.dumps(encode(c, e, iface, n_events, mine), separators=(",", ":")))
    print(f"sample ok: {len(c):,} items, {len(e):,} events, {OUT.stat().st_size / 1024:.0f} KB; "
          "flags equal the full-log audit")


if __name__ == "__main__":
    main()
