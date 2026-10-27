"""Build tiny case/event tables by hand for tests with known answers."""
import pandas as pd

CATEGORY = {
    "after": "3-way match, invoice after GR",
    "before": "3-way match, invoice before GR",
    "2way": "2-way match",
    "consign": "Consignment",
}


def make_log(spec):
    """spec: {case_id: (flow_key, [(iso_ts, activity, user, value), ...])}."""
    cases, events = [], []
    for cid, (flow, evs) in spec.items():
        cases.append({"case_id": cid, "item_category": CATEGORY[flow],
                      "vendor": "v1", "company": "c1", "spend_area": "s1"})
        for seq, (ts, act, user, val) in enumerate(evs):
            events.append({"case_id": cid, "seq": seq, "activity": act,
                           "timestamp": pd.Timestamp(ts, tz="UTC"),
                           "user": user, "resource": user, "value_eur": val})
    return pd.DataFrame(cases), pd.DataFrame(events)
