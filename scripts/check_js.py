#!/usr/bin/env python3
"""Syntax-check the JavaScript this repo embeds in self-contained HTML pages.

Both viewers ship as one file with an inline <script> block: the Rust tool's
`tools/harness-view/src/ui.html`, and the page `graph-html.py` writes. Nothing
executes that JavaScript in CI, so a syntax error ships silently and the only
symptom is a blank canvas - which is exactly what happened when a string
literal in ui.html was broken across real newlines. The whole script died, the
page rendered its chrome, and the graph never appeared.

This runs `node --check` over every embedded block. Node is a soft dependency:
when it is missing the check SKIPS loudly and exits 0, because a missing
optional tool must not fail a build - but a silent skip would be worse than no
check at all, so the skip is printed.

    python scripts/check_js.py

Exit 0 = every block parses (or node is unavailable), 1 = a block is broken.
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Files that carry inline <script> blocks. A Python file is included because
# graph-html.py holds the page as a string template; the same regex finds the
# block either way, which keeps this script from needing to know Python syntax.
SOURCES = [
    "tools/harness-view/src/ui.html",
    "harness-bootstrap/assets/scripts/graph-html.py",
    # The deck is the largest JavaScript blob in the repo and the file most often
    # edited by figure propagation, which reaches into object literals by hand.
    # A broken quote there would ship silently: nothing else parses this file.
    "presentation/index.html",
]

# Every clip carries its own inline timeline. These are globbed rather than listed,
# because a hand-maintained list only covers the files someone remembered to add:
# clip 07 was written, shipped, and checked green while its JavaScript was never
# parsed at all. A glob cannot forget a new clip.
SOURCE_GLOBS = [
    "video/html/*.html",
    "video/html/ja/*.html",
]

# CodeQL flags this as py/bad-tag-filter, and it is right that a regex cannot parse
# HTML in general. It is not doing that job here: the input is this repository's own
# files, and the output decides which text to hand to `node --check`. A miss means a
# block goes unchecked, which is a weaker linter, not a way in - there is no
# untrusted input and nothing is being sanitised.
#
# The closing tag still tolerates whitespace, because `</script >` is legal HTML and
# would silently truncate a block, and a truncated block reports a syntax error that
# is not in the source.
SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script\s*>", re.S | re.I)


def blocks(path: pathlib.Path) -> list[tuple[int, str]]:
    """-> [(1-based line where the block starts, javascript)]."""
    text = path.read_text(encoding="utf-8", errors="replace")
    out = []
    for m in SCRIPT_RE.finditer(text):
        body = m.group(1)
        if not body.strip():
            continue
        out.append((text[: m.start(1)].count("\n") + 1, body))
    return out


def main() -> int:
    node = shutil.which("node")
    if node is None:
        print("SKIP: node is not on PATH, so the embedded JavaScript was NOT syntax-checked.")
        print("      Install Node to enable this gate (CI runners have it by default).")
        return 0

    problems = 0
    checked = 0
    targets = list(SOURCES)
    for pattern in SOURCE_GLOBS:
        targets.extend(sorted(p.relative_to(ROOT).as_posix()
                              for p in ROOT.glob(pattern)))
    for rel in targets:
        path = ROOT / rel
        if not path.is_file():
            print(f"  [warn] {rel} is missing - skipped")
            continue
        found = blocks(path)
        if not found:
            print(f"  [warn] {rel} has no <script> block - skipped")
            continue
        for line, js in found:
            checked += 1
            # A template still carrying {{PLACEHOLDER}} or a Python %-format slot
            # is not valid JS on its own; those are substituted before the page
            # is written, so check what will actually run by blanking them.
            js_checked = re.sub(r"\{\{[A-Z0-9_]+\}\}", "null", js)
            with tempfile.NamedTemporaryFile(
                "w", suffix=".js", delete=False, encoding="utf-8"
            ) as fh:
                fh.write(js_checked)
                tmp = fh.name
            try:
                pr = subprocess.run(
                    [node, "--check", tmp], capture_output=True, text=True, encoding="utf-8"
                )
            finally:
                pathlib.Path(tmp).unlink(missing_ok=True)
            if pr.returncode == 0:
                print(f"  ok    {rel}: <script> at line {line} parses")
            else:
                problems += 1
                detail = (pr.stderr or pr.stdout or "").strip().splitlines()
                # node reports temp-file line numbers; offset them back to the source
                msg = "\n        ".join(d for d in detail[:6])
                print(f"  FAIL  {rel}: <script> starting at line {line} does not parse")
                print(f"        (line N below is N + {line - 1} in {rel})")
                print(f"        {msg}")

    if problems:
        print(f"\n  {problems} of {checked} embedded script block(s) failed to parse.")
        return 1
    print(f"\n  {checked} embedded script block(s) parse cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
