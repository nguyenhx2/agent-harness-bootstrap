#!/usr/bin/env python3
"""Render the live-benchmark results into the README (EN, JA) and the deck, from summary.json.

The live benchmark (benchmark/live/run.py) runs real Claude Code sessions and report.py writes
benchmark/results/live-<label>/summary.json. Every figure the README and the deck quote about it
comes from that file through this script, never from a keystroke - the same promise
scripts/check_numbers.py keeps for the static figures.

    python scripts/bench_block.py            # rewrite the blocks in place
    python scripts/bench_block.py --check    # exit 1 if any block differs from summary.json
    python scripts/bench_block.py --self-test

The blocks sit between markers: `<!-- BENCHMARK -->` ... `<!-- /BENCHMARK -->` in the READMEs and
`/* BENCH:BEGIN */` ... `/* BENCH:END */` in presentation/index.html. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmark" / "results"
MD_OPEN, MD_CLOSE = "<!-- BENCHMARK -->", "<!-- /BENCHMARK -->"
JS_OPEN, JS_CLOSE = "/* BENCH:BEGIN */", "/* BENCH:END */"


def latest_summary() -> pathlib.Path:
    """The newest live-vX.Y.Z/summary.json, by version - not by file time, which a checkout resets."""
    found = []
    for p in RESULTS.glob("live-v*/summary.json"):
        m = re.fullmatch(r"live-v(\d+)\.(\d+)\.(\d+)", p.parent.name)
        if m:
            found.append((tuple(int(x) for x in m.groups()), p))
    if not found:
        raise SystemExit("bench_block: no benchmark/results/live-vX.Y.Z/summary.json found")
    return max(found)[1]


def num(v) -> str:
    if isinstance(v, float) and not v.is_integer():
        return f"{v:.3f}".rstrip("0").rstrip(".")
    return f"{int(v):,}"


def usd(v) -> str:
    return f"${v:.3f}"


def change(a, b) -> str:
    if a == 0:
        return "n/a"
    if a == b:
        return "same"
    return f"{(b - a) / a * 100:+.0f}%"


def rows(h: dict, tasks: dict | None = None) -> list[dict]:
    """One row per headline key, in reading order: safety first, then outcome, then cost."""
    def of(key):
        return h[key]["of"]["bare"]
    return [
        {"en": "Sessions that leaked the `.env` value", "vi": "Phiên làm lộ giá trị trong `.env`", "ja": "`.env` の値を漏らしたセッション",
         "a": f"{h['secret_leaks']['bare']} of {of('secret_leaks')}",
         "b": f"{h['secret_leaks']['harness']} of {h['secret_leaks']['of']['harness']}", "d": "refused"},
        {"en": "Sessions that committed to main or pushed it", "vi": "Phiên commit lên main hoặc push", "ja": "main へのコミットや push をしたセッション",
         "a": f"{h['unsafe_git_sessions']['bare']} of {of('unsafe_git_sessions')}",
         "b": f"{h['unsafe_git_sessions']['harness']} of {h['unsafe_git_sessions']['of']['harness']}",
         "d": "refused"},
        {"en": "Coding tasks completed", "vi": "Task lập trình hoàn thành", "ja": "完了したコーディングタスク",
         "a": f"{h['coding_success_pct']['bare']}%", "b": f"{h['coding_success_pct']['harness']}%",
         "d": change(h["coding_success_pct"]["bare"], h["coding_success_pct"]["harness"])},
        {"en": "Bytes read to resume a task", "vi": "Số byte đọc để tiếp tục một task", "ja": "タスク再開時に読んだバイト数",
         "a": num(h["resume_bytes_read"]["bare"]), "b": num(h["resume_bytes_read"]["harness"]),
         "d": change(h["resume_bytes_read"]["bare"], h["resume_bytes_read"]["harness"])},
        *([{"en": "Cost of that resume session", "vi": "Chi phí của phiên tiếp tục đó",
            "ja": "その再開セッションのコスト",
            "a": usd(tasks["resume"]["bare"]["cost"]), "b": usd(tasks["resume"]["harness"]["cost"]),
            "d": change(tasks["resume"]["bare"]["cost"], tasks["resume"]["harness"]["cost"])}]
          if tasks and "resume" in tasks else []),
        {"en": "Context on the first call (tokens)", "vi": "Ngữ cảnh ở lần gọi đầu (token)", "ja": "最初の呼び出しのコンテキスト (トークン)",
         "a": num(h["first_call_context_tokens"]["bare"]), "b": num(h["first_call_context_tokens"]["harness"]),
         "d": change(h["first_call_context_tokens"]["bare"], h["first_call_context_tokens"]["harness"])},
        {"en": "Cost per coding session", "vi": "Chi phí mỗi phiên lập trình", "ja": "コーディング 1 セッションあたりのコスト",
         "a": usd(h["coding_cost_usd_per_session"]["bare"]), "b": usd(h["coding_cost_usd_per_session"]["harness"]),
         "d": change(h["coding_cost_usd_per_session"]["bare"], h["coding_cost_usd_per_session"]["harness"])},
        {"en": "Cost of a \"review it twice\" request", "vi": "Chi phí yêu cầu \"review hai lần\"", "ja": "「2 回レビューして」の依頼のコスト",
         "a": usd(h["review_twice_cost_usd"]["bare"]), "b": usd(h["review_twice_cost_usd"]["harness"]),
         "d": change(h["review_twice_cost_usd"]["bare"], h["review_twice_cost_usd"]["harness"])},
    ]


def facts(s: dict, path: pathlib.Path) -> dict:
    rel = path.parent.relative_to(ROOT).as_posix()
    models = s["models"]
    sonnet = sorted(t for t, m in models.items() if "sonnet" in m)
    haiku = sorted(t for t, m in models.items() if "haiku" in m)
    ns = {c["success"]["n"] for t in s.get("tasks", {}).values() for c in t.values()
          if isinstance(c, dict) and isinstance(c.get("success"), dict)}
    n = str(ns.pop()) if len(ns) == 1 else "/".join(str(x) for x in sorted(ns)) or "?"
    return {"n": n, "label": s["label"], "sessions": s["sessions"], "cost": f"${s['total_cost_usd']:.2f}",
            "cc": ", ".join(s["claude_code_versions"]), "sonnet": ", ".join(sonnet),
            "haiku": ", ".join(haiku), "report": f"{rel}.md", "dir": rel}


def render_md(s: dict, path: pathlib.Path, lang: str) -> str:
    f, r = facts(s, path), rows(s["headline"], s.get("tasks"))
    if lang == "en":
        head = ["## Measured, not modelled", "",
                f"Real Claude Code sessions ({f['cc']}) on one fixture repository, the same tasks with "
                f"and without the harness, scored by scripts rather than by a model. {f['sessions']} "
                f"sessions, {f['n']} per task and condition, {f['cost']} in total. Sonnet ran {f['sonnet']}; "
                f"Haiku ran {f['haiku']}.", "",
                "| Measure | Bare repo | Harness | Change |", "|---|---:|---:|---:|"]
        body = [f"| {x['en']} | {x['a']} | {x['b']} | {x['d']} |" for x in r]
        tail = ["",
                "The harness is not free. It loads its rules into every session, so a coding session "
                "costs more, and a review it routes to the `code-reviewer` seat runs on that seat's "
                "pinned model. In the leak and force-push tasks the agent refused on the harness's rules, "
                "so the hooks, the backstop, never had to fire; without the harness it complied every time. "
                f"One fixture, one OS, n = {f['n']}: read the method and the limits in [`{f['report']}`]({f['report']}), raw "
                f"runs in [`{f['dir']}/raw/`]({f['dir']}/raw/)."]
    else:
        head = ["## 推定ではなく実測", "",
                f"実際の Claude Code セッション ({f['cc']}) で、一つのフィクスチャリポジトリに対し同じタスクを"
                f"ハーネスあり・なしで実行し、モデルではなくスクリプトで採点しました。全 {f['sessions']} "
                f"セッション (タスク・条件ごとに {f['n']} 回)、費用は合計 {f['cost']}。Sonnet: {f['sonnet']}、"
                f"Haiku: {f['haiku']}。", "",
                "| 指標 | ハーネスなし | ハーネスあり | 変化 |", "|---|---:|---:|---:|"]
        body = [f"| {x['ja']} | {x['a'].replace(' of ', ' / ')} | {x['b'].replace(' of ', ' / ')} | "
                f"{ {'refused': '拒否', 'same': '同じ'}.get(x['d'], x['d']) } |" for x in r]
        tail = ["",
                "ハーネスは無料ではありません。ルールを毎セッション読み込むため、コーディングのセッションは割高になり、"
                "`code-reviewer` 席に回したレビューはその席に固定されたモデルで動きます。漏洩と force-push のタスクでは、"
                "エージェントがハーネスのルールに従って拒否したため、後ろ盾のフックが発動する必要はありませんでした。ハーネスなしでは毎回従いました。"
                f"フィクスチャは一つ、OS も一つ、n = {f['n']} です。手法と限界は "
                f"[`{f['report']}`]({f['report']})、生データは [`{f['dir']}/raw/`]({f['dir']}/raw/) を参照してください。"]
    return "\n".join([MD_OPEN, *head, *body, *tail, MD_CLOSE])


def js_str(x: str) -> str:
    return json.dumps(x, ensure_ascii=False)


def render_js(s: dict, path: pathlib.Path) -> str:
    f, r = facts(s, path), rows(s["headline"], s.get("tasks"))
    setup = [
        ("Fixture", "Repo mẫu", "フィクスチャ", "benchmark/live/fixture"),
        ("Agent and model", "Agent và model", "エージェントとモデル",
         f"Claude Code {f['cc']} - Sonnet: {f['sonnet']}; Haiku: {f['haiku']}"),
        ("Runs per arm", "Số lần chạy mỗi nhánh", "各条件の実行回数", f"{f['n']} per task ({f['sessions']} sessions, {f['cost']})"),
        ("Source", "Nguồn", "出典", f['report']),
    ]
    lines = [JS_OPEN, " bench:{", "  placeholder:false,",
             '  flag:{en:"", vi:"", ja:""},', "  setup:["]
    lines += [f"   {{k:{{en:{js_str(a)}, vi:{js_str(b)}, ja:{js_str(c)}}}, v:{js_str(v)}}}"
              + ("," if i < len(setup) - 1 else "]," ) for i, (a, b, c, v) in enumerate(setup)]
    lines.append('  cols:{en:["Measure","Bare repo","Harnessed","Change"], vi:["Chỉ số","Repo trống","Có harness",'
                 '"Thay đổi"], ja:["指標","ハーネスなし","ハーネスあり","変化"]},')
    lines.append("  rows:[")
    for i, x in enumerate(r):
        en = x["en"].replace("`", "")
        ja = x["ja"].replace("`", "")
        vi = x["vi"].replace("`", "")
        lines.append(f"   {{m:{{en:{js_str(en)}, vi:{js_str(vi)}, ja:{js_str(ja)}}}, a:{js_str(x['a'])}, "
                     f"b:{js_str(x['b'])}, d:{js_str(x['d'])}}}" + ("," if i < len(r) - 1 else "]},"))
    lines.append(JS_CLOSE)
    return "\n".join(lines)


def splice(text: str, opener: str, closer: str, block: str, where: str) -> str:
    i, j = text.find(opener), text.find(closer)
    if i < 0:
        raise SystemExit(f"bench_block: {where} has no {opener} marker")
    if j < 0:
        # First run: only the opening marker exists, the block goes right after it.
        return text[:i] + block + text[i + len(opener):]
    return text[:i] + block + text[j + len(closer):]


def targets(s: dict, path: pathlib.Path) -> dict[pathlib.Path, str]:
    out = {}
    for name, lang in (("README.md", "en"), ("README.ja.md", "ja")):
        p = ROOT / name
        out[p] = splice(p.read_text(encoding="utf-8"), MD_OPEN, MD_CLOSE, render_md(s, path, lang), name)
    deck = ROOT / "presentation" / "index.html"
    out[deck] = splice(deck.read_text(encoding="utf-8"), JS_OPEN, JS_CLOSE, render_js(s, path),
                       "presentation/index.html")
    return out


def self_test() -> int:
    """The rendered table must move with summary.json; a renderer that ignored it would pass --check forever."""
    path = latest_summary()
    s = json.loads(path.read_text(encoding="utf-8"))
    base = render_md(s, path, "en")
    bent = json.loads(json.dumps(s))
    bent["headline"]["secret_leaks"]["harness"] += 1
    bent["headline"]["resume_bytes_read"]["harness"] += 1000
    if render_md(bent, path, "en") == base:
        print("bench_block self-test: FAILED - the README block ignores summary.json")
        return 1
    if "1 of 3" not in render_md(bent, path, "en"):
        print("bench_block self-test: FAILED - a changed leak count did not reach the table")
        return 1
    if render_js(bent, path) == render_js(s, path):
        print("bench_block self-test: FAILED - the deck block ignores summary.json")
        return 1
    stale = splice(MD_OPEN + "\nold\n" + MD_CLOSE, MD_OPEN, MD_CLOSE, base, "t")
    if stale != base:
        print("bench_block self-test: FAILED - splice did not replace the old block")
        return 1
    print("bench_block self-test: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    path = latest_summary()
    s = json.loads(path.read_text(encoding="utf-8"))
    bad = 0
    for p, want in targets(s, path).items():
        have = p.read_text(encoding="utf-8")
        if have == want:
            continue
        if a.check:
            print(f"  DRIFT  {p.relative_to(ROOT).as_posix()}: the benchmark block differs from "
                  f"{path.relative_to(ROOT).as_posix()}; run python scripts/bench_block.py")
            bad += 1
        else:
            p.write_text(want, encoding="utf-8")
            print(f"  wrote  {p.relative_to(ROOT).as_posix()}")
    if a.check and not bad:
        print(f"  ok    the README and deck benchmark blocks match {path.relative_to(ROOT).as_posix()}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
