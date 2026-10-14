"""Runtime settings, read from the environment."""

import os


def currency() -> str:
    """ISO currency code used when printing amounts. Defaults to USD."""
    return os.environ.get("INVOICER_CURRENCY", "USD")
