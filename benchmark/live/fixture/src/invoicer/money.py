"""Integer-cent money helpers. See docs/adr/0001-integer-cents.md."""


def parse_cents(text: str) -> int:
    """'250' -> 250. Rejects negatives and non-integers."""
    value = int(text)
    if value < 0:
        raise ValueError(f"negative amount: {text}")
    return value


def format_cents(cents: int, currency: str = "USD") -> str:
    """1234 -> 'USD 12.34'."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{currency} {cents // 100}.{cents % 100:02d}"


def round_half_up(numerator: int, denominator: int) -> int:
    """Integer division rounded half up, for non-negative numerators."""
    return (2 * numerator + denominator) // (2 * denominator)
