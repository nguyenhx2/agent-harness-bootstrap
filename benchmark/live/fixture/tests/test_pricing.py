import unittest

from tests import _path  # noqa: F401
from invoicer.pricing import LineItem, parse_line, subtotal


class PricingTest(unittest.TestCase):
    def test_parse_line(self):
        self.assertEqual(parse_line("widget:250:2"), LineItem("widget", 250, 2))

    def test_bad_line(self):
        with self.assertRaises(ValueError):
            parse_line("widget:250")
        with self.assertRaises(ValueError):
            parse_line("widget:250:0")

    def test_subtotal(self):
        lines = [parse_line("a:250:2"), parse_line("b:1000:1")]
        self.assertEqual(subtotal(lines), 1500)


if __name__ == "__main__":
    unittest.main()
