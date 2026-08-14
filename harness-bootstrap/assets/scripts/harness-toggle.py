#!/usr/bin/env python3
"""Turn rules, commands, and hooks on or off at runtime - reversibly.

The only sanctioned mutator for enable/disable state. Mechanics:

  rule/command  .claude/rules/X.md      <->  .claude/disabled/rules/X.md
                .claude/commands/X.md   <->  .claude/disabled/commands/X.md
  hook          .claude/hooks/X.{sh,ps1} ->  .claude/disabled/hooks/  AND its
                settings.json registration objects are removed; the removed
                objects (with their event/matcher/position) are saved verbatim
                in .claude/disabled.json so `enable` restores them exactly.

.claude/disabled.json is a COMMITTED file (the team shares it; scaffold re-runs
read it and skip re-adding what it lists). It is written canonically: sorted
keys, indent 2, trailing newline, no dates. settings.json is rewritten with
indent 2 preserving key order - the first toggle normalizes its formatting,
after which disable/enable round-trips are byte-identical.

Safety tiers (hardcoded, not configurable):
  HARD - protect-secrets, guard-agent-spawn hooks; security-privacy,
         agent-guardrails rules; the review-changes command. Disabling needs
         --confirm "disable <name>" typed literally by the USER.
  SOFT - guard-main-commit, check-commit-msg, protect-adr hooks; the
         ai-governance rule. Disabling needs --yes.
Agents are never toggled here - roster changes go through /harness-update.

Usage:
  python .claude/scripts/harness-toggle.py list [--target <root>]
  python .claude/scripts/harness-toggle.py disable rule/performance --reason "..."
  python .claude/scripts/harness-toggle.py enable  hook/specs-reminder
  python .claude/scripts/harness-toggle.py reapply

Exit codes: 0 ok, 1 error, 2 safety refusal. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

KINDS = ("rule", "command", "hook")
DIRS = {"rule": "rules", "command": "commands", "hook": "hooks"}

HARD = {"hook/protect-secrets", "hook/guard-agent-spawn",
        "rule/security-privacy", "rule/agent-guardrails",
        "command/review-changes"}
SOFT = {"hook/guard-main-commit", "hook/check-commit-msg",
        "hook/protect-adr", "rule/ai-governance"}


def die(msg: str, code: int = 1) -> int:
    print(msg, file=sys.stderr)
    return code


def load_json(p: pathlib.Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_atomic(p: pathlib.Path, text: str) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(p)


def write_disabled(claude: pathlib.Path, entries: list[dict]) -> None:
    entries = sorted(entries, key=lambda e: (e["kind"], e["name"]))
    write_atomic(claude / "disabled.json",
                 json.dumps({"disabled": entries, "version": 1},
                            indent=2, sort_keys=True) + "\n")


def read_disabled(claude: pathlib.Path) -> list[dict]:
    data = load_json(claude / "disabled.json")
    if isinstance(data, dict) and isinstance(data.get("disabled"), list):
        return [e for e in data["disabled"]
                if isinstance(e, dict) and e.get("kind") and e.get("name")]
    return []


def write_settings(claude: pathlib.Path, data: dict) -> None:
    # indent 2, key order preserved (NOT sorted - order is semantic here)
    write_atomic(claude / "settings.json", json.dumps(data, indent=2) + "\n")


def item_files(claude: pathlib.Path, kind: str, name: str,
               disabled: bool) -> list[pathlib.Path]:
    base = claude / "disabled" / DIRS[kind] if disabled else claude / DIRS[kind]
    if kind == "hook":
        return [p for p in (base / f"{name}.sh", base / f"{name}.ps1") if p.is_file()]
    p = base / f"{name}.md"
    return [p] if p.is_file() else []


def strip_registration(settings: dict, name: str) -> list[dict]:
    """Remove every hook object whose command references hooks/<name>. and
    return the removed objects with their coordinates (for exact restore)."""
    removed: list[dict] = []
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return removed
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for gi, g in enumerate(groups):
            if not isinstance(g, dict):
                continue
            kept = []
            for hi, h in enumerate(g.get("hooks") or []):
                cmd = h.get("command", "") if isinstance(h, dict) else ""
                if f"hooks/{name}." in cmd.replace("\\", "/"):
                    removed.append({"event": event,
                                    "matcher": g.get("matcher", "*"),
                                    "group_index": gi, "hook_index": hi,
                                    "hook": h})
                else:
                    kept.append(h)
            g["hooks"] = kept
        hooks[event] = [g for g in groups
                        if not isinstance(g, dict) or g.get("hooks")]
    return removed


def restore_registration(settings: dict, regs: list[dict]) -> None:
    hooks = settings.setdefault("hooks", {})
    for r in regs:
        event, matcher = r.get("event"), r.get("matcher", "*")
        groups = hooks.setdefault(event, [])
        group = next((g for g in groups if isinstance(g, dict)
                      and g.get("matcher", "*") == matcher), None)
        if group is None:
            group = {"matcher": matcher, "hooks": []}
            groups.insert(min(r.get("group_index", len(groups)), len(groups)),
                          group)
        arr = group.setdefault("hooks", [])
        arr.insert(min(r.get("hook_index", len(arr)), len(arr)), r["hook"])


def regen_graph(root: pathlib.Path) -> None:
    """Re-run harness-graph.py --html in-process; script-driven mutations do
    not fire the Edit/Write graph-stale hook, so the graph is refreshed here."""
    hg = root / ".claude" / "scripts" / "harness-graph.py"
    if not hg.is_file():
        return
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location("harness_graph", hg)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        old = sys.argv
        sys.argv = ["harness-graph.py", "--target", str(root), "--html", "--quiet"]
        try:
            mod.main()
        finally:
            sys.argv = old
    except Exception:
        pass  # the graph is a view; never fail a toggle over it


def inventory(claude: pathlib.Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for kind, sub in DIRS.items():
        for state, base in (("active", claude / sub),
                            ("disabled", claude / "disabled" / sub)):
            names = set()
            if base.is_dir():
                pats = ("*.sh", "*.ps1") if kind == "hook" else ("*.md",)
                for pat in pats:
                    names.update(p.stem for p in base.glob(pat))
            out.setdefault(state, []).extend(f"{kind}/{n}" for n in sorted(names))
    return out


def cmd_list(claude: pathlib.Path) -> int:
    inv = inventory(claude)
    entries = {f"{e['kind']}/{e['name']}": e for e in read_disabled(claude)}
    print("active:")
    for item in inv.get("active", []):
        print(f"  {item}")
    print("disabled:")
    for item in inv.get("disabled", []):
        why = entries.get(item, {}).get("reason", "")
        print(f"  {item}" + (f"  ({why})" if why else ""))
    if not inv.get("disabled"):
        print("  (none)")
    return 0


def parse_item(item: str) -> tuple[str, str]:
    if "/" not in item:
        raise ValueError(f"expected <kind>/<name>, got `{item}`")
    kind, name = item.split("/", 1)
    kind = {"cmd": "command"}.get(kind, kind)
    if kind == "agent":
        raise ValueError("agents are not toggled here - roster changes go "
                         "through /harness-update (routing row first)")
    if kind not in KINDS:
        raise ValueError(f"unknown kind `{kind}` - use rule|command|hook")
    return kind, name


def check_safety(kind: str, name: str, confirm: str | None, yes: bool) -> int:
    key = f"{kind}/{name}"
    if key in HARD:
        want = f"disable {name}"
        if confirm != want:
            return die(
                f"{key} is a HARD-protected control. Disabling it removes a "
                f"guardrail the rest of the harness assumes.\n"
                f"If the USER really wants this, they must type the phrase "
                f"`{want}` and it must be passed as:\n"
                f"  --confirm \"{want}\"\n"
                f"Never synthesize this phrase on the user's behalf.", 2)
    elif key in SOFT and not yes:
        return die(f"{key} is a protected control - re-run with --yes to "
                   f"confirm the user asked for this.", 2)
    return 0


def do_disable(root: pathlib.Path, kind: str, name: str, reason: str) -> int:
    claude = root / ".claude"
    files = item_files(claude, kind, name, disabled=False)
    if not files:
        inv = inventory(claude)
        return die(f"no active {kind} named `{name}`.\nactive: "
                   + ", ".join(inv.get("active", [])))
    entries = read_disabled(claude)
    if any(e["kind"] == kind and e["name"] == name for e in entries):
        return die(f"{kind}/{name} is already listed in disabled.json - "
                   f"run `reapply` if its files came back.")

    entry: dict = {"kind": kind, "name": name,
                   "from": f".claude/{DIRS[kind]}/{files[0].name}",
                   "reason": reason or ""}
    if kind == "hook":
        settings = load_json(claude / "settings.json")
        if isinstance(settings, dict):
            regs = strip_registration(settings, name)
            if regs:
                entry["registration"] = regs
                write_settings(claude, settings)

    qdir = claude / "disabled" / DIRS[kind]
    qdir.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.move(str(f), str(qdir / f.name))
    entries.append(entry)
    write_disabled(claude, entries)
    regen_graph(root)
    print(f"disabled {kind}/{name}"
          + (f" ({len(entry.get('registration', []))} registration(s) removed)"
             if kind == "hook" else ""))
    return 0


def do_enable(root: pathlib.Path, kind: str, name: str) -> int:
    claude = root / ".claude"
    entries = read_disabled(claude)
    entry = next((e for e in entries
                  if e["kind"] == kind and e["name"] == name), None)
    files = item_files(claude, kind, name, disabled=True)
    if entry is None and not files:
        return die(f"{kind}/{name} is not disabled.")

    adir = claude / DIRS[kind]
    adir.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.move(str(f), str(adir / f.name))
    if kind == "hook" and entry and entry.get("registration"):
        settings = load_json(claude / "settings.json")
        if isinstance(settings, dict):
            restore_registration(settings, entry["registration"])
            write_settings(claude, settings)
    if entry:
        entries.remove(entry)
        write_disabled(claude, entries)
    regen_graph(root)
    print(f"enabled {kind}/{name}")
    return 0


def do_reapply(root: pathlib.Path) -> int:
    """Repair verb: after a scaffold --force or a hand edit resurrected a
    disabled item, quarantine it again and re-strip its registration."""
    claude = root / ".claude"
    entries = read_disabled(claude)
    if not entries:
        print("disabled.json is empty - nothing to reapply.")
        return 0
    fixed = 0
    settings = load_json(claude / "settings.json")
    for e in entries:
        kind, name = e["kind"], e["name"]
        for f in item_files(claude, kind, name, disabled=False):
            qdir = claude / "disabled" / DIRS[kind]
            qdir.mkdir(parents=True, exist_ok=True)
            quarantined = qdir / f.name
            if quarantined.is_file():
                f.unlink()   # pristine scaffold copy; the quarantined one is
                             # the user's - keep it
            else:
                shutil.move(str(f), str(quarantined))
            fixed += 1
        if kind == "hook" and isinstance(settings, dict):
            regs = strip_registration(settings, name)
            if regs and not e.get("registration"):
                e["registration"] = regs
            if regs:
                fixed += 1
    if isinstance(settings, dict):
        write_settings(claude, settings)
    write_disabled(claude, entries)
    regen_graph(root)
    print(f"reapply: {fixed} correction(s) for {len(entries)} disabled item(s).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Toggle rules/commands/hooks.")
    ap.add_argument("verb", choices=("disable", "enable", "list", "reapply"))
    ap.add_argument("item", nargs="?", help="<kind>/<name>, e.g. rule/performance")
    ap.add_argument("--reason", default="", help="recorded in disabled.json")
    ap.add_argument("--confirm", default=None,
                    help='HARD items: the literal phrase `disable <name>`, typed by the user')
    ap.add_argument("--yes", action="store_true", help="SOFT items: confirm")
    ap.add_argument("--target", type=pathlib.Path, default=pathlib.Path("."))
    a = ap.parse_args()

    root = a.target.resolve()
    if not (root / ".claude").is_dir():
        return die(f"no .claude/ under {root}")

    if a.verb == "list":
        return cmd_list(root / ".claude")
    if a.verb == "reapply":
        return do_reapply(root)
    if not a.item:
        return die("disable/enable need an item: <kind>/<name>")
    try:
        kind, name = parse_item(a.item)
    except ValueError as e:
        return die(str(e))
    if a.verb == "disable":
        rc = check_safety(kind, name, a.confirm, a.yes)
        if rc:
            return rc
        return do_disable(root, kind, name, a.reason)
    return do_enable(root, kind, name)


if __name__ == "__main__":
    sys.exit(main())
