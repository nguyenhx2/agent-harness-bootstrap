# ADR 0001: Money is integer cents, rounded half up

Status: Accepted

## Context

Floating-point amounts drift: 0.1 + 0.2 is not 0.3, and a tax line computed in floats can be off by
a cent from the same line computed by the accounting system downstream.

## Decision

Every amount is an `int` number of cents. Any division (tax, discounts) rounds **half up** to the
cent with `money.round_half_up`, never with `round()` (banker's rounding) and never by truncation.

## Consequences

- Parsing and formatting live in `money.py`; nothing else converts to or from a decimal string.
- A rate is an integer in basis points, so a rate times an amount is still an integer.
