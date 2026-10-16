//! The published rubric: every rule the assessment applies, with its id, the
//! category it scores, its weight, how much work the fix is, which repository
//! purposes it applies to, and - in English and Japanese - what it checks, what
//! full marks means, why it matters and how to fix it.
//!
//! This table is the single source. `assess.rs` renders every finding's title,
//! reason and fix from it; `harness-view rubric` prints it as Markdown; and
//! `RUBRIC.md` / `RUBRIC.ja.md` are that output, compared byte for byte by
//! `tests/rubric_test.rs`. A weight changed here and not in the published file
//! fails the build, which is what makes a score reproducible from the document.
//!
//! Templates take `{name}` (the seat, rule, hook, task or file the finding is
//! about) and `{extra}` (a second value: the tool, the missing seat, the line).

use serde_json::{json, Value};

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Debug)]
pub enum Sev {
    Info,
    Low,
    Medium,
    High,
}

impl Sev {
    pub fn as_str(self) -> &'static str {
        match self {
            Sev::High => "high",
            Sev::Medium => "medium",
            Sev::Low => "low",
            Sev::Info => "info",
        }
    }
    /// Points a finding of this severity takes off its category.
    pub fn weight(self) -> u32 {
        match self {
            Sev::High => 12,
            Sev::Medium => 5,
            Sev::Low => 2,
            Sev::Info => 0,
        }
    }
    /// Rank for worst-first ordering.
    pub fn rank(self) -> u8 {
        match self {
            Sev::High => 0,
            Sev::Medium => 1,
            Sev::Low => 2,
            Sev::Info => 3,
        }
    }
}

/// Which repositories a rule is about. `Code` rules are skipped when the
/// repository has no code purpose; `NonCode` rules apply only when it has a
/// research, strategy or docs purpose.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Applies {
    All,
    Code,
    NonCode,
}

impl Applies {
    pub fn as_str(self) -> &'static str {
        match self {
            Applies::All => "all",
            Applies::Code => "code",
            Applies::NonCode => "non-code",
        }
    }
}

pub struct Rule {
    pub id: &'static str,
    /// The stable machine name findings have always carried.
    pub check: &'static str,
    pub category: &'static str,
    pub sev: Sev,
    /// 1 = one click or one line, 2 = a small edit in one file, 3 = a decision
    /// or a new file.
    pub effort: u8,
    pub applies: Applies,
    /// [English, Japanese]
    pub title: [&'static str; 2],
    pub full: [&'static str; 2],
    pub why: [&'static str; 2],
    pub fix: [&'static str; 2],
}

/// Category names, in score order, with their Japanese label.
pub const CATEGORIES: &[(&str, &str)] = &[
    ("Safety", "安全性"),
    ("Cost control", "コスト管理"),
    ("Traceability", "トレーサビリティ"),
    ("Board health", "タスクボード"),
    ("Docs quality", "文書品質"),
    ("Contract", "契約（指示ファイル）"),
];

pub fn category_ja(en: &str) -> &'static str {
    CATEGORIES.iter().find(|(e, _)| *e == en).map(|(_, j)| *j).unwrap_or("")
}

pub const RULES: &[Rule] = &[
    // ------------------------------------------------------------- Safety
    Rule {
        id: "SAF-01", check: "reviewer-readonly", category: "Safety", sev: Sev::High, effort: 1,
        applies: Applies::All,
        title: ["review seat `{name}` holds `{extra}`",
                "レビュー担当 `{name}` が `{extra}` を持っている"],
        full: ["Every review seat (reviewer, checker, auditor ...) has no Edit, Write or NotebookEdit.",
               "すべてのレビュー担当（reviewer、checker、auditor など）が Edit・Write・NotebookEdit を持たない。"],
        why: ["A reviewer that can write is not a gate; it can fix what it was supposed to report, and the review becomes self-approval.",
              "書き込めるレビュー担当はゲートではありません。指摘すべきものを自分で直せてしまい、レビューが自己承認になります。"],
        fix: ["Remove `{extra}` from `tools:` in `.claude/agents/{name}.md` and list it in `disallowedTools:`.",
              "`.claude/agents/{name}.md` の `tools:` から `{extra}` を削除し、`disallowedTools:` に加える。"],
    },
    Rule {
        id: "SAF-02", check: "reviewer-disallowed", category: "Safety", sev: Sev::Low, effort: 1,
        applies: Applies::All,
        title: ["review seat `{name}` does not list Edit and Write in `disallowedTools`",
                "レビュー担当 `{name}` の `disallowedTools` に Edit と Write がない"],
        full: ["Every review seat names Edit and Write in `disallowedTools:`, so a later widening of `tools:` cannot grant them.",
               "すべてのレビュー担当が `disallowedTools:` に Edit と Write を書いている。後で `tools:` を広げても付与されない。"],
        why: ["`tools:` says what a seat may use today; `disallowedTools:` keeps it true after someone edits the list.",
              "`tools:` は今使えるものを示すだけです。`disallowedTools:` があれば、誰かが一覧を編集した後も読み取り専用のままです。"],
        fix: ["Add `disallowedTools: Edit, Write, NotebookEdit` to the frontmatter of `.claude/agents/{name}.md`.",
              "`.claude/agents/{name}.md` の frontmatter に `disallowedTools: Edit, Write, NotebookEdit` を加える。"],
    },
    Rule {
        id: "SAF-03", check: "reviewer-memory", category: "Safety", sev: Sev::Medium, effort: 1,
        applies: Applies::All,
        title: ["review seat `{name}` sets `memory:`",
                "レビュー担当 `{name}` が `memory:` を設定している"],
        full: ["No review seat sets `memory:`.",
               "どのレビュー担当も `memory:` を設定していない。"],
        why: ["Memory grants the seat Write and Edit on its memory directory, so a read-only reviewer is no longer read-only.",
              "memory はメモリ用ディレクトリへの Write と Edit を与えるため、読み取り専用のはずのレビュー担当が書き込めるようになります。"],
        fix: ["Delete the `memory:` line from `.claude/agents/{name}.md`.",
              "`.claude/agents/{name}.md` から `memory:` の行を削除する。"],
    },
    Rule {
        id: "SAF-04", check: "spawn-boundary", category: "Safety", sev: Sev::High, effort: 1,
        applies: Applies::All,
        title: ["agent `{name}` can spawn any subagent",
                "エージェント `{name}` が任意のサブエージェントを起動できる"],
        full: ["Only the orchestrator holds a bare `Agent`; any other spawning seat names its targets as `Agent(a, b)`.",
               "素の `Agent` を持つのはオーケストレーターだけ。ほかに起動するエージェントは `Agent(a, b)` で起動先を限定している。"],
        why: ["Any seat with a bare Agent can fan out, and the spawn allowlist no longer bounds what runs.",
              "素の Agent を持つエージェントは自由に展開でき、起動許可リストが実行範囲を制限しなくなります。"],
        fix: ["In `.claude/agents/{name}.md`, remove `Agent` from `tools:`, or bound it: `Agent(<seat>, <seat>)`.",
              "`.claude/agents/{name}.md` の `tools:` から `Agent` を削除するか、`Agent(<担当>, <担当>)` の形で限定する。"],
    },
    Rule {
        id: "SAF-05", check: "hook-missing-file", category: "Safety", sev: Sev::High, effort: 2,
        applies: Applies::All,
        title: ["hook `{name}` is registered but has no file on disk",
                "フック `{name}` は登録されているが、ファイルが存在しない"],
        full: ["Every hook registered in settings.json or in a seat's frontmatter exists under `.claude/hooks/`.",
               "settings.json やエージェントの frontmatter に登録したフックが、すべて `.claude/hooks/` に存在する。"],
        why: ["The registration runs a script that is not there, so the guardrail never fires and nothing reports it.",
              "存在しないスクリプトを実行する登録なので、ガードレールは一度も動かず、誰も気づきません。"],
        fix: ["Restore `.claude/hooks/{name}.sh` (`/harness-update` re-installs shipped hooks), or delete the registration at the evidence line.",
              "`.claude/hooks/{name}.sh` を復元する（同梱のフックは `/harness-update` で再導入できる）か、根拠の行にある登録を削除する。"],
    },
    Rule {
        id: "SAF-06", check: "hook-unregistered", category: "Safety", sev: Sev::Medium, effort: 2,
        applies: Applies::All,
        title: ["hook `{name}` exists but is not registered",
                "フック `{name}` は存在するが、登録されていない"],
        full: ["Every hook file is registered in settings.json or a seat's frontmatter, or is a library another hook sources.",
               "すべてのフックファイルが settings.json かエージェントの frontmatter に登録されているか、他のフックが読み込むライブラリである。"],
        why: ["A hook nothing invokes is inert; it looks like a control and enforces nothing.",
              "どこからも呼ばれないフックは何もしません。統制に見えて、何も強制していません。"],
        fix: ["Register it in `.claude/settings.json`, e.g. `\"PreToolUse\": [{\"matcher\": \"Edit|Write\", \"hooks\": [{\"type\": \"command\", \"command\": \"bash .claude/hooks/{name}.sh\"}]}]`, or disable it in the viewer.",
              "`.claude/settings.json` に登録する（例: `\"PreToolUse\": [{\"matcher\": \"Edit|Write\", \"hooks\": [{\"type\": \"command\", \"command\": \"bash .claude/hooks/{name}.sh\"}]}]`）か、ビューアーで無効化する。"],
    },
    Rule {
        id: "SAF-07", check: "deny-list", category: "Safety", sev: Sev::High, effort: 2,
        applies: Applies::All,
        title: ["settings.json has no permissions.deny entries",
                "settings.json に permissions.deny がない"],
        full: ["settings.json carries a non-empty `permissions.deny` list.",
               "settings.json に空でない `permissions.deny` がある。"],
        why: ["The deny list is the first of the four guardrail layers; without it every destructive command reaches the hook layer or nothing at all.",
              "deny リストは 4 層のガードレールの 1 層目です。これがないと、破壊的なコマンドはフックに頼るか、何にも止められません。"],
        fix: ["Add to `.claude/settings.json`: `\"permissions\": {\"deny\": [\"Bash(git push --force *)\", \"Bash(rm -rf *)\", \"Read(./**/.env)\"]}`.",
              "`.claude/settings.json` に `\"permissions\": {\"deny\": [\"Bash(git push --force *)\", \"Bash(rm -rf *)\", \"Read(./**/.env)\"]}` を加える。"],
    },
    Rule {
        id: "SAF-08", check: "deny-coverage", category: "Safety", sev: Sev::Low, effort: 1,
        applies: Applies::All,
        title: ["deny list does not mention {name}",
                "deny リストに {name} がない"],
        full: ["The deny list covers force push, recursive delete and secret reads.",
               "deny リストが force push、再帰削除、秘密情報の読み取りを含む。"],
        why: ["Deny rules are prefix matches and only a speed bump, but an absent one is not even that.",
              "deny は前方一致で、足止め程度のものです。それでも、ないよりはましです。"],
        fix: ["Add `{extra}` to `permissions.deny` in `.claude/settings.json`.",
              "`.claude/settings.json` の `permissions.deny` に `{extra}` を加える。"],
    },
    Rule {
        id: "SAF-09", check: "no-blocking-hook", category: "Safety", sev: Sev::High, effort: 2,
        applies: Applies::All,
        title: ["no blocking (PreToolUse) hook is active",
                "ツール呼び出しを止めるフック（PreToolUse）が有効になっていない"],
        full: ["At least one active hook is registered on PreToolUse or PermissionRequest.",
               "PreToolUse か PermissionRequest に登録された有効なフックが 1 つ以上ある。"],
        why: ["Hooks are the layer that actually stops a tool call; with none active the guardrails are advice.",
              "ツール呼び出しを実際に止めるのはフックです。1 つもなければ、ガードレールは助言にすぎません。"],
        fix: ["Register a PreToolUse hook such as `protect-secrets` in `.claude/settings.json`; `/harness-update` re-installs the shipped ones.",
              "`protect-secrets` などの PreToolUse フックを `.claude/settings.json` に登録する。同梱のものは `/harness-update` で再導入できる。"],
    },
    Rule {
        id: "SAF-10", check: "no-guardrail-rule", category: "Safety", sev: Sev::Medium, effort: 2,
        applies: Applies::All,
        title: ["agent-guardrails.md is not installed",
                "agent-guardrails.md がない"],
        full: ["`.claude/rules/agent-guardrails.md` exists.",
               "`.claude/rules/agent-guardrails.md` が存在する。"],
        why: ["It is the always-loaded rule that states the boundaries the hooks enforce; without it agents get the enforcement but never the reasoning.",
              "フックが強制する境界を説明する、常に読み込まれるルールです。これがないと、エージェントは強制だけを受け、理由を知りません。"],
        fix: ["Restore `.claude/rules/agent-guardrails.md` (`/harness-update` re-installs it).",
              "`.claude/rules/agent-guardrails.md` を復元する（`/harness-update` で再導入できる）。"],
    },
    Rule {
        id: "SAF-11", check: "no-review-gate", category: "Safety", sev: Sev::High, effort: 3,
        applies: Applies::Code,
        title: ["no review command and no review seat",
                "レビューコマンドもレビュー担当もない"],
        full: ["A code repository has a review seat (code-reviewer, reviewer ...) or a `/review*` command.",
               "コードのリポジトリに、レビュー担当（code-reviewer、reviewer など）か `/review*` コマンドがある。"],
        why: ["The review gate is the fourth guardrail layer and the only one that reads the diff as a whole.",
              "レビューゲートは 4 層目のガードレールで、差分全体を読む唯一の層です。"],
        fix: ["Add a read-only `.claude/agents/code-reviewer.md` (`tools: Read, Grep, Glob`) and a `.claude/commands/review-changes.md` that dispatches it.",
              "読み取り専用の `.claude/agents/code-reviewer.md`（`tools: Read, Grep, Glob`）と、それを起動する `.claude/commands/review-changes.md` を加える。"],
    },
    Rule {
        id: "SAF-12", check: "no-review-command", category: "Safety", sev: Sev::Low, effort: 2,
        applies: Applies::Code,
        title: ["a review seat exists but no command invokes it",
                "レビュー担当はいるが、起動するコマンドがない"],
        full: ["A code repository with a review seat also has a `/review*` command that routes work to it.",
               "レビュー担当のいるコードのリポジトリに、そこへ作業を回す `/review*` コマンドもある。"],
        why: ["A reviewer nobody routes work to is only enforced by whoever remembers to dispatch it by hand.",
              "誰も作業を回さないレビュー担当は、手で起動することを覚えている人がいる間しか機能しません。"],
        fix: ["Add `.claude/commands/review-changes.md` that runs the review seat over the current diff.",
              "現在の差分にレビュー担当を実行する `.claude/commands/review-changes.md` を加える。"],
    },
    Rule {
        id: "SAF-13", check: "noncode-checker", category: "Safety", sev: Sev::High, effort: 3,
        applies: Applies::NonCode,
        title: ["no read-only seat checks the deliverable",
                "成果物を確認する読み取り専用の担当がいない"],
        full: ["A research, strategy or docs repository has a read-only checking seat (`checker`, or any review seat without Edit or Write).",
               "調査・戦略・文書のリポジトリに、読み取り専用の確認担当（`checker`、または Edit も Write も持たないレビュー担当）がいる。"],
        why: ["Without a seat that only reads, every claim and every figure is approved by whoever wrote it.",
              "読むだけの担当がいなければ、すべての主張と数字を書いた本人が承認することになります。"],
        fix: ["Add `.claude/agents/checker.md` with `tools: Read, Grep, Glob, WebFetch, WebSearch` and `disallowedTools: Edit, Write, NotebookEdit` (the skill ships one for non-code purposes).",
              "`tools: Read, Grep, Glob, WebFetch, WebSearch` と `disallowedTools: Edit, Write, NotebookEdit` を持つ `.claude/agents/checker.md` を加える（スキルは非コード用に同梱している）。"],
    },
    Rule {
        id: "SAF-14", check: "harness-unprotected", category: "Safety", sev: Sev::Medium, effort: 2,
        applies: Applies::All,
        title: ["nothing guards the hooks and settings the guardrails live in",
                "ガードレールを収めたフックと設定を守るものがない"],
        full: ["An active hook (such as `protect-harness`) or a permissions entry guards `.claude/settings*.json` and `.claude/hooks/`.",
               "有効なフック（`protect-harness` など）か permissions の項目が `.claude/settings*.json` と `.claude/hooks/` を守っている。"],
        why: ["A guard an agent can rewrite is one `echo >> .claude/hooks/...` away from `exit 0`; every other layer is only as strong as the files that hold it.",
              "エージェントが書き換えられるガードは、`echo >> .claude/hooks/...` 一つで `exit 0` になります。ほかのすべての層は、それを収めたファイルと同じ強さしかありません。"],
        fix: ["Install `protect-harness` (`/harness-update` adds it) and register it on PreToolUse with matcher `Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell` in `.claude/settings.json`.",
              "`protect-harness` を導入し（`/harness-update` で追加される）、`.claude/settings.json` の PreToolUse に matcher `Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell` で登録する。"],
    },
    // ------------------------------------------------------- Cost control
    Rule {
        id: "COST-01", check: "agent-tools", category: "Cost control", sev: Sev::High, effort: 1,
        applies: Applies::All,
        title: ["agent `{name}` grants no explicit tool list",
                "エージェント `{name}` に明示的な tools がない"],
        full: ["Every agent has an explicit `tools:` list.",
               "すべてのエージェントが明示的な `tools:` を持つ。"],
        why: ["Omitting tools inherits every tool including every MCP server, at full schema cost on every request and with no scope limit.",
              "tools を省略すると、すべての MCP サーバーを含む全ツールを継承し、毎回スキーマ全体のコストがかかり、範囲の制限もありません。"],
        fix: ["Add `tools: Read, Grep, Glob` to `.claude/agents/{name}.md` and widen it only to what the seat needs.",
              "`.claude/agents/{name}.md` に `tools: Read, Grep, Glob` を加え、必要な分だけ広げる。"],
    },
    Rule {
        id: "COST-02", check: "agent-model", category: "Cost control", sev: Sev::Medium, effort: 1,
        applies: Applies::All,
        title: ["agent `{name}` does not pin a model",
                "エージェント `{name}` がモデルを指定していない"],
        full: ["Every agent sets `model:` to something other than `inherit`.",
               "すべてのエージェントが `inherit` 以外の `model:` を設定している。"],
        why: ["An unset model inherits the caller's tier, so mechanical work bills at the most expensive model in the roster.",
              "モデル未指定は呼び出し元を継承するため、機械的な作業が最も高いモデルで課金されます。"],
        fix: ["Add `model: sonnet` to `.claude/agents/{name}.md` (`haiku` for mechanical work, `opus` for judgment).",
              "`.claude/agents/{name}.md` に `model: sonnet` を加える（機械的な作業は `haiku`、判断が要る作業は `opus`）。"],
    },
    Rule {
        id: "COST-03", check: "agent-effort", category: "Cost control", sev: Sev::Low, effort: 1,
        applies: Applies::All,
        title: ["agent `{name}` does not pin an effort level",
                "エージェント `{name}` が effort を指定していない"],
        full: ["Every agent sets `effort:`.",
               "すべてのエージェントが `effort:` を設定している。"],
        why: ["Effort is the second half of the cost decision; unset means the caller's level applies to work that may not need it.",
              "effort はコスト判断のもう半分です。未指定だと、必要のない作業にも呼び出し元の水準が適用されます。"],
        fix: ["Add `effort: medium` to `.claude/agents/{name}.md`.",
              "`.claude/agents/{name}.md` に `effort: medium` を加える。"],
    },
    Rule {
        id: "COST-04", check: "agent-maxturns", category: "Cost control", sev: Sev::Low, effort: 1,
        applies: Applies::All,
        title: ["agent `{name}` does not cap its turns",
                "エージェント `{name}` が maxTurns を指定していない"],
        full: ["Every agent sets `maxTurns:`.",
               "すべてのエージェントが `maxTurns:` を設定している。"],
        why: ["Without a cap a seat that loses its way keeps billing until the session ends.",
              "上限がなければ、行き詰まった担当はセッションが終わるまで課金し続けます。"],
        fix: ["Add `maxTurns: 30` to `.claude/agents/{name}.md` (the scaffolder uses 10 to 100 by seat).",
              "`.claude/agents/{name}.md` に `maxTurns: 30` を加える（スキャフォルダーは担当ごとに 10〜100 を使う）。"],
    },
    Rule {
        id: "COST-05", check: "rule-scoping", category: "Cost control", sev: Sev::Medium, effort: 2,
        applies: Applies::All,
        title: ["rule `{name}` loads in every session",
                "ルール `{name}` が毎セッション読み込まれる"],
        full: ["Every rule carries `paths:` except the six that load unconditionally by design.",
               "設計上常に読み込む 6 つを除き、すべてのルールが `paths:` を持つ。"],
        why: ["A rule without paths frontmatter is a permanent context tax on every agent in every session, whether or not the work touches it.",
              "paths のないルールは、作業が関係するかどうかにかかわらず、すべてのセッションのすべてのエージェントに課されるコンテキスト税です。"],
        fix: ["Add to the top of `.claude/rules/{name}.md`: `---` / `paths:` / `  - \"<glob it governs>\"` / `---`.",
              "`.claude/rules/{name}.md` の先頭に `---` / `paths:` / `  - \"<対象のグロブ>\"` / `---` を加える。"],
    },
    Rule {
        id: "COST-06", check: "instruction-length", category: "Cost control", sev: Sev::Low, effort: 3,
        applies: Applies::All,
        title: ["CLAUDE.md and AGENTS.md together run to {extra} lines",
                "CLAUDE.md と AGENTS.md の合計が {extra} 行ある"],
        full: ["CLAUDE.md and AGENTS.md together stay under 200 lines.",
               "CLAUDE.md と AGENTS.md の合計が 200 行未満。"],
        why: ["Both load in every session, and adherence drops as they grow.",
              "どちらも毎セッション読み込まれ、長くなるほど守られにくくなります。"],
        fix: ["Move detail into path-scoped rules under `.claude/rules/` until the two files total under 200 lines.",
              "2 つのファイルの合計が 200 行未満になるまで、詳細を `.claude/rules/` の paths 付きルールへ移す。"],
    },
    // ------------------------------------------------------- Traceability
    Rule {
        id: "TRC-01", check: "task-owner-missing", category: "Traceability", sev: Sev::Medium, effort: 2,
        applies: Applies::All,
        title: ["task `{name}` is owned by `{extra}`, which is not on the roster",
                "タスク `{name}` の担当 `{extra}` が名簿にいない"],
        full: ["Every task's owner is a seat that exists.",
               "すべてのタスクの担当が実在するエージェントである。"],
        why: ["Work assigned to a seat that does not exist cannot be dispatched and will sit on the board unnoticed.",
              "存在しない担当に割り当てた作業は委譲できず、気づかれないままボードに残ります。"],
        fix: ["Set the owner at the evidence line to a seat in `.claude/agents/`, or create `.claude/agents/{extra}.md`.",
              "根拠の行の担当を `.claude/agents/` にいるエージェントに変えるか、`.claude/agents/{extra}.md` を作る。"],
    },
    Rule {
        id: "TRC-02", check: "dangling-script", category: "Traceability", sev: Sev::Medium, effort: 2,
        applies: Applies::All,
        title: ["`{name}` runs `{extra}`, which is not installed",
                "`{name}` が実行する `{extra}` がインストールされていない"],
        full: ["Every script a command runs exists in `.claude/scripts/`.",
               "コマンドが実行するスクリプトが、すべて `.claude/scripts/` に存在する。"],
        why: ["The command names a script that is not there, so it fails the first time it is used.",
              "存在しないスクリプトを指すコマンドは、最初に使ったときに失敗します。"],
        fix: ["Install the script (`/harness-update` re-installs shipped scripts), or remove the reference at the evidence line.",
              "スクリプトを導入する（同梱のものは `/harness-update` で再導入できる）か、根拠の行の参照を削除する。"],
    },
    Rule {
        id: "TRC-03", check: "skill-not-wired", category: "Traceability", sev: Sev::Low, effort: 2,
        applies: Applies::All,
        title: ["skill `{name}` is installed but nothing in the harness names it",
                "スキル `{name}` は導入済みだが、ハーネスのどこからも参照されていない"],
        full: ["Every installed skill is named by a seat, a command or a rule.",
               "導入したスキルが、すべていずれかのエージェント・コマンド・ルールから参照されている。"],
        why: ["An unwired skill still costs review and update attention while changing nothing about how the harness behaves.",
              "参照されないスキルは、ハーネスの動きを何も変えないのに、レビューと更新の手間だけがかかります。"],
        fix: ["Run `/skill-wire {name}` to declare it on the seat that uses it, or remove `.claude/skills/{name}/`.",
              "`/skill-wire {name}` で使う担当に宣言するか、`.claude/skills/{name}/` を削除する。"],
    },
    Rule {
        id: "TRC-04", check: "skill-wire-missing", category: "Traceability", sev: Sev::Medium, effort: 2,
        applies: Applies::All,
        title: ["`{name}` declares skill `{extra}`, which is not installed",
                "`{name}` が宣言するスキル `{extra}` が導入されていない"],
        full: ["Every skill a seat declares is installed under `.claude/skills/`.",
               "エージェントが宣言するスキルが、すべて `.claude/skills/` に導入されている。"],
        why: ["The seat's instructions promise a capability the repo cannot supply, so the model follows a procedure that is not there.",
              "担当の指示が存在しない能力を約束しているため、モデルはない手順に従おうとします。"],
        fix: ["Install the skill under `.claude/skills/{extra}/`, or remove it from the seat at the evidence line.",
              "スキルを `.claude/skills/{extra}/` に導入するか、根拠の行から削除する。"],
    },
    // ------------------------------------------------------- Board health
    Rule {
        id: "BRD-01", check: "blocked-no-unblocker", category: "Board health", sev: Sev::Medium, effort: 1,
        applies: Applies::All,
        title: ["task `{name}` is Blocked with no dependency recorded",
                "タスク `{name}` が Blocked なのに依存が記録されていない"],
        full: ["Every Blocked task records what would unblock it.",
               "Blocked のタスクが、すべて解除条件を記録している。"],
        why: ["Nothing names what would unblock it, so it cannot be picked up when the blocker clears.",
              "解除条件が書かれていないため、原因が解消しても再開されません。"],
        fix: ["Add `deps: TASK-NNN` (what unblocks it) to the frontmatter at the evidence line.",
              "根拠の行の frontmatter に `deps: TASK-NNN`（解除条件）を加える。"],
    },
    Rule {
        id: "BRD-02", check: "task-no-status", category: "Board health", sev: Sev::Low, effort: 1,
        applies: Applies::All,
        title: ["task `{name}` has no status",
                "タスク `{name}` に状態がない"],
        full: ["Every task carries a status.",
               "すべてのタスクが状態を持つ。"],
        why: ["A task with no status is invisible to every board sweep that filters by it.",
              "状態のないタスクは、状態で絞り込むボードの確認から漏れます。"],
        fix: ["Add `status: Pending` (or the board's real state) to the frontmatter of the task file.",
              "タスクファイルの frontmatter に `status: Pending`（またはボード上の実際の状態）を加える。"],
    },
    Rule {
        id: "BRD-03", check: "board-drift", category: "Board health", sev: Sev::Medium, effort: 1,
        applies: Applies::All,
        title: ["task `{name}`: {extra}",
                "タスク `{name}`: {extra}"],
        full: ["On an orchestrator-kit board, every task's folder, `status:` and `TASKS.md` row agree.",
               "orchestrator-kit のボードで、すべてのタスクのフォルダ・`status:`・`TASKS.md` の行が一致している。"],
        why: ["The folder, the status and the index disagree, so whichever one a reader trusts, another says something else.",
              "フォルダ・状態・集約ファイルが食い違い、どれを信じても別の場所が違うことを言っています。"],
        fix: ["Run `bash .claude/scripts/task.sh check`, then `bash .claude/scripts/task.sh move {name} <state>` to the state that is true. Never edit TASKS.md by hand.",
              "`bash .claude/scripts/task.sh check` を実行し、`bash .claude/scripts/task.sh move {name} <状態>` で正しい状態に移す。TASKS.md は手で編集しない。"],
    },
    // ------------------------------------------------------- Docs quality
    Rule {
        id: "DOC-01", check: "table-blank-line", category: "Docs quality", sev: Sev::Low, effort: 1,
        applies: Applies::All,
        title: ["{name}: blank line inside a table at line {extra}",
                "{name}: {extra} 行目で表の中に空行がある"],
        full: ["No Markdown table in a task or the master plan has a blank line between rows.",
               "タスクとマスタープランの Markdown の表に、行の間の空行がない。"],
        why: ["A blank line terminates a table in GitHub-flavoured Markdown, so every row after it renders as plain text here and on GitHub.",
              "GitHub 形式の Markdown では空行で表が終わるため、それ以降の行はここでも GitHub でもただの文章になります。"],
        fix: ["Delete the blank line at the evidence line.",
              "根拠の行の空行を削除する。"],
    },
    // ----------------------------------------------------------- Contract
    Rule {
        id: "CON-01", check: "instruction-contract", category: "Contract", sev: Sev::Medium, effort: 3,
        applies: Applies::All,
        title: ["no AGENTS.md at the repository root",
                "リポジトリのルートに AGENTS.md がない"],
        full: ["`AGENTS.md` exists at the repository root.",
               "リポジトリのルートに `AGENTS.md` がある。"],
        why: ["AGENTS.md is the vendor-neutral contract every tool but Claude Code reads; without it the rules under .claude/ reach one client and nothing else.",
              "AGENTS.md は Claude Code 以外のすべてのツールが読む共通の契約です。これがないと、.claude/ のルールは 1 つのクライアントにしか届きません。"],
        fix: ["Create `AGENTS.md` at the root (`/harness-update` scaffolds it) and make `CLAUDE.md` start with `@AGENTS.md`.",
              "ルートに `AGENTS.md` を作り（`/harness-update` で生成できる）、`CLAUDE.md` の先頭を `@AGENTS.md` にする。"],
    },
    Rule {
        id: "CON-02", check: "instruction-tiers", category: "Contract", sev: Sev::Info, effort: 2,
        applies: Applies::All,
        title: ["AGENTS.md states no routing tiers",
                "AGENTS.md に作業の区分表がない"],
        full: ["An instruction file carries the Direct / Standard / Guarded tier table.",
               "指示ファイルに Direct / Standard / Guarded の区分表がある。"],
        why: ["Without the tier table nothing says which changes go straight to the owning agent and which earn the orchestrator, so every change costs the heaviest process or none of it.",
              "区分表がなければ、どの変更を担当へ直接回し、どれをオーケストレーターに回すかが決まらず、すべてが最も重い手順か、何の手順もなしになります。"],
        fix: ["Add the tier table to AGENTS.md, as the skill's `assets/root/AGENTS.md` writes it.",
              "スキルの `assets/root/AGENTS.md` と同じ区分表を AGENTS.md に加える。"],
    },
    Rule {
        id: "CON-03", check: "instruction-nested-stub", category: "Contract", sev: Sev::Low, effort: 2,
        applies: Applies::All,
        title: ["{name} governs a subtree and says almost nothing",
                "{name} はサブツリーを管轄するのに、ほとんど何も書いていない"],
        full: ["Every per-folder instruction file says something specific about its subtree.",
               "フォルダ単位の指示ファイルが、すべてそのサブツリー固有の内容を書いている。"],
        why: ["A per-folder contract applies to every change under its directory; an empty one is worse than none, because the folder reads as governed.",
              "フォルダ単位の契約は配下のすべての変更に適用されます。中身のないものは、管理されているように見える分、ないより悪いです。"],
        fix: ["Write what is different about this subtree into {name}, or delete it.",
              "このサブツリー固有の決まりを {name} に書くか、ファイルを削除する。"],
    },
];

pub fn rule(check: &str) -> &'static Rule {
    RULES
        .iter()
        .find(|r| r.check == check)
        .unwrap_or_else(|| panic!("no rubric entry for check `{check}`"))
}

/// `{name}` and `{extra}` substituted.
pub fn render(t: &str, name: &str, extra: &str) -> String {
    t.replace("{name}", name).replace("{extra}", extra)
}

/// The scoring method, stated once so the page, the CLI and the document agree.
pub const METHOD: [&str; 2] = [
    "Each category starts at 100 and loses the weight of every finding in it (high 12, medium 5,      low 2, info 0), floored at 0. A rule that does not apply to this repository's purpose is not      checked, and a category with nothing to assess (Board health with no tasks; Traceability with      no tasks, commands or skills) is marked n/a rather than scored 100. Overall is the integer mean      of the six categories, n/a ones left out, rounded down; while a high Safety finding is open it      is capped at the Safety score, because a harness is only as trustworthy as its guardrails.      The weights are a stated convention, not a measurement.",
    "各カテゴリーは 100 点から始まり、そのカテゴリーの指摘ごとに重み（high 12、medium 5、low 2、     info 0）を引き、0 点で止まります。リポジトリの目的に当てはまらないルールは検査しません。検査対象が     ないカテゴリー（タスクのないタスクボード、タスク・コマンド・スキルのないトレーサビリティ）は 100 点     ではなく n/a とします。総合点は 6 カテゴリーのうち n/a を除いたものの平均の整数部分です。安全性に      high の指摘が残っている間は、総合点は安全性の点数を上限とします。ハーネスの信頼性はガードレール以上に     はならないからです。重みは取り決めであり、測定値ではありません。",
];

pub const NOT_MEASURED: [[&str; 2]; 4] = [
    ["whether the rules say anything useful for this codebase",
     "ルールがこのリポジトリにとって有用なことを言っているか"],
    ["whether the agents' scopes match how the work is really organised",
     "エージェントの担当範囲が実際の作業の分け方と合っているか"],
    ["whether a hook that exists actually blocks what it claims to",
     "存在するフックが、主張どおりのものを実際に止めるか"],
    ["code quality, test quality, writing quality, or the depth of any review",
     "コード・テスト・文章の品質や、レビューの深さ"],
];

/// The rubric as JSON, for the page.
pub fn to_json() -> Value {
    let rules: Vec<Value> = RULES
        .iter()
        .map(|r| {
            json!({
                "id": r.id, "check": r.check, "category": r.category,
                "category_ja": category_ja(r.category),
                "severity": r.sev.as_str(), "weight": r.sev.weight(), "effort": r.effort,
                "applies": r.applies.as_str(),
                "title": r.title[0], "title_ja": r.title[1],
                "full": r.full[0], "full_ja": r.full[1],
                "why": r.why[0], "why_ja": r.why[1],
                "fix": r.fix[0], "fix_ja": r.fix[1],
            })
        })
        .collect();
    json!({ "rules": rules, "method": METHOD[0], "method_ja": METHOD[1] })
}

/// The published document, in English (`lang` = "en") or Japanese ("ja").
/// RUBRIC.md and RUBRIC.ja.md are exactly this output.
pub fn markdown(lang: &str) -> String {
    let ja = lang == "ja";
    let i = usize::from(ja);
    let mut s = String::new();
    if ja {
        s.push_str("# harness-view 採点基準（ルーブリック）\n\n");
        s.push_str("<!-- 生成ファイル: `harness-view rubric --lang ja > RUBRIC.ja.md`。手で編集しない。");
        s.push_str("src/rubric.rs が正本で、tests/rubric_test.rs が一致を検査する。 -->\n\n");
        s.push_str("[English](RUBRIC.md) · **日本語**\n\n");
        s.push_str("`harness-view assess` が適用するすべてのルールです。指摘はルール ID・根拠（ファイル:行）・");
        s.push_str("理由・具体的な修正方法を持ち、点数はこの表だけで再計算できます。\n\n");
        s.push_str("## 計算方法\n\n");
    } else {
        s.push_str("# harness-view rubric\n\n");
        s.push_str("<!-- Generated: `harness-view rubric > RUBRIC.md`. Do not edit by hand. ");
        s.push_str("src/rubric.rs is the source; tests/rubric_test.rs keeps the two equal. -->\n\n");
        s.push_str("**English** · [日本語](RUBRIC.ja.md)\n\n");
        s.push_str("Every rule `harness-view assess` applies. Each finding names its rule id, the ");
        s.push_str("evidence (file:line), why it matters and a concrete fix, and the score can be ");
        s.push_str("recomputed from this table alone.\n\n");
        s.push_str("## How the score is computed\n\n");
    }
    s.push_str(METHOD[i]);
    s.push_str("\n\n");
    if ja {
        s.push_str("| 重大度 | 重み |\n|---|---|\n");
    } else {
        s.push_str("| severity | weight |\n|---|---|\n");
    }
    for sev in [Sev::High, Sev::Medium, Sev::Low, Sev::Info] {
        s.push_str(&format!("| {} | {} |\n", sev.as_str(), sev.weight()));
    }
    s.push('\n');
    if ja {
        s.push_str("**手間**: 1 = ワンクリックか 1 行、2 = 1 ファイルの小さな編集、3 = 判断か新しいファイルが必要。");
        s.push_str("作業リストは「重み × 件数 ÷ 手間」の大きい順に並びます。\n\n");
        s.push_str("**対象**: `all` はすべてのリポジトリ、`code` はコードを目的に含むリポジトリ、");
        s.push_str("`non-code` は調査・戦略・文書を目的に含むリポジトリ。目的は `.claude/state/vars.json` の ");
        s.push_str("`purpose_*` フラグから、なければエージェントの構成から判定します。\n\n");
    } else {
        s.push_str("**Effort**: 1 = one click or one line, 2 = a small edit in one file, 3 = a decision ");
        s.push_str("or a new file. The worklist orders rules by weight times count divided by effort.\n\n");
        s.push_str("**Applies**: `all` to every repository, `code` when the repository's purposes include ");
        s.push_str("code, `non-code` when they include research, strategy or docs. The purposes come from ");
        s.push_str("the `purpose_*` flags in `.claude/state/vars.json`, else from the roster.\n\n");
    }
    for (cat, cat_ja) in CATEGORIES {
        s.push_str(&format!("## {}\n\n", if ja { *cat_ja } else { *cat }));
        for r in RULES.iter().filter(|r| r.category == *cat) {
            s.push_str(&format!(
                "### {} `{}`\n\n",
                r.id, r.check
            ));
            if ja {
                s.push_str(&format!(
                    "- 重大度: {}（重み {}） · 手間: {} · 対象: {}\n",
                    r.sev.as_str(), r.sev.weight(), r.effort, r.applies.as_str()
                ));
                s.push_str(&format!("- 満点の条件: {}\n", r.full[1]));
                s.push_str(&format!("- 指摘: {}\n", r.title[1]));
                s.push_str(&format!("- 理由: {}\n", r.why[1]));
                s.push_str(&format!("- 修正: {}\n\n", r.fix[1]));
            } else {
                s.push_str(&format!(
                    "- severity: {} (weight {}) · effort: {} · applies: {}\n",
                    r.sev.as_str(), r.sev.weight(), r.effort, r.applies.as_str()
                ));
                s.push_str(&format!("- full marks: {}\n", r.full[0]));
                s.push_str(&format!("- finding: {}\n", r.title[0]));
                s.push_str(&format!("- why: {}\n", r.why[0]));
                s.push_str(&format!("- fix: {}\n\n", r.fix[0]));
            }
        }
    }
    s.push_str(if ja { "## 測定していないもの\n\n" } else { "## What the score does not measure\n\n" });
    for nm in NOT_MEASURED {
        s.push_str(&format!("- {}\n", nm[i]));
    }
    s
}
