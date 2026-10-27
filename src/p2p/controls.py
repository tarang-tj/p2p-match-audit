"""Procurement controls evaluated per purchase-order item.

Each control returns a boolean Series (True = exception) indexed by case_id,
plus the population it applies to, so rates always have an honest
denominator. Definitions live in docs/controls.md; keep the two in step.
"""
from dataclasses import dataclass
from typing import Callable, Dict, List

import pandas as pd

from . import activities as A
from .features import local_date


@dataclass(frozen=True)
class Control:
    key: str
    title: str
    family: str
    applies: Callable[[pd.DataFrame], pd.Series]
    flag: Callable[[pd.DataFrame], pd.Series]


def _flow(*flows: str) -> Callable[[pd.DataFrame], pd.Series]:
    return lambda f: f["flow"].isin(flows)


def _all(f: pd.DataFrame) -> pd.Series:
    return pd.Series(True, index=f.index)


THREE_WAY = (A.FLOW_3WAY_AFTER, A.FLOW_3WAY_BEFORE)

CONTROLS: List[Control] = [
    # --- Flow conformance: does the item follow its own matching rule? ---
    Control("ir_before_gr_gr_based", "Invoice recorded before any goods receipt "
            "on a GR-based item", "conformance", _flow(A.FLOW_3WAY_AFTER),
            lambda f: f["first_ir"].notna() & (f["first_gr"].isna() | (f["first_ir"] < f["first_gr"]))),
    Control("cleared_without_gr", "Invoice cleared with no net goods receipt "
            "on a 3-way item", "conformance", _flow(*THREE_WAY),
            lambda f: (f["n_clear"] > 0) & (f["net_gr"] <= 0)),
    Control("cleared_before_gr", "First invoice cleared before the first goods "
            "receipt on a 3-way item", "conformance", _flow(*THREE_WAY),
            lambda f: f["first_clear"].notna() & f["first_gr"].notna()
            & (f["first_clear"] < f["first_gr"])),
    Control("gr_on_2way", "Goods receipt recorded on a 2-way item", "conformance",
            _flow(A.FLOW_2WAY), lambda f: f["n_gr"] > 0),
    Control("invoice_on_consignment", "Invoice recorded or cleared on a "
            "consignment item", "conformance", _flow(A.FLOW_CONSIGNMENT),
            lambda f: (f["n_ir"] + f["n_clear"]) > 0),
    Control("invoices_exceed_receipts", "More net invoices than net goods "
            "receipts at the end of the log (3-way)", "conformance", _flow(*THREE_WAY),
            lambda f: (f["net_gr"] > 0) & (f["net_ir"] > f["net_gr"])),
    # --- Purchasing discipline ---
    Control("after_the_fact_po", "Vendor invoice dated before the PO item was "
            "created (local calendar date)", "purchasing", _all,
            lambda f: f["first_vinv"].notna()
            & (local_date(f["first_vinv"]) < local_date(f["first_po"]))),
    Control("price_change_after_invoice", "Price changed after an invoice was "
            "recorded", "purchasing", _all,
            lambda f: f["last_chg_price"].notna() & f["first_ir"].notna()
            & (f["last_chg_price"] > f["first_ir"])),
    # --- Rework ---
    Control("invoice_cancelled", "At least one invoice receipt cancelled",
            "rework", _all, lambda f: f["n_cancel_ir"] > 0),
    Control("gr_cancelled", "At least one goods receipt cancelled", "rework",
            _all, lambda f: f["n_cancel_gr"] > 0),
    # By design on invoice-before-GR items (invoice waits for goods), so this
    # is process volume, not an error; reported per flow.
    Control("payment_block_removed", "Payment block removed manually or by "
            "batch", "process", _all, lambda f: f["n_unblock"] > 0),
]

SOD_PAIRS = {
    "sod_create_and_receive": ("creators", "receivers",
                               "Same person created the PO item and recorded its goods receipt"),
    "sod_create_and_invoice": ("creators", "invoicers",
                               "Same person created the PO item and recorded its invoice"),
    "sod_invoice_and_clear": ("invoicers", "clearers",
                              "Same person recorded the invoice and cleared it for payment"),
}


def sod_flags(roles: pd.DataFrame, index: pd.Index) -> Dict[str, pd.Series]:
    """Segregation-of-duties conflicts: one human holds both roles on an item.

    Applies only to items where a person performed each of the two steps;
    elsewhere the flag is NaN (not applicable), never a pass.
    """
    roles = roles.reindex(index)
    out = {}
    for key, (left, right, _) in SOD_PAIRS.items():
        vals = []
        for a, b in zip(roles[left], roles[right]):
            if isinstance(a, frozenset) and isinstance(b, frozenset) and a and b:
                vals.append(bool(a & b))
            else:
                vals.append(None)
        out[key] = pd.Series(vals, index=index, dtype=object)
    return out


def sod_conflict_users(roles: pd.DataFrame, left: str, right: str) -> pd.Series:
    """Count conflicting items per human user for one SoD pair."""
    counts: Dict[str, int] = {}
    for a, b in zip(roles[left], roles[right]):
        if isinstance(a, frozenset) and isinstance(b, frozenset):
            for user in a & b:
                counts[user] = counts.get(user, 0) + 1
    return pd.Series(counts, dtype=int).sort_values(ascending=False)


def evaluate(facts: pd.DataFrame, roles: pd.DataFrame) -> pd.DataFrame:
    """Boolean exception frame: one column per control, NaN where n/a."""
    out = pd.DataFrame(index=facts.index)
    for c in CONTROLS:
        applies = c.applies(facts)
        out[c.key] = c.flag(facts).where(applies)
    for key, series in sod_flags(roles, facts.index).items():
        out[key] = series
    return out
