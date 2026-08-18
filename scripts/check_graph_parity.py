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

Cargo is a soft dependency: without it the check SKIPS loudly and exits 0, the same contract
`check_js.py` uses for node. A silent skip would be worse than no check.

    python scripts/check_graph_parity.py

Exit 0 = identical (or cargo unavailable), 1 = the two scanners disagree.
"""
from __future__ import annotations

import difflib
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tools/harness-view/tests/fixture"
SCANNER = ROOT / "harness-bootstrap/assets/scripts/harness-graph.py"
OUT = FIXTURE / ".claude/state/harness-graph.json"


def run_python() -> bytes:
    OUT.unlink(missing_ok=True)
    r = subprocess.run([sys.executable, str(SCANNER)], cwd=str(FIXTURE),
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("  FAIL  the Python scanner exited non-zero:")
        print("        " + (r.stderr or r.stdout).strip().replace("\n", "\n        ")[:800])
        raise SystemExit(1)
    return OUT.read_bytes()


def run_rust() -> bytes | None:
    OUT.unlink(missing_ok=True)
    r = subprocess.run(["cargo", "run", "--quiet", "--release", "--", "scan", str(FIXTURE)],
                       cwd=str(ROOT / "tools/harness-view"), capture_output=True, text=True)
    if r.returncode != 0:
        print("  FAIL  harness-view scan exited non-zero:")
        print("        " + (r.stderr or r.stdout).strip().replace("\n", "\n        ")[:800])
        return None
    return OUT.read_bytes()


def main() -> int:
    if not FIXTURE.is_dir():
        print(f"  FAIL  no fixture at {FIXTURE.relative_to(ROOT)}")
        return 1
    if shutil.which("cargo") is None:
        print("SKIP: cargo is not on PATH, so the two scanners were NOT compared.")
        print("      Install Rust to enable this gate (CI runners have it by default).")
        return 0

    py = run_python()
    rs = run_rust()
    if rs is None:
        return 1

    if py == rs:
        print(f"  ok    both scanners wrote the same {len(py):,} bytes on the fixture")
        return 0

    print(f"  FAIL  the scanners disagree: python {len(py):,} bytes, rust {len(rs):,} bytes")
    diff = difflib.unified_diff(
        py.decode("utf-8", "replace").splitlines(),
        rs.decode("utf-8", "replace").splitlines(),
        "harness-graph.py", "harness-view scan", lineterm="", n=1)
    for i, line in enumerate(diff):
        print("        " + line)
        if i > 40:
            print("        ... truncated")
            break
    return 1


if __name__ == "__main__":
    sys.exit(main())
