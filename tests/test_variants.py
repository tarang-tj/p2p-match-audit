"""Variant folding rules."""
import unittest

from p2p.variants import _collapse


class VariantTest(unittest.TestCase):
    def test_repeats_collapse(self):
        self.assertEqual(_collapse(["PO", "GR", "GR", "IR", "CLR"]), "PO>GR>IR>CLR")

    def test_recurring_cycle_folds(self):
        steps = ["PO"] + ["GR", "IR", "CLR"] * 4
        self.assertEqual(_collapse(steps), "PO>GR>IR>CLR(*)")

    def test_partial_cycle_does_not_fold(self):
        steps = ["PO", "GR", "IR", "CLR", "GR", "IR"]
        self.assertEqual(_collapse(steps), "PO>GR>IR>CLR>GR>IR")

    def test_steps_before_po_kept(self):
        self.assertEqual(_collapse(["VINV", "PO", "IR", "GR", "CLR"]), "VINV>PO>IR>GR>CLR")


if __name__ == "__main__":
    unittest.main()
