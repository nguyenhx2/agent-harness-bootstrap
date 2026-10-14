#!/usr/bin/env python3
"""Lint a project skill: metadata, progressive disclosure, trigger cases, and wiring.

Stdlib only, no install step - same discipline as `.claude/scripts/board-check.py`. A skill's
name and description are loaded into every session, and its SKILL.md is loaded whenever it
triggers or is preloaded into a seat, so a sloppy skill is paid for on every run. This checks
what can be checked deterministically and reports every violation rather than stopping at the
first one:

  frontmatter    SKILL.md opens with a `---` frontmatter block.
  name           present, lowercase letters/digits/single hyphens, at most NAME_MAX characters,
                 and equal to the folder name.
  description    present, at most DESCRIPTION_MAX characters, no XML-style tags.
  listing-cap    description + `when_to_use` fit in LISTING_MAX characters - Claude Code cuts the
                 rest from the skill listing, so a trigger written past it never fires.
  when           the description (or `when_to_use`) says WHEN to use it ("Use when ...").
  exclusion      the description says when NOT to use it ("Do not use ...", "Not for ...").
  placeholder    no `[[FILL: ...]]` left over from the template.
  ref-missing    every file or folder SKILL.md points at (`references/`, `scripts/`, `assets/`,
                 `templates/`, `examples/`, or a relative Markdown link) exists.
  ref-chain      a reference file does not lead to a further skill file that SKILL.md itself never
                 names - references stay one level deep, or the model reads half of them.
  budget         SKILL.md is at most LINE_BUDGET lines; the rest belongs in references/.
  cases-missing  `evals/trigger-cases.md` exists.
  cases-type     it covers all six case types: positive discovery, negative discovery, edge case,
                 conflict/composition, execution quality, efficiency.
  cases-field    every case type states Request, Repo state, Expected skills, Not expected and
                 Success criteria; execution quality also states a Baseline (without the skill).
  orphan         a seat (`.claude/agents/`, by `skills:` frontmatter or by name), a command or a
                 rule names the skill. Skipped with --template and --published.
  overlap        no quoted trigger phrase appears in two skills' descriptions.
  reasoning-dump SKILL.md or a reference it names does not ask the model to write out its
                 reasoning verbatim or in a fixed format (that can be refused as reasoning
                 extraction) - ask for a short summary of the actions taken instead.

Warnings (printed, never fail the run - they need a human read, not a verdict):

  script-review  a file under the skill's `scripts/` touches the network, installs something, or
                 deletes something. Say why in SKILL.md, or remove it.
  over-verify    the instructions ask for a double-check, a re-verification, a final verification
                 pass or a verifying subagent. The model already checks its work; one
                 deterministic validator (a script exit code) beats a second subjective review.

It also prints each description's estimated token cost (characters / 4 - an estimate, labelled
as one), because that text is in context in every session whether the skill fires or not.

Every run starts with a self-test that builds a clean fixture skill plus one mutant per detector
in a temporary folder, and fails if the clean one reports anything or a mutant goes unreported.
A few sound variants must also stay silent, so a detector that fires on everything is caught too.

Exit codes: 0 clean, 1 findings, 2 bad input (no such skill folder), 3 self-test failed.

Usage:
    python .claude/scripts/skill-check.py [--target <repo>]            # every .claude/skills/*
    python .claude/scripts/skill-check.py --skill .claude/skills/<name>
    python .claude/scripts/skill-check.py --template --skill .claude/templates/skill
    python .claude/scripts/skill-check.py --self-test
"""
from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import sys
import tempfile

# Limits from the Agent Skills specification (name and description) and Anthropic's authoring
# guidance (SKILL.md line count). Change them here, nowhere else.
NAME_MAX = 64
DESCRIPTION_MAX = 1024
LISTING_MAX = 1536  # Claude Code truncates description + when_to_use at this in the skill listing
LINE_BUDGET = 500

CASES_FILE = "evals/trigger-cases.md"
CASE_TYPES = {
    "positive-discovery": re.compile(r"positive", re.I),
    "negative-discovery": re.compile(r"negative", re.I),
    "edge-case": re.compile(r"\bedge\b", re.I),
    "conflict-composition": re.compile(r"conflict|composition", re.I),
    "execution-quality": re.compile(r"execution|quality", re.I),
    "efficiency": re.compile(r"efficien", re.I),
}
CASE_FIELDS = ("Request", "Repo state", "Expected skills", "Not expected", "Success criteria")
BASELINE_FIELD = "Baseline"

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# "Do not use for X" is an exclusion, not a when-clause - the lookbehinds keep it from counting.
WHEN_RE = re.compile(r"(?<!not )(?<!n't )(?<!never )\buse (?:it |this(?: skill)? )?(?:when|whenever|for|to)\b"
                     r"|\bwhen the user\b", re.I)
EXCLUSION_RE = re.compile(r"\b(?:do not|don't|never) use\b|\bnot for\b|\bskip (?:it|this)\b"
                          r"|\bnot (?:meant|intended) for\b", re.I)
XML_TAG_RE = re.compile(r"<[A-Za-z/][^>]*>")
PLACEHOLDER_RE = re.compile(r"\[\[FILL:([^\]]*)\]\]")
QUOTED_RE = re.compile(r"[\"\u201c]([^\"\u201d]{4,})[\"\u201d]")

LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
PATH_RE = re.compile(r"^(?:\$\{CLAUDE_(?:PLUGIN_ROOT|SKILL_DIR)\}/)?"
                     r"((?:references?|scripts|assets|templates|examples|evals)/\S*)$")

REASONING_DUMP_RE = re.compile(
    r"\b(?:write|print|output|show|record|log|dump|include)\s+(?:out\s+)?(?:all\s+of\s+)?(?:your|the)\s+"
    r"(?:full\s+|complete\s+|entire\s+|raw\s+|internal\s+|step-by-step\s+)*(?:reasoning|chain[- ]of[- ]thought|"
    r"thought process|thinking)\b|\breasoning\s+(?:verbatim|word for word)\b", re.I)
OVER_VERIFY_RE = re.compile(
    r"\bdouble[- ]check\b|\bre-?verify\b|\bverify (?:it |everything |your work )?again\b"
    r"|\bfinal verification (?:step|pass)\b|\bsubagent to (?:verify|double-check|review your)", re.I)

SCRIPT_RISKS = (
    ("network", re.compile(r"\burllib\b|\brequests\b|http\.client|\bsocket\b|\bcurl\s|\bwget\s"
                           r"|https?://")),
    ("install", re.compile(r"\bpip3? install\b|\bnpm (?:i|install)\b|\bnpx\s|\bapt(?:-get)? install\b"
                           r"|\bbrew install\b|\bcargo install\b")),
    ("destructive", re.compile(r"\brm -r|\bshutil\.rmtree\b|\bos\.remove\b|\.unlink\(|git reset --hard"
                               r"|git clean\b|\bDROP (?:TABLE|DATABASE)\b", re.I)),
)


# --------------------------------------------------------------------------- parsing

def split_frontmatter(text: str) -> tuple[dict[str, object] | None, str]:
    """Return (fields, body). Handles `key: value`, folded/literal blocks and `- item` lists."""
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    block, body = text[4:end], text[end + 4:].lstrip("\n")
    fields: dict[str, object] = {}
    key = None
    for line in block.split("\n"):
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if km:
            key, value = km.group(1), km.group(2).strip()
            if value in (">", "|", ">-", "|-", ""):
                fields[key] = ""
            elif value.startswith("[") and value.endswith("]"):
                fields[key] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            else:
                fields[key] = value.strip("'\"") if value[:1] in "'\"" else value
            continue
        if key is None:
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item:
            prev = fields.get(key)
            fields[key] = (prev if isinstance(prev, list) else []) + [item.group(1).strip().strip("'\"")]
        elif line.startswith((" ", "\t")) and isinstance(fields.get(key), str):
            fields[key] = (str(fields[key]) + " " + line.strip()).strip()
    return fields, body


def skill_file(skill_dir: pathlib.Path) -> pathlib.Path | None:
    for name in ("SKILL.md", "SKILL.md.tmpl"):
        if (skill_dir / name).is_file():
            return skill_dir / name
    return None


def unfill(text: str) -> str:
    """Template mode: `[[FILL: my-skill]]` reads as `my-skill`, so the shape is still checked."""
    return PLACEHOLDER_RE.sub(lambda m: m.group(1).strip(), text)


def references(text: str, base: pathlib.Path, skill_dir: pathlib.Path) -> list[pathlib.Path]:
    """Files inside the skill that `text` points at. Links resolve from `base`, backtick paths
    from the skill root; URLs, anchors, globs and placeholders are not paths."""
    out: list[pathlib.Path] = []
    for m in LINK_RE.finditer(text):
        raw = m.group(1).split("#")[0]
        if not raw or re.match(r"^[a-z]+:", raw) or raw.startswith(("/", "$")):
            continue
        out.append((base / raw).resolve())
    for span in CODE_SPAN_RE.findall(text):
        for token in span.split():
            m = PATH_RE.match(token.rstrip(".,;:)"))
            # A bare `templates/` is as likely the target repo's folder as the skill's - skip it.
            if not m or any(c in m.group(1) for c in "*<>{}[]") or m.group(1).count("/") == 1 \
                    and m.group(1).endswith("/"):
                continue
            out.append((skill_dir / m.group(1)).resolve())
    return out


def estimate_tokens(text: str) -> int:
    return (len(text) + 3) // 4


# --------------------------------------------------------------------------- checks

def check_skill(skill_dir: pathlib.Path, repo: pathlib.Path, template: bool = False,
                published: bool = False) -> tuple[list[tuple[str, str]], list[tuple[str, str]], dict]:
    """Return (findings, warnings, info). Each finding is (code, message)."""
    findings: list[tuple[str, str]] = []
    warnings: list[tuple[str, str]] = []
    info: dict[str, object] = {"name": skill_dir.name, "description": ""}
    skill_dir = skill_dir.resolve()
    md = skill_file(skill_dir)
    if md is None:
        return [("frontmatter", "no SKILL.md in this folder")], warnings, info
    raw = md.read_text(encoding="utf-8", errors="replace")

    if not template and PLACEHOLDER_RE.search(raw):
        findings.append(("placeholder", "SKILL.md still holds a [[FILL: ...]] placeholder"))
    text = unfill(raw) if template else raw
    fm, body = split_frontmatter(text)
    if fm is None:
        findings.append(("frontmatter", "SKILL.md does not open with a --- frontmatter block"))
        fm = {}

    name = str(fm.get("name", "") or "")
    info["name"] = name or skill_dir.name
    if not name:
        findings.append(("name", "frontmatter has no name"))
    else:
        if len(name) > NAME_MAX:
            findings.append(("name", f"name is {len(name)} characters, over {NAME_MAX}"))
        if not NAME_RE.match(name):
            findings.append(("name", f"name '{name}' is not lowercase letters, digits and single hyphens"))
        if not template and name != skill_dir.name:
            findings.append(("name", f"name '{name}' differs from its folder '{skill_dir.name}'"))

    desc = str(fm.get("description", "") or "")
    when_to_use = str(fm.get("when_to_use", "") or "")
    info["description"] = (desc + " " + when_to_use).strip()
    if len(desc) + len(when_to_use) > LISTING_MAX:
        findings.append(("listing-cap", f"description + when_to_use is {len(desc) + len(when_to_use)} "
                         f"characters; Claude Code truncates the listing at {LISTING_MAX}"))
    if not desc:
        findings.append(("description", "frontmatter has no description"))
    else:
        if len(desc) > DESCRIPTION_MAX:
            findings.append(("description", f"description is {len(desc)} characters, over {DESCRIPTION_MAX}"))
        if XML_TAG_RE.search(desc):
            findings.append(("description", "description contains an XML-style tag"))
        if not WHEN_RE.search(desc + " " + when_to_use):
            findings.append(("when", "description never says when to use it ('Use when ...')"))
        if not EXCLUSION_RE.search(desc):
            findings.append(("exclusion", "description never says when not to use it ('Do not use for ...')"))

    lines = text.count("\n") + 1
    info["lines"] = lines
    if lines > LINE_BUDGET:
        findings.append(("budget", f"SKILL.md is {lines} lines, over {LINE_BUDGET} - move detail into references/"))

    direct = set(references(body, md.parent, skill_dir))
    for target in sorted(direct):
        if not target.exists():
            findings.append(("ref-missing", f"SKILL.md points at {_rel(target, skill_dir)}, which does not exist"))
    # A chain is reading material the model must reach through another reading file. Files under
    # assets/ or templates/ are copied as output, not read for instructions, so they never count.
    for ref in sorted(direct):
        if not (ref.is_file() and ref.suffix == ".md" and _inside(ref, skill_dir)):
            continue
        for nxt in sorted(set(references(ref.read_text(encoding="utf-8", errors="replace"), ref.parent,
                                         skill_dir))):
            if (nxt.suffix == ".md" and nxt.exists() and _inside(nxt, skill_dir)
                    and _rel(nxt, skill_dir).split("/")[0] not in ("assets", "templates")
                    and nxt not in direct and nxt != md.resolve() and nxt != ref):
                findings.append(("ref-chain", f"SKILL.md -> {_rel(ref, skill_dir)} -> {_rel(nxt, skill_dir)}: "
                                 "name the second file from SKILL.md, or fold it in"))

    prose = [("SKILL.md", body)] + [
        (_rel(r, skill_dir), r.read_text(encoding="utf-8", errors="replace"))
        for r in sorted(direct) if r.is_file() and r.suffix == ".md" and _inside(r, skill_dir)]
    for where, chunk in prose:
        for rx, code, why, bucket in (
                (REASONING_DUMP_RE, "reasoning-dump",
                 "asks for the reasoning itself - ask for a short summary of the actions taken", findings),
                (OVER_VERIFY_RE, "over-verify",
                 "asks for a second subjective check - prefer one deterministic validator", warnings)):
            hit = rx.search(chunk)
            if hit:
                ln = chunk.count("\n", 0, hit.start()) + 1
                bucket.append((code, f"{where}:{ln} '{hit.group(0)}' {why}"))

    findings += check_cases(skill_dir / CASES_FILE)

    if not (template or published):
        if not wired(info["name"], repo, skill_dir):
            findings.append(("orphan", f"no seat, command or rule under {_rel(repo / '.claude', repo)}/ names "
                             f"'{info['name']}' - wire it (/skill-wire) or remove it"))

    scripts = skill_dir / "scripts"
    if scripts.is_dir():
        for f in sorted(p for p in scripts.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            src = f.read_text(encoding="utf-8", errors="replace")
            for kind, rx in SCRIPT_RISKS:
                hit = rx.search(src)
                if hit:
                    ln = src.count("\n", 0, hit.start()) + 1
                    warnings.append(("script-review", f"{_rel(f, skill_dir)}:{ln} {kind} ('{hit.group(0).strip()}')"))
    return findings, warnings, info


def check_cases(path: pathlib.Path) -> list[tuple[str, str]]:
    if not path.is_file():
        return [("cases-missing", f"no {CASES_FILE} - write the six trigger case types before wiring")]
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    sections: dict[str, str] = {}
    for chunk in re.split(r"(?m)^## ", text)[1:]:
        heading, _, rest = chunk.partition("\n")
        for key, rx in CASE_TYPES.items():
            if key not in sections and rx.search(heading):
                sections[key] = rest
                break
    out: list[tuple[str, str]] = []
    for key in CASE_TYPES:
        if key not in sections:
            out.append(("cases-type", f"{CASES_FILE} has no '## {key}' section"))
            continue
        need = CASE_FIELDS + ((BASELINE_FIELD,) if key == "execution-quality" else ())
        for field in need:
            if not re.search(rf"(?mi)^\s*[-*]\s+(?:\*\*)?{re.escape(field)}[^:\n]*:(?:\*\*)?\s*\S",
                             sections[key]):
                out.append(("cases-field", f"{CASES_FILE} '{key}' does not state '{field}:'"))
    return out


def wired(name: str, repo: pathlib.Path, skill_dir: pathlib.Path) -> bool:
    n = re.escape(name)
    mention = re.compile(rf"`{n}`|/{n}(?![\w-])|skills/{n}(?![\w-])|Skill\({n}")
    for sub in ("agents", "commands", "rules"):
        d = repo / ".claude" / sub
        if not d.is_dir():
            continue
        for f in d.rglob("*.md"):
            if _inside(f.resolve(), skill_dir):
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            fm, _ = split_frontmatter(text)
            pre = (fm or {}).get("skills")
            if isinstance(pre, str):
                pre = [s.strip() for s in pre.split(",")]
            if isinstance(pre, list) and name in pre:
                return True
            if mention.search(text):
                return True
    return False


def overlaps(infos: list[dict]) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    out: list[tuple[str, str]] = []
    for info in infos:
        for phrase in {p.strip().lower() for p in QUOTED_RE.findall(str(info["description"]))}:
            other = seen.get(phrase)
            if other and other != info["name"]:
                out.append(("overlap", f"'{phrase}' triggers both {other} and {info['name']} - route it to one"))
            seen.setdefault(phrase, str(info["name"]))
    return out


def _inside(p: pathlib.Path, d: pathlib.Path) -> bool:
    try:
        p.resolve().relative_to(d.resolve())
        return True
    except ValueError:
        return False


def _rel(p: pathlib.Path, base: pathlib.Path) -> str:
    try:
        return p.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


# --------------------------------------------------------------------------- self-test

_CASES = "\n".join(
    f"## {t}\n\n- Request: r\n- Repo state: s\n- Expected skills: demo-skill\n- Not expected: none\n"
    f"- Success criteria: c\n" + ("- Baseline (without the skill): b\n" if t == "execution-quality" else "")
    for t in CASE_TYPES)

_CLEAN = {
    ".claude/agents/seat.md": "---\nname: seat\ndescription: d\nskills:\n  - demo-skill\n---\nBody.\n",
    ".claude/skills/demo-skill/SKILL.md": (
        "---\nname: demo-skill\ndescription: Formats demo reports. Use when the user asks for a "
        "\"demo report\". Do not use for release notes.\n---\n# Demo\n\nSee [details](references/details.md)"
        ". Run `scripts/check.py`.\n"),
    ".claude/skills/demo-skill/references/details.md": "Details.\n",
    ".claude/skills/demo-skill/scripts/check.py": "print('ok')\n",
    ".claude/skills/demo-skill/" + CASES_FILE: _CASES,
}
_S = ".claude/skills/demo-skill/"
_SKILL = _CLEAN[_S + "SKILL.md"]
_MUTANTS: dict[str, dict[str, str | None]] = {
    "frontmatter": {_S + "SKILL.md": _SKILL.split("---\n", 2)[2]},
    "name": {_S + "SKILL.md": _SKILL.replace("name: demo-skill", "name: Demo_Skill")},
    "description": {_S + "SKILL.md": _SKILL.replace("Formats demo reports.", "x" * (DESCRIPTION_MAX + 1))},
    "listing-cap": {_S + "SKILL.md": _SKILL.replace("---\n# Demo",
                                                    "when_to_use: " + "y" * LISTING_MAX + "\n---\n# Demo")},
    "when": {_S + "SKILL.md": _SKILL.replace("Use when the user asks for a", "Handles a")},
    "exclusion": {_S + "SKILL.md": _SKILL.replace(" Do not use for release notes.", "")},
    "placeholder": {_S + "SKILL.md": _SKILL + "[[FILL: something]]\n"},
    "ref-missing": {_S + "references/details.md": None},
    "ref-chain": {_S + "references/details.md": "See [more](deeper.md).\n",
                  _S + "references/deeper.md": "Deeper.\n"},
    "budget": {_S + "SKILL.md": _SKILL + "line\n" * LINE_BUDGET},
    "cases-missing": {_S + CASES_FILE: None},
    "cases-type": {_S + CASES_FILE: _CASES.split("## efficiency")[0]},
    "cases-field": {_S + CASES_FILE: _CASES.replace("- Success criteria: c\n", "", 1)},
    # The seat stays, it just stops naming the skill - so a wiring test that answers "yes" to any
    # file at all is caught too, not only one that finds no files.
    "orphan": {".claude/agents/seat.md": "---\nname: seat\ndescription: d\nskills:\n  - other\n---\n"
                                         "Uses `other-skill` and /demo-skills.\n"},
    "overlap": {".claude/skills/twin/SKILL.md": "---\nname: twin\ndescription: Use when asked for a "
                "\"demo report\". Do not use otherwise.\n---\n"},
    "script-review": {_S + "scripts/check.py": "import urllib.request\n"},
    "reasoning-dump": {_S + "SKILL.md": _SKILL + "Write out your full reasoning before answering.\n"},
    "over-verify": {_S + "references/details.md": "Then double-check every step.\n"},
}
# Variants that are still sound and must stay silent: each proves a detector is not simply
# matching everything (wiring found by a command mention alone, a bare folder name not taken
# for a path, a `when_to_use` field carrying the when-clause).
_CLEAN_VARIANTS: dict[str, dict[str, str | None]] = {
    "wired by a command": {".claude/agents/seat.md": None,
                           ".claude/commands/report.md": "---\ndescription: d\n---\nRun /demo-skill.\n"},
    "bare folder mention": {_S + "SKILL.md": _SKILL + "Outputs go to `templates/`.\n"},
    "when_to_use field": {_S + "SKILL.md": _SKILL.replace(
        "Use when the user asks for a", "Handles a").replace(
        "---\n# Demo", "when_to_use: Use when a demo report is requested.\n---\n# Demo")},
}


def _build(root: pathlib.Path, files: dict[str, str | None]) -> None:
    for rel, content in files.items():
        p = root / rel
        if content is None:
            if p.exists():
                p.unlink()
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")


def _run_fixture(root: pathlib.Path) -> set[str]:
    infos, codes = [], set()
    for d in sorted((root / ".claude" / "skills").iterdir()):
        f, w, info = check_skill(d, root)
        if d.name == "demo-skill":
            codes |= {c for c, _ in f} | {c for c, _ in w}
        infos.append(info)
    return codes | {c for c, _ in overlaps(infos)}


def self_test() -> list[str]:
    """Prove every detector can fire, and that a clean skill passes. A detector that matches
    nothing prints ok exactly like a well-made skill does - this is what tells them apart."""
    dead: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        clean = pathlib.Path(tmp) / "clean"
        _build(clean, _CLEAN)
        got = _run_fixture(clean)
        if got:
            dead.append(f"self-test: the clean fixture reported {sorted(got)} - a sound skill must pass")
        for code, change in _MUTANTS.items():
            root = pathlib.Path(tmp) / code
            shutil.copytree(clean, root)
            _build(root, change)
            if code not in _run_fixture(root):
                dead.append(f"DEAD CHECK - {code}: its mutant fixture was not reported, so this "
                            "detector can never fail")
        for label, change in _CLEAN_VARIANTS.items():
            root = pathlib.Path(tmp) / ("ok-" + label.replace(" ", "-"))
            shutil.copytree(clean, root)
            _build(root, change)
            got = _run_fixture(root)
            if got:
                dead.append(f"self-test: the sound variant '{label}' reported {sorted(got)} - a "
                            "detector is firing on good input")
    return dead


# --------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=pathlib.Path, default=pathlib.Path("."),
                    help="repo root whose .claude/ is searched for wiring (default: .)")
    ap.add_argument("--skill", type=pathlib.Path, action="append", default=[],
                    help="a skill folder to check; repeatable (default: every .claude/skills/*)")
    ap.add_argument("--template", action="store_true",
                    help="checking the skill template: placeholders allowed, no wiring check")
    ap.add_argument("--published", action="store_true",
                    help="a published skill invoked by its own description: no wiring check")
    ap.add_argument("--self-test", action="store_true", help="run only the self-test")
    args = ap.parse_args()

    dead = self_test()
    for d in dead:
        print(f"  FAIL  {d}")
    if dead:
        print(f"skill-check: self-test failed ({len(dead)}) - the results below could not be trusted")
        return 3
    print(f"skill-check: self-test ok ({len(_MUTANTS)} detectors fire, clean fixture passes)")
    if args.self_test:
        return 0

    repo = args.target.resolve()
    dirs = [d.resolve() for d in args.skill]
    if not dirs:
        base = repo / ".claude" / "skills"
        dirs = sorted(d for d in base.iterdir() if d.is_dir()) if base.is_dir() else []
    bad = [d for d in dirs if not d.is_dir()]
    if bad:
        print(f"skill-check: not a folder: {', '.join(str(b) for b in bad)}")
        return 2
    if not dirs:
        print("skill-check: no skills under .claude/skills/ - nothing to check")
        return 0

    total, infos, failed = 0, [], 0
    for d in dirs:
        findings, warnings, info = check_skill(d, repo, args.template, args.published)
        infos.append(info)
        cost = estimate_tokens(f"{info['name']}: {info['description']}")
        total += cost
        failed += len(findings)
        print(f"  {'FAIL' if findings else 'ok  '}  {info['name']}  "
              f"(description ~{cost} tokens, estimate; SKILL.md {info.get('lines', '?')} lines)")
        for code, msg in findings:
            print(f"          [{code}] {msg}")
        for code, msg in warnings:
            print(f"          (warn {code}) {msg}")
    for code, msg in overlaps(infos):
        failed += 1
        print(f"  FAIL  [{code}] {msg}")

    print(f"skill-check: {len(dirs)} skill(s), always-loaded metadata ~{total} tokens (estimate), "
          f"{failed} finding(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
