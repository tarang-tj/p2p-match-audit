"""Collapse the event table into one row of facts per purchase-order item.

Every control and summary reads this table, so each fact is computed once.
Timestamps stay in UTC; `local_date` helpers convert to the company's
timezone (Europe/Amsterdam), because vendor invoice dates are recorded as
local midnight.
"""
import pandas as pd

from . import activities as A

LOCAL_TZ = "Europe/Amsterdam"

# Activity -> short column stem for counts and first/last timestamps.
TRACKED = {
    A.CREATE_PO: "po",
    A.GOODS_RECEIPT: "gr",
    A.CANCEL_GR: "cancel_gr",
    A.SERVICE_ENTRY: "ses",
    A.VENDOR_INVOICE: "vinv",
    A.INVOICE_RECEIPT: "ir",
    A.CANCEL_IR: "cancel_ir",
    A.SUBSEQUENT_INVOICE: "subseq_ir",
    A.CLEAR_INVOICE: "clear",
    A.REMOVE_BLOCK: "unblock",
    A.SET_BLOCK: "block",
    A.CHANGE_PRICE: "chg_price",
    A.CHANGE_QUANTITY: "chg_qty",
    A.DELETE_ITEM: "delete",
    A.REACTIVATE_ITEM: "reactivate",
}


def local_date(ts: pd.Series) -> pd.Series:
    """Calendar date in the company's timezone (NaT stays NaT)."""
    return ts.dt.tz_convert(LOCAL_TZ).dt.normalize()


def build_case_facts(cases: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Return one row per case_id with flow, counts, timings, values, users."""
    facts = cases.set_index("case_id").copy()
    unknown = set(facts["item_category"]) - set(A.FLOW_BY_CATEGORY)
    if unknown:
        raise ValueError(f"unknown item categories: {sorted(unknown)}")
    facts["flow"] = facts["item_category"].map(A.FLOW_BY_CATEGORY)

    tracked = events[events["activity"].isin(TRACKED)]
    stem = tracked["activity"].map(TRACKED)
    grouped = tracked.assign(stem=stem).groupby(["case_id", "stem"])["timestamp"]
    counts = grouped.size().unstack(fill_value=0)
    firsts = grouped.min().unstack()
    lasts = grouped.max().unstack()
    for col in TRACKED.values():
        facts[f"n_{col}"] = counts[col].reindex(facts.index).fillna(0).astype(int) \
            if col in counts else 0
        facts[f"first_{col}"] = firsts[col].reindex(facts.index) \
            if col in firsts else pd.NaT
        facts[f"last_{col}"] = lasts[col].reindex(facts.index) \
            if col in lasts else pd.NaT

    facts["net_gr"] = facts["n_gr"] - facts["n_cancel_gr"]
    facts["net_ir"] = facts["n_ir"] + facts["n_subseq_ir"] - facts["n_cancel_ir"]

    # Item value: the value recorded on Create Purchase Order Item.
    po_val = events[events["activity"] == A.CREATE_PO].groupby("case_id")["value_eur"].first()
    facts["po_value_eur"] = po_val.reindex(facts.index)
    facts["value_varies"] = events.groupby("case_id")["value_eur"].nunique() \
        .reindex(facts.index).fillna(1) > 1
    facts["n_events"] = events.groupby("case_id").size().reindex(facts.index).fillna(0).astype(int)
    return facts


def role_users(events: pd.DataFrame, exclude: frozenset = frozenset()) -> pd.DataFrame:
    """Human users per case for each SoD-relevant role, as frozensets.

    Columns: creators, receivers, invoicers, clearers. Batch jobs, NONE and
    any `exclude` accounts (interface users) are dropped: a
    segregation-of-duties conflict needs a person.
    """
    roles = {
        A.CREATE_PO: "creators",
        A.GOODS_RECEIPT: "receivers",
        A.INVOICE_RECEIPT: "invoicers",
        A.CLEAR_INVOICE: "clearers",
    }
    ev = events[events["activity"].isin(roles) & events["user"].map(A.is_human)
                & ~events["user"].isin(exclude)]
    ev = ev.assign(role=ev["activity"].map(roles))
    out = ev.groupby(["case_id", "role"])["user"].agg(frozenset).unstack()
    for col in roles.values():
        if col not in out:
            out[col] = None
    empty = frozenset()

    def fill(col: pd.Series) -> pd.Series:
        return col.map(lambda v: v if isinstance(v, frozenset) else empty)
    return out[list(roles.values())].apply(fill)
