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


def _const(rel: str, name: str) -> int:
    """Read a module-level integer constant that its own script asserts against reality.

    Most of these suites generate cases at run time, so a static scan of the source undercounts.
    The pattern used here instead: the script declares the number, fails loudly if the real count
    differs, and this reads the declaration. That makes the constant as trustworthy as a run.
    """
    m = re.search(rf'^{name}\s*=\s*(\d+)',
                  (ROOT / rel).read_text(encoding="utf-8"), re.M)
    if not m:
        sys.exit(f"{rel} no longer defines {name}, so its published figure cannot be policed.")
    return int(m.group(1))


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
        "read_files_pct": pct(old["read_files"], new["read_files"]),
        # Exact "after" byte figures, counted from disk. These drifted silently once (83,339 lingered
        # in four files after the read path grew to 85,641) because only the percentages were guarded.
        "read_bytes_after": new["read_bytes"],
        "write_bytes_after": new["write_bytes"],
        "tax_pct": round(scoped / (scoped + always) * 100),
        "unconditional_rules": len(tax["always_files"]),
        "scoped_rules": len(tax["scoped_files"]),
        "rules": len(tax["always_files"]) + len(tax["scoped_files"]),
        # dev-agent.md is a template instantiated per domain, not a shipped agent.
        "agents": len([a for a in agents if a != "dev-agent"]),
        "commands": len(list((ASSETS / "commands").glob("*.md"))),
        "hooks": len({p.stem for p in (ASSETS / "hooks").glob("*.*")
                      if p.suffix in (".sh", ".ps1")}),
        # The eval case count, derived from the eval file itself - the "N/N" badge in the deck and
        # the intro videos bakes it, and it drifted twice before this check existed.
        # Most eval cases are generated at run time, so counting them by scanning the source
        # undercounts. The eval declares CASES_PER_FLAVOR and asserts it against the real count
        # on every run, which makes the constant safe to read here.
        "eval_cases": int(re.search(r'^CASES_PER_FLAVOR\s*=\s*(\d+)',
                                    (ROOT / "eval/guardrail_eval.py").read_text(encoding="utf-8"),
                                    re.M).group(1)),
        # The same total split by intent, and the port adapter's own suite. All three are quoted
        # in the deck outline, all three are asserted against reality by the script that owns
        # them, and all three drifted unnoticed: the outline claimed "15 must-block, 25 must-allow"
        # beside a "107/107" that the split does not add up to, and "5/5" for a suite of 18.
        "eval_block": _const("eval/guardrail_eval.py", "MUST_BLOCK_PER_FLAVOR"),
        "eval_allow": _const("eval/guardrail_eval.py", "MUST_ALLOW_PER_FLAVOR"),
        # Both flavors run, so the published figure is per-flavor x 2.
        "adapter_cases": 2 * _const("harness-bootstrap/scripts/port.py", "CHECKS_PER_FLAVOR"),
        # Baseline A replays only the hook suite's must-block payloads, which is a SUBSET of
        # eval_block: the rest of the eval covers scaffold, ledger and toggle behaviour, which
        # is not a safety win to count here. Two different true numbers, so two keys - a single
        # "N must-block" rule would have to call one of them wrong.
        "bench_block": d["guardrails"]["cases"],
    }


# Checked in every document. These phrasings have exactly one meaning in this repo.
CHECKS = [
    # These live in markdown table rows, so the pattern has to cross the '|' cell separators. An
    # earlier version excluded '|' and therefore matched nothing: the check looked green and was
    # dead. Every pattern here is exercised by the self-test at the bottom of this file.
    # "bytes" is load-bearing. "Read path (files read) ... -71%" is a DIFFERENT metric that is also
    # correct, and an earlier pattern conflated the two and reported a false mismatch.
    ("read-path reduction",   r"[Rr]ead path \(bytes[^\n]*?[-−](\d\d)%|[Bb]ytes the model must read[^\n]*?[-−](\d\d)%", "read_pct"),
    ("write-path reduction",  r"[Ww]rite path \(bytes[^\n]*?[-−](\d\d)%|[Bb]ytes the model must write[^\n]*?[-−](\d\d)%", "write_pct"),
    ("read-path files",       r"[Rr]ead path \(files[^\n]*?[-−](\d\d)%", "read_files_pct"),
    ("session tax",           rf"{NUM}% of (?:the )?rule content", "tax_pct"),
    ("rule content kept out", r"[Rr]ule content kept out[^\n]*?\*\*(\d\d)%\*\*", "tax_pct"),
    ("unconditional rules",   rf"{NUM} unconditional rules?\b", "unconditional_rules"),
    ("path-scoped rules",     rf"{NUM} (?:of \d+ (?:rules are )?)?path-scoped", "scoped_rules"),
]

# A cheap plain-substring pre-check before each CHECKS regex: every pattern above requires one of
# these literal (lowercased) phrases to appear, so if none is present the regex cannot match and
# running it is wasted work. Each entry is a SAFE SUPERSET of what its pattern needs - never
# narrower - so this can only skip a file the regex would have skipped anyway. Most documents in a
# repo do not mention "path-scoped" or "unconditional rule" at all; on a doc-heavy tree this avoids
# firing all 7 regexes against every file's full text. Names not listed here always run the regex.
REQUIRED_SUBSTR: dict[str, tuple[str, ...]] = {
    "read-path reduction":   ("read path (bytes", "the model must read"),
    "write-path reduction":  ("write path (bytes", "the model must write"),
    "read-path files":       ("read path (files",),
    "session tax":           ("rule content",),
    "rule content kept out": ("rule content kept out",),
    "unconditional rules":   ("unconditional rule",),
    "path-scoped rules":     ("path-scoped",),
}

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

# The exact "after" byte figure that follows the known baseline constant in a before|after row. The
# token columns are prefixed "~" and so are not captured; the detail-table rows do not carry the
# baseline constant and so are covered by the summary rows instead.
# The presentation deck and the intro-video sources bake several counts as display text. They are
# not markdown, so the .md walk never sees them - and they drifted on every release until this list
# existed. English phrasings only: every baked stat has an EN variant, and the VI/JA strings are
# edited in the same pass.
#
# video/html/ja/*.html and video/src/ja/*.py are the Japanese twins of the same media (translated
# copies, not new content) - they bake the same numbers, so the gate has to see them too. MEDIA_CHECKS
# below is an EN-phrase regex list ("21 commands", "9 blocking hooks", ...) and will not match the
# JA prose ("コマンド21", "ブロッキングフック9") - that is expected, not a gap: the JA source is a
# translation of the already-checked EN source, so a divergence would have to be introduced by hand
# in the JA file itself, and the EVAL_PAIR check below still applies to it (the JA badge reads
# "ガードレール評価 26/26", and "ガードレール" is in the context regex the same as "guardrail" is).
MEDIA_FILES = ["presentation/index.html"]
MEDIA_GLOBS = ["video/html/*.html", "video/src/*.py", "video/html/ja/*.html", "video/src/ja/*.py"]
MEDIA_CHECKS = [
    ("media command count", r"(\d+) commands\b", "commands"),
    ("media hook count",    r"(\d+) (?:blocking )?hooks\b", "hooks"),
    ("media agent count",   r"(\d+) agents\b", "agents"),
]
# "N/N" pairs (the eval badge). Only equal pairs are claims; 04/05-style dates are not, and a pair
# far from the canonical count (a video timestamp, a score in an example) is not either.
EVAL_PAIR = re.compile(r"\b(\d{1,3})/(\d{1,3})\b")

# The guardrail-eval shields badge, whose numbers are a direct claim about the suite.
# It needs its own check because the prose rule above only looks at EQUAL pairs, to
# avoid matching a must-block/must-allow split. A badge reading "38/40" is unequal, so
# it slipped through for several releases while also implying the suite was failing.
EVAL_BADGE = re.compile(r"guardrail(?:%20|\s)eval-(\d{1,3})/(\d{1,3})", re.I)

# The eval total split by intent, and the size of the suite it is a split of. These are quoted
# only where the suite is described, so they are checked only there: CHANGELOG entries state what
# was true at their release and must not be rewritten, and benchmark/RESULTS.md quotes the hook
# subset instead (see bench_block). Every one of these drifted at once - the deck claimed
# "15 must-block, 25 must-allow" beside a 107/107 the pair does not add up to, and eval/README.md
# claimed a split summing to 69 - because the prose rule below only inspects EQUAL pairs.
SPLIT_FILES = {"docs/PRESENTATION-OUTLINE.md", "docs/ASSESSMENT.md", "eval/README.md",
               "docs/tools/claude-code.md", "README.md", "README.ja.md"}
SPLIT_CHECKS = [
    ("must-block split", r"(\d+) must-block", "eval_block"),
    ("must-allow split", r"(\d+) must-allow", "eval_allow"),
    ("blocked split",    r"\((\d+) blocked,", "eval_block"),
    ("allowed split",    r"(\d+) allowed\)", "eval_allow"),
    ("payload total",    r"(?:fires|\() ?(\d+) payloads", "eval_cases"),
]
# Baseline A's own subset, stated only in the benchmark write-up.
BENCH_FILES = {"benchmark/RESULTS.md"}
BENCH_CHECKS = [
    ("baseline block count", r"(\d+) must-block payloads", "bench_block"),
    ("eval cases per flavor", r"(\d+) cases per flavor", "eval_cases"),
]
# The port adapter's self-test result. It needs its own rule because the prose pair rule below
# deliberately EXCLUDES any pair whose context mentions an adapter or a self-test - which is why
# "5/5" survived in three places while the suite grew to 18.
ADAPTER_PAIR = re.compile(r"\b(\d{1,3})/(\d{1,3})\b")

BYTE_CHECKS = [
    ("read-path after bytes",  r"234,196\s*\|\s*([\d,]{4,})", "read_bytes_after"),
    ("write-path after bytes", r"95,064\s*\|\s*([\d,]{4,})",  "write_bytes_after"),
]


def as_bytes(tok: str) -> int:
    return int(tok.replace(",", ""))


def self_test(c: dict[str, int]) -> list[str]:
    """A pattern that matches nothing looks identical to a pattern that finds no problems: green,
    and useless. One of these was dead for its whole life. So every pattern must prove it can still
    fire, by matching a line built from the canonical values."""
    lines = {
        "read-path reduction":   "| Read path (bytes the model must pull into context) | 234,196 | 83,339 | -{read_pct}% |",
        "write-path reduction":  "| Write path (bytes the model must author) | 95,064 | 14,595 | -{write_pct}% |",
        "read-path files":       "| Read path (files read) | 24 | 7 | -{read_files_pct}% |",
        "session tax":           "keeping {tax_pct}% of rule content out of the default session",
        "rule content kept out": "| Rule content kept out of the default session | - | 49,394 of 74,697 B | **{tax_pct}%** |",
        "unconditional rules":   "{unconditional_rules} unconditional rules stay loaded",
        "path-scoped rules":     "{scoped_rules} path-scoped rules load on demand",
        "agent count":           "{agents} agents, each with a model",
        "rule count":            "{rules} rules - 6 always loaded",
        "command count":         "{commands} slash commands, two of them gated",
        "hook count":            "{hooks} blocking hooks",
        "media command count":    "{commands} commands",
        "media hook count":       "{hooks} blocking hooks",
        "media agent count":      "{agents} agents",
        "read-path after bytes":  "| Read path | 234,196 | {read_bytes_after} | -63% |",
        "write-path after bytes": "| Write path | 95,064 | {write_bytes_after} | -85% |",
        "must-block split":       "{eval_block} must-block, {eval_allow} must-allow",
        "must-allow split":       "{eval_block} must-block, {eval_allow} must-allow",
        "blocked split":          "**107/107** ({eval_block} blocked, {eval_allow} allowed)",
        "allowed split":          "**107/107** ({eval_block} blocked, {eval_allow} allowed)",
        "payload total":          "fires {eval_cases} payloads at a real generated harness",
        "baseline block count":   "counts only the {bench_block} must-block payloads",
        "eval cases per flavor":  "the eval's full {eval_cases} cases per flavor include",
    }
    dead = []
    for name, pat, key in (CHECKS + COUNT_CHECKS + BYTE_CHECKS + MEDIA_CHECKS
                           + SPLIT_CHECKS + BENCH_CHECKS):
        probe = lines[name].format(**c)
        if not re.search(pat, probe, re.I):
            dead.append(f"{name}: pattern never matches, so it can never fail")
    return dead


def main() -> int:
    c = canonical()
    print("  canonical (benchmark.py + the assets directory):")
    for k, v in c.items():
        print(f"    {k:<22} {v}")

    dead = self_test(c)
    if dead:
        print("\n  DEAD CHECKS - these would pass on any input:")
        for d in dead:
            print(f"    {d}")
        return 1

    bad = 0
    print("\n  documents:")
    for p in sorted(ROOT.rglob("*.md")):
        if SKIP_PARTS & set(p.parts):
            continue
        text = p.read_text(encoding="utf-8")
        # Blank out inline code spans. A figure in backticks is a quotation - a changelog entry
        # naming the wrong number it fixed, for instance - not a claim the repo is making. Skip
        # the regex entirely when there is no backtick to blank - cheap and exact, same result.
        if "`" in text:
            text = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), text)
        # A shields.io badge URL escapes its slash as %2F, so "107%2F107" hid from the
        # pair regex below. The README carried 38/40 in the image while its own alt text
        # said 107/107, and this checker saw only the alt text. This shifts character
        # offsets but adds no newline, so the reported line numbers stay correct.
        text = text.replace("%2F", "/").replace("%2f", "/")
        rel = p.relative_to(ROOT).as_posix()
        text_lower = text.lower()
        # The shields badge states the suite result outright, so both halves must be the
        # real case count. Checked separately from the prose rule below, which only looks
        # at equal pairs and therefore cannot see a badge claiming 38/40.
        for m in EVAL_BADGE.finditer(text):
            a, b = int(m.group(1)), int(m.group(2))
            if a != c["eval_cases"] or b != c["eval_cases"]:
                line = text[:m.start()].count("\n") + 1
                print(f"    MISMATCH  {rel}:{line}  guardrail eval badge: says {a}/{b}, "
                      f"reality is {c['eval_cases']}/{c['eval_cases']}")
                bad += 1
        # Eval badge in prose: "26/26" near eval-ish words is a claim about the suite. This drifted
        # across fifteen files at once while only the media files were scanned.
        for m in EVAL_PAIR.finditer(text):
            a, b = int(m.group(1)), int(m.group(2))
            ctx = text[max(0, m.start() - 120):m.start() + 60].lower()
            if a == b and a != c["eval_cases"] and a != 2 * c["eval_cases"] \
                    and re.search(r"eval|guardrail|payload|forbidden|permitted|judged|"
                                  r"floor hold|proof|禁止|許可|bị cấm", ctx) \
                    and not re.search(r"adapter|port|self-test", ctx) \
                    and not re.search(r"->|→|\bwas\b|from", ctx):
                line = text[:m.start()].count("\n") + 1
                print(f"    MISMATCH  {rel}:{line}  eval badge: says {a}/{b}, reality is "
                      f"{c['eval_cases']}/{c['eval_cases']}")
                bad += 1
        # The adapter self-test result, wherever it is quoted next to what produced it.
        for m in ADAPTER_PAIR.finditer(text):
            a, b = int(m.group(1)), int(m.group(2))
            ctx = text[max(0, m.start() - 130):m.start() + 70].lower()
            if a == b and a != c["adapter_cases"] \
                    and re.search(r"adapter|port\.py|--self-test", ctx) \
                    and not re.search(r"->|→|\bwas\b|from", ctx):
                line = text[:m.start()].count("\n") + 1
                print(f"    MISMATCH  {rel}:{line}  port adapter self-test: says {a}/{b}, "
                      f"reality is {c['adapter_cases']}/{c['adapter_cases']}")
                bad += 1
        active = (CHECKS
                  + (COUNT_CHECKS if rel in COUNT_FILES else [])
                  + (SPLIT_CHECKS if rel in SPLIT_FILES else [])
                  + (BENCH_CHECKS if rel in BENCH_FILES else []))
        for name, pat, key in active:
            reqs = REQUIRED_SUBSTR.get(name)
            if reqs is not None and not any(r in text_lower for r in reqs):
                continue
            for m in re.finditer(pat, text, re.I):
                tok = next(g for g in m.groups() if g)
                got = as_int(tok)
                if got != c[key]:
                    line = text[:m.start()].count("\n") + 1
                    print(f"    MISMATCH  {rel}:{line}  {name}: says {got}, reality is {c[key]}")
                    bad += 1
        for name, pat, key in BYTE_CHECKS:
            for m in re.finditer(pat, text):
                got = as_bytes(next(g for g in m.groups() if g))
                if got != c[key]:
                    line = text[:m.start()].count("\n") + 1
                    print(f"    MISMATCH  {rel}:{line}  {name}: says {got:,}, reality is {c[key]:,}")
                    bad += 1

    media_paths = [ROOT / f for f in MEDIA_FILES if (ROOT / f).exists()]
    for g in MEDIA_GLOBS:
        media_paths.extend(sorted(ROOT.glob(g)))
    for p in media_paths:
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(ROOT).as_posix()
        for name, pat, key in MEDIA_CHECKS:
            for m in re.finditer(pat, text):
                got = as_int(m.group(1))
                if got != c[key]:
                    line = text[:m.start()].count("\n") + 1
                    print(f"    MISMATCH  {rel}:{line}  {name}: says {got}, reality is {c[key]}")
                    bad += 1
        for m in EVAL_PAIR.finditer(text):
            a, b = int(m.group(1)), int(m.group(2))
            # Only a pair sitting near the words eval/guardrail/payload is the eval badge; "5/5"
            # next to "adapter" is the port self-test, and equal pairs elsewhere are not claims.
            # The window reaches further forward than the prose one: in the deck the number is a
            # slide-data value and the words that identify it ("forbidden", "floor hold", "proof")
            # follow it rather than precede it. A badge that sat just outside the old window is
            # exactly how the v1.8.0 deck kept claiming 40/40 after the suite reached 68.
            ctx = text[max(0, m.start() - 120):m.start() + 200].lower()
            if a == b and a != c["eval_cases"] \
                    and re.search(r"eval|guardrail|payload|ペイロード|ガードレール|forbidden|"
                                  r"permitted|judged|floor hold|proof|禁止|許可|bị cấm", ctx) \
                    and "adapter" not in ctx and "5/5" != m.group(0):
                line = text[:m.start()].count("\n") + 1
                print(f"    MISMATCH  {rel}:{line}  eval badge: says {a}/{b}, reality is "
                      f"{c['eval_cases']}/{c['eval_cases']}")
                bad += 1

    if bad:
        print(f"\n  {bad} figure(s) contradict reality. Fix the doc, or the code if the doc is right.")
        return 1
    print("    every checked figure matches.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
