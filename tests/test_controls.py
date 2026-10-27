"""Each control against hand-built items whose correct answer is known."""
import unittest

from p2p import activities as A
from p2p.controls import evaluate, sod_conflict_users
from p2p.features import build_case_facts, role_users

from helpers import make_log

PO, GR, IR, CLR = A.CREATE_PO, A.GOODS_RECEIPT, A.INVOICE_RECEIPT, A.CLEAR_INVOICE

SPEC = {
    # Clean 3-way after GR: PO, GR, IR, clear; different people.
    "clean": ("after", [("2018-01-02 10:00", PO, "user_1", 100.0),
                        ("2018-01-05 10:00", GR, "user_2", 100.0),
                        ("2018-01-06 10:00", IR, "user_3", 100.0),
                        ("2018-01-20 10:00", CLR, "user_4", 100.0)]),
    # Invoice before GR item cleared with no receipt at all.
    "no_gr_paid": ("before", [("2018-01-02 10:00", PO, "user_1", 50.0),
                              ("2018-01-03 10:00", IR, "user_3", 50.0),
                              ("2018-01-04 10:00", CLR, "user_4", 50.0)]),
    # Receipt cancelled, so net GR is zero, yet the invoice was cleared.
    "gr_reversed_paid": ("before", [("2018-01-02 10:00", PO, "user_1", 50.0),
                                    ("2018-01-03 10:00", GR, "user_2", 50.0),
                                    ("2018-01-03 11:00", A.CANCEL_GR, "user_2", 50.0),
                                    ("2018-01-04 10:00", IR, "user_3", 50.0),
                                    ("2018-01-05 10:00", CLR, "user_4", 50.0)]),
    # Vendor invoice dated a day before the PO (local date), price changed later.
    "after_fact": ("before", [("2018-01-01 22:59", A.VENDOR_INVOICE, "NONE", 10.0),
                              ("2018-01-03 09:00", PO, "user_1", 10.0),
                              ("2018-01-04 09:00", GR, "user_2", 10.0),
                              ("2018-01-05 09:00", IR, "user_3", 10.0),
                              ("2018-01-06 09:00", A.CHANGE_PRICE, "user_1", 10.0)]),
    # Vendor invoice stamped 22:59 UTC = 23:59 Amsterdam (winter) on the PO's
    # own calendar day, after the PO's clock time. Same date: NOT flagged.
    "same_day": ("before", [("2018-01-03 22:59", A.VENDOR_INVOICE, "NONE", 10.0),
                            ("2018-01-03 09:00", PO, "user_1", 10.0)]),
    # PO at 23:30 UTC Jan 2 = 00:30 Jan 3 in Amsterdam; vendor invoice dated
    # Jan 2 local. Local dates differ (flag); UTC dates are equal (would miss).
    "tz_edge": ("before", [("2018-01-02 22:59", A.VENDOR_INVOICE, "NONE", 10.0),
                           ("2018-01-02 23:30", PO, "user_1", 10.0)]),
    # SoD: one person creates, receives, invoices and clears. Batch job ignored.
    "sod": ("after", [("2018-01-02 10:00", PO, "user_9", 5.0),
                      ("2018-01-03 10:00", GR, "user_9", 5.0),
                      ("2018-01-04 10:00", IR, "user_9", 5.0),
                      ("2018-01-05 10:00", CLR, "user_9", 5.0)]),
    "batch_only": ("after", [("2018-01-02 10:00", PO, "batch_01", 5.0),
                             ("2018-01-03 10:00", GR, "batch_01", 5.0)]),
    "two_way_gr": ("2way", [("2018-01-02 10:00", PO, "user_1", 7.0),
                            ("2018-01-03 10:00", GR, "user_2", 7.0)]),
    "consign_inv": ("consign", [("2018-01-02 10:00", PO, "user_1", 0.0),
                                ("2018-01-03 10:00", IR, "user_3", 0.0)]),
    # Two invoices against one receipt.
    "over_invoiced": ("after", [("2018-01-02 10:00", PO, "user_1", 9.0),
                                ("2018-01-03 10:00", GR, "user_2", 9.0),
                                ("2018-01-04 10:00", IR, "user_3", 9.0),
                                ("2018-01-05 10:00", IR, "user_3", 9.0)]),
}


class ControlsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cases, events = make_log(SPEC)
        cls.facts = build_case_facts(cases, events)
        cls.roles = role_users(events)
        cls.flags = evaluate(cls.facts, cls.roles)

    def flagged(self, key):
        col = self.flags[key]
        return sorted(col[col == True].index)  # noqa: E712 (NaN-aware)

    def test_clean_item_trips_nothing(self):
        row = self.flags.loc["clean"]
        self.assertFalse(any(v is True for v in row))

    def test_cleared_without_gr_counts_reversed_receipts(self):
        self.assertEqual(self.flagged("cleared_without_gr"), ["gr_reversed_paid", "no_gr_paid"])

    def test_after_the_fact_po_uses_local_dates(self):
        self.assertEqual(self.flagged("after_the_fact_po"), ["after_fact", "tz_edge"])

    def test_price_change_after_invoice(self):
        self.assertEqual(self.flagged("price_change_after_invoice"), ["after_fact"])

    def test_flow_specific_controls_and_denominators(self):
        self.assertEqual(self.flagged("gr_on_2way"), ["two_way_gr"])
        self.assertEqual(self.flagged("invoice_on_consignment"), ["consign_inv"])
        # Not applicable outside its flow: NaN, not False.
        self.assertTrue(self.flags.loc["clean", "gr_on_2way"] != self.flags.loc["clean", "gr_on_2way"])

    def test_invoices_exceed_receipts(self):
        self.assertEqual(self.flagged("invoices_exceed_receipts"), ["over_invoiced"])

    def test_sod_needs_a_human(self):
        for key in ("sod_create_and_receive", "sod_create_and_invoice", "sod_invoice_and_clear"):
            self.assertEqual(self.flagged(key), ["sod"], key)
        users = sod_conflict_users(self.roles, "creators", "receivers")
        self.assertEqual(users.to_dict(), {"user_9": 1})


if __name__ == "__main__":
    unittest.main()
