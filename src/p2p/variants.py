"""Process variants per flow: how many paths explain most items?

A variant is the item's sequence of core document steps (PO, GR, IR,
clear, plus cancellations and blocks), with SRM and change events dropped
and immediate repeats collapsed, so a rent item with 12 GR/IR/clear cycles
reads as one repeating pattern instead of 12 unique paths.
"""
from typing import Dict, List

import pandas as pd

from . import activities as A

CORE = {
    A.CREATE_PO: "PO", A.GOODS_RECEIPT: "GR", A.CANCEL_GR: "xGR",
    A.INVOICE_RECEIPT: "IR", A.CANCEL_IR: "xIR", A.CLEAR_INVOICE: "CLR",
    A.REMOVE_BLOCK: "UNBLOCK", A.VENDOR_INVOICE: "VINV",
}


def _collapse(steps: List[str]) -> str:
    """Drop immediate repeats; fold a body that is one block repeated.

    The body is everything after the PO step. If it is exactly block*k for
    k >= 2 (recurring billing), it is written once with a "(*)" marker.
    """
    out: List[str] = []
    for s in steps:
        if not out or out[-1] != s:
            out.append(s)
    head: List[str] = []
    if "PO" in out:
        i = out.index("PO")
        head, out = out[:i + 1], out[i + 1:]
    n = len(out)
    for size in range(1, n // 2 + 1):
        if out == out[:size] * (n // size):
            out = out[:size] + ["(*)"]
            break
    return ">".join(head + out).replace(">(*)", "(*)")


def variants(events: pd.DataFrame, facts: pd.DataFrame) -> pd.Series:
    """Variant string per case_id."""
    ev = events[events["activity"].isin(CORE)]
    ev = ev.sort_values(["case_id", "timestamp", "seq"], kind="mergesort")
    steps = ev.groupby("case_id", sort=False)["activity"].agg(
        lambda s: _collapse([CORE[a] for a in s]))
    return steps.reindex(facts.index).fillna("")


def coverage(var: pd.Series, facts: pd.DataFrame, top: int = 5) -> Dict[str, Dict]:
    """Per flow: distinct variants, and the top variants with item share."""
    out = {}
    for flow, idx in facts.groupby("flow").groups.items():
        counts = var.loc[idx].value_counts()
        n = int(counts.sum())
        cum = 0.0
        rows = []
        for v, c in counts.head(top).items():
            share = 100.0 * c / n
            cum += share
            rows.append({"variant": v, "items": int(c), "share_pct": round(share, 2),
                         "cumulative_pct": round(cum, 2)})
        k80 = int((counts.cumsum() / n < 0.8).sum() + 1)
        out[flow] = {"items": n, "distinct_variants": int(len(counts)),
                     "variants_for_80pct": k80, "top": rows}
    return out
