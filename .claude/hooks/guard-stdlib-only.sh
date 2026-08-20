#!/usr/bin/env bash
# guard-stdlib-only.sh - THIS REPO's own hook, not a shipped asset.
# Event: PreToolUse   Matcher: Edit|Write
#
# CONTRIBUTING.md promises that every gate runs straight from a clone: "Everything here runs on
# stdlib Python 3.13 - no `pip install` needed to run a gate." No workflow in .github/workflows/
# installs anything, so that promise is load-bearing rather than aspirational: the moment a gate
# imports a third-party module, that job ends with an ImportError on the next push and the gate
# stops gating.
#
# This is not hypothetical. PR #18 proposed swapping `xml.etree` for `defusedxml` in
# scripts/check_svg.py, for an XXE that stdlib ElementTree already refuses. It carried no CI run,
# and merging it would have killed the SVG gate in CI while fixing nothing.
#
# So: an import added to a gate script must be stdlib, or a module that lives in this repository.
# Blocking - exit 2 - because the alternative is a green review and a red pipeline.
#
# The single documented exception is scripts/check_mermaid.py, which shells out to
# `npx @mermaid-js/mermaid-cli`. That is a subprocess, not an import, so it never reaches here.
set -u

payload=$(cat)

# Extract a dotted key from the hook payload. Same three-way fallback as media-sync-reminder.sh:
# jq is not guaranteed on a contributor's machine, and a hook that cannot read its own input
# silently allows everything.
json_str() {
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$payload" | jq -r --arg k "$1" 'getpath($k | split(".")) // empty' 2>/dev/null
  elif command -v python3 >/dev/null 2>&1; then
    printf '%s' "$payload" | python3 -c 'import json,sys
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
for p in sys.argv[1].split("."):
    d = d.get(p) if isinstance(d, dict) else None
    if d is None: break
sys.stdout.write(d if isinstance(d, str) else "")' "$1" 2>/dev/null
  elif command -v perl >/dev/null 2>&1; then
    printf '%s' "$payload" | perl -0777 -MJSON::PP -e 'my $k=shift; local $/; my $d=eval{decode_json(<STDIN>)}; exit 0 unless $d; for my $p (split /\./,$k){ $d = (ref($d) eq "HASH") ? $d->{$p} : undef; last unless defined $d } print $d if defined $d && !ref $d' "$1" 2>/dev/null
  fi
}

path=$(json_str tool_input.file_path)
[ -z "$path" ] && exit 0
norm=${path//\\//}

# Only the scripts that run as gates, and only THIS repository's own. The match is anchored to the
# project root rather than matching `*/scripts/*.py` anywhere in the path: the skills ship
# harness-bootstrap/assets/scripts/*.py as templates for OTHER projects, which are free to depend on
# whatever their stack already uses. An unanchored pattern blocked those too - caught by
# test-hooks.sh, which is the entire reason that file exists.
# Both sides need normalising before they can be compared. On Windows the tool reports
# `C:\repo\scripts\x.py` while the shell's $PWD is `/c/repo` - same directory, no common prefix,
# and a naive comparison quietly matches nothing, which is a guard that allows everything.
norm_path() {  # -> forward slashes, `/c/x` as `c:/x`, lowercased, no trailing slash
  local p=${1//\\//}
  case "$p" in
    /[A-Za-z]/*) p="${p:1:1}:${p:2}" ;;
  esac
  p=$(printf '%s' "$p" | tr '[:upper:]' '[:lower:]')
  printf '%s' "${p%/}"
}
root=$(norm_path "${CLAUDE_PROJECT_DIR:-$PWD}")
cmp=$(norm_path "$norm")
case "$cmp" in
  "$root"/scripts/*.py|"$root"/eval/*.py|"$root"/benchmark/*.py) ;;
  *) exit 0 ;;
esac
case "$norm" in
  */node_modules/*) exit 0 ;;
esac

# Edit carries new_string, Write carries content. Reading both means neither tool is a way past.
added=$(json_str tool_input.new_string)
[ -z "$added" ] && added=$(json_str tool_input.content)
[ -z "$added" ] && exit 0

python3 - "$added" <<'PY'
import pathlib
import sys

added = sys.argv[1]
root = pathlib.Path(__file__).resolve().parent.parent.parent if "__file__" in dir() else pathlib.Path.cwd()
root = pathlib.Path.cwd()

# Top-level module of every import statement in the added text. A dotted import is judged by its
# root package: `import xml.etree.ElementTree` is stdlib because `xml` is.
mods = set()
for raw in added.splitlines():
    line = raw.strip()
    if line.startswith("import "):
        for part in line[7:].split(","):
            name = part.strip().split(" as ")[0].strip().split(".")[0]
            if name:
                mods.add(name)
    elif line.startswith("from ") and " import " in line:
        name = line[5:].split(" import ")[0].strip()
        if name.startswith("."):      # relative import, local by definition
            continue
        name = name.split(".")[0]
        if name:
            mods.add(name)

if not mods:
    sys.exit(0)

stdlib = set(sys.stdlib_module_names)
# A module that exists in this repository is local, not a dependency.
local = {p.stem for p in root.rglob("*.py") if "node_modules" not in p.parts}
local |= {p.name for p in root.rglob("*") if p.is_dir() and (p / "__init__.py").exists()}
local.add("__future__")

foreign = sorted(m for m in mods if m not in stdlib and m not in local)
if foreign:
    names = ", ".join(f"`{m}`" for m in foreign)
    print(
        f"BLOCKED: this edit imports {names} into a gate script.\n"
        "\n"
        "CONTRIBUTING.md promises every gate runs straight from a clone with no `pip install`,\n"
        "and no workflow in .github/workflows/ installs anything - so a third-party import here\n"
        "ends that CI job with an ImportError and the gate stops gating. This is how PR #18 would\n"
        "have killed the SVG gate.\n"
        "\n"
        "Solve it with the standard library, or shell out to the tool as a subprocess the way\n"
        "scripts/check_mermaid.py calls `npx @mermaid-js/mermaid-cli`. If a dependency is genuinely\n"
        "the only answer, that is a decision to make with the repository owner first: it changes a\n"
        "promise the README makes to every contributor.",
        file=sys.stderr,
    )
    sys.exit(2)
PY
exit $?
