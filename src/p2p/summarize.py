"""Turn per-item flags and matched invoices into reportable aggregates.

Every number in docs/findings.md and the web page comes from the dict
returned by `summary()`, written to out/summary.json.
"""
from typing import Dict

import pandas as pd

from . import activities as A
from .controls import CONTROLS, SOD_PAIRS, sod_conflict_users


def clean_json(obj):
    """Replace NaN/NaT with None recursively so the output is strict JSON."""
    if isinstance(obj, dict):
        return {k: clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    if isinstance(obj, float) and obj != obj:
        return None
    return obj


def _pct(n: float, d: float) -> float:
    return round(100.0 * n / d, 2) if d else 0.0


def control_table(flags: pd.DataFrame, facts: pd.DataFrame) -> pd.DataFrame:
    """Per control: applicable items, exceptions, rate, item value at stake."""
    titles = {c.key: (c.title, c.family) for c in CONTROLS}
    titles.update({k: (v[2], "segregation of duties") for k, v in SOD_PAIRS.items()})
    rows = []
    for key in flags.columns:
        col = flags[key]
        applies = col.notna()
        hit = col == True  # noqa: E712
        rows.append({
            "control": key, "title": titles[key][0], "family": titles[key][1],
            "applicable_items": int(applies.sum()), "exceptions": int(hit.sum()),
            "rate_pct": _pct(hit.sum(), applies.sum()),
            "po_value_eur": round(float(facts.loc[hit[hit].index, "po_value_eur"].sum()), 2),
            "value_share_pct": _pct(facts.loc[hit[hit].index, "po_value_eur"].sum(),
                                    facts["po_value_eur"].sum()),
        })
    return pd.DataFrame(rows)


def by_dimension(flags: pd.DataFrame, facts: pd.DataFrame, control: str,
                 dim: str, min_items: int = 50, top: int = 10) -> pd.DataFrame:
    """Exception rate for one control by a case attribute (vendor, company...)."""
    col = flags[control]
    df = pd.DataFrame({dim: facts[dim], "applies": col.notna(), "hit": col == True})  # noqa: E712
    g = df[df["applies"]].groupby(dim).agg(items=("hit", "size"), exceptions=("hit", "sum"))
    g = g[g["items"] >= min_items]
    g["rate_pct"] = (100.0 * g["exceptions"] / g["items"]).round(2)
    return g.sort_values(["exceptions", "rate_pct"], ascending=False).head(top).reset_index()


def throughput_table(matched: pd.DataFrame) -> pd.DataFrame:
    """Median and P90 lags (days) per flow for matched, cleared invoices."""
    done = matched[matched["clear"].notna()]
    rows = []
    for flow, g in done.groupby("flow"):
        row = {"flow": flow, "label": A.FLOW_LABELS[flow], "cleared_invoices": len(g)}
        for col in ("gr_to_ir_days", "ir_to_clear_days", "ready_to_clear_days"):
            s = g[col].dropna()
            row[f"{col}_median"] = round(float(s.median()), 1) if len(s) else None
            row[f"{col}_p90"] = round(float(s.quantile(0.9)), 1) if len(s) else None
        rows.append(row)
    return pd.DataFrame(rows)


def naive_vs_matched(matched: pd.DataFrame, naive: pd.Series) -> Dict:
    """How much first-GR-to-last-clear overstates per-invoice time to pay.

    Compared on items with 2+ cleared invoices, where the two methods differ.
    """
    done = matched[matched["clear"].notna() & matched["gr"].notna()]
    per_item = done.groupby("case_id").agg(n=("k", "size"),
                                           matched_days=("ready_to_clear_days", "median"))
    multi = per_item[per_item["n"] >= 2].join(naive.rename("naive_days"))
    multi = multi.dropna()
    return {
        "items_with_2plus_cleared_invoices": int(len(multi)),
        "naive_median_days": round(float(multi["naive_days"].median()), 1),
        "matched_median_days": round(float(multi["matched_days"].median()), 1),
    }


def sod_concentration(roles: pd.DataFrame) -> Dict[str, Dict]:
    """Top users behind each SoD conflict and the share they account for."""
    out = {}
    for key, (left, right, _) in SOD_PAIRS.items():
        users = sod_conflict_users(roles, left, right)
        total = int(users.sum())
        top = users.head(5)
        out[key] = {"conflicting_user_items": total,
                    "distinct_users": int(len(users)),
                    "top_users": [[u, int(n)] for u, n in top.items()],
                    "top1_share_pct": _pct(top.iloc[0], total) if total else 0.0}
    return out


def block_effect(matched: pd.DataFrame, facts: pd.DataFrame) -> list:
    """Median days from payable to cleared, items with vs without a removed
    payment block, per 3-way flow. Shows what a block costs in time."""
    done = matched[matched["clear"].notna()].copy()
    done["blocked"] = done["case_id"].map(facts["n_unblock"] > 0)
    rows = []
    for (flow, blocked), g in done.groupby(["flow", "blocked"]):
        if flow not in (A.FLOW_3WAY_AFTER, A.FLOW_3WAY_BEFORE):
            continue
        rows.append({"flow": flow, "blocked": bool(blocked), "cleared_invoices": len(g),
                     "ready_to_clear_median_days": round(float(g["ready_to_clear_days"].median()), 1)})
    return rows
