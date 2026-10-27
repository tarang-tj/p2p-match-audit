"""Data-quality facts the analysis must disclose before any finding.

Main one: the challenge text says invoice values on an item add up to the
item's worth. In this log most items repeat the item's value on every
event, so value-based three-way matching is not supported. This module
measures that instead of assuming it.
"""
from typing import Dict

import pandas as pd

from . import activities as A


def value_semantics(events: pd.DataFrame, facts: pd.DataFrame) -> Dict:
    """Does each invoice event carry its own amount, or the item value?"""
    inv = events[events["activity"] == A.INVOICE_RECEIPT]
    inv = inv.join(facts["po_value_eur"], on="case_id")
    multi_inv_items = facts.index[facts["n_ir"] >= 2]
    m = inv[inv["case_id"].isin(multi_inv_items)]
    per_item = m.groupby("case_id").agg(total=("value_eur", "sum"),
                                        po=("po_value_eur", "first"))
    sums_to_po = ((per_item["total"] - per_item["po"]).abs() <= 1.0).sum()
    return {
        "items": int(len(facts)),
        "items_value_constant": int((~facts["value_varies"]).sum()),
        "items_value_constant_pct": round(100.0 * (~facts["value_varies"]).mean(), 2),
        "invoice_events_equal_item_value_pct": round(
            100.0 * (inv["value_eur"] == inv["po_value_eur"]).mean(), 2),
        "items_with_2plus_invoices": int(len(per_item)),
        "of_which_invoices_sum_to_item_value": int(sums_to_po),
        "zero_value_items": int((facts["po_value_eur"] == 0).sum()),
    }


def time_window(events: pd.DataFrame, facts: pd.DataFrame) -> Dict:
    """Events and PO creations outside the 2018 collection window."""
    ts = events["timestamp"]
    po = facts["first_po"]
    return {
        "first_event": str(ts.min()), "last_event": str(ts.max()),
        "events_before_2018": int((ts < "2018-01-01").sum()),
        "events_after_2019_01_31": int((ts > "2019-02-01").sum()),
        "po_items_created_outside_2018": int(((po < "2018-01-01") | (po >= "2019-01-01")).sum()),
    }


def interface_users(events: pd.DataFrame, min_events: int = 100,
                    min_share: float = 0.95) -> Dict[str, float]:
    """Human-named users who act like a system interface.

    Signal: their PO-item creations happen in the same minute as an SRM
    (shopping-cart system) event on the same item. A person keying POs by
    hand does not move in lockstep with a batch interface.
    """
    srm = events[events["activity"].str.startswith("SRM:")]
    srm_keys = set(zip(srm["case_id"], srm["timestamp"].dt.floor("min")))
    po = events[(events["activity"] == A.CREATE_PO) & events["user"].map(A.is_human)]
    out = {}
    for user, g in po.groupby("user"):
        if len(g) < min_events:
            continue
        keys = zip(g["case_id"], g["timestamp"].dt.floor("min"))
        share = sum(k in srm_keys for k in keys) / len(g)
        if share >= min_share:
            out[user] = round(share, 4)
    return out


def payment_runs(events: pd.DataFrame) -> Dict:
    """Is clearing a scheduled run? Weekday mix and top clearing account."""
    cl = events[events["activity"] == A.CLEAR_INVOICE]
    local = cl["timestamp"].dt.tz_convert("Europe/Amsterdam")
    weekday = local.dt.day_name().value_counts()
    top_user = cl["user"].value_counts()
    top = top_user.index[0]
    top_days = cl.loc[cl["user"] == top, "timestamp"].dt.tz_convert("Europe/Amsterdam").dt.date.nunique()
    return {
        "clears": int(len(cl)),
        "weekday_share_pct": {d: round(100.0 * n / len(cl), 2) for d, n in weekday.items()},
        "top_clearing_user": top,
        "top_clearing_user_share_pct": round(100.0 * top_user.iloc[0] / len(cl), 2),
        "top_clearing_user_distinct_days": int(top_days),
    }


def users(events: pd.DataFrame) -> Dict:
    u = events["user"]
    return {
        "human_users": int(u[u.map(A.is_human)].nunique()),
        "batch_users": int(u[u.map(A.is_batch)].nunique()),
        "events_without_user_pct": round(100.0 * (u == A.NO_USER).mean(), 2),
        "no_user_by_activity_pct": {
            a: round(100.0 * x, 1) for a, x in
            events.loc[u == A.NO_USER, "activity"].value_counts(normalize=True).head(3).items()},
    }
