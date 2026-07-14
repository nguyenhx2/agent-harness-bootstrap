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
BLOCK = re.compile(r"```mermaid\n(.*?)```", re.S)


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
        blocks = BLOCK.findall(f.read_text(encoding="utf-8"))
        for i, b in enumerate(blocks, 1):
            total += 1
            ok, err = render(b)
            rel = f.relative_to(ROOT).as_posix()
            if ok:
                print(f"  ok    {rel} block {i}")
            else:
                failed += 1
                print(f"  FAIL  {rel} block {i}: {err}")

    print(f"\n  {total - failed}/{total} mermaid blocks render.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
