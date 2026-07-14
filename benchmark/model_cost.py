#!/usr/bin/env python3
"""Cost of one feature, delivered through the generated harness, across model tiers.

READ THIS BEFORE QUOTING ANY NUMBER FROM IT
-------------------------------------------
This is a COST MODEL, not a measurement. It answers "what would this roster cost to run", by
arithmetic on published prices. It does NOT answer "would a cheaper roster produce acceptable work" -
that is a quality question, and quality cannot be derived from prices. See eval/ for how to actually
test that.

What is GROUNDED (measured from the repo):
  - each agent's system-prompt size = its own body + the 4 unconditional rules, in bytes.

What is ASSUMED (stated here, editable, not measured):
  - how many turns each seat takes, and how much it reads and writes per turn.
  - the effort multiplier on output tokens.
  - a chars-per-token divisor, when no ANTHROPIC_API_KEY is available.

Change the assumptions at the top and re-run. They are deliberately visible rather than buried,
because the conclusion is only as good as they are.

Usage:
  python model_cost.py                # table
  python model_cost.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

# --------------------------------------------------------------------------- prices (published)
# USD per 1M tokens. Source: Anthropic pricing, cached 2026-06-24. Verify before relying on it.
PRICES = {
    "fable":  {"in": 10.00, "out": 50.00},
    "opus":   {"in":  5.00, "out": 25.00},
    "sonnet": {"in":  3.00, "out": 15.00},
    "haiku":  {"in":  1.00, "out":  5.00},
}

# --------------------------------------------------------------------------- ASSUMPTIONS (edit me)
CHARS_PER_TOKEN = 3.6

# Effort changes how much the model thinks and writes. Modelled as a multiplier on OUTPUT tokens
# (thinking tokens are billed as output). These are plausible, not measured.
EFFORT_MULT = {"low": 0.4, "medium": 0.7, "high": 1.0, "xhigh": 1.7, "max": 2.6}

# Per-seat workload for ONE feature going through the standard flow.
#   turns       - agent turns (each turn re-sends the whole context: system + history so far)
#   read_kb     - source/spec/diff bytes the seat pulls in, beyond its system prompt
#   write_kb    - what it produces (code, tests, findings, log rows)
# Reviewers read a lot and write little. Dev agents write a lot. Mechanical seats do almost nothing.
WORKLOAD = {
    "orchestrator":      {"turns": 8, "read_kb": 30, "write_kb": 6},
    "spec-guardian":     {"turns": 2, "read_kb": 20, "write_kb": 3},
    "app-dev":           {"turns": 12, "read_kb": 60, "write_kb": 25},
    "qa-test":           {"turns": 6, "read_kb": 35, "write_kb": 15},
    "code-reviewer":     {"turns": 4, "read_kb": 50, "write_kb": 8},
    "security-reviewer": {"turns": 4, "read_kb": 50, "write_kb": 6},
    "history-tracker":   {"turns": 2, "read_kb": 15, "write_kb": 2},
}

# The roster's default allocation, from reference/roster.md.
DEFAULT_ALLOC = {
    "orchestrator":      ("opus",   "high"),
    "spec-guardian":     ("sonnet", "medium"),
    "app-dev":           ("sonnet", "high"),
    "qa-test":           ("sonnet", "medium"),
    "code-reviewer":     ("opus",   "high"),
    "security-reviewer": ("opus",   "high"),
    "history-tracker":   ("haiku",  "low"),
}

SEATS = list(WORKLOAD)


def profile(model: str, effort: str) -> dict:
    return {s: (model, effort) for s in SEATS}


PROFILES: dict[str, dict] = {
    # What a lot of teams actually do: put the best model everywhere and never set effort.
    "all-frontier (fable, xhigh)": profile("fable", "xhigh"),
    "all-opus (xhigh, no effort tuning)": profile("opus", "xhigh"),
    "all-opus (high)": profile("opus", "high"),
    "DEFAULT roster (this skill)": DEFAULT_ALLOC,
    # Sovereignty / portability tests: can the harness run on ONE mid or low tier model?
    "sonnet-only (high)": profile("sonnet", "high"),
    "sonnet-only (medium)": profile("sonnet", "medium"),
    "haiku-only (medium)": profile("haiku", "medium"),
    # The cheapest thing that keeps the review gates on a strong model.
    "economy (gates=opus, rest=haiku)": {
        **profile("haiku", "low"),
        "app-dev": ("sonnet", "medium"),
        "code-reviewer": ("opus", "high"),
        "security-reviewer": ("opus", "high"),
        "orchestrator": ("sonnet", "high"),
    },
}


def tok(nbytes: float) -> float:
    return nbytes / CHARS_PER_TOKEN


def system_prompt_bytes(root: pathlib.Path) -> dict[str, int]:
    """GROUNDED: agent body + the rules that load unconditionally into every session."""
    rules = root / "harness-bootstrap/assets/claude/rules"
    always = 0
    for p in sorted(rules.glob("*.md")):
        head = p.read_text(encoding="utf-8", errors="replace")
        fm = head.split("---")[1] if head.startswith("---") else ""
        if "paths:" not in fm:
            always += len(head)

    agents = root / "harness-bootstrap/assets/claude/agents"
    out: dict[str, int] = {}
    for seat in SEATS:
        f = agents / f"{seat}.md"
        if not f.is_file():
            f = agents / "dev-agent.md"  # app-dev is instantiated from the dev-agent template
        out[seat] = len(f.read_text(encoding="utf-8", errors="replace")) + always
    return out


def cost_of(alloc: dict, sysb: dict[str, int]) -> tuple[float, dict]:
    total = 0.0
    per_seat = {}
    for seat, (model, effort) in alloc.items():
        w = WORKLOAD[seat]
        p = PRICES[model]

        sys_tok = tok(sysb[seat])
        read_tok = tok(w["read_kb"] * 1024)
        out_tok = tok(w["write_kb"] * 1024) * EFFORT_MULT[effort]

        # Each turn re-sends system + everything read so far. Approximate the growing prefix as
        # linear: turn i carries sys + read*(i/turns). Sum over turns.
        n = w["turns"]
        in_tok = sum(sys_tok + read_tok * (i / n) for i in range(1, n + 1))

        c = in_tok / 1e6 * p["in"] + out_tok / 1e6 * p["out"]
        total += c
        per_seat[seat] = {"model": model, "effort": effort,
                          "in_tokens": round(in_tok), "out_tokens": round(out_tok),
                          "usd": round(c, 4)}
    return total, per_seat


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    root = pathlib.Path(__file__).resolve().parent.parent
    sysb = system_prompt_bytes(root)

    rows = []
    for name, alloc in PROFILES.items():
        total, per_seat = cost_of(alloc, sysb)
        rows.append({"profile": name, "usd_per_feature": round(total, 3), "seats": per_seat})

    base = next(r for r in rows if r["profile"] == "DEFAULT roster (this skill)")["usd_per_feature"]
    frontier = next(r for r in rows if r["profile"].startswith("all-opus (xhigh"))["usd_per_feature"]

    if a.json:
        print(json.dumps({"prices": PRICES, "assumptions": {
            "chars_per_token": CHARS_PER_TOKEN, "effort_mult": EFFORT_MULT,
            "workload": WORKLOAD}, "rows": rows}, indent=2))
        return 0

    print("=" * 78)
    print("  Cost of ONE feature through the harness, by roster profile")
    print("  MODELLED, not measured. Assumptions are at the top of this script.")
    print("=" * 78)
    print(f"\n  {'profile':<36} {'USD/feature':>12} {'vs default':>12} {'per 100 feat':>13}")
    print("  " + "-" * 74)
    for r in sorted(rows, key=lambda x: -x["usd_per_feature"]):
        d = r["usd_per_feature"] / base
        mark = "  <-- default" if r["profile"].startswith("DEFAULT") else ""
        print(f"  {r['profile']:<36} {r['usd_per_feature']:>12.3f} {d:>11.2f}x "
              f"{r['usd_per_feature']*100:>12.0f}{mark}")

    saving = round((1 - base / frontier) * 100)
    print(f"\n  The default roster costs {saving}% less than putting Opus at xhigh everywhere,")
    print(f"  which is the configuration a team lands on by NOT choosing.")

    print("\n  Where the money goes in the default roster (per feature):")
    dr = next(r for r in rows if r["profile"].startswith("DEFAULT"))["seats"]
    for seat, v in sorted(dr.items(), key=lambda kv: -kv[1]["usd"]):
        bar = "#" * max(1, round(v["usd"] / max(x["usd"] for x in dr.values()) * 28))
        print(f"    {seat:<19} {v['model']:>6}/{v['effort']:<6} ${v['usd']:>6.3f}  {bar}")

    print("\n  MODEL SOVEREIGNTY: can the harness run on one mid/low tier model?")
    for p in ("sonnet-only (high)", "sonnet-only (medium)", "haiku-only (medium)"):
        r = next(x for x in rows if x["profile"] == p)
        print(f"    {p:<24} ${r['usd_per_feature']:.3f}/feature "
              f"({r['usd_per_feature']/base:.2f}x default)")
    print("    Cost says yes. Whether the OUTPUT holds up is a quality question this script")
    print("    cannot answer - run the eval in eval/ against your own repo to find out.")

    if not (os.environ.get("ANTHROPIC_API_KEY")):
        print("\n  NOTE: token counts derived from bytes at "
              f"{CHARS_PER_TOKEN} chars/token (no API key set).")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
