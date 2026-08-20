#!/usr/bin/env bash
# guard-agent-scope.sh
# Event: PreToolUse   Matcher: Edit|Write
#
# ADVISORY, NOT ENFORCED - and that is a deliberate finding, not a shortcut. Before writing this
# hook we checked whether a PreToolUse payload for Edit|Write identifies the calling subagent, the
# way it would have to in order to BLOCK a write to a module a different seat owns. It does not.
# Evidence, from this harness's own hooks:
#   - agent-history.sh's header states plainly: subagent identity (agent_type, agent_id) arrives
#     ONLY on the SubagentStop event, and that event's payload carries NO tool_input/tool_response
#     at all - an earlier version of that hook was registered on PostToolUse and archived empty
#     files because of exactly this gap.
#   - guard-agent-spawn.sh reads tool_input.subagent_type, but only because IT fires on the
#     Agent|Task tool call itself (the dispatch), not on the dispatched agent's own subsequent tool
#     calls. Once a subagent starts working, its Edit/Write calls carry cwd and tool_input
#     (file_path, content) and nothing that names who is typing.
# So a hook on THIS event cannot tell "code-reviewer editing outside its lane" from "the
# orchestrator's own docs/ maintenance" from "the one dev agent this project has". Blocking on data
# that is not there would either block legitimate writes indiscriminately or silently no-op - both
# worse than an honest advisory. See hooks/README.md for the same note.
#
# What this hook does instead: using the module ownership already recorded by /code-graph
# (.claude/state/code-graph.json) and the sole in-flight task's declared scope
# (docs/tasks/active/*.md, "Related files and modules:"), it emits
# hookSpecificOutput.additionalContext when an edited file falls in a module the Active task did
# not name AND that module is owned (per the graph) by a DIFFERENT agent than the task's own
# `owner:`. That is a nudge, not a gate: it never blocks, and it stays silent whenever the picture
# is ambiguous (no graph yet, zero or more than one Active task, an unowned module) rather than
# guessing. Always exits 0.

# Same path normalization as guard-agent-spawn.sh: a bash on Windows cannot resolve "C:/x" in a
# file test (or hand it to a POSIX-built python3/perl and expect a resolvable path), which would
# make the graph and task-file lookups fail and this hook go silent everywhere instead of just
# where it should.
norm_path() {
  local p d rest
  p=$(printf '%s' "$1" | tr '\\' '/')
  case "$p" in
    [A-Za-z]:/*) ;;
    *) printf '%s' "$p"; return ;;
  esac
  if command -v wslpath >/dev/null 2>&1; then
    wslpath -u "$p" 2>/dev/null && return
  fi
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -u "$p" 2>/dev/null && return
  fi
  d=$(printf '%s' "${p%%:*}" | tr 'A-Z' 'a-z')
  rest=${p#*:}
  if [ -d "/mnt/$d" ]; then printf '/mnt/%s%s' "$d" "$rest"
  elif [ -d "/$d" ]; then printf '/%s%s' "$d" "$rest"
  else printf '%s' "$p"
  fi
}

# json_fields fetches every field this hook needs in ONE parser invocation instead of one per
# field - see hooks/README.md. Sets array JF, same length as the arg list, in order.
json_fields() {
  local keys=("$@")
  JF=()
  if command -v jq >/dev/null 2>&1; then
    local k
    for k in "${keys[@]}"; do
      JF+=("$(printf '%s' "$payload" | jq -r --arg k "$k" 'getpath($k | split(".")) // empty' 2>/dev/null)")
    done
  elif command -v perl >/dev/null 2>&1; then
    while IFS= read -r -d '' v; do JF+=("$v"); done < <(
      printf '%s' "$payload" | perl -0777 -MJSON::PP -e '
        local $/; my $d = eval { decode_json(<STDIN>) };
        for my $k (@ARGV) {
          my $v = $d;
          if ($d) {
            for my $p (split /\./, $k) {
              $v = (ref($v) eq "HASH") ? $v->{$p} : undef;
              last unless defined $v;
            }
          } else { $v = undef; }
          print(((defined $v && !ref $v) ? $v : "") . "\0");
        }
      ' "${keys[@]}" 2>/dev/null
    )
  elif command -v python3 >/dev/null 2>&1; then
    while IFS= read -r -d '' v; do JF+=("$v"); done < <(
      printf '%s' "$payload" | python3 -c '
import json, sys
try: root = json.load(sys.stdin)
except Exception: root = None
out = []
for k in sys.argv[1:]:
    v = root
    for p in k.split("."):
        v = v.get(p) if isinstance(v, dict) else None
        if v is None: break
    out.append(v if isinstance(v, str) else "")
sys.stdout.write("\0".join(out) + "\0")
' "${keys[@]}" 2>/dev/null
    )
  fi
  local i
  for ((i = ${#JF[@]}; i < ${#keys[@]}; i++)); do JF+=(""); done
}

payload=$(cat)
json_fields tool_input.file_path cwd
path="${JF[0]}"
[ -z "$path" ] && exit 0
base_cwd=$(norm_path "${JF[1]}")
[ -z "$base_cwd" ] && base_cwd=$(pwd)

[ -f "$base_cwd/.claude/state/code-graph.json" ] || exit 0

# The module-ownership / task-scope comparison below is more than a flat JSON field lookup (it
# cross-references a graph document against the sole Active task's frontmatter and body), so - same
# call as agent-history.sh's transcript_part() - jq is not a good fit and this step supports only
# perl or python3. Advisory hook: no interpreter simply means no nudge this time, never a block.
if command -v python3 >/dev/null 2>&1; then
  python3 - "$base_cwd" "$path" <<'PYEOF'
import json, os, re, sys

base, path = sys.argv[1], sys.argv[2]
norm_base = base.replace("\\", "/").rstrip("/")
norm = path.replace("\\", "/")
if norm.startswith(norm_base + "/"):
    norm = norm[len(norm_base) + 1:]

try:
    graph = json.load(open(os.path.join(base, ".claude/state/code-graph.json"), encoding="utf-8"))
except Exception:
    sys.exit(0)

modules = graph.get("modules", {})
target_mod = None
for mod, info in modules.items():
    if norm in info.get("files", []):
        target_mod = mod
        break
if target_mod is None:
    for mod in modules:
        if norm == mod or norm.startswith(mod.rstrip("/") + "/"):
            target_mod = mod
            break
if target_mod is None:
    sys.exit(0)

target_owner = modules[target_mod].get("owner", "-")
if not target_owner or target_owner == "-":
    sys.exit(0)

active_dir = os.path.join(base, "docs/tasks/active")
if not os.path.isdir(active_dir):
    sys.exit(0)

fm_re = re.compile(r"^---\n(.*?)\n---\n", re.S)
active = []
for fn in sorted(os.listdir(active_dir)):
    if not fn.endswith(".md"):
        continue
    fp = os.path.join(active_dir, fn)
    try:
        text = open(fp, encoding="utf-8", errors="replace").read()
    except OSError:
        continue
    m = fm_re.match(text)
    if not m:
        continue
    fm = m.group(1)
    sm = re.search(r"^status:\s*(\S+)", fm, re.M)
    if not sm or sm.group(1) != "Active":
        continue
    om = re.search(r"^owner:\s*(\S+)", fm, re.M)
    mm = re.search(r"Related files and modules:\s*(.+)", text)
    active.append({
        "file": fn,
        "owner": om.group(1) if om else None,
        "modules_line": mm.group(1).strip() if mm else "",
    })

if len(active) != 1:
    sys.exit(0)
task = active[0]

named = [p.strip() for p in re.split(r"[,;]", task["modules_line"]) if p.strip() and p.strip() != "-"]
in_scope = any(norm == p.rstrip("/") or norm.startswith(p.rstrip("/") + "/") for p in named)
if in_scope:
    sys.exit(0)
if not task["owner"] or task["owner"] == target_owner:
    sys.exit(0)

msg = (f"Advisory: this write to {norm} falls in module '{target_mod}' (owner per code-graph.json: "
       f"{target_owner}), which the sole Active task {task['file']} (owner: {task['owner']}) did "
       f"not name under 'Related files and modules' ({task['modules_line'] or '(none named)'}). "
       "This may be crossing a module boundary the task brief did not scope for - confirm before "
       "continuing. (Advisory only: this hook cannot see who is calling it, so it cannot block.)")
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": msg}}))
PYEOF
elif command -v perl >/dev/null 2>&1; then
  perl -MJSON::PP -e '
    my ($base, $path) = @ARGV;
    (my $norm_base = $base) =~ s{\\}{/}g; $norm_base =~ s{/+$}{};
    (my $norm = $path) =~ s{\\}{/}g;
    if (index($norm, "$norm_base/") == 0) { $norm = substr($norm, length($norm_base) + 1); }

    my $gf = "$base/.claude/state/code-graph.json";
    open(my $fh, "<", $gf) or exit 0;
    local $/; my $graph = eval { decode_json(<$fh>) } or exit 0;
    my $modules = $graph->{modules} // {};

    my ($target_mod, $target_owner);
    for my $mod (keys %$modules) {
      my $files = $modules->{$mod}{files} // [];
      if (grep { $_ eq $norm } @$files) { $target_mod = $mod; last; }
    }
    if (!defined $target_mod) {
      for my $mod (keys %$modules) {
        (my $pfx = $mod) =~ s{/+$}{};
        if ($norm eq $pfx || index($norm, "$pfx/") == 0) { $target_mod = $mod; last; }
      }
    }
    exit 0 unless defined $target_mod;
    $target_owner = $modules->{$target_mod}{owner} // "-";
    exit 0 if !$target_owner || $target_owner eq "-";

    my $active_dir = "$base/docs/tasks/active";
    exit 0 unless -d $active_dir;
    opendir(my $dh, $active_dir) or exit 0;
    my @files = grep { /\.md$/ } readdir($dh);
    closedir $dh;

    my @active;
    for my $fn (sort @files) {
      open(my $tf, "<", "$active_dir/$fn") or next;
      local $/; my $text = <$tf>;
      next unless $text =~ /^---\n(.*?)\n---\n/s;
      my $fm = $1;
      next unless $fm =~ /^status:\s*(\S+)/m && $1 eq "Active";
      my ($owner) = $fm =~ /^owner:\s*(\S+)/m;
      my ($mline) = $text =~ /Related files and modules:\s*(.+)/;
      $mline =~ s/^\s+|\s+$//g if defined $mline;
      push @active, { file => $fn, owner => $owner, modules_line => $mline // "" };
    }
    exit 0 unless @active == 1;
    my $task = $active[0];

    my @named = grep { $_ ne "" && $_ ne "-" } map { s/^\s+|\s+$//gr } split(/[,;]/, $task->{modules_line});
    my $in_scope = 0;
    for my $p (@named) {
      (my $pfx = $p) =~ s{/+$}{};
      if ($norm eq $pfx || index($norm, "$pfx/") == 0) { $in_scope = 1; last; }
    }
    exit 0 if $in_scope;
    exit 0 if !$task->{owner} || $task->{owner} eq $target_owner;

    my $named_txt = $task->{modules_line} ne "" ? $task->{modules_line} : "(none named)";
    my $msg = "Advisory: this write to $norm falls in module '\''$target_mod'\'' (owner per code-graph.json: $target_owner), which the sole Active task $task->{file} (owner: $task->{owner}) did not name under '\''Related files and modules'\'' ($named_txt). This may be crossing a module boundary the task brief did not scope for - confirm before continuing. (Advisory only: this hook cannot see who is calling it, so it cannot block.)";
    print encode_json({ hookSpecificOutput => { hookEventName => "PreToolUse", additionalContext => $msg } }), "\n";
  ' "$base_cwd" "$path" 2>/dev/null
fi

exit 0
