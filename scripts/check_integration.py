#!/usr/bin/env python3
"""Gate that every harness the scaffolder can produce hangs together, and that the skill's assets
and its manifest describe the same set of files.

Two halves:

  matrix    Scaffold a harness for each flag combination in COMBOS - the purpose profiles
            (purpose_code / research / strategy / docs) crossed with hooks_strict, long, db, tests
            and solo_review, on both hook flavors - and validate each one with the checker the
            harness itself ships, `harness-bootstrap/assets/scripts/harness-check.py --stage
            scaffold`. A flag combination nobody scaffolds by hand is exactly where a command that
            names an unfielded seat, or a tier row for a seat that does not exist, hides. Every
            text file each scaffold writes must also be LF: a Windows checkout holds CRLF assets,
            and a path that copies them byte for byte ships the checkout's line endings instead
            of the harness's (`crlf`).

  coverage  Every file under harness-bootstrap/assets is a manifest `src`, or is listed in
            EXCLUDED with the reason it is not copied (the dev-agent template is instantiated by
            hand, per domain). Every manifest `src` exists. Every shipped .sh is marked "exec".
            Every hook ships in both flavors under the same flags. And harness-check.py's
            catalogs (the seat and command names it recognises, the tool names it accepts) match
            the assets and references/models-and-tools.json - a catalog that drifts makes the
            checker blind to exactly the names that changed.

Stdlib only. A self-test runs first and proves every coverage detector fires on a synthetic assets
tree, and that the matrix validation fires on a real scaffold with a deleted hook. A DEAD CHECK
fails the run.

    python scripts/check_integration.py [--quick] [--json]

--quick runs one combination per flavor instead of the whole matrix. Exit 0 clean, 1 findings or
a dead check.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = ROOT / "harness-bootstrap"
ASSETS = SKILL / "assets"
SCAFFOLD = SKILL / "scripts" / "scaffold.py"
CHECKER = ASSETS / "scripts" / "harness-check.py"
REFERENCE = ASSETS / "references" / "models-and-tools.json"

# Asset files deliberately not in the manifest, each with the reason. Adding to this list is a
# decision, so it carries the why.
EXCLUDED = {
    "manifest.json": "the manifest itself",
    "claude/agents/dev-agent.md": "per-domain template, instantiated by hand once per dev seat",
    "claude/hooks/registration.posix.json": "registration reference for hand wiring and the wiki",
    "claude/hooks/registration.windows.json": "registration reference for hand wiring and the wiki",
    "references/models-and-tools.json": "seed data compiled into harness-view, not a harness file",
    "root/module-CLAUDE.md": "rendered once per module by scaffold.py from vars.json `modules`",
}

# (name, flags). The OS flag is added per flavor.
COMBOS = (
    ("code-min", []),
    ("code-full", ["purpose_code", "hooks_strict", "long", "db", "db_engineer", "db_seeder",
                   "tests", "unit", "e2e", "merge_gate"]),
    ("code-solo", ["purpose_code", "solo_review", "tests", "unit"]),
    ("research", ["purpose_research"]),
    ("strategy", ["purpose_strategy", "long"]),
    ("docs", ["purpose_docs", "hooks_strict"]),
    ("all-noncode", ["purpose_research", "purpose_strategy", "purpose_docs", "long",
                     "hooks_strict"]),
    ("code+docs", ["purpose_code", "purpose_docs", "solo_review", "db", "tests", "unit",
                   "hooks_strict", "long"]),
    ("code+research", ["purpose_code", "purpose_research", "long", "tests", "e2e"]),
    # Audit mode fields seats authored at audit time; this combo once failed only outside the matrix.
    ("audit", ["purpose_code", "audit", "tests", "unit"]),
    ("code-extras", ["purpose_code", "ui", "ai", "terse", "rtk", "pr_cli", "deploy_ask", "tdd", "tests", "unit"]),
)
QUICK = ("code-full", "all-noncode")
FLAVORS = ("posix", "windows")


def load_checker():
    spec = importlib.util.spec_from_file_location("harness_check", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def base_vars() -> dict:
    sys.path.insert(0, str(ROOT / "eval"))
    import guardrail_eval as G  # stdlib-only; the same vars the eval and the CI matrix use
    return json.loads(json.dumps(G.VARS))


# ------------------------------------------------------------------------------ coverage
def coverage_problems(assets: pathlib.Path, manifest: list[dict], checker,
                      reference: dict | None) -> list[str]:
    out: list[str] = []
    files = {p.relative_to(assets).as_posix() for p in assets.rglob("*")
             if p.is_file() and "__pycache__" not in p.parts}
    srcs = {e["src"] for e in manifest}
    for f in sorted(files - srcs - set(EXCLUDED)):
        out.append(f"unlisted asset: {f} is in assets/ but no manifest entry copies it - add an "
                   "entry, or add it to EXCLUDED in scripts/check_integration.py with the reason")
    for s in sorted(srcs - files):
        out.append(f"missing src: manifest entry `{s}` names a file that does not exist")
    for f in sorted(set(EXCLUDED) & srcs):
        out.append(f"contradiction: {f} is both a manifest src and in EXCLUDED")
    for e in manifest:
        if e["src"].endswith(".sh") and not e.get("exec"):
            out.append(f"not executable: manifest entry `{e['src']}` ships a shell hook without "
                       "\"exec\": true")
    hooks = {}
    for e in manifest:
        stem, _, ext = e["src"].rpartition(".")
        if "/hooks/" in e["src"] and ext in ("sh", "ps1"):
            when = tuple(sorted(set(e.get("when") or []) - {"posix", "windows"}))
            hooks.setdefault(stem, {})[ext] = when
    for stem, flav in sorted(hooks.items()):
        if set(flav) != {"sh", "ps1"}:
            have = next(iter(flav))
            out.append(f"one flavor: {stem}.{have} ships without its "
                       f"{'ps1' if have == 'sh' else 'sh'} twin")
        elif flav["sh"] != flav["ps1"]:
            out.append(f"flavor flags differ: {stem}.sh ships when {list(flav['sh'])}, "
                       f"{stem}.ps1 when {list(flav['ps1'])}")
    seats = {p.stem for p in (assets / "claude" / "agents").glob("*.md")} - {"dev-agent"}
    if set(checker.CATALOG_SEATS) != seats:
        out.append("seat catalog drift: harness-check.py CATALOG_SEATS "
                   f"missing {sorted(seats - set(checker.CATALOG_SEATS))}, "
                   f"stale {sorted(set(checker.CATALOG_SEATS) - seats)}")
    commands = {p.stem for d in ("claude/commands", "audit/commands")
                for p in (assets / d).glob("*.md")}
    if set(checker.CATALOG_COMMANDS) != commands:
        out.append("command catalog drift: harness-check.py CATALOG_COMMANDS "
                   f"missing {sorted(commands - set(checker.CATALOG_COMMANDS))}, "
                   f"stale {sorted(set(checker.CATALOG_COMMANDS) - commands)}")
    if reference is not None:
        names = {t.get("name") for t in reference["vendors"]["claude-code"].get("tools", [])}
        missing = sorted(n for n in names - set(checker.KNOWN_TOOLS) if n)
        if missing:
            out.append(f"tool catalog drift: models-and-tools.json lists {missing}, which "
                       "harness-check.py KNOWN_TOOLS would report as unknown")
    return out


# -------------------------------------------------------------------------------- matrix
def scaffold(target: pathlib.Path, vars_: dict, flags: list[str], flavor: str) -> tuple[int, str]:
    v = json.loads(json.dumps(vars_))
    v["flags"] = [flavor] + flags
    # Audit mode needs the workspace layout it protects; the other combos ignore these.
    v["vars"].setdefault("REPO_DIR_LIST", "repos/app")
    v["vars"].setdefault("WORKSPACE_ROOT", ".")
    v["vars"]["HOOK_RUNNER"] = ("bash" if flavor == "posix"
                                else "powershell -NoProfile -ExecutionPolicy Bypass -File")
    v["vars"]["HOOK_EXT"] = "sh" if flavor == "posix" else "ps1"
    vf = target.parent / f"{target.name}.vars.json"
    vf.write_text(json.dumps(v), encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCAFFOLD), "--target", str(target), "--vars", str(vf)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout + r.stderr


def validate(target: pathlib.Path) -> list[dict]:
    r = subprocess.run([sys.executable, str(CHECKER), "--target", str(target), "--json",
                        "--stage", "scaffold"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(r.stdout)["findings"]
    except (ValueError, KeyError):
        return [{"check": "harness-check", "file": None, "line": None,
                 "message": f"harness-check.py did not produce JSON (exit {r.returncode}): "
                            f"{(r.stderr or r.stdout)[-400:]}", "fix": "run it by hand"}]


def crlf_files(target: pathlib.Path) -> list[str]:
    """-> the text files under `target` holding a CRLF line ending, relative to it.

    Scaffold output is LF everywhere, whatever line endings the skill's own checkout holds, so a
    harness scaffolded on Windows is byte-identical to one scaffolded on Linux. Binary files (a NUL
    byte, or not UTF-8) are skipped: a CR-LF pair inside an image is not a line ending.
    """
    out = []
    for p in sorted(target.rglob("*")):
        if not p.is_file() or ".git" in p.relative_to(target).parts:
            continue
        data = p.read_bytes()
        if b"\r\n" not in data or b"\0" in data:
            continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        out.append(p.relative_to(target).as_posix())
    return out


def run_matrix(combos, work: pathlib.Path) -> tuple[dict, list[str]]:
    """-> ({(check, file, line, message, fix): [combo names]}, scaffold failures)."""
    vars_ = base_vars()
    seen: dict[tuple, list[str]] = {}
    failures: list[str] = []
    for name, flags in combos:
        for flavor in FLAVORS:
            label = f"{name}/{flavor}"
            target = work / label.replace("/", "-")
            rc, log = scaffold(target, vars_, flags, flavor)
            if rc not in (0, 1) or "UNRESOLVED VARIABLES" in log or not (target / ".claude").is_dir():
                failures.append(f"{label}: scaffold exited {rc}: {log.strip()[-300:]}")
                continue
            for f in validate(target):
                key = (f["check"], f["file"], f["line"], f["message"], f["fix"])
                seen.setdefault(key, []).append(label)
            for rel in crlf_files(target):
                key = ("crlf", rel, None, "scaffolded with CRLF line endings; every harness file "
                       "is LF", "write it through scaffold.py's LF normalisation, not byte for byte")
                seen.setdefault(key, []).append(label)
    return seen, failures


# ----------------------------------------------------------------------------- self-test
def self_test(checker) -> list[str]:
    dead: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a = pathlib.Path(tmp) / "assets"
        good = {
            "claude/agents/orchestrator.md": "x", "claude/agents/dev-agent.md": "x",
            "claude/commands/test.md": "x",
            "claude/hooks/g.sh": "x", "claude/hooks/g.ps1": "x",
        }
        for rel, body in good.items():
            (a / rel).parent.mkdir(parents=True, exist_ok=True)
            (a / rel).write_text(body, encoding="utf-8")
        man = [{"src": "claude/agents/orchestrator.md"}, {"src": "claude/commands/test.md"},
               {"src": "claude/hooks/g.sh", "when": ["posix"], "exec": True},
               {"src": "claude/hooks/g.ps1", "when": ["windows"]}]

        class Cat:
            CATALOG_SEATS = ("orchestrator",)
            CATALOG_COMMANDS = ("test",)
            KNOWN_TOOLS = {"Read"}
        ref = {"vendors": {"claude-code": {"tools": [{"name": "Read"}]}}}
        if coverage_problems(a, man, Cat, ref):
            dead.append(f"clean synthetic assets report problems: "
                        f"{coverage_problems(a, man, Cat, ref)}")

        def fires(label, prefix, assets_fn=None, man2=None, cat=Cat, ref2=ref):
            if assets_fn:
                assets_fn()
            got = coverage_problems(a, man2 if man2 is not None else man, cat, ref2)
            if not any(g.startswith(prefix) for g in got):
                dead.append(f"{label}: expected `{prefix}`, got {got}")

        stray = a / "claude/rules/stray.md"
        fires("unlisted asset", "unlisted asset",
              lambda: (stray.parent.mkdir(parents=True, exist_ok=True),
                       stray.write_text("x", encoding="utf-8")))
        stray.unlink()
        fires("missing src", "missing src", man2=man + [{"src": "claude/rules/gone.md"}])
        fires("no exec", "not executable",
              man2=[e if not e["src"].endswith(".sh") else {**e, "exec": False} for e in man])
        fires("one flavor", "one flavor", man2=[e for e in man if not e["src"].endswith(".ps1")])
        fires("flavor flags", "flavor flags differ",
              man2=[e if not e["src"].endswith(".ps1") else {**e, "when": ["windows", "db"]}
                    for e in man])

        class SeatDrift(Cat):
            CATALOG_SEATS = ("orchestrator", "ghost")
        fires("seat catalog", "seat catalog drift", cat=SeatDrift)

        class CmdDrift(Cat):
            CATALOG_COMMANDS = ()
        fires("command catalog", "command catalog drift", cat=CmdDrift)
        fires("tool catalog", "tool catalog drift",
              ref2={"vendors": {"claude-code": {"tools": [{"name": "Frobnicate"}]}}})

        # The matrix half: a real scaffold with a registered hook deleted must be reported.
        work = pathlib.Path(tmp) / "m"
        work.mkdir()
        target = work / "t"
        rc, log = scaffold(target, base_vars(), [], "posix")
        hook = target / ".claude" / "hooks" / "protect-secrets.sh"
        if not hook.is_file():
            dead.append(f"matrix self-test could not scaffold (exit {rc}): {log[-300:]}")
        else:
            hook.unlink()
            if not any(f["check"] == "hook-missing" for f in validate(target)):
                dead.append("matrix validation did not report a deleted, registered hook")
            # The CRLF scan: a real scaffold is clean, one CRLF text file is reported, and a
            # binary file holding the same bytes is not.
            stray = crlf_files(target)
            if stray:
                dead.append(f"the scaffolder itself wrote CRLF, so the crlf scan has no clean "
                            f"baseline: {stray[:4]}")
            (target / "docs" / "crlf.md").write_bytes(b"one\r\ntwo\r\n")
            # Valid UTF-8 apart from the NUL, so the NUL test is what keeps it out.
            (target / "docs" / "blob.bin").write_bytes(b"\0\r\nPNG\r\n")
            got = crlf_files(target)
            if "docs/crlf.md" not in got:
                dead.append("the crlf scan did not report a CRLF text file")
            if "docs/blob.bin" in got:
                dead.append("the crlf scan reported a binary file as a CRLF text file")
    r = subprocess.run([sys.executable, str(CHECKER), "--self-test"], capture_output=True,
                       text=True)
    if r.returncode != 0:
        dead.append("harness-check.py --self-test failed:\n" + r.stdout + r.stderr)
    return dead


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quick", action="store_true", help="one combination per flavor pair")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    checker = load_checker()

    dead = self_test(checker)
    if dead:
        print("DEAD CHECK - check_integration cannot be trusted:")
        for d in dead:
            print(f"  {d}")
        return 1
    if not args.json:
        print("self-test: ok - every coverage detector, the matrix validation and "
              "harness-check.py's own detectors fire on their mutants")

    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))["files"]
    ref = json.loads(REFERENCE.read_text(encoding="utf-8")) if REFERENCE.is_file() else None
    cov = coverage_problems(ASSETS, manifest, checker, ref)

    combos = [c for c in COMBOS if not args.quick or c[0] in QUICK]
    work = pathlib.Path(tempfile.mkdtemp(prefix="check-integration-"))
    try:
        seen, failures = run_matrix(combos, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    total = len(combos) * len(FLAVORS)

    if args.json:
        print(json.dumps({
            "coverage": cov, "scaffold_failures": failures, "harnesses": total,
            "findings": [{"check": k[0], "file": k[1], "line": k[2], "message": k[3],
                          "fix": k[4], "in": v} for k, v in sorted(seen.items(),
                                                                   key=lambda kv: str(kv[0]))],
        }, indent=2))
    else:
        print(f"\ncoverage (assets vs manifest vs harness-check catalogs): "
              f"{'clean' if not cov else f'{len(cov)} problem(s)'}")
        for c in cov:
            print(f"  FAIL  {c}")
        print(f"\nmatrix: {total} harnesses scaffolded and checked")
        for f in failures:
            print(f"  FAIL  scaffold {f}")
        for (check, file, line, msg, fix), where in sorted(seen.items(), key=lambda kv: str(kv[0])):
            loc = f"{file}:{line}" if file and line else (file or "-")
            shown = ", ".join(where[:4]) + (f" +{len(where) - 4}" if len(where) > 4 else "")
            print(f"  FAIL  [{check}] {loc}  {msg}\n          fix: {fix}\n          in: {shown}")
        if not seen and not failures:
            print("  ok    every harness validates clean")
    return 1 if (cov or seen or failures) else 0


if __name__ == "__main__":
    sys.exit(main())
