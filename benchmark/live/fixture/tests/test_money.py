import unittest

from tests import _path  # noqa: F401
from invoicer.money import format_cents, parse_cents, round_half_up


class MoneyTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_cents("250"), 250)
        with self.assertRaises(ValueError):
            parse_cents("-1")

    def test_format(self):
        self.assertEqual(format_cents(1234), "USD 12.34")
        self.assertEqual(format_cents(5, "EUR"), "EUR 0.05")

    def test_round_half_up(self):
        self.assertEqual(round_half_up(5, 10), 1)
        self.assertEqual(round_half_up(4, 10), 0)
        self.assertEqual(round_half_up(15, 10), 2)


if __name__ == "__main__":
    unittest.main()
