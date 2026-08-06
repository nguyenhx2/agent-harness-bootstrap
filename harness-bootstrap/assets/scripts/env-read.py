#!/usr/bin/env python3
"""Work with local env files WITHOUT their values ever entering the conversation.

The secrets hook blocks reading `.env*` outright, and that is correct as a default: a value an
agent reads is a value in the transcript, the archive, and the provider's logs forever. But a
devops, db, or qa seat has legitimate needs - does DATABASE_URL exist in .env.test, is the port a
number, run the migration with .env.local loaded - and blocking those pushes people to disable the
hook, which is worse.

This script is the sanctioned path: values are read into THIS PROCESS and never printed. What
comes back is presence, shape, and exit codes.

  list    which variables are defined (names only, never values)
  check   does a variable match a shape (regex), yes or no
  diff    which keys does .env.example promise that this file lacks, and vice versa
  run     execute a command with the file's variables loaded into its environment

Production is never a target: a file whose name says prod/production/live, or one outside the
repo, is refused outright. Values are redacted even in error messages.

  python .claude/scripts/env-read.py list .env.local
  python .claude/scripts/env-read.py check .env.test DATABASE_URL '^postgres://'
  python .claude/scripts/env-read.py diff .env.local
  python .claude/scripts/env-read.py run .env.test -- npm run test:integration
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys

PROD_RE = re.compile(r"(^|[.\-_])(prod|production|live|release)([.\-_]|$)", re.I)
LINE_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")


def refuse(msg: str) -> int:
    print(f"REFUSED: {msg}", file=sys.stderr)
    return 2


def resolve(target: str) -> tuple[pathlib.Path | None, str]:
    p = pathlib.Path(target)
    root = pathlib.Path.cwd().resolve()
    try:
        full = (root / p).resolve() if not p.is_absolute() else p.resolve()
    except OSError:
        return None, "unreadable path"
    if root not in full.parents and full != root:
        return None, "the file is outside this repo"
    if PROD_RE.search(full.name):
        return None, (f"{full.name} names a production environment. Production values are not read "
                      "by agents through any path, including this one.")
    if not full.is_file():
        return None, f"{target} does not exist"
    return full, ""


def parse(path: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = LINE_RE.match(raw)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
    return out


def shape(val: str) -> str:
    """A description of the value that leaks nothing: length and character classes only."""
    if not val:
        return "empty"
    kinds = []
    if re.search(r"[A-Za-z]", val):
        kinds.append("alpha")
    if re.search(r"\d", val):
        kinds.append("digits")
    if re.search(r"[^A-Za-z0-9]", val):
        kinds.append("symbols")
    return f"{len(val)} chars, {'+'.join(kinds)}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="variable names and value shapes, never values")
    p_list.add_argument("file")

    p_check = sub.add_parser("check", help="does KEY match REGEX (prints yes/no, never the value)")
    p_check.add_argument("file")
    p_check.add_argument("key")
    p_check.add_argument("regex")

    p_diff = sub.add_parser("diff", help="keys .env.example promises vs keys this file defines")
    p_diff.add_argument("file")
    p_diff.add_argument("--example", default=".env.example")

    p_run = sub.add_parser("run", help="run a command with the file's variables loaded")
    p_run.add_argument("file")
    p_run.add_argument("argv", nargs=argparse.REMAINDER)

    args = ap.parse_args()
    path, why = resolve(args.file)
    if path is None:
        return refuse(why)

    if args.cmd == "list":
        env = parse(path)
        print(f"{path.name}: {len(env)} variable(s). Names and shapes only - no values.")
        for k in sorted(env):
            print(f"  {k:<32} {shape(env[k])}")
        return 0

    if args.cmd == "check":
        env = parse(path)
        if args.key not in env:
            print(f"NO: {args.key} is not defined in {path.name}")
            return 1
        ok = re.search(args.regex, env[args.key]) is not None
        print(f"{'YES' if ok else 'NO'}: {args.key} "
              f"{'matches' if ok else 'does not match'} the expected shape "
              f"({shape(env[args.key])})")
        return 0 if ok else 1

    if args.cmd == "diff":
        env = parse(path)
        ex_path, why = resolve(args.example)
        if ex_path is None:
            return refuse(f"{args.example}: {why}")
        ex = parse(ex_path)
        missing = sorted(set(ex) - set(env))
        extra = sorted(set(env) - set(ex))
        print(f"{path.name} vs {ex_path.name}:")
        print(f"  missing here ({len(missing)}): {', '.join(missing) or '-'}")
        print(f"  undocumented in the example ({len(extra)}): {', '.join(extra) or '-'}")
        return 1 if missing else 0

    if args.cmd == "run":
        argv = [a for a in args.argv if a != "--"]
        if not argv:
            return refuse("no command given after --")
        file_env = parse(path)
        merged = dict(os.environ)
        merged.update(file_env)
        print(f"running with {path.name} loaded ({len(file_env)} variables, values not shown): "
              f"{' '.join(argv)}")
        r = subprocess.run(argv, env=merged)
        return r.returncode

    return 2


if __name__ == "__main__":
    sys.exit(main())
