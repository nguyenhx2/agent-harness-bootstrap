import unittest

from tests import _path  # noqa: F401
from invoicer.tax import compute_tax


class TaxTest(unittest.TestCase):
    def test_zero_rate(self):
        self.assertEqual(compute_tax(1000, 0), 0)

    def test_rounds_half_up(self):
        # 1005 * 8.25% = 82.9125 cents -> 83
        self.assertEqual(compute_tax(1005, 825), 83)
        # 1000 * 0.05% = 0.5 cents -> 1 (half rounds up, ADR 0001)
        self.assertEqual(compute_tax(1000, 5), 1)

    def test_negative_rate(self):
        with self.assertRaises(ValueError):
            compute_tax(100, -1)


if __name__ == "__main__":
    unittest.main()
