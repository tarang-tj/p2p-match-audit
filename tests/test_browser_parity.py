"""The in-browser audit (web/audit.js) must be the same audit as src/p2p, item by item.

web/data/sample.json is decoded back into case and event tables here, independently of
scripts/build_sample.py, audited with the Python controls, then audited again by audit.js
under Node. Every flag on every sampled item must agree (true, false, or not applicable).
Needs Node on PATH (CI installs it before `make test`).
"""
import json
import math
import subprocess
import unittest
from pathlib import Path

import pandas as pd

from p2p.controls import evaluate
from p2p.features import build_case_facts, role_users

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "web" / "data" / "sample.json"
SITE = ROOT / "web" / "data" / "site.json"


def decode(sample):
    cases, events = [], []
    for cid, cat, evs, *_ in sample["items"]:
        cases.append({"case_id": cid, "item_category": sample["categories"][cat]})
        for seq, (a, t, u) in enumerate(evs):
            events.append({"case_id": cid, "seq": seq, "activity": sample["activities"][a],
                           "timestamp": pd.Timestamp(t * 60, unit="s", tz="UTC"),
                           "user": sample["users"][u], "value_eur": float("nan")})
    return pd.DataFrame(cases), pd.DataFrame(events)


def python_flags(sample):
    cases, events = decode(sample)
    roles = role_users(events, exclude=frozenset(sample["interface_users"]))
    flags = evaluate(build_case_facts(cases, events), roles)
    return {cid: {k: (None if v is None or (isinstance(v, float) and math.isnan(v)) else bool(v))
                  for k, v in row.items()} for cid, row in flags.to_dict(orient="index").items()}


def browser_flags(path=SAMPLE):
    out = subprocess.run(["node", str(ROOT / "scripts" / "run_browser_audit.mjs"), str(path)],
                         capture_output=True, text=True, check=True, cwd=ROOT)
    return json.loads(out.stdout)


CO, GR, IR, CL = ("Create Purchase Order Item", "Record Goods Receipt", "Record Invoice Receipt",
                  "Clear Invoice")
VI, CP, CIR, SUB = ("Vendor creates invoice", "Change Price", "Cancel Invoice Receipt",
                    "Record Subsequent Invoice")
AFTER, BEFORE = "3-way match, invoice after GR", "3-way match, invoice before GR"
# Hand-built edges a random sample can miss: (category, [(UTC time, activity, user), ...]).
EDGES = {  # times are 2018, UTC, written MM-DD HH:MM
    # local midnight: 23:00 UTC is the next day in Amsterdam, so this is NOT after the fact
    "tz_same_local_day": (BEFORE, [("03-01 23:00", VI, "NONE"), ("03-02 08:00", CO, "user_001")]),
    # 22:30 UTC is 03-01 locally, 23:30 UTC is 03-02 locally: after the fact only in local time
    "tz_local_day_before": (BEFORE, [("03-01 22:30", VI, "NONE"), ("03-01 23:30", CO, "user_001")]),
    "tz_summer_time": (BEFORE, [("07-01 21:30", VI, "NONE"), ("07-01 22:30", CO, "user_001")]),
    "same_minute_gr_clear": (BEFORE, [("02-01 09:00", CO, "user_001"), ("02-02 09:00", IR, "user_002"),
                                      ("02-03 09:00", GR, "user_003"), ("02-03 09:00", CL, "user_004")]),
    "same_minute_ir_gr": (AFTER, [("02-01 09:00", CO, "user_001"), ("02-02 09:00", GR, "user_002"),
                                  ("02-02 09:00", IR, "user_003")]),
    "ir_no_gr": (AFTER, [("02-01 09:00", CO, "user_001"), ("02-02 09:00", IR, "user_003")]),
    "price_same_minute_as_ir": (AFTER, [("02-01 09:00", CO, "user_001"), ("02-02 09:00", GR, "user_002"),
                                        ("02-03 09:00", IR, "user_003"), ("02-03 09:00", CP, "user_001")]),
    "subsequent_invoice_counts": (BEFORE, [("02-01 09:00", CO, "user_001"), ("02-02 09:00", GR, "user_002"),
                                           ("02-03 09:00", IR, "user_003"), ("02-04 09:00", SUB, "user_003"),
                                           ("02-05 09:00", CIR, "user_003")]),
    "interface_and_batch_are_not_people": (
        BEFORE, [("02-01 09:00", CO, "user_000"), ("02-02 09:00", GR, "user_000"),
                 ("02-03 09:00", IR, "batch_01"), ("02-04 09:00", CL, "batch_01")]),
    "one_person_invoice_and_clear": (
        BEFORE, [("02-01 09:00", CO, "user_001"), ("02-02 09:00", IR, "user_005"),
                 ("02-03 09:00", GR, "user_002"), ("02-04 09:00", CL, "user_005")]),
    "consignment_cleared": ("Consignment", [("02-01 09:00", CO, "user_001"),
                                            ("02-04 09:00", CL, "batch_01")]),
    "two_way_receipt": ("2-way match", [("02-01 09:00", CO, "user_001"), ("02-02 09:00", GR, "user_002")]),
    # the FIRST invoice is what counts: an invoice before the receipt, then one after it
    "first_invoice_before_receipt": (AFTER, [("02-01 09:00", IR, "user_003"), ("02-02 09:00", GR, "user_002"),
                                             ("02-03 09:00", IR, "user_003")]),
    # a reversed receipt still counts as a receipt recorded on a 2-way item
    "two_way_receipt_reversed": ("2-way match", [("02-01 09:00", CO, "user_001"),
                                                 ("02-02 09:00", GR, "user_002"),
                                                 ("02-03 09:00", "Cancel Goods Receipt", "user_002")]),
    # the LAST price change is what counts: one before the invoice, one after it
    "last_price_change_after_invoice": (
        AFTER, [("02-01 09:00", CP, "user_001"), ("02-02 09:00", GR, "user_002"),
                ("02-03 09:00", IR, "user_003"), ("02-04 09:00", CP, "user_001")]),
    # a subsequent invoice pushes net invoices past a single receipt
    "subsequent_invoice_exceeds": (
        BEFORE, [("02-01 09:00", CO, "user_001"), ("02-02 09:00", GR, "user_002"),
                 ("02-03 09:00", IR, "user_003"), ("02-04 09:00", SUB, "user_003")]),
}


def edge_sample():
    acts = sorted({a for _, evs in EDGES.values() for _, a, _ in evs})
    users = sorted({u for _, evs in EDGES.values() for _, _, u in evs})
    cats = sorted({c for c, _ in EDGES.values()})

    def minute(t):
        return int(pd.Timestamp(f"2018-{t}", tz="UTC").timestamp()) // 60
    items = [[cid, cats.index(cat), [[acts.index(a), minute(t), users.index(u)] for t, a, u in evs]]
             for cid, (cat, evs) in EDGES.items()]
    return {"activities": acts, "users": users, "categories": cats,
            "interface_users": ["user_000"], "items": items}


class EdgeParity(unittest.TestCase):
    def test_edge_items_match(self):
        import tempfile
        sample = edge_sample()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(sample, fh)
        py, js = python_flags(sample), browser_flags(fh.name)
        Path(fh.name).unlink()
        for cid in EDGES:
            self.assertEqual(js[cid], py[cid], cid)
        # the edges really are edges: pin the Python answers the port must reproduce
        self.assertFalse(py["tz_same_local_day"]["after_the_fact_po"])
        self.assertTrue(py["tz_local_day_before"]["after_the_fact_po"])
        self.assertTrue(py["tz_summer_time"]["after_the_fact_po"])
        self.assertFalse(py["same_minute_gr_clear"]["cleared_before_gr"])
        self.assertFalse(py["same_minute_ir_gr"]["ir_before_gr_gr_based"])
        self.assertTrue(py["ir_no_gr"]["ir_before_gr_gr_based"])
        self.assertFalse(py["price_same_minute_as_ir"]["price_change_after_invoice"])
        self.assertIsNone(py["interface_and_batch_are_not_people"]["sod_create_and_receive"])
        self.assertTrue(py["one_person_invoice_and_clear"]["sod_invoice_and_clear"])
        self.assertTrue(py["first_invoice_before_receipt"]["ir_before_gr_gr_based"])
        self.assertTrue(py["two_way_receipt_reversed"]["gr_on_2way"])
        self.assertTrue(py["last_price_change_after_invoice"]["price_change_after_invoice"])
        self.assertTrue(py["subsequent_invoice_exceeds"]["invoices_exceed_receipts"])
        self.assertFalse(py["subsequent_invoice_counts"]["invoices_exceed_receipts"])


class BrowserParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample = json.loads(SAMPLE.read_text())
        cls.py = python_flags(cls.sample)
        cls.js = browser_flags()

    def test_same_items(self):
        self.assertEqual(len(self.js), 5000)
        self.assertEqual(set(self.py), set(self.js))

    def test_every_flag_matches(self):
        diffs = [(cid, k, v, self.js[cid].get(k)) for cid, row in self.py.items()
                 for k, v in row.items() if self.js[cid].get(k) != v]
        self.assertEqual(diffs[:5], [], f"{len(diffs)} flags differ")
        self.assertEqual(set(next(iter(self.js.values()))), set(next(iter(self.py.values()))))

    def test_sample_rates_sit_near_the_full_log(self):
        """A seeded random sample should estimate each full-log rate within 4 standard errors."""
        full = {c["control"]: c for c in json.loads(SITE.read_text())["controls"]}
        for key, f in full.items():
            vals = [row[key] for row in self.py.values() if row[key] is not None]
            n, k = len(vals), sum(vals)
            p = f["exceptions"] / f["applicable_items"]
            band = 4 * math.sqrt(n * p * (1 - p)) + 1
            self.assertLessEqual(abs(k - n * p), band, f"{key}: {k} of {n} vs full-log rate {p:.4f}")


if __name__ == "__main__":
    unittest.main()
