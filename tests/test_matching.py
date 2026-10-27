"""Pairing rules on hand-built sequences."""
import unittest

import pandas as pd

from p2p import activities as A
from p2p.matching import match_case

GR, IR, CLR = A.GOODS_RECEIPT, A.INVOICE_RECEIPT, A.CLEAR_INVOICE


def ts(day, hour=10):
    return pd.Timestamp(f"2018-01-{day:02d} {hour:02d}:00", tz="UTC")


class MatchingTest(unittest.TestCase):
    def test_one_to_one(self):
        r = match_case([(ts(1), GR), (ts(2), IR), (ts(9), CLR)])
        self.assertEqual(r["pairs"], [{"gr": ts(1), "ir": ts(2), "clear": ts(9)}])

    def test_monthly_rent_pairs_in_order_not_first_to_last(self):
        seq = []
        for m in (3, 10, 17):
            seq += [(ts(m), GR), (ts(m + 1), IR), (ts(m + 2), CLR)]
        r = match_case(seq)
        lags = [(p["clear"] - p["ir"]).days for p in r["pairs"]]
        self.assertEqual(lags, [1, 1, 1])
        self.assertEqual([p["gr"] for p in r["pairs"]], [ts(3), ts(10), ts(17)])

    def test_invoice_before_goods(self):
        r = match_case([(ts(1), IR), (ts(4), GR), (ts(5), CLR)])
        p = r["pairs"][0]
        self.assertLess(p["ir"], p["gr"])
        self.assertEqual(p["clear"], ts(5))

    def test_cancelled_invoice_clear_is_unmatched(self):
        # Mirrors a real log pattern: IR, cancel IR, clear (of the reversal),
        # new IR, clear.
        r = match_case([(ts(1), GR), (ts(2), IR), (ts(5), A.CANCEL_IR),
                        (ts(5, 11), CLR), (ts(5, 12), IR), (ts(8), CLR)])
        self.assertEqual(r["unmatched_clears"], 1)
        self.assertEqual(r["pairs"], [{"gr": ts(1), "ir": ts(5, 12), "clear": ts(8)}])

    def test_reversal_clear_does_not_take_an_older_open_invoice(self):
        # IR1 open, IR2 recorded then reversed, the reversal is cleared.
        # IR1 must stay open; the clear is unmatched.
        r = match_case([(ts(1), GR), (ts(2), IR), (ts(3), IR), (ts(4), A.CANCEL_IR),
                        (ts(4, 11), CLR)])
        self.assertEqual(r["unmatched_clears"], 1)
        self.assertEqual(r["pairs"], [{"gr": ts(1), "ir": ts(2), "clear": None}])

    def test_subsequent_invoice_takes_no_receipt_slot(self):
        r = match_case([(ts(1), GR), (ts(2), IR), (ts(3), A.SUBSEQUENT_INVOICE),
                        (ts(5), GR), (ts(6), IR)])
        self.assertEqual([p["gr"] for p in r["pairs"]], [ts(1), None, ts(5)])

    def test_cancelled_gr_removes_latest_receipt(self):
        r = match_case([(ts(1), GR), (ts(2), GR), (ts(3), A.CANCEL_GR), (ts(4), IR)])
        self.assertEqual(r["surviving_gr"], 1)
        self.assertEqual(r["pairs"][0]["gr"], ts(1))

    def test_clear_cannot_pay_an_invoice_recorded_later(self):
        r = match_case([(ts(1), GR), (ts(2), CLR), (ts(3), IR)])
        self.assertEqual(r["unmatched_clears"], 1)
        self.assertIsNone(r["pairs"][0]["clear"])

    def test_open_invoice_has_no_clear(self):
        r = match_case([(ts(1), GR), (ts(2), IR)])
        self.assertIsNone(r["pairs"][0]["clear"])


if __name__ == "__main__":
    unittest.main()
