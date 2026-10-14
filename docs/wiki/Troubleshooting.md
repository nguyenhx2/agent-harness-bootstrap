# Troubleshooting

**English** · [[日本語|Troubleshooting-ja]]

Every entry here is a failure that actually happened, not a hypothetical. Find the symptom, run
the first move, then read the section.

| Symptom | First move | Section |
|---|---|---|
| A hook blocks nothing | Check the flavour, pipe a payload by hand | [below](#a-hook-does-not-block-anything) |
| Every call is refused | Check the interpreter the hook needs | [below](#every-call-is-refused) |
| A dispatch is refused | Read the ledger line the message cites | [below](#a-dispatch-is-refused-by-guard-agent-spawn) |
| A board edit is refused | `task.py move` | [below](#a-hand-edit-of-the-task-board-is-refused) |
| A link points at nothing | `harness-check.py` | [below](#the-harness-does-not-hang-together) |
| Cursor or Codex allows everything | `port.py --self-test` | [below](#the-adapter-allows-everything-on-cursor-or-codex) |
| The viewer looks stale | `harness-graph.py` | [below](#the-graph-or-the-viewer-shows-stale-data) |
| Scaffold reports CONFLICT or exits 1 | Reconcile, or fill the variable | [below](#scaffolding-reports-conflict-or-exits-1) |

## A hook does not block anything

**Check the flavour first.** A Windows harness ships `.ps1` hooks. If `settings.json` registers
`.sh` commands, every lookup misses and everything is allowed. The flavour and the registration
both derive from one OS flag, so a mismatch means the harness was hand-edited.

```bash
harness-view assess .        # reports a hook that ships but is not registered
```

**Then test the hook directly.** Hooks read JSON on stdin and answer with an exit code:

```bash
echo '{"cwd":"'"$PWD"'","tool_name":"Bash","tool_input":{"command":"cat .env"}}' \
  | bash .claude/hooks/protect-secrets.sh; echo "exit=$?"
```

`2` blocked, `0` allowed. In PowerShell check `$LASTEXITCODE`, never `$?`: that is a boolean saying
the script ran, not what it decided. On Windows, `bash` on `PATH` may be the WSL launcher rather than
Git Bash; the two resolve paths differently, so test with the one your settings call.

**On a harness older than v1.20.1,** upgrade (`/harness-update`). Four live holes were closed there:
`git -c k=v commit` and other git global options walked past the commit and destructive-command
guards, the Windows PowerShell 5.1 payload carried a byte-order mark that switched the verification
ledger off, a guard that timed out let its command run, and `protect-secrets` did not see the
PowerShell tool.

## Every call is refused

The blocking hooks carry `onFailure: "block"` and a 30 s timeout: a guard that cannot run refuses
rather than allows. If every Bash call is blocked, the hook itself is failing. Run it by hand as
above. The usual cause is that the interpreter the registration names (`bash`, `pwsh` or
`powershell`) is not on `PATH`, or the hook is too slow for its timeout.

## A dispatch is refused by `guard-agent-spawn`

The hook reads the verification ledger (`.claude/state/verify-ledger.jsonl`) and refuses:

- a review or suite run on content that already passed
- a seat dispatched twice on the same content with no result recorded
- a third review round, or an identical brief
- a dispatch past the task's budget (`dispatch_budget`, default 24)
- a write-capable seat that names neither a registered `TASK-NNN` nor `TIER: direct` or
  `TIER: standard`

The message cites the ledger line. Use the recorded result, or change something and run the gate
once. Only you can override it, as `.claude/hooks/README.md` says.

## A hand edit of the task board is refused

`guard-board` blocks an edit to a task row of `docs/tasks/master-plan.md`. A task's state lives in
the file's `status:`, its folder and the board row, and `python .claude/scripts/task.py move TASK-NNN
<state>` changes all three and reads the row back. The Phases table and the prose around the board
can still be edited.

## The harness does not hang together

```bash
python .claude/scripts/harness-check.py
```

It checks that every registered hook script exists, every seat a command or table names exists, the
tier table agrees with the seats, every cited rule exists, and every skill a seat lists is
installed. Each finding names `file:line` and the fix.

## An agent cannot read a file it obviously needs

A real bug: the deny rule matched `.env.example`, the one file every block message tells the agent
to read. It is fixed, and the eval covers reading the example, seeding a local one and running with
one loaded. In your own harness, the deny list should name **value-bearing** files, not every
filename containing `env`. Check `.claude/settings.json` and the `protect-secrets` hook.

## The adapter allows everything on Cursor or Codex

```bash
python harness-bootstrap/scripts/port.py --self-test
```

It checks both hook flavours, that the adapter offers every interpreter name its platform may use,
and that it **denies** a call it cannot evaluate. The adapter once baked in `powershell`, which
exists only on Windows; on macOS and Linux the binary is `pwsh`, so every call raised a traceback and
the guard never ran.

On Codex, also check that the project is trusted and its hooks were reviewed through `/hooks`;
until then the ported hooks are on disk and inert. See
[docs/tools/codex.md](https://github.com/nguyenhx2/agent-harness-bootstrap/blob/main/docs/tools/codex.md).

## The graph or the viewer shows stale data

The `graph-stale` hook regenerates `.claude/state/harness-graph.json` after an edit under `.claude/`,
and `/harness-update` and `/harness-toggle` regenerate it themselves, because script-driven writes
do not fire editor hooks. Two maps are on demand: `/code-graph` refreshes the module-boundary map,
and `/docs-graph` prints orphan requirement IDs. To force a rebuild:

```bash
python .claude/scripts/harness-graph.py     # or: harness-view scan .
```

## A published number looks wrong

```bash
python scripts/check_numbers.py
```

It compares every figure in the documents, the deck, the clips and the figures with what the
scripts print, and exits non-zero on a contradiction. A clip once claimed "26 / 26" long after the
eval reached 107, hidden from the checker by the spaces around the slash. If a page and a script
disagree, trust the script and open an issue.

## Scaffolding reports CONFLICT, or exits 1

- **`CONFLICT`** is not an error. The file exists and differs from what would be installed. Resolve
  each one by hand: keep yours, adapt it, take the new one, or register the difference as a task.
  The scaffolder never overwrites or deletes what you wrote.
- **Exit 1 on a variable** means an unresolved `{{VAR}}`. A placeholder in a rule file would match
  nothing and fail silently, so the run writes nothing instead. Fill it in `vars.json` and re-run.
- **Exit 1 on the roster or links** means an invalid flag set, a second seat holding `Agent`, a
  control installed but not wired, or a link `harness-check.py` cannot resolve. The message names
  the file and line.

## Still stuck

Open an [issue](https://github.com/nguyenhx2/agent-harness-bootstrap/issues) with the output of
`harness-view assess .` and the failing command. The assess output names the node, which is usually
enough to locate the problem.
