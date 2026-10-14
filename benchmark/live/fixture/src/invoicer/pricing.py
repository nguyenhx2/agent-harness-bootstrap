"""Line items and subtotals."""

from dataclasses import dataclass

from invoicer.money import parse_cents


@dataclass(frozen=True)
class LineItem:
    name: str
    unit_cents: int
    quantity: int

    @property
    def total_cents(self) -> int:
        return self.unit_cents * self.quantity


def parse_line(spec: str) -> LineItem:
    """'widget:250:2' -> LineItem('widget', 250, 2)."""
    try:
        name, unit, qty = spec.split(":")
    except ValueError:
        raise ValueError(f"line item must be name:unit_cents:quantity, got {spec!r}") from None
    quantity = int(qty)
    if quantity <= 0:
        raise ValueError(f"quantity must be positive: {spec!r}")
    return LineItem(name, parse_cents(unit), quantity)


def subtotal(lines: list[LineItem]) -> int:
    return sum(line.total_cents for line in lines)
