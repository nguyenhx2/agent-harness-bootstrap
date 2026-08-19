#!/usr/bin/env python3
"""Syntax-check the JavaScript this repo ships inside self-contained HTML pages.

Most of it is inline: the page `graph-html.py` writes, the deck, and every
explainer clip carry their JavaScript in a <script> block. Nothing executes that
JavaScript in CI, so a syntax error ships silently and the only symptom is a
blank canvas - which is exactly what happened when a string literal in ui.html
was broken across real newlines. The whole script died, the page rendered its
chrome, and the graph never appeared.

The viewer's UI is the exception, and the reason this script has two lists. Its
script moved out of `tools/harness-view/src/ui.html` into a real
`tools/harness-view/src/ui.js` (spliced back in by serve.rs) so that GitHub
detects JavaScript and CodeQL analyses the one page that renders scanned
repository text into the DOM. ui.html still has <script> tags after that move,
but they hold only the `/*__VENDOR__*/` and `/*__UI_JS__*/ ` placeholders: a
comment, which parses cleanly forever. Leaving ui.html in SOURCES alone would
therefore have kept printing "ok" while checking nothing - the exact failure
this script exists to prevent - so ui.js is checked by path in JS_SOURCES, and
those entries are REQUIRED: a missing or shrunken one fails the run instead of
warning past it.

This runs `node --check` over every block and every listed file. Node is a soft
dependency: when it is missing the check SKIPS loudly and exits 0, because a
missing optional tool must not fail a build - but a silent skip would be worse
than no check at all, so the skip is printed.

    python scripts/check_js.py

Exit 0 = everything parses (or node is unavailable), 1 = something is broken or
a required file went missing.
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

# Standalone .js files, checked by path. Each carries a minimum byte count,
# because `node --check` is perfectly happy with an empty file: truncating
# ui.js to nothing would delete the entire viewer UI and still report "ok".
# The floor is the only thing that distinguishes "this parses" from "there is
# nothing left to parse". Raise it only when the file genuinely grows past it;
# never lower it to make a build go green.
#
# Unlike the globs, these are REQUIRED. A path that no longer exists is a
# failure, not a warning: this list is short and hand-written, so a miss means
# either the file moved (and this list must follow) or it was deleted (and the
# page it belonged to is broken).
JS_SOURCES = [
    ("tools/harness-view/src/ui.js", 50_000),
    ("tools/harness-view/src/ui-steps.js", 3_000),
    # The landing page's only script (nav disclosure + progressive touches). Small on
    # purpose; the floor says "the menu logic still exists", not "the file is big".
    ("site/src/main.js", 400),
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


def parses(node: str, js: str) -> tuple[bool, str]:
    """-> (does node accept this as a script, node's complaint if not)."""
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
        return True, ""
    detail = (pr.stderr or pr.stdout or "").strip().splitlines()
    return False, "\n        ".join(d for d in detail[:6])


def main() -> int:
    node = shutil.which("node")
    if node is None:
        print("SKIP: node is not on PATH, so the embedded JavaScript was NOT syntax-checked.")
        print("      Install Node to enable this gate (CI runners have it by default).")
        return 0

    problems = 0
    checked = 0

    # Standalone files first: these are the required ones, and a report that
    # starts with them makes it obvious at a glance whether ui.js was covered.
    for rel, floor in JS_SOURCES:
        path = ROOT / rel
        if not path.is_file():
            problems += 1
            print(f"  FAIL  {rel} is missing - it is a required file, not an optional one")
            continue
        js = path.read_text(encoding="utf-8", errors="replace")
        size = len(js.encode("utf-8"))
        checked += 1
        if size < floor:
            problems += 1
            print(f"  FAIL  {rel} is {size} bytes, below its {floor}-byte floor - "
                  f"it has been truncated or emptied")
            continue
        ok, msg = parses(node, js)
        if ok:
            print(f"  ok    {rel} parses ({size} bytes)")
        else:
            problems += 1
            print(f"  FAIL  {rel} does not parse")
            print(f"        {msg}")

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
            ok, msg = parses(node, js)
            if ok:
                print(f"  ok    {rel}: <script> at line {line} parses")
            else:
                problems += 1
                # node reports temp-file line numbers; offset them back to the source
                print(f"  FAIL  {rel}: <script> starting at line {line} does not parse")
                print(f"        (line N below is N + {line - 1} in {rel})")
                print(f"        {msg}")

    if problems:
        print(f"\n  {problems} of {checked} script(s) failed to parse.")
        return 1
    print(f"\n  {checked} script(s) parse cleanly "
          f"({len(JS_SOURCES)} standalone file(s), {checked - len(JS_SOURCES)} embedded block(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
