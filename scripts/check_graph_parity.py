#!/usr/bin/env python3
"""Assert the two graph scanners produce byte-identical output.

`tools/harness-view/SCHEMA.md` states that `.claude/state/harness-graph.json` is written by
BOTH the skill's `harness-graph.py` and `harness-view scan`, byte for byte, so a repo can use
either and the viewer and CI cannot disagree about what the harness contains.

Nothing checked it. The claim was kept by prose comments in `scan.rs` ("like harness-graph.py")
and by whoever remembered to update both sides. It had drifted three ways at once:

  1. `code-graph.json` storing `files` as a COUNT crashed the Python scanner outright
     ("object of type 'int' has no len()") while the Rust one scanned happily.
  2. An edge written as a `[from, to]` PAIR was skipped by Python and emitted by Rust, so the
     Python graph was missing edges that harness-view showed.
  3. An agent frontmatter `tools:` written as a YAML BLOCK LIST came out of Python as the
     single item "- Read", dash included, against Rust's full list.

Each was silent. Two scanners that disagree are worse than one, so this is now a gate.

It compares on more than one tree, because a single fixture only proves parity for the
features that fixture uses. The original `tests/fixture` used none of the subagent fields,
seat-registered hooks, the task board or the spawn allowlist, so harness-view learned all of
them while this gate stayed green and every real repo diverged. The trees now are:

  - tools/harness-view/tests/fixture       the original, small harness
  - tools/harness-view/tests/kit-fixture   an orchestrator-kit repo: every subagent field,
                                           frontmatter hooks, Agent(a, b), the task board
  - an edge-case tree written by this gate the inputs neither of those reaches (EDGE_TREE)
  - a fresh scaffold, sh and ps1 flavors   what harness-bootstrap actually ships today

Each tree is copied to a temp directory before scanning, so the fixtures are never written to.

Cargo is a soft dependency: without it the check SKIPS loudly and exits 0, the same contract
`check_js.py` uses for node. A silent skip would be worse than no check.

    python scripts/check_graph_parity.py

Exit 0 = identical everywhere (or cargo unavailable), 1 = the two scanners disagree somewhere.
"""
from __future__ import annotations

import difflib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools/harness-view"
FIXTURES = (TOOL / "tests/fixture", TOOL / "tests/kit-fixture")
SCANNER = ROOT / "harness-bootstrap/assets/scripts/harness-graph.py"
SCAFFOLD = ROOT / "harness-bootstrap/scripts/scaffold.py"
# The eval's scaffold baseline: one known-good vars set, so this gate does not keep a second
# copy that falls behind when scaffold.py starts requiring a new variable.
EVAL = ROOT / "eval/guardrail_eval.py"
OUT = pathlib.Path(".claude/state/harness-graph.json")

# A tree written by this gate for the cases neither fixture nor a scaffold reaches: a BOM and
# CRLF frontmatter, folded and literal block scalars, `Agent(a, "b")` beside other tools, a
# frontmatter hook with a stray `hooks/` argument and a prompt hook, a README among the agents,
# an empty `paths:`, a script referenced with backslashes, a sourced library hook, a hook
# registered on PermissionRequest with an empty matcher, an inline settings hook, a code graph
# with a junk module and duplicate edges, a board whose folder, status and TASKS.md disagree,
# an index row with no file, a doubled `.md.md`, a translated tier table, and a `checker`
# seat. Every one of these once differed between the two scanners, or could.
EDGE_TREE: dict[str, bytes] = {
    ".claude/agents/lead.md": (
        b"\xef\xbb\xbf---\r\nname: lead\r\ndescription: >\r\n  folded text\r\n"
        b"model: sonnet # pick\r\nmaxTurns: +5\r\ntools: [Agent(writer, \"Plan\"), Read]\r\n"
        b"skills:\r\n  - pdf\r\nbackground: maybe\r\nmcpServers:\r\n  - drive\r\n  - local:\r\n"
        b"      command: x\r\ninitialPrompt: |\r\n  line one\r\n  line two\r\nhooks:\r\n"
        b"  PreToolUse:\r\n    - matcher: \"Bash\"\r\n      hooks:\r\n        - type: command\r\n"
        b"          command: bash .claude/hooks/guard.sh .claude/hooks/data\r\n  Stop:\r\n"
        b"    - hooks:\r\n        - type: prompt\r\n          prompt: \"check it\"\r\n---\r\n"
        b"Skills available: pdf, nothing.\r\n"),
    ".claude/agents/qa-checker.md": b"---\ntools: Agent\n---\nI am the qa-checker\n",
    ".claude/agents/checker.md": b"---\nmodel: opus\ntools:\n  - Read\n  - Grep\n---\n",
    ".claude/agents/writer.md": b"---\nmodel: haiku\n---\n",
    ".claude/agents/README.md": b"readme\n",
    ".claude/rules/empty-paths.md": b"---\npaths:\n---\nrule\n",
    ".claude/rules/scoped.md": b"---\npaths: [\"src/**\", 'b/*']\ndescription: \"quoted\"\n---\n",
    ".claude/commands/go.md": (b"run .claude/scripts/foo.py and .claude\\scripts\\bar.py "
                               b"and .claude/scripts/\n"),
    ".claude/hooks/guard.sh": b"#!/bin/sh\n. \"$(dirname \"$0\")/lib.sh\"\ncat spawn-allowlist\n",
    ".claude/hooks/lib.sh": b"#!/bin/sh\n",
    ".claude/disabled/hooks/old.ps1": b"x\n",
    ".claude/hooks/spawn-allowlist": b"Explore # built-in\n\nPlan\n",
    ".claude/scripts/foo.py": b"print(1)\n",
    ".claude/scripts/foo.sh": b"x",
    ".claude/skills/pdf/SKILL.md": b"---\ndescription: pdf skill\n---\n",
    ".claude/settings.json": (
        b'{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"echo hi"}]}],'
        b'"PermissionRequest":[{"matcher":"","hooks":[{"command":"bash .claude/hooks/guard.sh"}]}]},'
        b'"env":{"TASK_BOARD_DIR":".agent-base/tasks"}}'),
    ".claude/state/code-graph.json": (
        b'{"modules":{"src/app":{"files":3,"owner":""},"lib":"junk",'
        b'"src/x":{"files":[1,2],"owner":"writer"}},"edges":[["src/app","src/x"],'
        b'{"from":"src/x","to":"src/app","refs":0},{"from":"src/x","to":"src/app","refs":4}]}'),
    ".agent-base/tasks/active/TASK-002-x.md": (b"---\nagent: writer+lead\nstatus: active\n"
                                              b"depends_on: -\nmission: \"m\"\n---\nsrc/app\n"),
    ".agent-base/tasks/pending/TASK-003.md": b"---\nstatus: active # nope\n---\n",
    ".agent-base/tasks/TASKS.md": (
        b"| ID | task | agent | state | deps | mission |\n|---|---|---|---|---|---|\n"
        b"| TASK-002 | x | writer | pending | - | m |\n"
        b"| TASK-009 | ghost | qa-checker | pending | - | - |\n"),
    "docs/tasks/sub/TASK-1.md.md": b"---\ntitle: \" spaced \"\nowner: lead\n---\n",
    "AGENTS.md": (
        "# Contract\r\n\r\n| 区分 | 変更の内容 | 誰が行うか |\r\n|---|---|---|\r\n"
        "| Direct | typo | owning agent |\r\n| **Standard** | feature | writer |\r\n"
        "| Guarded | release | lead, checker |\r\n\r\n"
        "See .claude/rules/scoped.md and `lead`.\r\n").encode("utf-8"),
    "CLAUDE.md": b"@AGENTS.md\n",
}


def write_edge_tree(dest: pathlib.Path) -> pathlib.Path:
    for rel, data in EDGE_TREE.items():
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return dest


def run_python(tree: pathlib.Path) -> bytes | None:
    (tree / OUT).unlink(missing_ok=True)
    r = subprocess.run([sys.executable, str(SCANNER), "--target", str(tree), "--quiet"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("  FAIL  the Python scanner exited non-zero:")
        print("        " + (r.stderr or r.stdout).strip().replace("\n", "\n        ")[:800])
        return None
    return (tree / OUT).read_bytes()


def run_rust(tree: pathlib.Path) -> bytes | None:
    (tree / OUT).unlink(missing_ok=True)
    r = subprocess.run(["cargo", "run", "--quiet", "--release", "--", "scan", str(tree)],
                       cwd=str(TOOL), capture_output=True, text=True)
    if r.returncode != 0:
        print("  FAIL  harness-view scan exited non-zero:")
        print("        " + (r.stderr or r.stdout).strip().replace("\n", "\n        ")[:800])
        return None
    return (tree / OUT).read_bytes()


def compare(label: str, py: bytes, rs: bytes) -> bool:
    """True when the two outputs are the same bytes; prints the diff when they are not."""
    if py == rs:
        print(f"  ok    {label}: both scanners wrote the same {len(py):,} bytes")
        return True
    print(f"  FAIL  {label}: the scanners disagree: python {len(py):,} bytes, rust {len(rs):,} bytes")
    diff = difflib.unified_diff(
        py.decode("utf-8", "replace").splitlines(),
        rs.decode("utf-8", "replace").splitlines(),
        "harness-graph.py", "harness-view scan", lineterm="", n=1)
    for i, line in enumerate(diff):
        print("        " + line)
        if i > 40:
            print("        ... truncated")
            break
    return False


def self_test() -> bool:
    """The comparison must be able to fail. A gate that cannot go red proves nothing."""
    a = b'{"version": 1}\n'
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        same, differ = compare("self-test", a, a), compare("self-test", a, a.replace(b"1", b"2"))
    if same and not differ:
        return True
    print("  FAIL  self-test: compare() does not tell equal bytes from different ones")
    return False


def scaffold(work: pathlib.Path, flavor: str) -> pathlib.Path | None:
    """A fresh harness from today's assets, or None (printed) when scaffolding failed."""
    try:
        spec = importlib.util.spec_from_file_location("guardrail_eval", EVAL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        v = mod.base_vars(flavor)
    except Exception as e:   # noqa: BLE001 - any failure here is reported, never swallowed
        print(f"  FAIL  could not load the scaffold vars from {EVAL.relative_to(ROOT)}: {e}")
        return None
    vf = work / f"vars-{flavor}.json"
    vf.write_text(json.dumps(v), encoding="utf-8")
    target = work / f"scaffold-{flavor}"
    r = subprocess.run([sys.executable, str(SCAFFOLD), "--target", str(target), "--vars", str(vf)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not (target / ".claude").is_dir():
        print(f"  FAIL  scaffold.py ({flavor}) exited {r.returncode}:")
        print("        " + (r.stderr or r.stdout).strip().replace("\n", "\n        ")[-800:])
        return None
    return target


def main() -> int:
    if not self_test():
        return 1
    missing = [f for f in FIXTURES if not f.is_dir()]
    if missing:
        for f in missing:
            print(f"  FAIL  no fixture at {f.relative_to(ROOT)}")
        return 1
    if shutil.which("cargo") is None:
        print("SKIP: cargo is not on PATH, so the two scanners were NOT compared.")
        print("      Install Rust to enable this gate (CI runners have it by default).")
        return 0

    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        trees: list[tuple[str, pathlib.Path | None]] = []
        for f in FIXTURES:
            dest = work / f.name
            shutil.copytree(f, dest, ignore=shutil.ignore_patterns("harness-graph.json"))
            trees.append((str(f.relative_to(ROOT).as_posix()), dest))
        trees.append(("edge cases (generated)", write_edge_tree(work / "edge-cases")))
        for flavor in ("sh", "ps1"):
            trees.append((f"fresh scaffold ({flavor})", scaffold(work, flavor)))
        for label, tree in trees:
            if tree is None:
                ok = False
                continue
            py = run_python(tree)
            rs = run_rust(tree)
            if py is None or rs is None or not compare(label, py, rs):
                ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
