#!/usr/bin/env python3
"""Package the skills into release artifacts.

Produces, under dist/:

    harness-bootstrap-v<X.Y.Z>.zip          one skill
    spec-builder-v<X.Y.Z>.zip               one skill
    agent-harness-bootstrap-v<X.Y.Z>.zip   both skills
    SHA256SUMS

Plus an unversioned alias of each, because GitHub's permanent download URL
(/releases/latest/download/<NAME>) needs an exact filename and cannot carry a version.

A skill is a directory under ~/.claude/skills/, so installing one is an unzip. Every archive carries
a VERSION file at the root of each skill directory, so a skill on disk can be traced back to the
release it came from.

Usage:
    python scripts/package.py --version 1.0.0
    python scripts/package.py --version 1.0.0 --check   # preflight only, write nothing
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
BUNDLE = "agent-harness-bootstrap"
DIST = ROOT / "dist"

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "node_modules"}
EXCLUDE_NAMES = {".DS_Store", "vars.json"}
EXCLUDE_SUFFIX = {".pyc", ".pyo"}


def wanted(p: pathlib.Path) -> bool:
    if any(part in EXCLUDE_DIRS for part in p.parts):
        return False
    return p.name not in EXCLUDE_NAMES and p.suffix not in EXCLUDE_SUFFIX


def skill_files(skill: str) -> list[pathlib.Path]:
    return sorted(p for p in (ROOT / skill).rglob("*") if p.is_file() and wanted(p))


def preflight(version: str) -> list[str]:
    problems: list[str] = []
    if not SEMVER.match(version):
        problems.append(f"version '{version}' is not semver (X.Y.Z)")

    for skill in SKILLS:
        base = ROOT / skill
        if not (base / "SKILL.md").is_file():
            problems.append(f"{skill}/SKILL.md is missing")
            continue
        if not skill_files(skill):
            problems.append(f"{skill} has no files")
        if (base / "scripts/scaffold.py").is_file() and not (base / "assets/manifest.json").is_file():
            problems.append(f"{skill} ships a scaffolder but no assets/manifest.json")

    ch = ROOT / "CHANGELOG.md"
    if not ch.is_file():
        problems.append("CHANGELOG.md is missing")
    elif f"## v{version}" not in ch.read_text(encoding="utf-8"):
        problems.append(f"CHANGELOG.md has no '## v{version}' section")

    return problems


def add_skill(zf: zipfile.ZipFile, skill: str, version: str) -> None:
    """Everything sits under the skill directory. These archives extract straight into
    ~/.claude/skills/, so a file at the archive root would land loose in the user's skills folder."""
    for f in skill_files(skill):
        zf.write(f, f.relative_to(ROOT).as_posix())
    zf.writestr(f"{skill}/VERSION", f"{version}\n")
    zf.write(ROOT / "LICENSE", f"{skill}/LICENSE")


def build(version: str) -> list[pathlib.Path]:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    written: list[pathlib.Path] = []

    for skill in SKILLS:
        out = DIST / f"{skill}-v{version}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            add_skill(zf, skill, version)
        written.append(out)

    bundle = DIST / f"{BUNDLE}-v{version}.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
        for skill in SKILLS:
            add_skill(zf, skill, version)
    written.append(bundle)

    # Unversioned aliases: /releases/latest/download/<NAME> needs an exact filename, so a versioned
    # name can never be a permanent URL. The VERSION file inside still identifies the build.
    for p in list(written):
        alias = DIST / re.sub(r"-v\d+\.\d+\.\d+\.zip$", ".zip", p.name)
        if alias != p:
            shutil.copyfile(p, alias)
            written.append(alias)

    sums = DIST / "SHA256SUMS"
    sums.write_text(
        "\n".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
                  for p in written) + "\n", encoding="utf-8")
    written.append(sums)
    return written


def verify(written: list[pathlib.Path], version: str) -> bool:
    """Checked rather than trusted: nothing at an archive root (it would land loose in the user's
    skills folder), no unexpected top-level directory, and a correct VERSION inside each skill."""
    ok = True
    print("\nverifying:")
    for p in written:
        if p.suffix != ".zip":
            continue
        with zipfile.ZipFile(p) as zf:
            names = zf.namelist()
            loose = sorted({n for n in names if "/" not in n.rstrip("/")})
            stray = sorted({n.split("/", 1)[0] for n in names} - set(SKILLS))
            stamps = {n: zf.read(n).decode().strip() for n in names if n.endswith("/VERSION")}
            if loose or stray:
                print(f"  FAIL  {p.name}: loose at root={loose} unexpected dirs={stray}")
                ok = False
                continue
            if not stamps or any(v != version for v in stamps.values()):
                print(f"  FAIL  {p.name}: VERSION {stamps} != {version}")
                ok = False
                continue
            expect = len(SKILLS) if p.name.startswith(BUNDLE) else 1
            if len(stamps) != expect:
                print(f"  FAIL  {p.name}: expected {expect} skill(s), found {len(stamps)}")
                ok = False
                continue
        print(f"  ok    {p.name:<44} {len(stamps)} skill(s), VERSION {version}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="semver, e.g. 1.0.0 (no leading v)")
    ap.add_argument("--check", action="store_true", help="preflight only, write nothing")
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
        print(f"  {p.name:<46} {p.stat().st_size:>9,} bytes")

    if not verify(written, version):
        print("\npackaging failed its own checks. Nothing here is safe to release.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
