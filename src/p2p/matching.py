"""Pair goods receipts, invoices and clearings inside one PO item.

The challenge asks how multiple GRs and invoices on one item relate. The
log's per-event values cannot settle it (see docs/data-quality.md), so the
pairing uses order and time only:

1. Cancellations reverse the most recent open document of their kind
   (Cancel Goods Receipt -> latest GR, Cancel Invoice Receipt -> latest IR).
2. The k-th surviving invoice pairs with the k-th surviving goods receipt.
   For invoice-before-GR items the invoice may come first; the lag is then
   negative and means "invoice waited for goods".
3. Each Clear Invoice pairs with the earliest surviving invoice recorded at
   or before it that is not yet cleared. A clear with no open invoice is
   unmatched (typically the clearing of a reversed invoice).

Throughput per matched invoice: GR->IR lag, IR->clear lag, and
ready->clear where ready = max(GR, IR), the moment the item became payable.
"""
from typing import Dict, List, Optional

import pandas as pd

from . import activities as A

_RELEVANT = {A.GOODS_RECEIPT, A.CANCEL_GR, A.INVOICE_RECEIPT,
             A.SUBSEQUENT_INVOICE, A.CANCEL_IR, A.CLEAR_INVOICE}


def match_case(events: List[tuple]) -> Dict[str, list]:
    """Match one case. `events` = [(timestamp, activity)] in time order."""
    grs: List[pd.Timestamp] = []
    irs: List[pd.Timestamp] = []
    clears: List[pd.Timestamp] = []
    for ts, act in events:
        if act == A.GOODS_RECEIPT:
            grs.append(ts)
        elif act == A.CANCEL_GR:
            if grs:
                grs.pop()
        elif act in (A.INVOICE_RECEIPT, A.SUBSEQUENT_INVOICE):
            irs.append(ts)
        elif act == A.CANCEL_IR:
            if irs:
                irs.pop()
        elif act == A.CLEAR_INVOICE:
            clears.append(ts)

    pairs = []
    cleared_by: List[Optional[pd.Timestamp]] = [None] * len(irs)
    unmatched_clears = 0
    for clr in clears:
        slot = next((i for i, t in enumerate(irs) if cleared_by[i] is None and t <= clr), None)
        if slot is None:
            unmatched_clears += 1
        else:
            cleared_by[slot] = clr
    for k, ir in enumerate(irs):
        gr = grs[k] if k < len(grs) else None
        pairs.append({"gr": gr, "ir": ir, "clear": cleared_by[k]})
    return {"pairs": pairs, "surviving_gr": len(grs), "surviving_ir": len(irs),
            "unmatched_clears": unmatched_clears}


def match_all(events: pd.DataFrame, facts: pd.DataFrame) -> pd.DataFrame:
    """One row per surviving invoice across the log, with lags in days."""
    ev = events[events["activity"].isin(_RELEVANT)]
    ev = ev.sort_values(["case_id", "timestamp", "seq"], kind="mergesort")
    rows = []
    for case_id, grp in ev.groupby("case_id", sort=False):
        result = match_case(list(zip(grp["timestamp"], grp["activity"])))
        for k, p in enumerate(result["pairs"]):
            rows.append({"case_id": case_id, "k": k, **p,
                         "case_unmatched_clears": result["unmatched_clears"]})
    out = pd.DataFrame(rows, columns=["case_id", "k", "gr", "ir", "clear",
                                      "case_unmatched_clears"])
    for col in ("gr", "ir", "clear"):
        out[col] = pd.to_datetime(out[col], utc=True)
    day = pd.Timedelta(days=1)
    out["gr_to_ir_days"] = (out["ir"] - out["gr"]) / day
    out["ir_to_clear_days"] = (out["clear"] - out["ir"]) / day
    ready = out[["gr", "ir"]].max(axis=1)
    out["ready_to_clear_days"] = (out["clear"] - ready) / day
    out["flow"] = out["case_id"].map(facts["flow"])
    return out


def naive_throughput(facts: pd.DataFrame) -> pd.Series:
    """Baseline most dashboards show: first GR to last clear, per item, days."""
    return (facts["last_clear"] - facts["first_gr"]) / pd.Timedelta(days=1)
