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


def roster_range() -> tuple[int, int]:
    """How many of the shipped agent seats a single run can install, at least and at most.

    "Tailored, not comprehensive" is the claim the README makes about the roster, and a range
    is the honest way to state it. It is computed with the scaffolder's OWN `wanted()` over
    every combination of the flags that gate an agent, so it cannot drift from what a real run
    would install: re-implementing the selection rule here would just create a second answer.
    dev-agent is a template instantiated per module, not a seat, and is excluded.
    """
    import itertools

    sys.path.insert(0, str(ROOT / "harness-bootstrap" / "scripts"))
    import scaffold  # noqa: E402

    manifest = json.loads((ROOT / "harness-bootstrap/assets/manifest.json")
                          .read_text(encoding="utf-8"))
    entries = manifest if isinstance(manifest, list) else manifest.get(
        "files", manifest.get("items", []))
    agents = [e for e in entries
              if "agents/" in str(e.get("dest", ""))
              and pathlib.Path(str(e.get("dest"))).stem != "dev-agent"]

    gating = sorted({f for e in agents
                     for f in (e.get("when") or []) + (e.get("when_any") or [])
                     + (e.get("when_not") or [])})
    counts = []
    for r in range(len(gating) + 1):
        for combo in itertools.combinations(gating, r):
            flags = set(combo)
            counts.append(sum(1 for e in agents if scaffold.wanted(e, flags)))
    return min(counts), max(counts)


def flag_sync() -> list[str]:
    """The flag set must be identical in the four places that claim to agree.

    scaffold.py says of KNOWN_FLAGS: "Keep in sync with assets/manifest.json's schema comment,
    SKILL.md, and reference/intake.md - the auditors check all four agree." No auditor did. The
    only other reader of KNOWN_FLAGS was build_wiki.py, which renders the set and never compares
    it, so the sentence described a control that did not exist.

    The failure it lets through is silent both ways: a flag in KNOWN_FLAGS but not in intake.md is
    a capability no questionnaire can reach, and a flag documented in SKILL.md but not in
    KNOWN_FLAGS is a scaffolder error the user meets at the worst possible moment.

    Each source is parsed for bare flag tokens rather than for its prose, because the four are
    written in four different shapes: a Python set, a JSON comment string, and two markdown
    sentences with backticks.
    """
    scaffold = (ROOT / "harness-bootstrap/scripts/scaffold.py").read_text(encoding="utf-8")
    m = re.search(r"KNOWN_FLAGS = \{(.*?)\}", scaffold, re.S)
    if not m:
        return ["scaffold.py no longer defines KNOWN_FLAGS, so the flag set cannot be policed"]
    # [a-z0-9_]+, not [a-z_]+: an earlier version of this dropped `e2e` on the floor because the
    # digit did not match, so one real flag was silently exempt from the very check meant to
    # cover all of them.
    truth = sorted(set(re.findall(r'"([a-z0-9_]+)"', m.group(1))))

    manifest = json.loads((ROOT / "harness-bootstrap/assets/manifest.json")
                          .read_text(encoding="utf-8"))
    comment = manifest.get("_comment", "") if isinstance(manifest, dict) else ""

    skill = (ROOT / "harness-bootstrap/SKILL.md").read_text(encoding="utf-8")
    intake = (ROOT / "harness-bootstrap/reference/intake.md").read_text(encoding="utf-8")

    def window(text: str, anchor: str, span: int) -> str:
        i = text.find(anchor)
        return text[i:i + span] if i != -1 else ""

    # Each source states the set once, in its own shape. Search the enumeration rather than the
    # whole file: a flag mentioned in passing elsewhere is not the same as being on the list.
    sources = {
        "manifest.json _comment": window(comment, "Flags:", 400),
        "SKILL.md": window(skill, "Flags gate conditional assets", 500),
        "intake.md": window(intake, "Flags are exactly:", 400),
    }

    problems = []
    for name, text in sources.items():
        if not text:
            problems.append(f"{name} no longer contains its flag enumeration, so it cannot be "
                            f"compared - fix the anchor in flag_sync() or restore the list")
            continue
        # Word-boundary search, so `db` does not count as found inside `db_engineer`.
        missing = [f for f in truth if not re.search(rf"(?<![a-z0-9_]){re.escape(f)}(?![a-z0-9_])",
                                                     text)]
        if missing:
            problems.append(f"{name} is missing flag(s) KNOWN_FLAGS has: {', '.join(missing)}")
    return problems


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
        # The tailored-roster claim: how few and how many seats a run can install.
        "roster_min": roster_range()[0],
        "roster_max": roster_range()[1],
        # The scanned-PDF threshold spec-builder's router applies (a page under this many
        # extracted characters routes to vision). Quoted on the README (both languages), the
        # wiki FAQ and two reference files; derived here from the constant so a retuned
        # threshold cannot leave four documents quoting the old number.
        "scan_chars": int(re.search(
            r"^TEXT_LAYER_MIN_CHARS_PER_PAGE\s*=\s*(\d+)",
            (ROOT / "spec-builder/scripts/route_sources.py").read_text(encoding="utf-8"),
            re.M).group(1)),
        # The published version. Not an artifact count, but the same failure class: a figure
        # written by hand into a user-facing page that nothing re-reads on the way past. The
        # install snippets now name the UNVERSIONED archive the release also attaches, which
        # takes them out of this entirely; the badge cannot avoid naming a number, so it is
        # checked. validate_release.py already asserts CHANGELOG and SKILL.md agree, which
        # makes either one safe to read here.
        "version": re.search(r"^## v(\d+\.\d+\.\d+)",
                             (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
                             re.M).group(1),
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
    # The emphasis blanking above turns '**63%**' into '  63%  ', so every one of these
    # tolerates the run of spaces it leaves behind rather than demanding a tight phrase.
    ("session tax",           rf"{NUM}% *of (?:the )?rule content", "tax_pct"),
    ("rule content kept out", r"[Rr]ule content kept out[^\n]*?\b(\d\d)%", "tax_pct"),
    # Same figure, stated as a label under a big number instead of in a sentence. The landing
    # pages and the Japanese README both write it this way and neither was ever checked.
    ("session tax (label)",   r"\b(\d\d)%[\s\S]{0,140}?of rule content stays out", "tax_pct"),
    ("session tax (ja label)", r"\b(\d\d)%[\s\S]{0,160}?既定セッションから外れるルール本文", "tax_pct"),
    ("session tax (ja prose)", r"ルール本文の[^\n]{0,8}?(\d\d)%", "tax_pct"),
    # Both word orders. "6 rules unconditional" sat in the deck outline while the count was 7,
    # because only "N unconditional rules" was ever matched.
    # The router's scanned-PDF threshold, in every phrasing a document states it: EN prose
    # ("under 80 characters a/per page"), the reference's "fewer than 80 characters", the
    # heading form "80-chars-per-page", and the Japanese "80文字未満".
    # \s+ everywhere a space appears, because the first version demanded single spaces and
    # both the README and the FAQ wrap this phrase across a line break - the gate was born
    # dead and only the mutation test noticed.
    ("scanned-pdf threshold", r"under\s+(\d+)\s+characters\s+(?:a|per)\s+page"
                              r"|fewer\s+than\s+(\d+)\s+[a-z ]*characters"
                              r"|(\d+)-chars-per-page"
                              r"|(\d+)文字未満", "scan_chars"),
    ("unconditional rules",   rf"{NUM} unconditional rules?\b", "unconditional_rules"),
    ("unconditional rules (reversed)", r"\b(\d+) +rules? +unconditional\b", "unconditional_rules"),
    ("path-scoped rules",     rf"{NUM} (?:of \d+ (?:rules are )?)?path-scoped", "scoped_rules"),
    # The roster range behind "tailored, not comprehensive". Both ends are checked, because a
    # claim that the build is smaller than the catalogue is only worth making if it is true.
    ("roster range low",      r"\b(\d+) to \d+ of (?:the |them|its )?\d* ?seats?\b", "roster_min"),
    ("roster range high",     r"\b\d+ to (\d+) of (?:the |them|its )?\d* ?seats?\b", "roster_max"),
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
    "session tax (label)":   ("rule content stays out",),
    "session tax (ja label)": ("ルール本文",),
    "session tax (ja prose)": ("ルール本文",),
    # "characters" alone, not "characters a page": the phrase wraps across a line break in
    # the README, and a pre-filter narrower than its regex silently disables the check for
    # exactly that file - the contract above says SAFE SUPERSET, and this one was not.
    "scanned-pdf threshold": ("characters", "-chars-per-page", "文字未満"),
    "unconditional rules":   ("unconditional rule",),
    "unconditional rules (reversed)": ("rules unconditional", "rule unconditional"),
    "path-scoped rules":     ("path-scoped",),
}

# Counts of the shipped artifact set, checked only in the two files that describe it. Elsewhere the
# same words carry different claims - "5-6 agents" is a preset size, "the two rules that matter" is a
# heading - and a checker that flags those is a checker people learn to ignore.
# PRESENTATION-OUTLINE.md is the deck's script and restates every asset count. It was outside
# this set, so it still said "15 rules" and "6 rules unconditional" after both had moved.
COUNT_FILES = {"README.md", "CHANGELOG.md", "docs/PRESENTATION-OUTLINE.md"}
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
# index.html is the GitHub Pages landing page. It bakes the same artifact counts as the deck and
# is the first thing a visitor reads, so it is policed the same way. Its Japanese twin is a
# translation of the checked English source, exactly as the video files are.
# The landing pages moved into site/ when the page became a Vite build (the served
# index.html is produced by CI from these sources). The gate follows the SOURCES,
# because the built output is never committed and a gate on an uncommitted file is
# a gate on nothing.
MEDIA_FILES = ["presentation/index.html", "site/index.html", "site/index.ja.html"]
# The figures bake the same numbers as the prose and nothing was reading them: the roster
# range and the session-tax percentage both appear inside docs/assets/*.svg.
MEDIA_GLOBS = ["video/html/*.html", "video/src/*.py", "video/html/ja/*.html",
               "video/src/ja/*.py", "docs/assets/*.svg"]
MEDIA_CHECKS = [
    ("media command count", r"(\d+) commands\b", "commands"),
    ("media hook count",    r"(\d+) (?:blocking )?hooks\b", "hooks"),
    ("media agent count",   r"(\d+) agents\b", "agents"),
    # The deck and the figures quote the roster range too, so it is policed on both paths:
    # the markdown walk covers the READMEs, this covers the deck and docs/assets/*.svg.
    ("media roster low",    r"\b(\d+) to \d+ of (?:the |them|its )?\d* ?seats?\b", "roster_min"),
    ("media roster high",   r"\b\d+ to (\d+) of (?:the |them|its )?\d* ?seats?\b", "roster_max"),
    # The landing pages state the session tax as a big number over a label, and nothing read
    # it: both index.html and index.ja.html said 63% against a real 64% for several releases.
    ("media session tax",    r"\b(\d\d)%[\s\S]{0,140}?of rule content stays out", "tax_pct"),
    ("media session tax ja", r"\b(\d\d)%[\s\S]{0,160}?既定セッションから外れるルール本文", "tax_pct"),
    ("media session tax en", r"\b(\d\d)% *of (?:the )?rule content", "tax_pct"),
    ("media session tax ja prose", r"ルール本文の[^\n]{0,8}?(\d\d)%", "tax_pct"),
]
# "N/N" pairs (the eval badge). Only equal pairs are claims; 04/05-style dates are not, and a pair
# far from the canonical count (a video timestamp, a score in an example) is not either.
# The optional spaces matter. A clip rendered the eval result as "26 / 26" and this regex,
# which demanded a tight slash, walked past it for four releases while the suite grew to 107.
EVAL_PAIR = re.compile(r"\b(\d{1,3}) ?/ ?(\d{1,3})\b")

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
ADAPTER_PAIR = re.compile(r"\b(\d{1,3}) ?/ ?(\d{1,3})\b")

# The version badge on the landing pages. Only the badge uses this markup, so the pattern needs no
# context words - and matching the markup rather than the label covers the Japanese page too,
# which carries the same badge with a translated caption.
VERSION_BADGE = re.compile(r"<b>v(\d+\.\d+\.\d+)</b>")

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
        # The bolded form is the one that mattered: this probe carries the '  ' the emphasis
        # blanking leaves behind, so it proves the pattern survives a headline number.
        "session tax (label)":   '<div class="big">{tax_pct}%</div>\n'
                                 '<div class="lab">of rule content stays out of the session</div>',
        "session tax (ja label)": '<div class="big">{tax_pct}%</div>\n'
                                  '<div class="lab">既定セッションから外れるルール本文の割合。</div>',
        "session tax (ja prose)": "ルール本文の  {tax_pct}%  が既定セッションの外に出る",
        "scanned-pdf threshold": "a scan (under {scan_chars} characters a page) routes to vision",
        "unconditional rules":   "{unconditional_rules} unconditional rules stay loaded",
        "unconditional rules (reversed)": "  {unconditional_rules}   rules unconditional",
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
        "roster range low":      "installs {roster_min} to {roster_max} of the 16 seats",
        "roster range high":     "installs {roster_min} to {roster_max} of the 16 seats",
        "media roster low":      "{roster_min} to {roster_max} of the 16 seats",
        "media roster high":     "{roster_min} to {roster_max} of the 16 seats",
        "media session tax":     '<div class="big">{tax_pct}%</div>\n'
                                 '<div class="lab">of rule content stays out of the session</div>',
        "media session tax ja":  '<div class="big">{tax_pct}%</div>\n'
                                 '<div class="lab">既定セッションから外れるルール本文の割合。</div>',
        "media session tax en":  "keeping {tax_pct}% of rule content out of the session",
        "media session tax ja prose": "ルール本文の{tax_pct}%が既定セッションの外に出る",
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

    flag_problems = flag_sync()
    print("\n  flag set (scaffold.py vs the three places that claim to match it):")
    if flag_problems:
        for p in flag_problems:
            print(f"    MISMATCH  {p}")
        print("\n  the flag list has drifted. Fix the source that is wrong, not KNOWN_FLAGS,")
        print("  unless KNOWN_FLAGS is the one that is wrong.")
        return 1
    print("    all four sources list the same flags.")

    bad = 0
    print("\n  documents:")
    for p in sorted(ROOT.rglob("*.md")):
        if SKIP_PARTS & set(p.parts):
            continue
        text = p.read_text(encoding="utf-8")
        # A shields.io badge URL escapes its slash as %2F, so "107%2F107" hid from the
        # pair regex below. The README carried 38/40 in the image while its own alt text
        # said 107/107, and this checker saw only the alt text. This shifts character
        # offsets but adds no newline, so the reported line numbers stay correct. Done
        # before the blanking below so raw and text stay offset-aligned.
        text = text.replace("%2F", "/").replace("%2f", "/")
        # Blank out inline code spans. A figure in backticks is a quotation - a changelog entry
        # naming the wrong number it fixed, for instance - not a claim the repo is making. Skip
        # the regex entirely when there is no backtick to blank - cheap and exact, same result.
        #
        # `raw` keeps the spans, because blanking them also erased the words that IDENTIFY a
        # claim. "`port.py --self-test` is 5/5" lost its subject and read as a bare pair, so a
        # stale figure sat in the release skill's own quality gate while this checker was green.
        # Blanking replaces each span with spaces of equal length, so the two share offsets:
        # match on `text` (a backticked figure is still not a claim), read context from `raw`.
        raw = text
        if "`" in text:
            text = re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), text)
        # Markdown emphasis around a figure defeated EVERY pattern here, silently. The main
        # README said "keeps **63%** of rule content out of the default session" while the real
        # figure was 64%, and the session-tax check found ZERO matches in that file: the '**'
        # sits between "63%" and " of rule content", so the regex never reached the phrase that
        # identifies the claim. A bolded figure is the NORMAL way to write a headline number in
        # this repo, so the check was dead exactly where it mattered most. One asterisk becomes
        # one space, which keeps every offset and therefore every reported line number correct.
        # `raw` keeps the markup, for the context reads above.
        if "*" in text:
            text = text.replace("*", " ")
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
        # A changelog entry states what was true at ITS release: "5/5" in an older section is a
        # correct historical record, not a stale claim, and rewriting it would falsify the
        # history. Current-state documents get no such exemption.
        historical = rel.endswith("CHANGELOG.md")
        # Eval badge in prose: "26/26" near eval-ish words is a claim about the suite. This drifted
        # across fifteen files at once while only the media files were scanned.
        for m in (() if historical else EVAL_PAIR.finditer(text)):
            a, b = int(m.group(1)), int(m.group(2))
            ctx = raw[max(0, m.start() - 120):m.start() + 60].lower()
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
        for m in (() if historical else ADAPTER_PAIR.finditer(text)):
            a, b = int(m.group(1)), int(m.group(2))
            ctx = raw[max(0, m.start() - 130):m.start() + 70].lower()
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
            # The other true pairs a page may legitimately quote next to the same words. Each is
            # derived, not typed: an earlier version excluded the literal string "5/5", which
            # silently stopped excluding anything the moment that suite grew to 18.
            other_truths = {c["eval_cases"], 2 * c["eval_cases"],
                            c["adapter_cases"], c["bench_block"]}
            # There is deliberately no "adapter not in ctx" exclusion here. The window is 200
            # characters wide, so on the landing page the word "adapter" in the NEXT badge fell
            # inside the eval badge's context and silenced it: a 99/99 eval claim went unreported.
            # `other_truths` already lets the adapter's own number through, which is what the
            # string exclusion was really for.
            if a == b and a not in other_truths \
                    and re.search(r"eval|guardrail|payload|ペイロード|ガードレール|forbidden|"
                                  r"permitted|judged|floor hold|proof|禁止|許可|bị cấm", ctx):
                line = text[:m.start()].count("\n") + 1
                print(f"    MISMATCH  {rel}:{line}  eval badge: says {a}/{b}, reality is "
                      f"{c['eval_cases']}/{c['eval_cases']}")
                bad += 1
        # The version badge. The install snippets beside it name the unversioned archive on
        # purpose, so this is the only place on these pages that has to carry a number.
        for m in VERSION_BADGE.finditer(text):
            if m.group(1) != c["version"]:
                line = text[:m.start()].count("\n") + 1
                print(f"    MISMATCH  {rel}:{line}  version badge: says v{m.group(1)}, "
                      f"reality is v{c['version']}")
                bad += 1
        # The adapter's own figure, in the pages as well as the markdown. Same rule, so a page
        # cannot quote a self-test result the markdown would have been failed for.
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

    if bad:
        print(f"\n  {bad} figure(s) contradict reality. Fix the doc, or the code if the doc is right.")
        return 1
    print("    every checked figure matches.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
