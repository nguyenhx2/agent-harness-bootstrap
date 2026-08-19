#!/usr/bin/env python3
"""Assert every shipped clip was rendered from the scene source that ships beside it.

`check_numbers.py` derives every published figure from the scripts and fails when a document
contradicts one. It reads text. The clips under `video/mp4/` and `video/gif/` are pixels, and
their figures are BURNED IN at render time, so that gate could never see them.

It cost us. `video/gif/04-solution.gif` is the first moving image on the README, and it read
"guardrail eval 69/69" for three releases while the scene source said 107/107 and every text
document on the site agreed with the source. The number had moved twice, 69 to 89 to 107, and
the GIF was re-rendered for neither. Two more clips had drifted the same way.

The check a renderer can actually make is provenance, not pixels: an artifact is stale when its
scene source changed after the artifact was last produced from it. This records the source hash
in `video/RENDERED.json` at render time and compares it here.

What this does NOT catch, stated plainly rather than implied:

  - A figure that is wrong in the SOURCE too. That is `check_numbers.py`'s job, and it reads
    these sources - `video/src/**.py` is in its search set.
  - A change to `theme.py` or `jatheme.py`. Those alter every frame of every clip, and hashing
    them here would demand a fourteen-clip re-render for one colour tweak. A palette change does
    not make a published number false, which is the failure this gate exists to stop. Re-render
    deliberately after a theme change; `video/README.md` says so.

This script had no self-test: its ability to fail was proven once by hand, then never again -
the "green and useless" failure mode `check_numbers.py` and `check_svg.py` both guard against,
and `check_numbers.py`'s self-test caught a dead pattern the first time it ran. `self_test()`
below builds disposable fixtures in a temp directory - never the real `video/` tree - and proves
all three branches this script can report still fire: a matching hash reads current, a source
edited after the recording reads stale, and an artifact with no recorded provenance is flagged.
It runs at the start of every verification invocation, before any real artifact is checked.

Usage:
    python scripts/check_media.py            # verify (CI)
    python scripts/check_media.py --update <artifact> [<artifact> ...]

Exit 0 = every artifact matches its source, 1 = at least one clip is stale.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "video/RENDERED.json"

# artifact (relative to ROOT) -> the scene source it is rendered from.
CLIPS = [
    "01-overview", "02-flow", "03-layers", "04-solution",
    "05-spec-builder", "06-harness-bootstrap", "07-skills-and-view",
]


def pairs() -> dict[str, str]:
    """Every shipped artifact mapped to the scene source that produces it."""
    out: dict[str, str] = {}
    for name in CLIPS:
        out[f"video/mp4/{name}.mp4"] = f"video/src/{name}.py"
        out[f"video/mp4/ja/{name}.mp4"] = f"video/src/ja/{name}.py"
    # The GIFs are transcoded from the MP4 of the same clip, so they carry the same provenance.
    out["video/gif/04-solution.gif"] = "video/src/04-solution.py"
    out["video/gif/ja/04-solution.gif"] = "video/src/ja/04-solution.py"
    return out


def digest(rel: str, root: pathlib.Path = ROOT) -> str:
    return hashlib.sha256((root / rel).read_bytes()).hexdigest()


def load() -> dict[str, str]:
    if not MANIFEST.is_file():
        return {}
    return json.loads(MANIFEST.read_text(encoding="utf-8")).get("rendered_from", {})


def save(data: dict[str, str]) -> None:
    body = {
        "comment": "sha256 of the scene source each shipped clip was last rendered from. "
                   "Written by scripts/check_media.py --update, verified by the same script.",
        "version": 1,
        "rendered_from": dict(sorted(data.items())),
    }
    MANIFEST.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8", newline="\n")


def update(targets: list[str]) -> int:
    known = pairs()
    data = load()
    bad = [t for t in targets if t.replace("\\", "/") not in known]
    if bad:
        print(f"  FAIL  not a shipped artifact: {', '.join(bad)}")
        return 1
    for t in targets:
        rel = t.replace("\\", "/")
        data[rel] = digest(known[rel])
        print(f"  recorded  {rel}  <-  {known[rel]}")
    save(data)
    return 0


def verify(known: dict[str, str], recorded: dict[str, str],
           root: pathlib.Path) -> tuple[list[tuple[str, str]], list[str], int]:
    """The three-branch detector: current, stale, or missing provenance.

    Parameterised on `root` (rather than reading the ROOT global) so `self_test()` below can
    run it against disposable fixtures instead of the real `video/` tree.
    """
    stale: list[tuple[str, str]] = []
    missing: list[str] = []
    ok = 0
    for artifact, source in sorted(known.items()):
        if not (root / artifact).is_file():
            missing.append(f"{artifact} (shipped artifact is absent)")
            continue
        if not (root / source).is_file():
            missing.append(f"{source} (scene source is absent)")
            continue
        if artifact not in recorded:
            missing.append(f"{artifact} (no provenance recorded)")
            continue
        if recorded[artifact] != digest(source, root):
            stale.append((artifact, source))
        else:
            ok += 1
    return stale, missing, ok


def self_test() -> list[str]:
    """Prove the three branches `verify()` can report still fire.

    Builds three tiny artifact/source pairs in a temp directory - never the real `video/`
    tree - and drives them through `verify()` exactly as the real check does:

      (a) artifact a: recorded hash matches the source's current hash -> must read current.
      (b) artifact b: source is edited AFTER its hash was recorded -> must read stale.
      (c) artifact c: artifact exists, source exists, but nothing was ever recorded for it ->
          must be flagged for missing provenance.

    A pattern or comparison that stops matching anything still prints and exits 0 - exactly the
    failure this repo keeps finding - so each branch is checked individually rather than trusting
    an aggregate pass/fail.
    """
    import tempfile

    problems: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / "video/mp4").mkdir(parents=True)
        (root / "video/src").mkdir(parents=True)

        art_a, src_a = "video/mp4/a.mp4", "video/src/a.py"
        art_b, src_b = "video/mp4/b.mp4", "video/src/b.py"
        art_c, src_c = "video/mp4/c.mp4", "video/src/c.py"

        (root / src_a).write_text("scene a", encoding="utf-8", newline="\n")
        (root / art_a).write_bytes(b"fixture a")
        (root / src_b).write_text("scene b, before the recording", encoding="utf-8", newline="\n")
        (root / art_b).write_bytes(b"fixture b")
        (root / src_c).write_text("scene c", encoding="utf-8", newline="\n")
        (root / art_c).write_bytes(b"fixture c")

        recorded_b = digest(src_b, root)
        # Edit the source AFTER its hash was captured, exactly as a real re-write of a scene
        # would happen after the clip was last rendered from it.
        (root / src_b).write_text("scene b, edited after the recording",
                                  encoding="utf-8", newline="\n")

        known = {art_a: src_a, art_b: src_b, art_c: src_c}
        # art_c is deliberately absent from `recorded`: nothing was ever run with --update for it.
        recorded = {art_a: digest(src_a, root), art_b: recorded_b}

        stale, missing, ok = verify(known, recorded, root)

        if ok != 1:
            problems.append("DEAD CHECK: branch (a) matching hash -> current never fires "
                            f"(got {ok} current, expected 1)")
        if not any(a == art_b for a, s in stale):
            problems.append("DEAD CHECK: branch (b) source edited after recording -> stale "
                            "never fires")
        if not any(m.startswith(art_c) and "no provenance recorded" in m for m in missing):
            problems.append("DEAD CHECK: branch (c) artifact with no recorded provenance -> "
                            "flagged never fires")
    return problems


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--update":
        if len(argv) < 2:
            print("  FAIL  --update needs at least one artifact path")
            return 1
        return update(argv[1:])

    dead = self_test()
    if dead:
        print("  DEAD CHECK - a detector branch cannot fire, so a real stale clip could pass "
              "silently:")
        for d in dead:
            print(f"    {d}")
        return 1

    known = pairs()
    recorded = load()
    stale, missing, ok = verify(known, recorded, ROOT)

    for artifact, source in stale:
        print(f"  FAIL  {artifact}")
        print(f"        {source} changed after this clip was last rendered, so any figure")
        print("        burned into it may now contradict the source. Re-render, then:")
        print(f"        python scripts/check_media.py --update {artifact}")
    for m in missing:
        print(f"  FAIL  {m}")

    if stale or missing:
        print(f"\n  {len(stale) + len(missing)} stale, {ok} current.")
        return 1
    print(f"  ok    {ok} clips, each rendered from the source that ships beside it")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
