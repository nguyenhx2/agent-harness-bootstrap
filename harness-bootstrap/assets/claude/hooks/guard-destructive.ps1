# guard-destructive.ps1
# Event: PreToolUse   Matcher: Bash|PowerShell
# Flag: none - ships with every harness (the deny rules alone are prefix matches)
# Enforces: .claude/rules/agent-guardrails.md
# BLOCKS (exit 2) shell commands whose damage cannot be undone from inside the session:
#   1. rm with recursive+force on the repo root, the home dir, `/`, a top-level system dir, a
#      drive root or a top-level folder on a drive, `.`/`..`/`*`, or `.git` (and anything with
#      --no-preserve-root); the same targets for Remove-Item / ri / rd / rmdir / del / erase with
#      -Recurse (any abbreviation; -Force is not needed to delete a tree) and cmd's /s
#   2. a force push (--force, -f, --force-with-lease, or a `+refspec`) to {{DEFAULT_BRANCH}},
#      main, master, production, prod or release/* - explicit refspec or, failing that, the
#      branch currently checked out (--all / --mirror count as protected)
#   3. git reset --hard; git clean with force AND -x/-X; `git checkout .` / `git restore .`
#   4. DROP TABLE|DATABASE|SCHEMA or TRUNCATE sent to a host that is not local
#
# WHY BLOCK, NOT WARN: see guard-destructive.sh. The settings.json deny rules only match the
# literal prefix form; this hook catches the wrapped, chained and reordered forms.
#
# PARITY CONTRACT: guard-destructive.sh and guard-destructive.ps1 must stay behaviorally
# EQUIVALENT. Token and flag tests are case-SENSITIVE (-ceq / -cmatch) like the bash twin; only
# the SQL keyword test is case-insensitive in both.
#
# Contract: reads the PreToolUse JSON payload on stdin. exit 2 = BLOCK (reason on stderr, shown
# to Claude); exit 0 = allow. Fails OPEN on an unreadable payload.

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
} catch {
    exit 0
}

# --- fast path: decide the common case without ConvertFrom-Json -------------------------------
# This hook starts on every shell call. ConvertFrom-Json loads a module, about a fifth of the run
# on Windows PowerShell 5.1, and most commands can never be blocked here - so that case is decided
# from the raw text first. Get-FastString returns one string field decoded EXACTLY, or $null: the
# key must occur once, and the value must be printable ASCII using no JSON escape but \" \\ \n \r
# \t (everything JSON.stringify writes for such text). A hook may only exit 0 on it, and only on a
# test that is a necessary condition of every block it raises; $null or an exception falls
# through to the full parse, which is unchanged. Copied verbatim - see "Latency" in
# hooks/README.md.
function Get-FastString([string]$raw, [string]$key) {
    if ([regex]::Matches($raw, '"' + $key + '"\s*:').Count -ne 1) { return $null }
    $m = [regex]::Match($raw, '"' + $key + '"\s*:\s*"((?:[^"\\]|\\.)*)"')
    if (-not $m.Success) { return $null }
    $s = $m.Groups[1].Value
    if ($s -cmatch '[^\x20-\x7E]') { return $null }
    $s = $s.Replace('\\', [string][char]1)
    if ($s -cmatch '\\([^"nrt]|$)') { return $null }
    $s = $s.Replace('\"', '"').Replace('\n', "`n").Replace('\r', "`r").Replace('\t', "`t")
    return $s.Replace([string][char]1, '\')
}

# Every block below needs a deletion verb or `git` standing as its own token (compared
# lowercased, as the checks below compare them), or DROP / TRUNCATE (matched with -match, as
# below).
try {
    $fc = Get-FastString $raw 'command'
    if ($null -ne $fc -and -not ($fc.ToLower() -cmatch '(^|[^a-z0-9_-])(rm|ri|rd|rmdir|del|erase|remove-item|git)([^a-z0-9_-]|$)' -or $fc -match 'drop|truncate')) { exit 0 }
} catch { }

try {
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

function Block([string]$why) {
    [Console]::Error.WriteLine("BLOCKED by guard-destructive: $why")
    exit 2
}

function Unquote([string]$t) {
    if ($t.StartsWith('"')) { $t = $t.Substring(1) }
    if ($t.EndsWith('"')) { $t = $t.Substring(0, $t.Length - 1) }
    if ($t.StartsWith("'")) { $t = $t.Substring(1) }
    if ($t.EndsWith("'")) { $t = $t.Substring(0, $t.Length - 1) }
    return $t
}

$cmd = [string]$payload.tool_input.command
if (-not $cmd) { exit 0 }
$rawCwd = [string]$payload.cwd
$cwdPosix = ($rawCwd -replace '\\', '/').TrimEnd('/')
$baseCwd = if ($rawCwd) { $rawCwd } else { (Get-Location).Path }

function Test-DangerTarget([string]$t) {
    $t = (Unquote $t) -replace '\\', '/'
    $b = $t
    if ($b.EndsWith('/*')) { $b = $b.Substring(0, $b.Length - 2) }
    while ($b.Length -gt 1 -and $b.EndsWith('/')) { $b = $b.Substring(0, $b.Length - 1) }
    $exact = @('', '/', '~', '$HOME', '${HOME}', '.', '..', '*', '.*', '$PWD', '${PWD}', '$(pwd)', '`pwd`', '.git', './.git')
    $exact += @('$env:USERPROFILE', '$env:HOMEPATH', '%USERPROFILE%', '$env:SystemDrive', '%SystemDrive%')
    foreach ($e in $exact) { if ($b -ceq $e) { return $true } }
    if ($b -cmatch '^/[^/]+$') { return $true }
    if ($b -cmatch '^[A-Za-z]:/?$') { return $true }
    if ($b -cmatch '^[A-Za-z]:/[^/]+$') { return $true }
    if ($cwdPosix) {
        if ($b -ceq $cwdPosix) { return $true }
        if ($b.ToLower() -ceq $cwdPosix.ToLower()) { return $true }
    }
    return $false
}

function Test-ProtectedBranch([string]$b) {
    if ($b.StartsWith('refs/heads/')) { $b = $b.Substring(11) }
    foreach ($p in @('{{DEFAULT_BRANCH}}', 'main', 'master', 'production', 'prod')) {
        if ($b -ceq $p) { return $true }
    }
    return ($b -clike 'release/*')
}

function Get-Branch([string]$dir) {
    try {
        $out = & git -C $dir rev-parse --abbrev-ref HEAD 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return ([string]$out).Trim() }
    } catch { }
    return ''
}

function Join-Dir([string]$base, [string]$d) {
    $d = $d -replace '\\', '/'
    if ($d -cmatch '^(/|[A-Za-z]:/)') { return $d }
    return "$base/$d"
}

# --- per-segment checks ----------------------------------------------------------------------
$workdir = $baseCwd
$segments = $cmd -split '&&|\|\||;|\||\r?\n'
foreach ($seg in $segments) {
    $toks = @($seg.Trim() -split '\s+' | Where-Object { $_ -ne '' })
    $n = $toks.Count
    if ($n -eq 0) { continue }

    if ($toks[0] -ceq 'cd' -and $n -ge 2) {
        $workdir = Join-Dir $workdir (Unquote $toks[1])
        continue
    }

    for ($i = 0; $i -lt $n; $i++) {
        $tok = Unquote $toks[$i]
        # PowerShell and cmd deletion: Remove-Item and its aliases (ri, rd, rmdir, del, erase)
        # delete a tree with -Recurse alone, and cmd's rd/del take /s. Case-insensitive, and
        # parameters may be abbreviated.
        $tl = $tok.ToLower()
        if (@('remove-item', 'ri', 'rd', 'rmdir', 'del', 'erase') -ccontains $tl -or $tl -clike '*/rmdir') {
            $rec = $false; $targets = @(); $skip = $false
            for ($j = $i + 1; $j -lt $n; $j++) {
                $a = Unquote $toks[$j]
                $al = $a.ToLower()
                if ($skip) { $skip = $false; continue }
                if (@('-r', '-re', '-rec', '-recu', '-recur', '-recurs', '-recurse', '/s') -ccontains $al) { $rec = $true }
                elseif ($al -clike '-inc*' -or $al -clike '-exc*' -or $al -clike '-fil*' -or $al -clike '-cr*' -or $al -clike '-str*') { $skip = $true }
                elseif ($al.StartsWith('-') -or $al -clike '/?') { }
                else { $targets += $a }
            }
            if ($rec) {
                foreach ($t in $targets) {
                    if (Test-DangerTarget $t) {
                        Block "$tok with -Recurse on '$t' would delete the repository, the home directory or a system path. Remove the specific build output you mean, or ask the user to do this by hand."
                    }
                }
            }
            break
        }
        if ($tok -ceq 'rm' -or $tok -clike '*/rm') {
            $rec = $false; $force = $false; $npr = $false; $targets = @(); $opts = $true
            for ($j = $i + 1; $j -lt $n; $j++) {
                $a = $toks[$j]
                if ($opts -and $a -ceq '--') { $opts = $false; continue }
                if ($opts) {
                    if ($a -ceq '--recursive') { $rec = $true; continue }
                    if ($a -ceq '--force') { $force = $true; continue }
                    if ($a -ceq '--no-preserve-root') { $npr = $true; continue }
                    if ($a.StartsWith('--')) { continue }
                    if ($a.StartsWith('-')) {
                        # PowerShell's rm alias takes -Force (and its abbreviations)
                        if (@('-fo', '-for', '-forc', '-force') -ccontains $a.ToLower()) { $force = $true }
                        if ($a -cmatch '[rR]') { $rec = $true }
                        if ($a -cmatch 'f') { $force = $true }
                        continue
                    }
                }
                $targets += $a
            }
            if ($npr) { Block 'rm --no-preserve-root is never a legitimate step in a repo task.' }
            if ($rec -and $force) {
                foreach ($t in $targets) {
                    if (Test-DangerTarget $t) {
                        Block ("rm -rf on '" + (Unquote $t) + "' would delete the repository, the home directory or a system path. Delete the specific build output you mean (for example dist/ or node_modules/), or ask the user to do this by hand.")
                    }
                }
            }
            break
        }
        if ($tok -ceq 'git' -or $tok -clike '*/git') {
            $gdir = $workdir; $sub = ''; $k = $i + 1
            while ($k -lt $n) {
                $a = Unquote $toks[$k]
                if ($a -ceq '-C') { $k++; if ($k -lt $n) { $gdir = Join-Dir $gdir (Unquote $toks[$k]) } }
                elseif (@('-c', '--git-dir', '--work-tree', '--namespace', '--config-env') -ccontains $a) { $k++ }
                elseif ($a.StartsWith('-')) { }
                else { $sub = $a; break }
                $k++
            }
            $rest = @()
            for ($j = $k + 1; $j -lt $n; $j++) { $rest += (Unquote $toks[$j]) }
            switch -CaseSensitive ($sub) {
                'push' {
                    $forced = $false; $all = $false; $pos = @(); $skip = $false
                    foreach ($a in $rest) {
                        if ($skip) { $skip = $false; continue }
                        if ($a -ceq '--force' -or $a -ceq '--force-with-lease' -or $a -clike '--force-with-lease=*') { $forced = $true }
                        elseif ($a -ceq '--all' -or $a -ceq '--mirror') { $all = $true }
                        elseif (@('-o', '--push-option', '--repo', '--receive-pack', '--exec') -ccontains $a) { $skip = $true }
                        elseif ($a.StartsWith('--')) { }
                        elseif ($a.StartsWith('-')) { if ($a -cmatch 'f') { $forced = $true } }
                        else { $pos += $a }
                    }
                    $branches = @()
                    if ($pos.Count -ge 2) {
                        foreach ($r in $pos[1..($pos.Count - 1)]) {
                            if ($r.StartsWith('+')) { $forced = $true; $r = $r.Substring(1) }
                            if ($r.Contains(':')) { $r = $r.Substring($r.LastIndexOf(':') + 1) }
                            if ($r -ceq 'HEAD') { $r = Get-Branch $gdir }
                            $branches += $r
                        }
                    } else {
                        $branches += (Get-Branch $gdir)
                    }
                    if ($forced) {
                        if ($all) { Block 'a force push with --all/--mirror rewrites every branch, protected ones included.' }
                        foreach ($b in $branches) {
                            if (Test-ProtectedBranch $b) {
                                Block "force push to protected branch '$b' rewrites shared history. Push to a feature branch and open a PR, or ask the user to do this by hand."
                            }
                        }
                    }
                }
                'reset' {
                    if ($rest -ccontains '--hard') {
                        Block "git reset --hard discards uncommitted work with no undo. Use 'git stash' (recoverable) or 'git reset --soft', or ask the user."
                    }
                }
                'clean' {
                    $cf = $false; $cx = $false
                    foreach ($a in $rest) {
                        if ($a -ceq '--force') { $cf = $true }
                        elseif ($a.StartsWith('--')) { }
                        elseif ($a.StartsWith('-')) {
                            if ($a -cmatch 'f') { $cf = $true }
                            if ($a -cmatch '[xX]') { $cx = $true }
                        }
                    }
                    if ($cf -and $cx) {
                        Block "git clean -x also deletes ignored files - local env files, local databases, caches - none of which git can restore. Drop -x, or list with 'git clean -n -x' first and ask the user."
                    }
                }
                { $_ -ceq 'checkout' -or $_ -ceq 'restore' } {
                    $stagedOnly = $false; $wt = $false; $dot = $false
                    foreach ($a in $rest) {
                        if ($a -ceq '--staged' -or $a -ceq '-S') { $stagedOnly = $true }
                        elseif ($a -ceq '--worktree' -or $a -ceq '-W') { $wt = $true }
                        elseif (@('.', './', ':/', '*') -ccontains $a) { $dot = $true }
                    }
                    if ($dot -and ((-not $stagedOnly) -or $wt)) {
                        Block "git $sub . discards every uncommitted change in the tree. Name the files you mean, or 'git stash' first."
                    }
                }
            }
            break
        }
    }
}

# --- destructive SQL against a non-local host ------------------------------------------------
if ($cmd -match '(DROP\s+(TABLE|DATABASE|SCHEMA)|TRUNCATE\s+)') {
    $hosts = @()
    foreach ($m in [regex]::Matches($cmd, '(^|\s)(-h|-S|--host|--server)[\s=]*\S+')) {
        $hosts += ($m.Value -replace '^\s*(-h|-S|--host|--server)[\s=]*', '')
    }
    foreach ($m in [regex]::Matches($cmd, '(?i)host=[^\s;]+')) {
        $hosts += ($m.Value -replace '^(?i)host=', '')
    }
    foreach ($m in [regex]::Matches($cmd, '[a-zA-Z][a-zA-Z0-9+.-]*://([^/@\s]*@)?[^/:?\s]+')) {
        $hosts += ($m.Value -replace '^[^:]*://([^@]*@)?', '')
    }
    foreach ($h in $hosts) {
        $h = Unquote (Unquote $h)
        if (-not $h) { continue }
        if ($h.StartsWith('/')) { continue }
        $bs = $h.IndexOf('\'); if ($bs -ge 0) { $h = $h.Substring(0, $bs) }
        $cm = $h.IndexOf(','); if ($cm -ge 0) { $h = $h.Substring(0, $cm) }
        if ($h.StartsWith('[')) { $h = $h.Substring(1); $e = $h.IndexOf(']'); if ($e -ge 0) { $h = $h.Substring(0, $e) } }
        else { $c = $h.IndexOf(':'); if ($c -ge 0) { $h = $h.Substring(0, $c) } }
        $hl = $h.ToLower()
        if (@('', 'localhost', '127.0.0.1', '::1', '0.0.0.0', '.', '(local)') -ccontains $hl) { continue }
        Block "destructive SQL (DROP/TRUNCATE) aimed at host '$h', which is not local. Run it against a local database, or hand the exact statement to the user."
    }
}

exit 0
