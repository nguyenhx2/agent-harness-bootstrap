#!/usr/bin/env python3
"""Assert the figures quoted in the docs match what the scripts actually print.

The repo's contributing rule is "no invented numbers". A rule nobody checks is a rule that drifts:
the session-tax figure has already been wrong in two files at once (68% vs 66%), and the read-path
reduction was quoted as 65% after it had moved to 64%.

This runs the benchmark, derives the canonical figures, and greps the docs for a contradicting
number. It exits non-zero on a mismatch, so CI catches a stale figure before a reader does.

    python scripts/check_numbers.py
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ["README.md", "benchmark/RESULTS.md", "docs/ASSESSMENT.md",
        "docs/CONTEXT-MANAGEMENT.md", "eval/README.md", "CHANGELOG.md"]


def canonical() -> dict[str, int]:
    r = subprocess.run([sys.executable, str(ROOT / "benchmark/benchmark.py"), "--json"],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"benchmark failed:\n{r.stderr}")
    d = json.loads(r.stdout)
    old, new, tax = d["old"], d["new"], d["session_tax"]

    def pct(a: int, b: int) -> int:
        return round((a - b) / a * 100)

    scoped = tax["scoped_bytes"]
    total = tax["always_bytes"] + tax["scoped_bytes"]
    return {
        "read_pct": pct(old["read_bytes"], new["read_bytes"]),
        "write_pct": pct(old["write_bytes"], new["write_bytes"]),
        "tax_pct": round(scoped / total * 100),
        "read_after": new["read_bytes"],
        "write_after": new["write_bytes"],
        "scoped_bytes": scoped,
        "total_bytes": total,
        "unconditional_rules": len(tax["always_files"]),
        "scoped_rules": len(tax["scoped_files"]),
    }


def main() -> int:
    c = canonical()
    print("  canonical (from benchmark.py):")
    for k, v in c.items():
        print(f"    {k:<22} {v:,}" if isinstance(v, int) else f"    {k:<22} {v}")

    # Each check: a regex that finds a percentage in a context, and the value it must equal.
    checks = [
        ("read-path reduction",  r"(?:read|Bytes the model must read)[^\n|]*?[-−](\d\d)%", c["read_pct"]),
        ("write-path reduction", r"(?:write|Bytes the model must write)[^\n|]*?[-−](\d\d)%", c["write_pct"]),
        ("session tax",          r"(\d\d)% of (?:the )?rule content", c["tax_pct"]),
        ("rule content kept out",r"[Rr]ule content kept out[^\n|]*?\|\s*\*?\*?(\d\d)%", c["tax_pct"]),
    ]

    bad = 0
    print("\n  documents:")
    for doc in DOCS:
        p = ROOT / doc
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        for name, pat, want in checks:
            for m in re.finditer(pat, text):
                got = int(m.group(1))
                if got != want:
                    line = text[:m.start()].count("\n") + 1
                    print(f"    MISMATCH  {doc}:{line}  {name}: says {got}%, benchmark says {want}%")
                    bad += 1

        # counts of unconditional / path-scoped rules
        for pat, want, label in (
            (r"(\d+) unconditional", c["unconditional_rules"], "unconditional rules"),
            (r"(\d+) (?:of \d+ )?(?:rules are )?path-scoped", c["scoped_rules"], "path-scoped rules"),
        ):
            for m in re.finditer(pat, text):
                got = int(m.group(1))
                if got != want:
                    line = text[:m.start()].count("\n") + 1
                    print(f"    MISMATCH  {doc}:{line}  {label}: says {got}, benchmark says {want}")
                    bad += 1

    if bad:
        print(f"\n  {bad} figure(s) in the docs contradict the benchmark. Update the docs, or the "
              f"benchmark if it is the one that is wrong.")
        return 1
    print("    every checked figure matches the benchmark.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
