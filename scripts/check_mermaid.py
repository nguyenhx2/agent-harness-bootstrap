#!/usr/bin/env python3
"""Render every mermaid block in the repo and fail on any that does not draw.

GitHub renders mermaid server-side and shows "Unable to render rich display" when a block does not
parse. That message says nothing about which line is wrong, so the only way to find out is to render
the block yourself. This does that, with the same engine GitHub uses.

Needs node (it shells out to `npx @mermaid-js/mermaid-cli`).

    python scripts/check_mermaid.py          # check every .md
    python scripts/check_mermaid.py README.md docs/FLOWS.md
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent


def find_blocks(text: str) -> list[tuple[str, bool]]:
    """Return (source, closing_on_own_line) for every ```mermaid block.

    A closing fence must sit on a line by itself (CommonMark). mermaid-cli does not care - it splits
    on the ``` wherever it is - but GitHub does: a fence glued to the last content line
    (`    class A art` + ```` ``` ````) never closes the block, so GitHub pulls the following prose
    into the diagram and fails to parse it. That exact bug shipped once and rendered fine locally.
    """
    lines = text.splitlines()
    blocks: list[tuple[str, bool]] = []
    i = 0
    while i < len(lines):
        if lines[i].rstrip() == "```mermaid":
            body: list[str] = []
            j, closing_ok = i + 1, False
            while j < len(lines):
                line = lines[j]
                if re.match(r"^\s*```\s*$", line):          # proper closing fence, own line
                    closing_ok = True
                    break
                if line.rstrip().endswith("```"):           # fence glued to content
                    body.append(line.rstrip()[:-3])
                    closing_ok = False
                    break
                body.append(line)
                j += 1
            blocks.append(("\n".join(body), closing_ok))
            i = j + 1
        else:
            i += 1
    return blocks


# A label containing a tag-shaped token - "<name>", "<slug>", "<T>" - is parsed as HTML by the
# renderer. mermaid-cli silently EATS it: the diagram still renders, the text is just gone. GitHub's
# sanitiser is stricter and fails the whole block with "Unable to render rich display", naming
# neither the file nor the line. So this is checked before rendering, because rendering will not
# catch it. <br/> is the one tag a label may legitimately carry.
# The lookahead requires a letter or a slash right after the "<", so mermaid's own bidirectional
# arrows (<-->, <==>, <-.->) are not mistaken for tags.
TAGLIKE = re.compile(r"<(?!br\s*/?>)(?=[A-Za-z/])[^<>\n]{1,30}>")


def lint(src: str) -> list[str]:
    problems = []
    for n, line in enumerate(src.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(("%%", "classDef", "class ", "style ")):
            continue
        for m in TAGLIKE.finditer(line):
            problems.append(f"line {n}: '{m.group(0)}' is parsed as an HTML tag and the text is "
                            f"dropped. Rewrite the label without angle brackets.")
        # ';' ends a statement in mermaid, so one inside a message truncates the line.
        if ";" in stripped and not stripped.startswith(("classDef", "class ", "style ")):
            if re.match(r"\s*(Note (over|right of|left of)|[\w-]+\s*-?-?>>?)", line):
                problems.append(f"line {n}: ';' ends a mermaid statement. Use a comma or a hyphen.")
    return problems


def render(src: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td)
        mmd, out = t / "d.mmd", t / "d.svg"
        mmd.write_text(src, encoding="utf-8")

        # mermaid-cli drives a headless Chrome through puppeteer. In a container without a user
        # namespace (GitHub Actions, most CI images) Chrome's sandbox cannot start, and it fails
        # with "Failed to launch the browser process: Code: null" - which looks exactly like a
        # broken diagram. Disable the sandbox: the input is our own repo, not untrusted content.
        cfg = t / "puppeteer.json"
        cfg.write_text('{"args": ["--no-sandbox", "--disable-setuid-sandbox"]}', encoding="utf-8")

        r = subprocess.run(
            ["npx", "-y", "@mermaid-js/mermaid-cli@11",
             "-i", str(mmd), "-o", str(out), "-q", "-p", str(cfg)],
            capture_output=True, text=True, shell=(sys.platform == "win32"),
        )
        if r.returncode == 0 and out.is_file() and out.stat().st_size > 0:
            return True, ""
        err = (r.stderr or r.stdout).strip().splitlines()
        # keep the lines that actually name the problem
        useful = [l for l in err if any(k in l.lower() for k in
                                        ("error", "expecting", "got '", "parse"))]
        return False, " | ".join(useful[:3]) or "render produced nothing"


def main() -> int:
    args = sys.argv[1:]
    files = [ROOT / a for a in args] if args else sorted(ROOT.rglob("*.md"))
    # baseline/ is the superseded skill, vendored only so its byte counts can be recomputed.
    # It is not maintained, so its diagrams are not this repo's problem.
    skip = {".git", "node_modules", ".eval-workdir", "dist", "baseline"}
    files = [f for f in files if not (skip & set(f.parts))]

    total = failed = 0
    for f in files:
        blocks = find_blocks(f.read_text(encoding="utf-8"))
        for i, (b, closing_ok) in enumerate(blocks, 1):
            total += 1
            rel = f.relative_to(ROOT).as_posix()

            if not closing_ok:
                failed += 1
                print(f"  FAIL  {rel} block {i}: closing ``` is glued to the last line. Put it on "
                      f"its own line, or GitHub will not close the block.")
                continue

            issues = lint(b)
            if issues:
                failed += 1
                print(f"  FAIL  {rel} block {i}:")
                for p in issues:
                    print(f"          {p}")
                continue

            ok, err = render(b)
            if ok:
                print(f"  ok    {rel} block {i}")
            else:
                failed += 1
                print(f"  FAIL  {rel} block {i}: {err}")

    print(f"\n  {total - failed}/{total} mermaid blocks render.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
