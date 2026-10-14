"""CSV export of line items (TASK-001, step 1)."""

import csv
import io

from invoicer.pricing import LineItem

HEADER = ("name", "unit_cents", "quantity", "total_cents")


def to_csv(lines: list[LineItem]) -> str:
    """Line items as CSV text with a header row and Unix line endings."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(HEADER)
    for line in lines:
        writer.writerow((line.name, line.unit_cents, line.quantity, line.total_cents))
    return buf.getvalue()
