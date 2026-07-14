#!/usr/bin/env python3
"""Assert the figures quoted in the docs match reality.

"No invented numbers" is a contributing rule. A rule nobody checks drifts: the session-tax figure has
been wrong in two files at once, the read-path reduction was quoted after it had moved, and FLOWS.md
carried "four unconditional rules, seven path-scoped, 77%" long after the answer was 6, 8 and 66%.

Reality here means two things:
  - the percentages that benchmark.py computes, and
  - the artifact counts you get by listing the assets directory.

Both are derived, never typed. Exits non-zero on a contradiction.

    python scripts/check_numbers.py
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "harness-bootstrap/assets/claude"

# Scan every document, not a hand-maintained list: the last stale figure survived precisely because
# the file holding it was not on the list.
SKIP_PARTS = {".git", "node_modules", ".eval-workdir", "dist", "baseline", "assets"}

WORD = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
        "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16}
NUM = r"(\d+|" + "|".join(WORD) + r")"


def as_int(tok: str) -> int:
    return int(tok) if tok.isdigit() else WORD[tok.lower()]


def canonical() -> dict[str, int]:
    r = subprocess.run([sys.executable, str(ROOT / "benchmark/benchmark.py"), "--json"],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"benchmark failed:\n{r.stderr}")
    d = json.loads(r.stdout)
    old, new, tax = d["old"], d["new"], d["session_tax"]

    def pct(a: int, b: int) -> int:
        return round((a - b) / a * 100)

    scoped, always = tax["scoped_bytes"], tax["always_bytes"]

    # Counted from the filesystem, not from anyone's memory.
    agents = sorted(p.stem for p in (ASSETS / "agents").glob("*.md"))
    return {
        "read_pct": pct(old["read_bytes"], new["read_bytes"]),
        "write_pct": pct(old["write_bytes"], new["write_bytes"]),
        "tax_pct": round(scoped / (scoped + always) * 100),
        "unconditional_rules": len(tax["always_files"]),
        "scoped_rules": len(tax["scoped_files"]),
        "rules": len(tax["always_files"]) + len(tax["scoped_files"]),
        # dev-agent.md is a template instantiated per domain, not a shipped agent.
        "agents": len([a for a in agents if a != "dev-agent"]),
        "commands": len(list((ASSETS / "commands").glob("*.md"))),
        "hooks": len({p.stem for p in (ASSETS / "hooks").glob("*.*")
                      if p.suffix in (".sh", ".ps1")}),
    }


# Checked in every document. These phrasings have exactly one meaning in this repo.
CHECKS = [
    ("read-path reduction",   r"(?:read|Bytes the model must read)[^\n|]*?[-−](\d\d)%", "read_pct"),
    ("write-path reduction",  r"(?:write|Bytes the model must write)[^\n|]*?[-−](\d\d)%", "write_pct"),
    ("session tax",           rf"{NUM}% of (?:the )?rule content", "tax_pct"),
    ("rule content kept out", r"[Rr]ule content kept out[^\n|]*?\|\s*\*?\*?(\d\d)%", "tax_pct"),
    ("unconditional rules",   rf"{NUM} unconditional rules?\b", "unconditional_rules"),
    ("path-scoped rules",     rf"{NUM} (?:of \d+ (?:rules are )?)?path-scoped", "scoped_rules"),
]

# Counts of the shipped artifact set, checked only in the two files that describe it. Elsewhere the
# same words carry different claims - "5-6 agents" is a preset size, "the two rules that matter" is a
# heading - and a checker that flags those is a checker people learn to ignore.
COUNT_FILES = {"README.md", "CHANGELOG.md"}
COUNT_CHECKS = [
    ("agent count",   rf"{NUM} agents,", "agents"),
    ("rule count",    rf"{NUM} rules(?:,| -)", "rules"),
    ("command count", rf"{NUM} (?:slash )?commands,", "commands"),
    ("hook count",    rf"{NUM} (?:blocking )?hooks", "hooks"),
]


def main() -> int:
    c = canonical()
    print("  canonical (benchmark.py + the assets directory):")
    for k, v in c.items():
        print(f"    {k:<22} {v}")

    bad = 0
    print("\n  documents:")
    for p in sorted(ROOT.rglob("*.md")):
        if SKIP_PARTS & set(p.parts):
            continue
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(ROOT).as_posix()
        active = CHECKS + (COUNT_CHECKS if rel in COUNT_FILES else [])
        for name, pat, key in active:
            for m in re.finditer(pat, text, re.I):
                tok = next(g for g in m.groups() if g)
                got = as_int(tok)
                if got != c[key]:
                    line = text[:m.start()].count("\n") + 1
                    print(f"    MISMATCH  {rel}:{line}  {name}: says {got}, reality is {c[key]}")
                    bad += 1

    if bad:
        print(f"\n  {bad} figure(s) contradict reality. Fix the doc, or the code if the doc is right.")
        return 1
    print("    every checked figure matches.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
