"""Pair goods receipts, invoices and clearings inside one PO item.

The challenge asks how multiple GRs and invoices on one item relate. The
log's per-event values cannot settle it (see docs/data-quality.md), so the
pairing uses order and time only:

1. Cancellations reverse the most recent open document of their kind
   (Cancel Goods Receipt -> latest GR, Cancel Invoice Receipt -> latest IR).
2. The k-th surviving invoice pairs with the k-th surviving goods receipt.
   For invoice-before-GR items the invoice may come first; the lag is then
   negative and means "invoice waited for goods".
3. Events are applied in time order. Each Cancel Invoice Receipt creates
   one reversal document; the next Clear Invoice after it (before any new
   invoice) clears that reversal and stays unmatched. Any other clear pairs with the earliest invoice
   still open at that moment. Record Subsequent Invoice is an invoice but
   takes no goods-receipt slot.

Throughput per matched invoice: GR->IR lag, IR->clear lag, and
ready->clear where ready = max(GR, IR), the moment the item became payable.
"""
from typing import Dict, List

import pandas as pd

from . import activities as A

_RELEVANT = {A.GOODS_RECEIPT, A.CANCEL_GR, A.INVOICE_RECEIPT,
             A.SUBSEQUENT_INVOICE, A.CANCEL_IR, A.CLEAR_INVOICE}


def match_case(events: List[tuple]) -> Dict[str, list]:
    """Match one case in a single pass. `events` = [(timestamp, activity)]
    in time order. Cancellations and clearings are applied in the order they
    happened, so a clearing can only see invoices still open at that moment.
    """
    grs: List[pd.Timestamp] = []
    irs: List[dict] = []  # {"ts", "clear", "subsequent"} for surviving invoices
    unmatched_clears = 0
    pending_reversals = 0  # Cancel IR seen, its reversal not yet cleared
    for ts, act in events:
        if act == A.GOODS_RECEIPT:
            grs.append(ts)
        elif act == A.CANCEL_GR:
            if grs:
                grs.pop()
        elif act in (A.INVOICE_RECEIPT, A.SUBSEQUENT_INVOICE):
            irs.append({"ts": ts, "clear": None, "subsequent": act == A.SUBSEQUENT_INVOICE})
            pending_reversals = 0
        elif act == A.CANCEL_IR:
            if irs:
                reversed_ir = irs.pop()
                if reversed_ir["clear"] is not None:
                    unmatched_clears += 1  # it paid an invoice that no longer exists
            pending_reversals += 1
        elif act == A.CLEAR_INVOICE:
            if pending_reversals:
                pending_reversals -= 1
                unmatched_clears += 1  # clearing of the reversal document
                continue
            # Single pass: every invoice in `irs` was recorded before this clear.
            slot = next((i for i in irs if i["clear"] is None), None)
            if slot is None:
                unmatched_clears += 1
            else:
                slot["clear"] = ts

    pairs = []
    regular = 0
    for ir in irs:
        gr = None
        if not ir["subsequent"]:
            gr = grs[regular] if regular < len(grs) else None
            regular += 1
        pairs.append({"gr": gr, "ir": ir["ts"], "clear": ir["clear"]})
    return {"pairs": pairs, "surviving_gr": len(grs), "surviving_ir": len(irs),
            "unmatched_clears": unmatched_clears}


def match_all(events: pd.DataFrame, facts: pd.DataFrame) -> pd.DataFrame:
    """One row per surviving invoice across the log, with lags in days."""
    ev = events[events["activity"].isin(_RELEVANT)]
    ev = ev.sort_values(["case_id", "timestamp", "seq"], kind="mergesort")
    rows = []
    unmatched = {}
    for case_id, grp in ev.groupby("case_id", sort=False):
        result = match_case(list(zip(grp["timestamp"], grp["activity"])))
        unmatched[case_id] = result["unmatched_clears"]
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
    # Per-item count, kept for every item, including items whose invoices
    # were all reversed and so have no row above.
    out.attrs["unmatched_clears"] = pd.Series(unmatched, dtype=int)
    return out


def naive_throughput(facts: pd.DataFrame) -> pd.Series:
    """Baseline most dashboards show: first GR to last clear, per item, days."""
    return (facts["last_clear"] - facts["first_gr"]) / pd.Timedelta(days=1)
