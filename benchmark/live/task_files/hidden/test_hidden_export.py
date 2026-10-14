"""Hidden acceptance test for the resume task. Copied in by the checker after the session ends;
the agent never sees it."""
import contextlib
import io
import unittest

from tests import _path  # noqa: F401
from invoicer.cli import main
from invoicer.export import to_csv
from invoicer.pricing import parse_line


class HiddenExportTest(unittest.TestCase):
    def test_export_subcommand_prints_to_csv(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["export", "widget:250:2", "gadget:1000:1"])
        self.assertIn(code, (0, None))
        expected = to_csv([parse_line("widget:250:2"), parse_line("gadget:1000:1")])
        self.assertEqual(out.getvalue().strip(), expected.strip())

    def test_total_still_works(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            main(["total", "widget:250:2"])
        self.assertIn("5.00", out.getvalue())


if __name__ == "__main__":
    unittest.main()
