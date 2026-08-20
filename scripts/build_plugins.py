#!/usr/bin/env python3
"""Generate the Agent Plugins tree so the skills install in Cursor, Codex and the rest.

Claude Code loads these skills through `.claude-plugin/marketplace.json`, whose entries point
straight at `harness-bootstrap/` and `spec-builder/` (each auto-loads as a single-skill plugin
because its SKILL.md sits at the directory root). No other client works that way.

The portable answer is Agent Plugins 1.1.0 (agent-plugins.org), the vendor-neutral packaging
standard whose steering committee is Amazon, Cursor, Microsoft, OpenAI and Vercel, and which
ChatGPT, Codex, Cursor, GitHub Copilot, Kiro and VS Code read. Its rules that shape this script:

  - the manifest is `plugin.json` at the PLUGIN ROOT, and its schema is CLOSED: only $schema,
    name, version, description, author, homepage, repository, license, keywords, extensions;
  - skills are discovered at the fixed path `skills/`, one per immediate child directory that
    contains a regular `SKILL.md`, and clients MUST NOT search deeper;
  - every path a client resolves MUST stay inside the plugin root, so a symlink pointing back
    at `../../harness-bootstrap` is not an option: the content has to be really there.

The manifests do not collide, so one directory serves every client at once. Claude reads
`.claude-plugin/`, Codex reads `.codex-plugin/`, and Cursor plus the other Agent Plugins clients
read the root `plugin.json`. All of them read the SAME `skills/` tree, which is why one copy is
enough. Cursor also defines a native `.cursor-plugin/` manifest; it is deliberately NOT written,
because Cursor documents the Agent Plugins root manifest as a supported format and a second
manifest for the same client is one more thing that can disagree with the first.

WHY GENERATED AND GATED, NOT HAND-MAINTAINED
--------------------------------------------
The skills stay the single source of truth; this copies them. `--check` re-runs the generation
into a temp directory and fails when the committed tree differs, so an edit to a skill that is
not mirrored is a red build rather than a plugin that silently ships last month's instructions.
That is the same contract `build_wiki.py` has for the wiki.

The copies are byte-identical, so git stores one blob for both paths and the repository grows by
tree entries rather than by content.

    python scripts/build_plugins.py            # write the tree
    python scripts/build_plugins.py --check    # verify it matches the skills (CI)
"""
from __future__ import annotations

import filecmp
import json
import pathlib
import re
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "plugins"
SPEC = "https://agent-plugins.org/schemas/1.1.0/plugin.schema.json"

# The skills this repo ships. Each becomes one plugin, matching how the Claude marketplace
# lists them, so a user can install either on its own.
SKILLS = ("harness-bootstrap", "spec-builder")

# Agent Plugins closes its manifest schema. Writing a field outside this set produces a manifest
# clients must report and ignore, so the set is asserted rather than trusted.
ALLOWED = {"$schema", "name", "version", "description", "author", "homepage", "repository",
           "license", "keywords", "extensions"}
NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")

# Files that belong to the developing repo, not to an installed skill.
SKIP_NAMES = {"CHANGELOG.md", "__pycache__", ".gitignore"}
SKIP_SUFFIX = {".pyc"}

REPO_URL = "https://github.com/nguyenhx2/agent-harness-bootstrap"


def repo_version() -> str:
    """The release version, from the same place validate_release.py reads it."""
    text = (ROOT / "harness-bootstrap" / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"^version:\s*(\d+\.\d+\.\d+)\s*$", text, re.M)
    if not m:
        sys.exit("harness-bootstrap/SKILL.md has no version in its frontmatter")
    return m.group(1)


def blurb(skill: str) -> str:
    """The human-facing description, taken from the Claude marketplace entry.

    A SKILL.md description is a long trigger carpet written for a MODEL: the harness-bootstrap
    one runs past 400 characters before its first full stop, which is unreadable in a plugin
    browser. `.claude-plugin/marketplace.json` already carries a curated one-line blurb per
    skill, so every marketplace quotes that single reviewed sentence instead of inventing a
    second wording that can drift from it.
    """
    entries = json.loads((ROOT / ".claude-plugin" / "marketplace.json")
                         .read_text(encoding="utf-8"))["plugins"]
    for e in entries:
        if e.get("name") == skill:
            return e["description"]
    sys.exit(f".claude-plugin/marketplace.json has no entry for {skill}, so its plugin "
             "description has no source")


def claude_marketplace_version() -> str:
    entries = json.loads((ROOT / ".claude-plugin" / "marketplace.json")
                         .read_text(encoding="utf-8"))["plugins"]
    versions = {e.get("version") for e in entries}
    if len(versions) != 1:
        sys.exit(f".claude-plugin/marketplace.json entries disagree on version: {versions}")
    return versions.pop()


def manifest(skill: str, version: str) -> dict:
    body = {
        "$schema": SPEC,
        "name": skill,
        "version": version,
        "description": blurb(skill),
        "author": {"name": "nguyenhx2", "url": "https://github.com/nguyenhx2"},
        "homepage": REPO_URL,
        "repository": REPO_URL,
        "license": "MIT",
        "keywords": ["agent", "harness", "skills", "guardrails",
                     "specifications" if skill == "spec-builder" else "scaffolding"],
    }
    bad = set(body) - ALLOWED
    if bad:
        sys.exit(f"manifest for {skill} carries fields outside the closed schema: {sorted(bad)}")
    if not NAME_RE.match(body["name"]):
        sys.exit(f"plugin name {body['name']!r} does not match the spec's name pattern")
    return body


def codex_manifest(skill: str, version: str) -> dict:
    """Codex reads `.codex-plugin/plugin.json`, its own path, with its own (open) shape."""
    return {
        "name": skill,
        "version": version,
        "description": blurb(skill),
        "author": {"name": "nguyenhx2"},
        "homepage": REPO_URL,
        "license": "MIT",
    }


def write_json(path: pathlib.Path, body: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8", newline="\n")


def copy_skill(skill: str, dest: pathlib.Path) -> int:
    """Copy the skill verbatim. Byte-identical, so git stores one blob for both paths."""
    src = ROOT / skill
    n = 0
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src)
        if set(rel.parts) & SKIP_NAMES or p.suffix in SKIP_SUFFIX:
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(p.read_bytes())
        n += 1
    return n


def marketplace(version: str) -> dict:
    """The Codex marketplace, at the path Codex looks for it.

    `codex plugin marketplace add nguyenhx2/agent-harness-bootstrap` reads
    $REPO_ROOT/.agents/plugins/marketplace.json, so it lives there rather than beside the
    plugins it lists.
    """
    return {
        "name": "agent-harness-bootstrap",
        "interface": {"displayName": "Agent Harness Bootstrap"},
        "plugins": [
            {
                "name": skill,
                "description": blurb(skill),
                "version": version,
                "category": "development",
                "source": {"path": f"../../plugins/{skill}"},
                "policy": {"installation": "user", "authentication": "none"},
            }
            for skill in SKILLS
        ],
    }


def build(out: pathlib.Path, agents_dir: pathlib.Path) -> list[str]:
    version = repo_version()
    mkt_v = claude_marketplace_version()
    if mkt_v != version:
        sys.exit(f".claude-plugin/marketplace.json says {mkt_v} but the skills say {version} - "
                 "every marketplace has to name one version, or a user installs a build the "
                 "release never made")
    lines = []
    if out.exists():
        shutil.rmtree(out)
    for skill in SKILLS:
        root = out / skill
        write_json(root / "plugin.json", manifest(skill, version))
        write_json(root / ".codex-plugin" / "plugin.json", codex_manifest(skill, version))
        n = copy_skill(skill, root / "skills" / skill)
        lines.append(f"  ok    plugins/{skill}: manifest + .codex-plugin + {n} skill file(s)")
    write_json(agents_dir / "marketplace.json", marketplace(version))
    # --check builds into a temp directory, which is not under ROOT, so the label is fixed
    # rather than derived: relative_to() would raise there and take the check down with it.
    lines.append(f"  ok    .agents/plugins/marketplace.json: {len(SKILLS)} plugin(s), v{version}")
    return lines


def differences(a: pathlib.Path, b: pathlib.Path) -> list[str]:
    """Every path that differs between two trees, by content and not by timestamp."""
    out: list[str] = []

    def walk(d: filecmp.dircmp, prefix: str) -> None:
        for n in sorted(d.left_only):
            out.append(f"only in the committed tree: {prefix}{n}")
        for n in sorted(d.right_only):
            out.append(f"missing from the committed tree: {prefix}{n}")
        # shallow=False: compare bytes, never size-and-mtime, or a same-size edit slips past.
        _, mismatch, errors = filecmp.cmpfiles(d.left, d.right, d.common_files, shallow=False)
        for n in sorted(mismatch) + sorted(errors):
            out.append(f"differs: {prefix}{n}")
        for name, sub in sorted(d.subdirs.items()):
            walk(sub, f"{prefix}{name}/")

    walk(filecmp.dircmp(a, b), "")
    return out


def self_test() -> list[str]:
    """Prove the drift detector fires, on synthetic trees, before it judges the real one.

    A tree comparison that quietly returns nothing is indistinguishable from a clean build, and
    that is the exact failure mode this repository keeps finding in its own checks.
    """
    dead = []
    with tempfile.TemporaryDirectory() as td:
        a, b = pathlib.Path(td) / "a", pathlib.Path(td) / "b"
        for d in (a, b):
            (d / "skills" / "x").mkdir(parents=True)
            (d / "skills" / "x" / "SKILL.md").write_text("same\n", encoding="utf-8", newline="\n")
        if differences(a, b):
            dead.append("identical trees are reported as different")
        (b / "skills" / "x" / "SKILL.md").write_text("edit\n", encoding="utf-8", newline="\n")
        if not differences(a, b):
            dead.append("an edited file is not reported")
        (b / "skills" / "x" / "SKILL.md").write_text("same\n", encoding="utf-8", newline="\n")
        (b / "extra.md").write_text("x\n", encoding="utf-8", newline="\n")
        if not differences(a, b):
            dead.append("an added file is not reported")
    return dead


def main() -> int:
    check = "--check" in sys.argv[1:]

    dead = self_test()
    if dead:
        print("  DEAD CHECK - the drift detector cannot report drift:")
        for d in dead:
            print(f"    {d}")
        return 1

    if not check:
        for line in build(OUT, ROOT / ".agents" / "plugins"):
            print(line)
        print("  wrote the plugin tree. Commit it: it is what Cursor and Codex install.")
        return 0

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        build(tmp / "plugins", tmp / ".agents" / "plugins")
        problems = []
        if not OUT.is_dir():
            problems.append("plugins/ does not exist - run scripts/build_plugins.py")
        else:
            problems += differences(OUT, tmp / "plugins")
        mk = ROOT / ".agents" / "plugins" / "marketplace.json"
        want = (tmp / ".agents" / "plugins" / "marketplace.json")
        if not mk.is_file():
            problems.append(".agents/plugins/marketplace.json is missing")
        elif mk.read_bytes() != want.read_bytes():
            problems.append(".agents/plugins/marketplace.json differs from what the skills imply")

    if problems:
        print("  FAIL  the committed plugin tree does not match the skills:")
        for p in problems[:20]:
            print(f"    {p}")
        if len(problems) > 20:
            print(f"    ... and {len(problems) - 20} more")
        print("\n  Run `python scripts/build_plugins.py` and commit the result. The skills are")
        print("  the source of truth; this tree is the copy Cursor and Codex actually install.")
        return 1

    n = sum(1 for p in OUT.rglob("*") if p.is_file())
    print(f"  ok    the committed plugin tree matches the skills ({n} files, "
          f"{len(SKILLS)} plugins)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
