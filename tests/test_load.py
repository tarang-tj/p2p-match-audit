"""Loader on a 3-trace XES fixture: every trace and event, typed correctly."""
import unittest
from pathlib import Path

from p2p.load_log import load

FIXTURE = Path(__file__).parent / "fixtures" / "mini.xes"


class LoadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, cls.events = load(FIXTURE)

    def test_counts(self):
        self.assertEqual(len(self.cases), 3)
        self.assertEqual(len(self.events), 5)

    def test_case_attributes_and_types(self):
        row = self.cases.set_index("case_id").loc["1_00001"]
        self.assertEqual(row["po_document"], "1")
        self.assertEqual(row["item_category"], "3-way match, invoice after GR")
        self.assertIs(bool(row["gr_based_iv"]), True)

    def test_events_keep_order_value_and_utc_time(self):
        ev = self.events[self.events["case_id"] == "2_00001"]
        self.assertEqual(list(ev["seq"]), [0, 1])
        self.assertEqual(list(ev["activity"]), ["Record Goods Receipt", "Change Quantity"])
        self.assertEqual(str(ev["timestamp"].iloc[0].tz), "UTC")
        v = self.events.loc[self.events["case_id"] == "1_00002", "value_eur"].iloc[0]
        self.assertEqual(v, 7.5)


if __name__ == "__main__":
    unittest.main()
