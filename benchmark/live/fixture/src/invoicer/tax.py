"""Sales tax. Rates are basis points (825 = 8.25%)."""

from invoicer.money import round_half_up


def compute_tax(subtotal_cents: int, rate_bp: int) -> int:
    """Tax on a subtotal, rounded half up to the cent (ADR 0001)."""
    if rate_bp < 0:
        raise ValueError("tax rate cannot be negative")
    return round_half_up(subtotal_cents * rate_bp, 10_000)
