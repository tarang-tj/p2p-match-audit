"""Stream the BPI Challenge 2019 XES log into two flat tables.

The raw file is a single 729 MB line of XML, so it is parsed trace by trace
with lxml.iterparse and each element is cleared after use. Output:

- cases: one row per purchase-order item (the XES trace) with its attributes.
- events: one row per event, keyed by case_id, in file order.
"""
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

import pandas as pd
from lxml import etree

# XES trace attribute key -> column name used everywhere downstream.
CASE_FIELDS = {
    "concept:name": "case_id",
    "Purchasing Document": "po_document",
    "Item": "po_item",
    "Item Category": "item_category",
    "Item Type": "item_type",
    "GR-Based Inv. Verif.": "gr_based_iv",
    "Goods Receipt": "goods_receipt_flag",
    "Document Type": "document_type",
    "Purch. Doc. Category name": "doc_category",
    "Company": "company",
    "Vendor": "vendor",
    "Name": "vendor_name",
    "Spend area text": "spend_area",
    "Sub spend area text": "sub_spend_area",
    "Spend classification text": "spend_class",
    "Source": "source_system",
}

EVENT_FIELDS = {
    "concept:name": "activity",
    "time:timestamp": "timestamp",
    "User": "user",
    "org:resource": "resource",
    "Cumulative net worth (EUR)": "value_eur",
}


def _attr_value(el: etree._Element):
    """Convert one typed XES attribute element to a Python value."""
    tag = etree.QName(el).localname
    raw = el.get("value")
    if tag == "boolean":
        return raw == "true"
    if tag == "float":
        return float(raw)
    if tag == "int":
        return int(raw)
    return raw


def iter_traces(path: Path) -> Iterator[Tuple[Dict, List[Dict]]]:
    """Yield (case_attributes, events) per trace without loading the file."""
    for _, trace in etree.iterparse(str(path), events=("end",), tag="{*}trace"):
        case: Dict = {}
        events: List[Dict] = []
        for child in trace:
            name = etree.QName(child).localname
            if name == "event":
                ev = {}
                for attr in child:
                    key = attr.get("key")
                    if key in EVENT_FIELDS:
                        ev[EVENT_FIELDS[key]] = _attr_value(attr)
                events.append(ev)
            else:
                key = child.get("key")
                if key in CASE_FIELDS:
                    case[CASE_FIELDS[key]] = _attr_value(child)
        if "case_id" not in case:
            raise ValueError("trace without concept:name; log is malformed")
        yield case, events
        trace.clear()
        while trace.getprevious() is not None:
            del trace.getparent()[0]


def load(path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Parse the XES file into (cases, events) DataFrames."""
    cases: List[Dict] = []
    rows: List[Dict] = []
    for case, events in iter_traces(path):
        cases.append(case)
        cid = case["case_id"]
        for seq, ev in enumerate(events):
            ev["case_id"] = cid
            ev["seq"] = seq
            rows.append(ev)
    cases_df = pd.DataFrame(cases, columns=list(CASE_FIELDS.values()))
    events_df = pd.DataFrame(rows, columns=["case_id", "seq"] + list(EVENT_FIELDS.values()))
    events_df["timestamp"] = pd.to_datetime(events_df["timestamp"], utc=True)
    return cases_df, events_df


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xes", type=Path)
    parser.add_argument("--out", type=Path, default=Path("data"))
    args = parser.parse_args()
    cases, events = load(args.xes)
    args.out.mkdir(parents=True, exist_ok=True)
    cases.to_parquet(args.out / "cases.parquet", index=False)
    events.to_parquet(args.out / "events.parquet", index=False)
    print(f"cases={len(cases)} events={len(events)}")


if __name__ == "__main__":
    main()
