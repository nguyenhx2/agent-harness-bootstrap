#!/usr/bin/env python3
"""Deterministic completion check for this skill. Replace check() with the real rules.

The skill's "done" is this script's exit code, not the model's opinion of its own output.
Stdlib only. Reads its input, writes nothing, touches no network - so running it twice gives the
same answer, and running it is always safe.

Exit codes: 0 valid, 1 findings (printed one per line), 2 bad input (missing or unreadable).

Usage:
    python scripts/validate.py <output-path>
"""
from __future__ import annotations

import pathlib
import sys


def check(text: str) -> list[str]:
    """Return one message per problem. An empty list means the output is complete."""
    problems: list[str] = []
    if not text.strip():
        problems.append("output is empty")
    # Add the skill's own rules here: required headings, fields, IDs, formats.
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate.py <output-path>")
        return 2
    path = pathlib.Path(argv[1])
    if not path.is_file():
        print(f"not a file: {path}")
        return 2
    problems = check(path.read_text(encoding="utf-8", errors="replace"))
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
