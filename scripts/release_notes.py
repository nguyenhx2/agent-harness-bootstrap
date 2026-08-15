#!/usr/bin/env python3
"""Assemble the GitHub release body for a version from the two skills' CHANGELOGs.

Each skill's CHANGELOG.md is the single source of truth for what changed in it - not a
hand-written release description. This extracts the `## [X.Y.Z] - YYYY-MM-DD` section from each
skill's CHANGELOG, demotes its Added/Changed/Fixed headings one level (so they read as children of
the skill instead of siblings of it), and stitches the results into one release body:

    harness-bootstrap/CHANGELOG.md
    spec-builder/CHANGELOG.md
    tools/harness-view/CHANGELOG.md

The tools are included because their binaries are attached to the same release: a body that only
described the skills left someone downloading `harness-view-<version>-<target>.zip` with no way to
learn what changed in it.

    py -3.13 scripts/release_notes.py 1.7.0            # -> stdout
    py -3.13 scripts/release_notes.py 1.7.0 -o notes.md
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS = ("harness-bootstrap", "spec-builder")
# (heading, path to CHANGELOG.md) for the shipped tools
TOOLS = (("harness-view", pathlib.Path("tools") / "harness-view"),)


def section(changelog: pathlib.Path, version: str) -> str | None:
    """The body of a skill's `## [version] - DATE` entry, or None if the file or entry is missing."""
    if not changelog.is_file():
        return None
    text = changelog.read_text(encoding="utf-8")
    pat = re.compile(rf"^##\s*\[{re.escape(version)}\][^\n]*\n(.*?)(?=^##\s*\[|\Z)", re.M | re.S)
    m = pat.search(text)
    return m.group(1).strip() if m else None


def build(version: str) -> str | None:
    """The assembled body, or None when no skill has an entry for this version."""
    parts = []
    for skill in SKILLS:
        body = section(ROOT / skill / "CHANGELOG.md", version)
        if body is None:
            continue
        # The skill name becomes an H3 below, so its own Added/Changed/Fixed headings have to
        # drop a level or they render as siblings of the skill name instead of children of it.
        body = re.sub(r"^###\s", "#### ", body, flags=re.M)
        parts.append(f"### `{skill}`\n\n{body}")

    tool_parts = []
    for name, rel in TOOLS:
        body = section(ROOT / rel / "CHANGELOG.md", version)
        if body is None:
            continue
        body = re.sub(r"^###\s", "#### ", body, flags=re.M)
        tool_parts.append(f"### `{name}`\n\n{body}")

    if not parts and not tool_parts:
        return None

    out = "\n\n---\n\n".join(parts)
    if tool_parts:
        # Called out separately because the tools ship as platform binaries on this
        # same release while the skills ship as zips: different things to download.
        head = "## Tools\n\nDownloadable builds for Windows, macOS and Linux are attached to this release."
        joined = "\n\n---\n\n".join(tool_parts)
        out = (out + "\n\n---\n\n" if out else "") + f"{head}\n\n{joined}"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version", help="semver, with or without a leading v")
    ap.add_argument("-o", "--out", help="write the notes to this file instead of stdout")
    args = ap.parse_args()

    version = args.version.lstrip("vV")
    notes = build(version)

    if notes is None:
        # Publishing a release whose body is a placeholder is exactly the failure this script
        # replaced - fail loudly instead, so CI stops before `gh release create`.
        print(
            f"ERROR: no CHANGELOG entry for {version} in any skill - add one under "
            f"`## [{version}] - YYYY-MM-DD` in each changed skill's CHANGELOG.md before releasing.",
            file=sys.stderr,
        )
        return 1

    if args.out:
        pathlib.Path(args.out).write_text(notes + "\n", encoding="utf-8")
        print(f"notes -> {args.out}")
    else:
        # Windows consoles default to a non-UTF-8 code page; the CHANGELOGs carry `->` and other
        # non-ASCII-adjacent punctuation that would otherwise raise UnicodeEncodeError on stdout.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.write(notes + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
