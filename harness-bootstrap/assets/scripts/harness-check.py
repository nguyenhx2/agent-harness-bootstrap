#!/usr/bin/env python3
"""Check that the harness hangs together: every link between its parts points at something real.

Stdlib only, no install step - same discipline as `board-check.py`. Each part of a harness can be
correct on its own and the whole still be broken: a command that dispatches a seat nobody fielded,
a hook registered in settings.json whose script was renamed, a model changed in an agent file but
not in the tier table that is supposed to decide it, a rule cited by five files that was never
installed. Each of those looks like a working control and is not one. This is the one entry point
that checks the links, and it delegates to the checkers that already exist rather than repeating
them: the task board goes to `board-check.py`, project skills to `skill-check.py`.

Checks (each reports file:line and the fix):

  settings-json     .claude/settings.json parses.
  hook-missing      every hook script settings.json or a seat's `hooks:` frontmatter runs exists.
  hook-not-exec     ...and, on a POSIX machine, a registered .sh is executable.
  hook-unregistered every hook script in .claude/hooks/ is registered, or parked by harness-toggle
                    (parked hooks live in .claude/disabled/hooks/ and are not looked at).
  seat-frontmatter  every seat has tools, maxTurns, a real model and effort, no bypassPermissions,
                    and only the orchestrator holds Agent.
  review-readonly   review seats hold no Edit/Write and no memory:.
  tier-table        model-tiers.md and the seats agree: model, effort, every row's seat exists,
                    every seat has a row.
  agent-ref         every seat a command, rule, seat, routing table or Agent(...) allowlist names
                    exists (or is parked).
  routing           every seat appears in the AGENTS.md routing table (stage `full` only - at
                    scaffold time the table is still being written).
  command-ref       every shipped /command the harness tells someone to run is installed.
  cite-missing      every rule or file an agent, command, rule or CLAUDE.md/AGENTS.md cites exists.
  skill-missing     every skill a seat lists in `skills:` (or declares as available) is installed.
  unknown-tool      allowed-tools, tools and disallowedTools name only tools that exist.
  purpose           the seats present match one coherent set of purpose profiles: no dev, test or
                    data seat without the code review gate, no checker without a non-code purpose.
  nested-claude     @imports and relative links in CLAUDE.md / AGENTS.md (root and nested) resolve.
  structure         the folders and files every harness ships exist: the .claude/ tree with
                    hooks/README.md, and the docs/ tree (README, specs, requirements, architecture,
                    tasks with master-plan.md and its three state folders, context, templates).
  instruction-length the root CLAUDE.md and AGENTS.md together stay under INSTRUCTION_MAX_LINES -
                    both load in every session (harness-view's COST-06 uses the same budget).
  board             delegated to board-check.py (enums, deps, board-vs-file drift) plus the two
                    board directories the shipped hooks key off.
  skill-lint        delegated to skill-check.py for every skill under .claude/skills/.
  spec              delegated to spec-check.py (shipped by spec-builder) once docs/specs/ holds
                    a spec set: IDs, criteria, references, and the generated sheet and index.

Exit codes: 0 clean, 1 findings, 3 self-test failed.

Usage:
    python .claude/scripts/harness-check.py [--target <repo>] [--json] [--stage full|scaffold]
    python .claude/scripts/harness-check.py --self-test

--json prints {"version", "tool", "root", "stage", "ok", "checks": [...], "findings": [{"check",
"file", "line", "message", "fix"}]} for harness-view and other readers.

Optional CI step (GitHub Actions; any runner with Python 3 works the same way):

    - name: The harness hangs together
      run: python .claude/scripts/harness-check.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile

# Importing a sibling script must not leave bytecode in .claude/scripts/: a stray .pyc there
# is an untracked file, and verify-plan.py would ask for a review of it.
sys.dont_write_bytecode = True

# ------------------------------------------------------------------------------- catalogs
# The seats and commands the skill ships. A backticked name from these lists that is not installed
# is a link to nowhere; a name outside them is not assumed to be a seat (prose is full of backticked
# words). scripts/check_integration.py in the skill repo fails when these drift from the assets.
# Deliberately absent: the audit-mode seats (`<repo>-auditor`, `sast-runner`, `perf-reviewer`).
# They are authored per audited repo at audit time (reference/audit-mode.md), never shipped as
# assets, so model-tiers.md may name `sast-runner` before its seat file exists - not a dead link.
CATALOG_SEATS = (
    "ba-analyst", "checker", "code-reviewer", "data-modeler", "db-engineer", "db-seeder",
    "debugger", "devops", "history-tracker", "merge-manager", "orchestrator", "qa-test",
    "researcher", "reviewer", "security-reviewer", "spec-guardian", "strategist", "writer",
)
# Seats an audit harness authors per audited repo, so the tier table may name them before they exist.
AUDIT_AUTHORED = ("sast-runner", "perf-reviewer")
CATALOG_COMMANDS = (
    "agent-permissions", "board-audit", "brainstorm", "code-graph", "db-migration", "deploy",
    "docs-graph", "harness-toggle", "harness-tune", "harness-update", "implement-fr", "new-adr",
    "new-skill", "new-spec-section", "new-task", "review-changes", "scaffold-feature",
    "secret-scan", "security-scan", "seed-db", "skill-wire", "sync-context", "task-resume",
    "test", "triage-findings",
)
# Claude Code's tool names (references/models-and-tools.json in the skill repo, checked against
# this set), plus legacy names the runtime still accepts. mcp__* tools are not checkable offline.
KNOWN_TOOLS = {
    "Agent", "Artifact", "AskUserQuestion", "Bash", "CronCreate", "CronDelete", "CronList", "Edit",
    "EndConversation", "EnterPlanMode", "EnterWorktree", "ExitPlanMode", "ExitWorktree", "Glob",
    "Grep", "ListAgents", "ListMcpResourcesTool", "LSP", "Monitor", "NotebookEdit", "PowerShell",
    "PushNotification", "Read", "ReadMcpResourceTool", "RemoteTrigger", "ReportFindings",
    "ScheduleWakeup", "SendMessage", "SendUserFile", "ShareOnboardingGuide", "Skill", "TaskCreate",
    "TaskGet", "TaskList", "TaskOutput", "TaskStop", "TaskUpdate", "TodoWrite", "ToolSearch",
    "WaitForMcpServers", "WebFetch", "WebSearch", "Workflow", "Write",
    # legacy aliases
    "Task", "MultiEdit", "NotebookRead", "BashOutput", "KillShell", "SlashCommand", "LS",
}
SEAT_MODELS = {"opus", "sonnet", "haiku", "fable", "inherit"}
SEAT_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
SEAT_MODES = {"default", "acceptEdits", "auto", "dontAsk", "plan"}
SPAWNER = "orchestrator"
# Seats whose whole value is that they do not change what they judge. `editor` judges a writing
# repo but corrects copy as its job, so it is not held read-only (same rule as harness-view).
REVIEWERS = {"code-reviewer", "merge-manager", "reviewer", "security-reviewer", "spec-guardian",
             "checker", "debugger"}
# Names the harness may cite before they exist: rules the bootstrap run authors per repo, the spec
# file written later, the run-archive index written at runtime, and the dev-agent template's name.
AUTHORED_LATER = {"coding-standards.md", "tech-stack.md", "git-workflow.md",
                  "13-revision-history.md", "index.md", "dev-agent.md"}
# Files another skill installs, cited only as "when present": spec-builder ships
# .claude/scripts/spec-check.py with the spec set and owns its version. harness-bootstrap never
# copies it (a copy would fork it), so its absence is a state, not a broken link.
INSTALLED_BY_OTHER = {"spec-check.py"}

# Seats and hooks that only make sense in a code harness, and the markers that say it is one.
CODE_MARKERS = {"ba-analyst", "debugger", "devops", "spec-guardian", "code-reviewer",
                "security-reviewer", "reviewer"}
CODE_ONLY_SEATS = {"qa-test", "data-modeler", "db-engineer", "db-seeder", "merge-manager"}
CODE_ONLY_HOOKS = {"guard-deps", "guard-migration"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "worktrees", "dist", "build",
             "target", ".next", "vendor"}

CHECKS = {
    "settings-json": "settings.json parses",
    "hook-missing": "every registered hook script exists",
    "hook-not-exec": "registered .sh hooks are executable",
    "hook-unregistered": "every hook on disk is registered or parked",
    "seat-frontmatter": "seat frontmatter is complete and bounded",
    "review-readonly": "review seats are read-only",
    "tier-table": "model-tiers.md agrees with the seats",
    "agent-ref": "every referenced seat exists",
    "routing": "every seat is in the AGENTS.md routing table",
    "command-ref": "every referenced command exists",
    "cite-missing": "every cited rule or file exists",
    "skill-missing": "every skill a seat lists is installed",
    "unknown-tool": "tool lists name real tools",
    "purpose": "seats match one coherent purpose",
    "nested-claude": "CLAUDE.md / AGENTS.md links resolve",
    "structure": "the shipped .claude/ and docs/ trees are complete",
    "instruction-length": "root CLAUDE.md + AGENTS.md stay under the line budget",
    "board": "task board is consistent (board-check.py)",
    "skill-lint": "project skills lint clean (skill-check.py)",
    "spec": "spec set is consistent (spec-check.py)",
}
STAGE_SKIPS = {"scaffold": {"routing"}, "full": set()}


class Finding:
    __slots__ = ("check", "file", "line", "message", "fix")

    def __init__(self, check: str, file: str | None, line: int | None, message: str, fix: str):
        self.check, self.file, self.line, self.message, self.fix = check, file, line, message, fix

    def where(self) -> str:
        if not self.file:
            return "-"
        return f"{self.file}:{self.line}" if self.line else self.file

    def to_json(self) -> dict:
        return {"check": self.check, "file": self.file, "line": self.line,
                "message": self.message, "fix": self.fix}


# --------------------------------------------------------------------------------- helpers
def read(p: pathlib.Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    except OSError:
        return ""


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def find_line(text: str, needle: str, default: int | None = None) -> int | None:
    i = text.find(needle)
    return line_of(text, i) if i >= 0 else default


def front(text: str) -> str:
    """The raw frontmatter block (without the fences), or ''."""
    m = re.match(r"\A---\n(.*?)\n---[ \t]*(\n|\Z)", text, re.DOTALL)
    return m.group(1) if m else ""


def scalars(fm: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in fm.splitlines():
        kv = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):[ \t]*(.*?)[ \t]*$", line)
        if kv:
            out[kv.group(1)] = kv.group(2).strip("\"'")
    return out


def split_top(s: str) -> list[str]:
    """Split on commas that are not inside parentheses or brackets."""
    out, depth, cur = [], 0, ""
    for c in s:
        if c in "([":
            depth += 1
        elif c in ")]":
            depth = max(0, depth - 1)
        if c == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += c
    out.append(cur)
    return [x.strip().strip("\"'") for x in out if x.strip().strip("\"'")]


def list_value(fm: str, key: str) -> list[str]:
    """A frontmatter key as a list: `k: a, b`, `k: [a, b]`, or a YAML block list."""
    m = re.search(rf"^{re.escape(key)}:[ \t]*(.*)$", fm, re.MULTILINE)
    if not m:
        return []
    inline = m.group(1).strip()
    if inline:
        if inline.startswith("[") and inline.endswith("]"):
            inline = inline[1:-1]
        return split_top(inline)
    out = []
    for line in fm[m.end():].splitlines():
        if not line.strip():
            continue
        item = re.match(r"^[ \t]+-[ \t]*(.+)$", line)
        if not item:
            break
        out.append(item.group(1).strip().strip("\"'"))
    return out


def tool_name(entry: str) -> str:
    return entry.split("(", 1)[0].strip()


def holds_agent(tools: list[str]) -> bool:
    return any(tool_name(t) in ("Agent", "Task") for t in tools)


def spawn_list(tools: list[str]) -> list[str]:
    out = []
    for t in tools:
        m = re.match(r"^(?:Agent|Task)\((.*)\)$", t.strip())
        if m:
            out += split_top(m.group(1))
    return out


HOOK_PATH = re.compile(r"hooks/([A-Za-z0-9_-]+)\.(sh|ps1|py)\b")


class Harness:
    """Everything the checks read, loaded once."""

    def __init__(self, root: pathlib.Path):
        self.root = root
        self.claude = root / ".claude"
        self.agents = {p.stem: p for p in sorted((self.claude / "agents").glob("*.md"))}
        self.commands = {p.stem for p in (self.claude / "commands").glob("*.md")}
        self.commands |= {p.parent.name for p in (self.claude / "commands").glob("*/SKILL.md")}
        dis = self.claude / "disabled"
        self.parked = {k: {p.stem for p in (dis / k).glob("*")} for k in
                       ("agents", "commands", "rules", "hooks")}
        self.texts: dict[pathlib.Path, str] = {}

    def text(self, p: pathlib.Path) -> str:
        if p not in self.texts:
            self.texts[p] = read(p)
        return self.texts[p]

    def rel(self, p: pathlib.Path) -> str:
        try:
            return p.relative_to(self.root).as_posix()
        except ValueError:
            return p.as_posix()

    def seat_known(self, name: str) -> bool:
        return name in self.agents or name in self.parked["agents"]

    def prose_files(self) -> list[pathlib.Path]:
        """The files that tell a model what to do: seats, commands, rules, the hooks README and the
        root contracts."""
        out: list[pathlib.Path] = []
        for d in ("agents", "commands", "rules"):
            out += sorted((self.claude / d).rglob("*.md"))
        out += [p for p in (self.claude / "hooks" / "README.md", self.root / "AGENTS.md",
                            self.root / "CLAUDE.md") if p.is_file()]
        return out


# -------------------------------------------------------------------------------- checks
def check_hooks(h: Harness, out: list[Finding]) -> None:
    settings = h.claude / "settings.json"
    regs: list[tuple[str, str, str, int | None]] = []  # (stem, ext, file, line)
    if settings.is_file():
        text = h.text(settings)
        try:
            data = json.loads(text)
        except ValueError as e:
            out.append(Finding("settings-json", h.rel(settings), getattr(e, "lineno", None),
                               f"settings.json is not valid JSON ({e.msg if hasattr(e, 'msg') else e})"
                               " - no hook, allow or deny entry is in force",
                               "fix the JSON syntax at that line; `python -m json.tool` names it"))
            data = {}
        for event, groups in (data.get("hooks") or {}).items() if isinstance(data, dict) else []:
            for g in groups if isinstance(groups, list) else []:
                for hk in (g.get("hooks") if isinstance(g, dict) else None) or []:
                    cmd = str(hk.get("command", "")) if isinstance(hk, dict) else ""
                    for m in HOOK_PATH.finditer(cmd):
                        regs.append((m.group(1), m.group(2), h.rel(settings),
                                     find_line(text, m.group(0))))
    for seat, p in h.agents.items():
        text = h.text(p)
        fm = front(text)
        if not re.search(r"^hooks:", fm, re.MULTILINE):
            continue
        for m in HOOK_PATH.finditer(fm):
            regs.append((m.group(1), m.group(2), h.rel(p), line_of(text, text.find(m.group(0)))))

    hooks_dir = h.claude / "hooks"
    for stem, ext, where, line in regs:
        f = hooks_dir / f"{stem}.{ext}"
        if not f.is_file():
            parked = stem in h.parked["hooks"]
            out.append(Finding(
                "hook-missing", where, line,
                f"runs .claude/hooks/{stem}.{ext}, which is not on disk"
                + (" (it is parked in .claude/disabled/hooks/ but still registered)" if parked else "")
                + " - the guardrail never fires and nothing reports it",
                "run `python .claude/scripts/harness-toggle.py reapply`" if parked else
                f"restore .claude/hooks/{stem}.{ext}, or remove the registration"))
        elif ext == "sh" and os.name == "posix" and not os.access(f, os.X_OK):
            out.append(Finding("hook-not-exec", h.rel(f), None,
                               f"{stem}.sh is registered but not executable",
                               f"chmod +x .claude/hooks/{stem}.sh (and mark it \"exec\": true in "
                               "the skill manifest)"))
    registered = {s for s, _, _, _ in regs}
    if hooks_dir.is_dir():
        for f in sorted(hooks_dir.iterdir()):
            if f.is_file() and f.suffix in (".sh", ".ps1") and not f.stem.startswith("_") \
                    and f.stem not in registered:
                out.append(Finding(
                    "hook-unregistered", h.rel(f), None,
                    f"hook {f.stem} is installed but nothing registers it - it looks like a "
                    "control and enforces nothing",
                    f"register it in .claude/settings.json, or park it with `python "
                    f".claude/scripts/harness-toggle.py disable hook/{f.stem} --yes`"))


def check_seats(h: Harness, out: list[Finding]) -> None:
    for seat, p in h.agents.items():
        text = h.text(p)
        fm = front(text)
        sc = scalars(fm)
        rel = h.rel(p)

        def ln(key: str) -> int:
            return find_line(text, f"\n{key}:", 0) + 1 if f"\n{key}:" in text else 1

        tools = list_value(fm, "tools")
        if not tools:
            out.append(Finding("seat-frontmatter", rel, 1,
                               f"{seat} has no tools: line - it inherits every tool on the machine",
                               "add an explicit tools: list"))
        if not re.fullmatch(r"[1-9][0-9]*", sc.get("maxTurns", "")):
            out.append(Finding("seat-frontmatter", rel, ln("maxTurns") if "maxTurns" in sc else 1,
                               f"{seat} has no positive maxTurns - a looping seat runs unbounded",
                               "add maxTurns: <n>"))
        model = sc.get("model", "")
        if model not in SEAT_MODELS - {"inherit"} and not re.fullmatch(r"claude-[a-z0-9.-]+", model):
            out.append(Finding("seat-frontmatter", rel, ln("model") if model else 1,
                               f"{seat} has model `{model}` - unset or inherit bills it at the "
                               "caller's tier", "set model: to the tier's alias in model-tiers.md"))
        if sc.get("effort") not in SEAT_EFFORTS:
            out.append(Finding("seat-frontmatter", rel, ln("effort") if "effort" in sc else 1,
                               f"{seat} has effort `{sc.get('effort', '')}`",
                               f"set effort: to one of {', '.join(sorted(SEAT_EFFORTS))}"))
        mode = sc.get("permissionMode")
        if mode == "bypassPermissions" or (mode is not None and mode not in SEAT_MODES):
            out.append(Finding("seat-frontmatter", rel, ln("permissionMode"),
                               f"{seat} has permissionMode `{mode}`",
                               f"use one of {', '.join(sorted(SEAT_MODES))}"))
        if seat != SPAWNER and holds_agent(tools):
            out.append(Finding("seat-frontmatter", rel, ln("tools"),
                               f"{seat} holds the Agent tool - only the {SPAWNER} dispatches",
                               "remove Agent from its tools:"))
        if seat in REVIEWERS:
            writes = [t for t in tools if tool_name(t) in ("Edit", "Write", "NotebookEdit",
                                                           "MultiEdit")]
            if writes:
                out.append(Finding("review-readonly", rel, ln("tools"),
                                   f"review seat {seat} holds {', '.join(writes)} - a reviewer "
                                   "that can edit has stopped being a reviewer",
                                   "remove them from tools: and list them in disallowedTools:"))
            if "memory" in sc:
                out.append(Finding("review-readonly", rel, ln("memory"),
                                   f"review seat {seat} sets memory:, which grants Write and Edit",
                                   "remove memory: from the review seat"))
        for key in ("tools", "disallowedTools"):
            for t in list_value(fm, key):
                name = tool_name(t)
                if name and name not in KNOWN_TOOLS and not name.startswith("mcp__"):
                    out.append(Finding("unknown-tool", rel, ln(key),
                                       f"{seat} {key} names `{name}`, which is not a tool",
                                       "fix the spelling or remove it"))
        for target in spawn_list(tools):
            if not h.seat_known(target) and target not in ("Explore", "Plan", "general-purpose"):
                out.append(Finding("agent-ref", rel, ln("tools"),
                                   f"{seat} may spawn `{target}`, which is not a seat",
                                   f"create .claude/agents/{target}.md or drop it from Agent(...)"))
        for sk in list_value(fm, "skills"):
            if not skill_installed(h, sk):
                out.append(Finding("skill-missing", rel, ln("skills"),
                                   f"{seat} preloads skill `{sk}`, which is not installed",
                                   f"install it under .claude/skills/{sk}/ or remove it from "
                                   "skills:"))
        for i, line in enumerate(text.splitlines(), 1):
            val = skill_decl(line)
            if val is None:
                continue
            for sk in re.findall(r"`([a-z0-9][a-z0-9:_-]*)`", val):
                if not skill_installed(h, sk):
                    out.append(Finding("skill-missing", rel, i,
                                       f"{seat} declares skill `{sk}`, which is not installed",
                                       f"install .claude/skills/{sk}/ or remove the line "
                                       "(/skill-wire)"))


def skill_decl(line: str) -> str | None:
    """A line that declares skills for a seat (the /skill-wire convention)."""
    low = line.lower()
    kw, colon = low.find("skill"), line.find(":")
    if kw < 0 or colon < kw:
        return None
    if not any(m in low[kw:colon] for m in ("available", "to load", "in use", "when relevant")):
        return None
    return line[colon + 1:]


def skill_installed(h: Harness, name: str) -> bool:
    if ":" in name:  # plugin-namespaced: resolved by the plugin system, not checkable here
        return True
    return ((h.claude / "skills" / name / "SKILL.md").is_file()
            or (pathlib.Path.home() / ".claude" / "skills" / name / "SKILL.md").is_file())


def check_tiers(h: Harness, out: list[Finding]) -> None:
    tiers = h.claude / "rules" / "model-tiers.md"
    if not tiers.is_file():
        return
    text = h.text(tiers)
    rel = h.rel(tiers)
    rowed: set[str] = set()
    dev_row, dev_effort, dev_model = False, "", ""
    for i, row in enumerate(text.splitlines(), 1):
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) != 4 or not re.fullmatch(r"`[a-z0-9.-]+`", cells[3]):
            continue
        want = cells[3].strip("`")
        for seat, effort in re.findall(r"`([^`]+)`\s*(?:\(([a-z]+)\))?", cells[2]):
            if "<" in seat:
                if seat.endswith("-dev"):
                    dev_row, dev_effort, dev_model = True, effort, want
                continue
            rowed.add(seat)
            p = h.agents.get(seat)
            if p is None:
                if seat in AUDIT_AUTHORED:
                    continue  # authored at audit time (reference/audit-mode.md), not shipped
                if seat not in h.parked["agents"]:
                    out.append(Finding("tier-table", rel, i,
                                       f"the tier table names `{seat}`, which this harness does "
                                       "not field", "delete the row, or field the seat"))
                continue
            check_seat_tier(h, out, seat, p, want, effort, cells[0], rel, i)
    for seat, p in h.agents.items():
        if seat in rowed:
            continue
        if seat.endswith("-dev") and dev_row:
            check_seat_tier(h, out, seat, p, dev_model, dev_effort, "Implementation", rel, None)
            continue
        out.append(Finding("tier-table", h.rel(p), 1,
                           f"{seat} has no row in model-tiers.md, so nothing decides its model",
                           f"add a row for `{seat}` to the tier table in {rel}"))


def check_seat_tier(h, out, seat, p, want, effort, tier, rel, line) -> None:
    sc = scalars(front(h.text(p)))
    text = h.text(p)
    if sc.get("model") and sc["model"] != want:
        out.append(Finding("tier-table", h.rel(p), find_line(text, "\nmodel:", 0) + 1,
                           f"{seat} runs on {sc['model']} but model-tiers.md "
                           f"({rel}{':' + str(line) if line else ''}) puts it in the {tier} "
                           f"tier ({want})",
                           "change the table first, then the seat - or put the seat back"))
    if effort and sc.get("effort") and sc["effort"] != effort:
        out.append(Finding("tier-table", h.rel(p), find_line(text, "\neffort:", 0) + 1,
                           f"{seat} has effort {sc['effort']} but model-tiers.md says ({effort})",
                           "make the seat's effort: and the table's bracket agree"))


def check_refs(h: Harness, out: list[Finding]) -> None:
    present_md = {p.name for p in walk(h.root) if p.suffix == ".md"}
    present_md |= {f"{s}.md" for k in h.parked.values() for s in k}
    for p in h.prose_files():
        text = h.text(p)
        rel = h.rel(p)
        own = p.stem
        # seats named in backticks: only names the skill ships, so prose is not mistaken for one.
        # Two shapes name an unfielded seat on purpose and are not links: a policy line that
        # enumerates a class of seats (`code-reviewer`, `reviewer`, ...) when at least one of them
        # is fielded, and roster-change advice that names what /harness-update would add.
        lines = text.splitlines()
        for m in re.finditer(r"`([a-z][a-z0-9-]*)`", text):
            name = m.group(1)
            if name in CATALOG_SEATS and name != own and not h.seat_known(name):
                if rel.endswith("model-tiers.md"):
                    continue  # reported row-by-row by tier-table
                line = lines[line_of(text, m.start()) - 1]
                named = [n for n in re.findall(r"`([a-z][a-z0-9-]*)`", line) if n in CATALOG_SEATS]
                enumerates = len(set(named)) >= 2 and any(h.seat_known(n) for n in named)
                if enumerates or "harness-update" in line:
                    continue
                out.append(Finding("agent-ref", rel, line_of(text, m.start()),
                                   f"names seat `{name}`, which this harness does not field",
                                   f"remove or condition the reference, or field `{name}`"))
        for m in re.finditer(r"subagent_type[\"']?\s*[:=]\s*[\"']?([A-Za-z][A-Za-z0-9-]*)", text):
            name = m.group(1)
            if not h.seat_known(name) and name not in ("Explore", "Plan", "general-purpose"):
                out.append(Finding("agent-ref", rel, line_of(text, m.start()),
                                   f"dispatches `{name}`, which is not a seat",
                                   f"create .claude/agents/{name}.md or fix the name"))
        for m in re.finditer(r"(?<![\w/.-])/([a-z][a-z0-9-]*)\b", text):
            name = m.group(1)
            if name in CATALOG_COMMANDS and name not in h.commands \
                    and name not in h.parked["commands"]:
                # `/deploy` inside a path such as `docs/deploy` is excluded by the lookbehind
                out.append(Finding("command-ref", rel, line_of(text, m.start()),
                                   f"tells someone to run /{name}, which is not installed",
                                   f"remove or condition the reference, or install /{name}"))
        # cited markdown files, by basename (the scaffolder's rule, now with a line number)
        seen: set[str] = set()
        for m in re.finditer(r"(?<![\w/.${<-])(?:\.claude/rules/)?([a-z0-9][a-z0-9-]*\.md)\b",
                             text):
            name = m.group(1)
            if name in present_md or name in AUTHORED_LATER or name in seen:
                continue
            seen.add(name)
            out.append(Finding("cite-missing", rel, line_of(text, m.start()),
                               f"cites {name}, which this harness does not contain - an agent "
                               "told to obey a file that is not there obeys nothing",
                               f"install {name}, or remove the citation"))
        # cited harness paths
        for m in re.finditer(r"\.claude/(agents|rules|commands|hooks|scripts|templates)/"
                             r"([A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:md|py|sh|ps1|json))\b", text):
            kind, fname = m.group(1), m.group(2)
            if path_known(h, kind, fname) or fname in AUTHORED_LATER                     or fname in INSTALLED_BY_OTHER:
                continue
            key = f"{kind}/{fname}"
            if key in seen:
                continue
            seen.add(key)
            out.append(Finding("cite-missing", rel, line_of(text, m.start()),
                               f"cites .claude/{kind}/{fname}, which is not installed",
                               f"install it, or fix the path"))
        if p.parent.name == "commands":
            fm = front(text)
            for t in list_value(fm, "allowed-tools"):
                name = tool_name(t)
                if name and name not in KNOWN_TOOLS and not name.startswith("mcp__"):
                    out.append(Finding("unknown-tool", rel,
                                       find_line(text, "allowed-tools:", 1),
                                       f"allowed-tools names `{name}`, which is not a tool",
                                       "fix the spelling or remove it"))


def path_known(h: Harness, kind: str, fname: str) -> bool:
    base = h.claude / kind
    if (base / fname).exists():
        return True
    stem, _, ext = fname.rpartition(".")
    if kind == "hooks" and ext in ("sh", "ps1"):
        if any((base / f"{stem}.{e}").is_file() for e in ("sh", "ps1")):
            return True  # the other flavor of the same hook
    return stem in h.parked.get(kind, set())


def check_routing(h: Harness, out: list[Finding]) -> None:
    agents_md = h.root / "AGENTS.md"
    if not agents_md.is_file():
        return
    text = h.text(agents_md)
    lines = text.splitlines()
    routed: set[str] = set()
    i = 0
    while i < len(lines):
        head = [c.strip().lower() for c in lines[i].strip().strip("|").split("|")]
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) \
                and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            cols = [k for k, c in enumerate(head) if c in ("agent", "seat", "owner", "owning seat",
                                                           "agents", "seats")]
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                for k in cols:
                    if k < len(cells):
                        for name in re.findall(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+|[a-z]{3,}",
                                               cells[k].replace("`", " ")):
                            routed.add(name)
                            if name.endswith("-dev") and not h.seat_known(name):
                                out.append(Finding("agent-ref", "AGENTS.md", j + 1,
                                                   f"routing row sends work to `{name}`, which "
                                                   "is not a seat",
                                                   f"create .claude/agents/{name}.md or fix "
                                                   "the row"))
                j += 1
            i = j
            continue
        i += 1
    for seat, p in h.agents.items():
        if seat not in routed and seat not in text:
            out.append(Finding("routing", "AGENTS.md", None,
                               f"seat {seat} is not in the AGENTS.md routing table - a seat "
                               "outside it is unreachable",
                               f"add a routing row for `{seat}`"))


def check_purpose(h: Harness, out: list[Finding]) -> None:
    seats = set(h.agents) | h.parked["agents"]
    hooks = {p.stem for p in (h.claude / "hooks").glob("*.*")} | h.parked["hooks"]
    code = bool(seats & CODE_MARKERS)
    docs = "writer" in seats or "docs-links" in hooks
    research = "research-sources" in hooks
    strategy = "strategist" in seats
    where = ".claude/agents/"
    if not code:
        for s in sorted((seats & CODE_ONLY_SEATS) | {s for s in seats if s.endswith("-dev")}):
            out.append(Finding("purpose", f"{where}{s}.md", 1,
                               f"{s} works on code, but this harness has no code purpose (no "
                               "review gate, no spec seat) - nothing reviews what it produces",
                               "add purpose_code and re-scaffold, or retire the seat"))
        for hk in sorted(hooks & CODE_ONLY_HOOKS):
            out.append(Finding("purpose", f".claude/hooks/{hk}", None,
                               f"hook {hk} guards code, but this harness has no code purpose",
                               "remove the hook, or add purpose_code"))
    if code:
        gate = ({"code-reviewer", "security-reviewer"} <= seats) or "reviewer" in seats
        if not gate:
            out.append(Finding("purpose", where, None,
                               "a code harness without its review gate: neither the "
                               "code-reviewer + security-reviewer pair nor the merged reviewer",
                               "field the review gate (solo_review picks the merged reviewer)"))
        if "reviewer" in seats and seats & {"code-reviewer", "security-reviewer"}:
            out.append(Finding("purpose", f"{where}reviewer.md", 1,
                               "both the merged reviewer and the split reviewers are fielded - "
                               "two review gates disagree about who signs off",
                               "keep one: reviewer (solo_review) or the split pair"))
    # `long` fields the strategist in a code harness too, so on its own it signals a strategy
    # purpose only where there is no code purpose to explain it.
    noncode = docs or research or (strategy and not code)
    if noncode and "checker" not in seats:
        out.append(Finding("purpose", where, None,
                           "a non-code purpose is fielded (writer, strategist or a research "
                           "hook) but no checker - nothing checks the deliverable",
                           "field the checker seat"))
    if "checker" in seats and not (docs or research or strategy):
        out.append(Finding("purpose", f"{where}checker.md", 1,
                           "checker is fielded but no non-code purpose is - it has nothing to "
                           "check", "retire the checker, or field the purpose it serves"))
    if "docs-links" in hooks and "writer" not in seats:
        out.append(Finding("purpose", ".claude/hooks/docs-links", None,
                           "the docs-links hook is installed but no writer seat owns the docs",
                           "field writer (purpose_docs), or park the hook"))
    if research and "researcher" not in seats:
        out.append(Finding("purpose", ".claude/hooks/research-sources", None,
                           "the research-sources hook is installed but no researcher seat",
                           "field researcher (purpose_research), or park the hook"))


def check_nested(h: Harness, out: list[Finding]) -> None:
    for p in walk(h.root):
        if p.name not in ("CLAUDE.md", "AGENTS.md"):
            continue
        text = h.text(p)
        rel = h.rel(p)
        fence = False
        for i, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("```"):
                fence = not fence
                continue
            if fence:
                continue
            targets = re.findall(r"(?:^|\s)@([A-Za-z0-9_./~-]+\.[A-Za-z0-9]+)", line)
            targets += [t for t in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", line)
                        if not re.match(r"^[a-z]+:", t) and not t.startswith("/")]
            for t in targets:
                if t.startswith("~"):
                    continue
                if not (p.parent / t).exists() and not (h.root / t).exists():
                    out.append(Finding("nested-claude", rel, i,
                                       f"links to {t}, which does not exist",
                                       "fix the path or remove the link"))


# What every scaffold ships, whatever the purpose or flags: a seat, hook or command that cites one
# of these assumes it is there. Directories end in "/".
REQUIRED_PATHS = (
    ".claude/settings.json", ".claude/agents/", ".claude/commands/", ".claude/rules/",
    ".claude/hooks/", ".claude/hooks/README.md", ".claude/scripts/",
    "docs/README.md", "docs/specs/", "docs/requirements/", "docs/architecture/",
    "docs/architecture/decisions/", "docs/context/", "docs/templates/", "docs/tasks/master-plan.md",
    "docs/tasks/active/", "docs/tasks/pending/", "docs/tasks/done/",
)


def check_structure(h: Harness, out: list[Finding]) -> None:
    for rel in REQUIRED_PATHS:
        p = h.root / rel.rstrip("/")
        if p.is_dir() if rel.endswith("/") else p.is_file():
            continue
        out.append(Finding("structure", rel.rstrip("/"), None,
                           f"{rel} is missing - every harness ships it, and the seats, hooks and "
                           f"commands that cite it assume it exists",
                           "restore it with /harness-update (the scaffolder re-adds missing files "
                           "and never overwrites existing ones)"))


# Both root files load into every session, and adherence drops as they grow. Same budget as
# harness-view's COST-06: the pair must stay UNDER this many lines.
INSTRUCTION_MAX_LINES = 200


def check_instruction_length(h: Harness, out: list[Finding]) -> None:
    lines = sum(len(h.text(p).splitlines()) for p in (h.root / "CLAUDE.md", h.root / "AGENTS.md")
                if p.is_file())
    if lines >= INSTRUCTION_MAX_LINES:
        out.append(Finding("instruction-length", "AGENTS.md", 1,
                           f"CLAUDE.md and AGENTS.md together run to {lines} lines "
                           f"(budget: under {INSTRUCTION_MAX_LINES})",
                           "move module guidance into that module's CLAUDE.md and path-specific "
                           "guidance into a rule with `paths:` under .claude/rules/"))


def load_module(path: pathlib.Path):
    """Import a checker script by path. It is registered in sys.modules first: a @dataclass in the
    loaded module looks its own module up there, and fails to load without it."""
    name = "_hc_" + path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:  # a broken checker is itself a finding, reported by the caller
        sys.modules.pop(name, None)
        return None
    return mod


def load_sibling(name: str):
    path = pathlib.Path(__file__).resolve().parent / name
    return load_module(path) if path.is_file() else None


def check_board(h: Harness, out: list[Finding]) -> None:
    for rel in ("docs/tasks/active", "docs/tasks/pending"):
        if not (h.root / rel).is_dir():
            out.append(Finding("board", rel, None,
                               f"{rel}/ is missing, and the shipped board hooks key off it",
                               f"mkdir -p {rel} (with a .gitkeep)"))
    bc = load_sibling("board-check.py")
    if bc is None:
        out.append(Finding("board", ".claude/scripts/board-check.py", None,
                           "board-check.py is missing or does not load, so the board is unchecked",
                           "restore it from the skill (/harness-update)"))
        return
    _n, findings = bc.check(h.root)
    for f in findings:
        file, _, msg = f.partition(": ")
        if not msg:
            file, msg = None, f
        out.append(Finding("board", file, None, msg,
                           "fix it with `python .claude/scripts/task.py move ...` - /board-audit "
                           "explains each"))


def check_skills(h: Harness, out: list[Finding]) -> None:
    sk = h.claude / "skills"
    dirs = sorted(d for d in sk.iterdir() if (d / "SKILL.md").is_file()) if sk.is_dir() else []
    if not dirs:
        return
    mod = load_sibling("skill-check.py")
    if mod is None:
        out.append(Finding("skill-lint", ".claude/scripts/skill-check.py", None,
                           "skill-check.py is missing or does not load, so skills are unlinted",
                           "restore it from the skill (/harness-update)"))
        return
    for d in dirs:
        findings, _warn, _info = mod.check_skill(d, h.root, False, False)
        for code, msg in findings:
            out.append(Finding("skill-lint", h.rel(d / "SKILL.md"), None, f"[{code}] {msg}",
                               "see `python .claude/scripts/skill-check.py --skill "
                               f"{h.rel(d)}`"))


def spec_checker_path(root: pathlib.Path | None = None) -> pathlib.Path | None:
    """spec-check.py, shipped by spec-builder: the project's installed copy first, then the one
    beside this script, then the skill repo's own (where the two skills sit side by side)."""
    here = pathlib.Path(__file__).resolve().parent
    for p in ([root / ".claude" / "scripts" / "spec-check.py"] if root else []) + [
            here / "spec-check.py",
            here.parent.parent.parent / "spec-builder" / "assets" / "scripts" / "spec-check.py"]:
        if p.is_file():
            return p
    return None


def check_specs(h: Harness, out: list[Finding]) -> None:
    """Delegated to spec-check.py once a spec set exists; before that there is nothing to check."""
    path = spec_checker_path(h.root)
    if path is None or not (h.root / "docs" / "specs").is_dir():
        return
    mod = load_module(path)
    if mod is None:
        out.append(Finding("spec", h.rel(path), None,
                           "spec-check.py is installed but does not load, so the spec is unchecked",
                           "restore it from spec-builder"))
        return
    if not mod.spec_files(h.root):
        return
    rep = mod.run(h.root, False, None)
    for code, msg in rep.errors:
        m = re.match(r"^((?:docs|\.claude)/[^\s:]+?)(?::(\d+))?(?::|\s)", msg)
        out.append(Finding("spec", m.group(1) if m else "docs/specs",
                           int(m.group(2)) if m and m.group(2) else None, f"[{code}] {msg}",
                           "fix the spec, then `python .claude/scripts/spec-check.py --write`"))


def walk(root: pathlib.Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS
                       and not (d == "disabled" and pathlib.Path(dirpath).name == ".claude")]
        for f in filenames:
            yield pathlib.Path(dirpath) / f


DETECTORS = (check_hooks, check_seats, check_tiers, check_refs, check_routing, check_purpose,
             check_nested, check_structure, check_instruction_length, check_board, check_skills, check_specs)


def run(root: pathlib.Path, stage: str = "full") -> list[Finding]:
    h = Harness(root.resolve())
    out: list[Finding] = []
    for det in DETECTORS:
        det(h, out)
    skip = STAGE_SKIPS.get(stage, set())
    return [f for f in out if f.check not in skip]


# ------------------------------------------------------------------------------ self-test
FIXTURE = {
    ".claude/settings.json": json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": "bash .claude/hooks/guard.sh"}]}]}}, indent=2),
    ".claude/hooks/guard.sh": "#!/usr/bin/env bash\nexit 0\n",
    ".claude/agents/orchestrator.md": (
        "---\nname: orchestrator\ndescription: d\ntools: Read, Agent(app-dev, code-reviewer)\n"
        "model: opus\neffort: high\nmaxTurns: 60\n---\nDispatch `app-dev`, then `code-reviewer`. "
        "Follow agent-guardrails.md and run /review-changes.\n"),
    ".claude/agents/app-dev.md": (
        "---\nname: app-dev\ndescription: d\ntools: Read, Write, Edit\nmodel: sonnet\n"
        "effort: medium\nmaxTurns: 40\n---\nBuild it.\n"),
    ".claude/agents/code-reviewer.md": (
        "---\nname: code-reviewer\ndescription: d\ntools: Read, Grep\n"
        "disallowedTools: Edit, Write\nmodel: opus\neffort: high\nmaxTurns: 25\n---\nReview.\n"),
    ".claude/agents/security-reviewer.md": (
        "---\nname: security-reviewer\ndescription: d\ntools: Read, Grep\nmodel: opus\n"
        "effort: high\nmaxTurns: 25\n---\nReview.\n"),
    # Sound variants that must stay silent: a class enumeration naming an unfielded `reviewer`
    # beside fielded ones, and roster advice naming what /harness-update would add.
    ".claude/rules/agent-guardrails.md": (
        "# Guardrails\nSee `.claude/scripts/board-check.py`.\n"
        "Review seats `code-reviewer`, `security-reviewer`, `reviewer` stay read-only.\n"
        "To add tests, field `qa-test` via `/harness-update`.\n"),
    ".claude/rules/model-tiers.md": (
        "| Seat tier | The work | Seat (`effort:`) | Model |\n|---|---|---|---|\n"
        "| Judgment | Dispatch | `orchestrator` (high) | `opus` |\n"
        "| Judgment | Review | `code-reviewer` (high) | `opus` |\n"
        "| Judgment | Security | `security-reviewer` (high) | `opus` |\n"
        "| Implementation | Code | `<domain>-dev` (medium) | `sonnet` |\n"),
    ".claude/commands/review-changes.md": (
        "---\ndescription: d\nallowed-tools: Read, Grep, Bash(git diff:*)\n---\n"
        "Dispatch `code-reviewer` and `security-reviewer`.\n"),
    ".claude/commands/harness-update.md": "---\ndescription: d\nallowed-tools: Read\n---\nx\n",
    ".claude/scripts/board-check.py": "# stand-in\n",
    "AGENTS.md": (
        "# Contract\n\n| Work | Agent |\n|---|---|\n| plan | `orchestrator` |\n| code | `app-dev` |\n"
        "| review | `code-reviewer`, `security-reviewer` |\n"),
    "CLAUDE.md": "@AGENTS.md\n\nSee [the contract](AGENTS.md).\n",
    "docs/tasks/active/.gitkeep": "",
    "docs/tasks/pending/.gitkeep": "",
    "docs/tasks/master-plan.md": "| Task | Title | Status |\n|---|---|---|\n",
    "docs/tasks/done/.gitkeep": "",
    "docs/README.md": "# Docs\n",
    "docs/specs/.gitkeep": "",
    "docs/requirements/.gitkeep": "",
    "docs/architecture/decisions/.gitkeep": "",
    "docs/context/.gitkeep": "",
    "docs/templates/.gitkeep": "",
    ".claude/hooks/README.md": "# Hooks\n",
}

# (detector id, files to write; None deletes)
MUTANTS: tuple[tuple[str, dict[str, str | None]], ...] = (
    ("settings-json", {".claude/settings.json": "{ not json"}),
    ("hook-missing", {".claude/hooks/guard.sh": None,
                      ".claude/hooks/other.sh": "#!/bin/sh\n"}),
    ("hook-unregistered", {".claude/hooks/stray.sh": "#!/bin/sh\n"}),
    ("seat-frontmatter", {".claude/agents/app-dev.md": (
        "---\nname: app-dev\ndescription: d\ntools: Read, Agent\nmodel: sonnet\neffort: medium\n"
        "maxTurns: 40\n---\n")}),
    ("review-readonly", {".claude/agents/code-reviewer.md": (
        "---\nname: code-reviewer\ndescription: d\ntools: Read, Grep, Edit\nmodel: opus\n"
        "effort: high\nmaxTurns: 25\n---\n")}),
    ("tier-table", {".claude/agents/code-reviewer.md": (
        "---\nname: code-reviewer\ndescription: d\ntools: Read, Grep\nmodel: sonnet\n"
        "effort: high\nmaxTurns: 25\n---\n")}),
    ("agent-ref", {".claude/commands/review-changes.md": (
        "---\ndescription: d\nallowed-tools: Read\n---\nDispatch `qa-test`.\n")}),
    ("routing", {"AGENTS.md": "# Contract\n\n| Work | Agent |\n|---|---|\n| plan | `orchestrator` |\n"
                              "| code | `app-dev` |\n| review | `code-reviewer` |\n"}),
    ("command-ref", {".claude/rules/agent-guardrails.md": "# G\nRun /db-migration first.\n"}),
    ("cite-missing", {".claude/rules/agent-guardrails.md": "# G\nObey task-control.md.\n"}),
    ("skill-missing", {".claude/agents/app-dev.md": (
        "---\nname: app-dev\ndescription: d\ntools: Read\nmodel: sonnet\neffort: medium\n"
        "maxTurns: 40\nskills:\n  - ghost-skill\n---\n")}),
    ("unknown-tool", {".claude/commands/review-changes.md": (
        "---\ndescription: d\nallowed-tools: Read, Frobnicate\n---\nx\n")}),
    ("purpose", {".claude/agents/security-reviewer.md": None}),
    ("nested-claude", {"pkg/CLAUDE.md": "@missing-notes.md\n"}),
    ("structure", {"docs/architecture": None}),
    ("instruction-length", {"CLAUDE.md": "@AGENTS.md\n" + "line\n" * 192}),
    ("board", {"docs/tasks/pending": None}),
)
# Mutants that need a working sibling script: the real board-check / skill-check.
SIBLING_MUTANTS = (
    ("board", "board-check.py", {"docs/tasks/active/TASK-001-x.md":
                                 "---\nstatus: Sideways\n---\n# TASK-001\n"}),
    ("skill-lint", "skill-check.py", {".claude/skills/thing/SKILL.md": "no frontmatter\n"}),
    ("spec", "spec-check.py", {"docs/specs/05-functional-requirements.md": "# FR\n"}),
)


def _build(root: pathlib.Path, files: dict[str, str | None]) -> None:
    for rel, body in files.items():
        p = root / rel
        if body is None:
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8", newline="\n")
        if p.suffix == ".sh":
            p.chmod(0o755)


def self_test() -> list[str]:
    dead: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        clean = base / "clean"
        _build(clean, FIXTURE)
        noise = [f"{f.check} {f.where()} {f.message}" for f in run(clean)]
        if noise:
            dead.append(f"the clean fixture is not clean: {noise}")
        cases = list(MUTANTS)
        here = pathlib.Path(__file__).resolve().parent
        for check, sibling, files in SIBLING_MUTANTS:
            if (here / sibling).is_file() or (sibling == "spec-check.py" and spec_checker_path()):
                cases.append((check, files))
        if os.name == "posix":
            cases.append(("hook-not-exec", {}))
        for n, (check, files) in enumerate(cases):
            d = base / f"m{n}"
            _build(d, FIXTURE)
            _build(d, files)
            if check == "hook-not-exec":
                (d / ".claude/hooks/guard.sh").chmod(0o644)
            got = {f.check for f in run(d)}
            if check not in got:
                dead.append(f"detector `{check}` did not fire on its mutant (got {sorted(got)})")
            if not all(f.file is None or f.line is None or f.line > 0 for f in run(d)):
                dead.append(f"mutant for `{check}` produced a finding with a bad line number")
        # One line under the budget must stay silent: a detector that fires on any long file
        # would pass its mutant and still be wrong.
        d = base / "under-budget"
        _build(d, FIXTURE)
        _build(d, {"CLAUDE.md": "@AGENTS.md\n" + "line\n" * 191})
        if any(f.check == "instruction-length" for f in run(d)):
            dead.append("`instruction-length` fired on a pair one line under the budget")
        # The scaffold stage must drop the routing check and nothing else.
        d = base / f"m{len(cases)}"
        _build(d, FIXTURE)
        _build(d, dict(MUTANTS)["routing"])
        if any(f.check == "routing" for f in run(d, "scaffold")):
            dead.append("--stage scaffold still reports routing")
    return dead


# ----------------------------------------------------------------------------------- main
def report(root: pathlib.Path, findings: list[Finding], stage: str) -> str:
    lines = [f"harness-check: {root}  (stage {stage})"]
    skip = STAGE_SKIPS.get(stage, set())
    for cid, title in CHECKS.items():
        if cid in skip:
            continue
        mine = [f for f in findings if f.check == cid]
        lines.append(f"  {'FAIL' if mine else 'pass'}  {cid:<18} {title}"
                     + (f" ({len(mine)})" if mine else ""))
        for f in mine:
            lines.append(f"        {f.where()}  {f.message}")
            lines.append(f"            fix: {f.fix}")
    lines.append(f"harness-check: {len(findings)} finding(s)" if findings
                 else "harness-check: clean - every link resolves")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=pathlib.Path, default=pathlib.Path("."))
    ap.add_argument("--json", action="store_true", help="machine-readable output for harness-view")
    ap.add_argument("--stage", choices=sorted(STAGE_SKIPS), default="full",
                    help="scaffold: skip what is authored after the scaffolder runs")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        dead = self_test()
        for d in dead:
            print(f"harness-check self-test: DEAD - {d}")
        print("harness-check self-test: " + ("FAILED" if dead else "ok"))
        return 3 if dead else 0
    root = args.target.resolve()
    findings = run(root, args.stage)
    findings.sort(key=lambda f: (list(CHECKS).index(f.check), f.file or "", f.line or 0))
    if args.json:
        skip = STAGE_SKIPS.get(args.stage, set())
        print(json.dumps({
            "version": 1, "tool": "harness-check", "root": root.as_posix(), "stage": args.stage,
            "ok": not findings,
            "checks": [{"id": c, "title": t,
                        "status": "fail" if any(f.check == c for f in findings) else "pass",
                        "findings": sum(f.check == c for f in findings)}
                       for c, t in CHECKS.items() if c not in skip],
            "findings": [f.to_json() for f in findings],
        }, indent=2, sort_keys=True))
    else:
        print(report(root, findings, args.stage))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
