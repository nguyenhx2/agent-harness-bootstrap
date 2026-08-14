#!/usr/bin/env python3
"""Version-sync gate for the two skills' CHANGELOGs. Run by CI and before cutting a release.

Checks (all cheap, all deterministic):
  1. every skill has a CHANGELOG.md
  2. its newest entry is a valid `## [X.Y.Z] - YYYY-MM-DD` heading
  3. entries are newest-first (by semver, not by file order)
  4. the newest CHANGELOG version matches that skill's SKILL.md frontmatter `version:`
  5. both skills' SKILL.md frontmatter agree on the version - they are released together as one
     repo version, so one skill bumped without the other is a half-finished release

With a version argument, additionally:
  6. every skill has an entry for exactly that version - the release gate CI runs before
     publishing, so a tag can never ship a placeholder body

Exit 0 = clean (prints one summary line). Exit 1 = problems (printed one per line).

    py -3.13 scripts/validate_release.py           # structure + sync only
    py -3.13 scripts/validate_release.py 1.8.0     # plus: both skills carry a 1.8.0 entry
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS = ("harness-bootstrap", "spec-builder")

ENTRY = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]\s*-\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)
# Any bracketed version heading, valid or not - the delta against ENTRY is a malformed heading
# (usually a bad or missing date) that release_notes.py would happily extract; catch it here with
# a clear message instead of letting the two scripts disagree about what counts as an entry.
LOOSE_ENTRY = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\][^\n]*$", re.M)


def ver_tuple(v: str) -> tuple[int, int, int]:
    return tuple(int(x) for x in v.split("."))  # type: ignore[return-value]


def skill_md_version(path: pathlib.Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^version:\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).lstrip("vV") if m else None


def main() -> int:
    required = sys.argv[1].lstrip("vV") if len(sys.argv) > 1 else None
    if required and not re.fullmatch(r"\d+\.\d+\.\d+", required):
        print(f"usage error: '{sys.argv[1]}' is not a semver version (X.Y.Z)")
        return 1

    errs: list[str] = []
    changelog_versions: dict[str, str] = {}
    skill_md_versions: dict[str, str] = {}

    for skill in SKILLS:
        base = ROOT / skill
        changelog = base / "CHANGELOG.md"
        skill_md = base / "SKILL.md"

        if not skill_md.is_file():
            errs.append(f"{skill}/SKILL.md is missing")
        else:
            v = skill_md_version(skill_md)
            if v is None:
                errs.append(f"{skill}/SKILL.md has no 'version:' in its frontmatter")
            else:
                skill_md_versions[skill] = v

        if not changelog.is_file():
            errs.append(f"{skill}/CHANGELOG.md is missing")
            continue

        text = changelog.read_text(encoding="utf-8")
        entries = ENTRY.findall(text)
        loose = LOOSE_ENTRY.findall(text)

        strict_versions = [v for v, _ in entries]
        for v in loose:
            if v not in strict_versions:
                errs.append(f"{skill}/CHANGELOG.md: heading for {v} is malformed - the required "
                            "form is '## [X.Y.Z] - YYYY-MM-DD'")
        seen: set[str] = set()
        for v in strict_versions:
            if v in seen:
                errs.append(f"{skill}/CHANGELOG.md: duplicate entry for {v} - merge the two "
                            "sections, release notes would silently use only the first")
            seen.add(v)

        if not entries:
            errs.append(f"{skill}/CHANGELOG.md: no '## [X.Y.Z] - YYYY-MM-DD' entry found")
            continue

        newest_version, _newest_date = entries[0]
        order = [ver_tuple(v) for v, _ in entries]
        if order != sorted(order, reverse=True):
            errs.append(f"{skill}/CHANGELOG.md: entries are not newest-first")

        changelog_versions[skill] = newest_version

        if required and required not in strict_versions:
            errs.append(f"{skill}/CHANGELOG.md: no entry for {required} - every skill needs one "
                        "for the version being released (a no-op note is fine)")

        skill_v = skill_md_versions.get(skill)
        if skill_v is not None and skill_v != newest_version:
            errs.append(
                f"{skill}: CHANGELOG.md's newest entry is {newest_version} but "
                f"SKILL.md frontmatter says {skill_v} - bump one to match the other"
            )

    # Both skills are released together under one repo version - a version present in one
    # SKILL.md and not the other means the release is half-bumped.
    distinct_skill_md = set(skill_md_versions.values())
    if len(distinct_skill_md) > 1:
        detail = ", ".join(f"{s}={v}" for s, v in sorted(skill_md_versions.items()))
        errs.append(f"SKILL.md versions disagree across skills ({detail}) - they must match")

    distinct_changelog = set(changelog_versions.values())
    if len(distinct_changelog) > 1:
        detail = ", ".join(f"{s}={v}" for s, v in sorted(changelog_versions.items()))
        errs.append(f"CHANGELOG.md newest versions disagree across skills ({detail}) - they "
                    "must match, even if one skill's entry is a no-op note")

    if errs:
        print(f"VALIDATION FAILED ({len(errs)} problem(s)):")
        for e in errs:
            print("  - " + e)
        return 1

    version = next(iter(distinct_skill_md)) if distinct_skill_md else "?"
    print(f"ok: {len(SKILLS)} skill(s) valid, repo version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
