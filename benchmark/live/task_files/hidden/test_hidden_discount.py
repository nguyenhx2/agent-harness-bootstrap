"""Hidden acceptance test for the two-module feature task. Copied in by the checker after the
session ends; the agent never sees it."""
import contextlib
import io
import os
import re
import unittest
from unittest import mock

from tests import _path  # noqa: F401
from invoicer.cli import main
from invoicer.pricing import apply_discount


class HiddenDiscountTest(unittest.TestCase):
    def test_apply_discount_rounds_half_up(self):
        # 10% of 1005 is 100.5 cents -> discount 101 (ADR 0001) -> 904 left
        self.assertEqual(apply_discount(1005, 10), 904)
        self.assertEqual(apply_discount(1500, 0), 1500)
        self.assertEqual(apply_discount(1500, 100), 0)

    def test_apply_discount_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            apply_discount(100, 101)
        with self.assertRaises(ValueError):
            apply_discount(100, -1)

    def test_cli_discount_before_tax(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"INVOICER_CURRENCY": "USD"}):
            with contextlib.redirect_stdout(out):
                code = main(["total", "widget:250:2", "gadget:1000:1",
                             "--discount", "10", "--tax-bp", "825"])
        text = out.getvalue()
        self.assertIn(code, (0, None))
        # subtotal 15.00, discount 1.50, taxable 13.50, tax 1.11, total 14.61
        self.assertRegex(text, re.compile(r"^discount\s+USD 1\.50$", re.MULTILINE))
        self.assertRegex(text, re.compile(r"^tax\s+USD 1\.11$", re.MULTILINE))
        self.assertRegex(text, re.compile(r"^total\s+USD 14\.61$", re.MULTILINE))

    def test_cli_without_discount_unchanged(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"INVOICER_CURRENCY": "USD"}):
            with contextlib.redirect_stdout(out):
                main(["total", "widget:250:2", "gadget:1000:1", "--tax-bp", "825"])
        self.assertRegex(out.getvalue(), re.compile(r"^total\s+USD 16\.24$", re.MULTILINE))


if __name__ == "__main__":
    unittest.main()
