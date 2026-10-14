import contextlib
import io
import os
import unittest
from unittest import mock

from tests import _path  # noqa: F401
from invoicer.cli import main


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(argv)
    return code, out.getvalue()


class CliTest(unittest.TestCase):
    def test_total(self):
        with mock.patch.dict(os.environ, {"INVOICER_CURRENCY": "USD"}):
            code, out = run(["total", "widget:250:2", "gadget:1000:1", "--tax-bp", "825"])
        self.assertEqual(code, 0)
        self.assertIn("subtotal USD 15.00", out)
        self.assertIn("tax      USD 1.24", out)
        self.assertIn("total    USD 16.24", out)


if __name__ == "__main__":
    unittest.main()
