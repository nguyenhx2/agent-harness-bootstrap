#!/usr/bin/env python3
"""Turn rules, commands, and hooks on or off at runtime - reversibly.

The only sanctioned mutator for enable/disable state. Mechanics:

  rule/command/ .claude/rules/X.md      <->  .claude/disabled/rules/X.md
  agent         .claude/commands/X.md   <->  .claude/disabled/commands/X.md
                .claude/agents/X.md     <->  .claude/disabled/agents/X.md
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
         agent-guardrails rules; the review-changes command; the orchestrator
         and reviewer SEATS. Disabling needs --confirm "disable <name>" typed
         literally by the USER.
  SOFT - guard-main-commit, check-commit-msg, protect-adr hooks; the
         ai-governance rule; and EVERY agent seat, by category rather than by
         name - parking a seat the routing table still lists is a dispatch to
         nowhere. Disabling needs --yes.
Parking a seat is reversible and recorded; ADDING or RETIRING one is still a
roster change and goes through /harness-update.

Parity: tools/harness-view/src/toggle.rs implements this same contract for the
native viewer. The tier tables and the confirmation phrase must match.

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
import re
import shutil
import sys

KINDS = ("rule", "command", "hook", "agent")
DIRS = {"rule": "rules", "command": "commands", "hook": "hooks",
        "agent": "agents"}

HARD = {"hook/protect-secrets", "hook/guard-agent-spawn",
        "rule/security-privacy", "rule/agent-guardrails",
        "command/review-changes",
        # the seats the rest of the harness assumes: only the orchestrator
        # spawns, and the review seats ARE the code-review gate
        "agent/orchestrator", "agent/code-reviewer",
        "agent/security-reviewer", "agent/reviewer", "agent/spec-guardian"}
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


class CorruptLedger(Exception):
    pass


def read_disabled(claude: pathlib.Path) -> list[dict]:
    """A missing ledger means nothing is disabled. A CORRUPT ledger must never
    be treated as empty - that would silently orphan every quarantine record -
    so it raises and the caller aborts."""
    p = claude / "disabled.json"
    if not p.is_file():
        return []
    data = load_json(p)
    if isinstance(data, dict) and isinstance(data.get("disabled"), list):
        return [e for e in data["disabled"]
                if isinstance(e, dict) and e.get("kind") and e.get("name")]
    raise CorruptLedger(f"{p} is unreadable - fix or delete it. Refusing to "
                        "proceed: treating a corrupt ledger as empty would "
                        "destroy the quarantine records it holds.")


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


def canonical_name(claude: pathlib.Path, kind: str, name: str) -> str:
    """Resolve the caller's name to the actual on-disk stem, case-insensitively.

    NTFS resolves paths without case, so `hook/Protect-Secrets` would move the
    real protect-secrets files while a case-SENSITIVE safety check waves it
    through. Canonicalizing first makes the guard and the move agree."""
    want = name.casefold()
    for base in (claude / DIRS[kind], claude / "disabled" / DIRS[kind]):
        if base.is_dir():
            for p in sorted(base.iterdir()):
                if p.is_file() and p.stem.casefold() == want:
                    return p.stem
    return name


def strip_registration(settings: dict, name: str) -> list[dict]:
    """Remove every hook object whose command references hooks/<name>. and
    return the removed objects with their coordinates (for exact restore)."""
    removed: list[dict] = []
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return removed
    needle = f"hooks/{name}.".casefold()
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        emptied: set[int] = set()
        for gi, g in enumerate(groups):
            if not isinstance(g, dict):
                continue
            orig = g.get("hooks") or []
            kept = []
            for hi, h in enumerate(orig):
                cmd = h.get("command", "") if isinstance(h, dict) else ""
                if needle in cmd.replace("\\", "/").casefold():
                    removed.append({"event": event,
                                    "matcher": g.get("matcher", "*"),
                                    "group_index": gi, "hook_index": hi,
                                    "hook": h})
                else:
                    kept.append(h)
            if orig and not kept and len(kept) != len(orig):
                emptied.add(gi)
            g["hooks"] = kept
        # only drop groups THIS strip emptied - a group that was already empty
        # belongs to someone else's state and is not ours to garbage-collect
        hooks[event] = [g for gi, g in enumerate(groups)
                        if not (gi in emptied and isinstance(g, dict)
                                and not g.get("hooks"))]
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
        if r["hook"] in arr:
            continue  # already registered (e.g. a hand re-add) - never duplicate
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


NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def parse_item(item: str) -> tuple[str, str]:
    if "/" not in item:
        raise ValueError(f"expected <kind>/<name>, got `{item}`")
    kind, name = item.split("/", 1)
    kind = {"cmd": "command"}.get(kind, kind)
    if kind not in KINDS:
        raise ValueError(f"unknown kind `{kind}` - use rule|command|hook")
    # The name becomes a path component. Reject separators and dot-dot so a
    # crafted name can never reach outside .claude/<dir>/.
    if ("/" in name or "\\" in name or ".." in name
            or not NAME_RE.match(name)):
        raise ValueError(f"invalid name `{name}` - a bare item name only "
                         "(letters, digits, dot, dash, underscore)")
    return kind, name


def check_safety(kind: str, name: str, confirm: str | None, yes: bool) -> int:
    # Membership is case-insensitive: the HARD/SOFT sets are lowercase and the
    # name has been canonicalized, but casefold again so a name that matched
    # no on-disk file (and so kept its typed case) still cannot slip the tier.
    key = f"{kind}/{name.casefold()}"
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
    elif (key in SOFT or kind == "agent") and not yes:
        # Agents are SOFT by category, not by name: whatever a seat is called,
        # the orchestrator's routing table still points at it.
        why = ("is a roster seat the routing table still lists"
               if kind == "agent" else "is a protected control")
        return die(f"{key} {why} - re-run with --yes to "
                   f"confirm the user asked for this.", 2)
    return 0


def do_disable(root: pathlib.Path, kind: str, name: str, reason: str) -> int:
    claude = root / ".claude"
    entries = read_disabled(claude)
    if any(e["kind"] == kind and e["name"] == name for e in entries):
        return die(f"{kind}/{name} is already disabled - "
                   f"run `reapply` if its files came back.")
    files = item_files(claude, kind, name, disabled=False)
    if not files:
        inv = inventory(claude)
        return die(f"no active {kind} named `{name}`.\nactive: "
                   + ", ".join(inv.get("active", [])))

    entry: dict = {"kind": kind, "name": name,
                   "from": f".claude/{DIRS[kind]}/{files[0].name}",
                   "reason": reason or ""}
    if kind == "hook":
        sj = claude / "settings.json"
        settings = load_json(sj)
        if sj.is_file() and not isinstance(settings, dict):
            # Proceeding would quarantine the files while the registration
            # stays live: a registered hook whose script is gone. Refuse.
            return die(f"cannot disable {kind}/{name}: {sj} exists but is "
                       "unreadable, so its registration cannot be removed. "
                       "Fix settings.json first.")
        if isinstance(settings, dict):
            regs = strip_registration(settings, name)
            if regs:
                entry["registration"] = regs
                write_settings(claude, settings)

    qdir = claude / "disabled" / DIRS[kind]
    qdir.mkdir(parents=True, exist_ok=True)
    for f in files:
        quarantined = qdir / f.name
        if quarantined.is_file():
            # A stale copy already sits in quarantine (e.g. after a hand
            # edit). Keep the active file's content - it is current.
            quarantined.unlink()
        shutil.move(str(f), str(quarantined))
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

    # The mirror of the case below, and the one that was missing: a ledger entry with NO
    # quarantined files. Enabling moved nothing, restored the settings.json registration, and
    # consumed the record - leaving every matching tool call pointed at a script that is not
    # there, with no ledger left for `reapply` to repair from. Refuse, and keep the record.
    if entry is not None and not files:
        return die(f"cannot enable {kind}/{name}: its ledger entry exists but no file is "
                   f"quarantined under .claude/disabled/{DIRS[kind]}/. Restoring the "
                   "registration would point it at a missing script. Put the file back, or "
                   "drop the entry from .claude/disabled.json by hand. The record is kept.")

    # A hook's saved registration must be restorable BEFORE anything moves:
    # dropping the record while settings.json is missing or unparseable would
    # leave the hook permanently unregistered while reporting success.
    settings = None
    if kind == "hook" and entry and entry.get("registration"):
        settings = load_json(claude / "settings.json")
        if not isinstance(settings, dict):
            return die(f"cannot enable {kind}/{name}: .claude/settings.json is "
                       "missing or unreadable, so its saved registration cannot "
                       "be restored. Fix settings.json first - the disabled.json "
                       "record has been kept.")

    adir = claude / DIRS[kind]
    adir.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.move(str(f), str(adir / f.name))
    if settings is not None:
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
    settings_changed = False
    settings = load_json(claude / "settings.json")
    for e in entries:
        kind, name = e["kind"], e["name"]
        if kind not in DIRS:
            print(f"  [warn] disabled.json entry with unknown kind "
                  f"`{kind}/{name}` - skipped", file=sys.stderr)
            continue
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
                settings_changed = True
                fixed += 1
    if settings_changed and isinstance(settings, dict):
        write_settings(claude, settings)
    if fixed:
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

    try:
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
        # resolve the typed name to the real on-disk case (NTFS-safe) so the
        # safety tier, the file move, and the registration strip all agree
        name = canonical_name(root / ".claude", kind, name)
        if a.verb == "disable":
            rc = check_safety(kind, name, a.confirm, a.yes)
            if rc:
                return rc
            return do_disable(root, kind, name, a.reason)
        return do_enable(root, kind, name)
    except CorruptLedger as e:
        return die(str(e))


if __name__ == "__main__":
    sys.exit(main())
