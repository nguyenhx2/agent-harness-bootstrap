#!/usr/bin/env python3
"""Package the skills into installable release artifacts.

Produces, under dist/:
    harness-bootstrap-v<X.Y.Z>.zip        one skill, ready to drop into ~/.claude/skills/
    spec-builder-v<X.Y.Z>.zip             one skill, ready to drop into ~/.claude/skills/
    claude-harness-bootstrap-v<X.Y.Z>.zip both skills together
    SHA256SUMS                            checksums for all of the above

Every archive carries a VERSION file at the root of each skill directory, so an installed skill can
always be traced back to the release it came from. A skill on disk with no VERSION is an unknown
build, and that is exactly the situation this script exists to prevent.

The zip is the format because it is what actually installs: a skill is a directory under
~/.claude/skills/, so unzipping it there is the install. There is no separate ".skill" package format
in Claude Code - inventing an extension would imply a loader that does not exist.

Usage:
    python scripts/package.py --version 1.2.0
    python scripts/package.py --version 1.2.0 --check   # verify only, write nothing
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import shutil
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS = ("harness-bootstrap", "spec-builder")
DIST = ROOT / "dist"

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

# Never ship these into a release artifact.
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules"}
EXCLUDE_NAMES = {".DS_Store", "vars.json"}
EXCLUDE_SUFFIX = {".pyc", ".pyo"}


def wanted(p: pathlib.Path) -> bool:
    if any(part in EXCLUDE_DIRS for part in p.parts):
        return False
    if p.name in EXCLUDE_NAMES or p.suffix in EXCLUDE_SUFFIX:
        return False
    return True


def skill_files(skill: str) -> list[pathlib.Path]:
    base = ROOT / skill
    return sorted(p for p in base.rglob("*") if p.is_file() and wanted(p))


def preflight(version: str) -> list[str]:
    """Refuse to package something broken. A release that ships a placeholder into a rule file is
    worse than no release: the harness looks armed and is not."""
    problems: list[str] = []

    if not SEMVER.match(version):
        problems.append(f"version '{version}' is not semver (X.Y.Z)")

    for skill in SKILLS:
        base = ROOT / skill
        if not (base / "SKILL.md").is_file():
            problems.append(f"{skill}/SKILL.md is missing")
            continue
        files = skill_files(skill)
        if not files:
            problems.append(f"{skill} has no files")
        # A scaffolder with no manifest, or a manifest pointing at nothing, is a dead skill.
        man = base / "assets/manifest.json"
        if (base / "scripts/scaffold.py").is_file() and not man.is_file():
            problems.append(f"{skill} ships a scaffolder but no assets/manifest.json")

    if not (ROOT / "CHANGELOG.md").is_file():
        problems.append("CHANGELOG.md is missing at the repo root")
    else:
        ch = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        if f"## v{version}" not in ch:
            problems.append(f"CHANGELOG.md has no '## v{version}' section")

    return problems


def build(version: str) -> list[pathlib.Path]:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    stamp = f"{version}\n"
    written: list[pathlib.Path] = []

    def add_skill(zf: zipfile.ZipFile, skill: str) -> None:
        for f in skill_files(skill):
            zf.write(f, f.relative_to(ROOT).as_posix())
        # VERSION goes INSIDE the skill dir, so an installed skill is self-identifying.
        zf.writestr(f"{skill}/VERSION", stamp)

    for skill in SKILLS:
        out = DIST / f"{skill}-v{version}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            add_skill(zf, skill)
            zf.write(ROOT / "LICENSE", "LICENSE")
        written.append(out)

    bundle = DIST / f"claude-harness-bootstrap-v{version}.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
        for skill in SKILLS:
            add_skill(zf, skill)
        for extra in ("LICENSE", "README.md", "CHANGELOG.md"):
            zf.write(ROOT / extra, extra)
    written.append(bundle)

    # Unversioned aliases. GitHub's stable "latest" download URL is
    #   /releases/latest/download/<ASSET_NAME>
    # and it needs an EXACT filename, so a versioned name can never be linked that way. Shipping an
    # alias alongside the versioned artifact gives a permanent install URL that always resolves to
    # the newest release. The VERSION file inside still identifies exactly which build it is, so the
    # alias costs nothing in traceability.
    aliases: list[pathlib.Path] = []
    for p in list(written):
        alias = DIST / re.sub(r"-v\d+\.\d+\.\d+\.zip$", ".zip", p.name)
        if alias != p:
            shutil.copyfile(p, alias)
            aliases.append(alias)
    written += aliases

    sums = DIST / "SHA256SUMS"
    lines = []
    for p in written:
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(f"{h}  {p.name}")
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    written.append(sums)

    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="semver, e.g. 1.2.0 (no leading v)")
    ap.add_argument("--check", action="store_true", help="run preflight only, write nothing")
    a = ap.parse_args()

    version = a.version.lstrip("v")

    problems = preflight(version)
    if problems:
        print("preflight FAILED:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"preflight ok for v{version}")

    if a.check:
        return 0

    written = build(version)
    print(f"\nwrote {len(written)} files to dist/:")
    for p in written:
        size = p.stat().st_size
        print(f"  {p.name:<48} {size:>9,} bytes")

    # Prove the artifact is installable: the VERSION must be inside, at the skill root.
    print("\nverifying each archive carries VERSION inside the skill dir:")
    for p in written:
        if p.suffix != ".zip":
            continue
        with zipfile.ZipFile(p) as zf:
            names = zf.namelist()
            for skill in SKILLS:
                key = f"{skill}/VERSION"
                if key in names:
                    got = zf.read(key).decode().strip()
                    ok = "ok" if got == version else f"MISMATCH ({got})"
                    print(f"  {p.name:<48} {key:<28} {ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
