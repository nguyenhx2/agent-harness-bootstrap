#!/usr/bin/env python3
"""Derive every figure the intro clip shows on screen. Never typed, always read.

Writes three things, none carrying a timestamp:

  - video/intro/src/figures.json   what the Remotion composition reads at render time
  - the generated block at the foot of video/intro/SCRIPT.md and of SCRIPT.ja.md, in the same
    phrasings scripts/check_numbers.py already polices, so a figure that drifts in the repo makes
    that gate name these files, and a re-derived figure changes the scene source
    scripts/check_media.py hashes - which reports the rendered clip stale until it is rendered again.

Counts come from scripts/check_numbers.py's own helpers (roster_range, spec_sections, _const,
ASSETS) rather than a second implementation, because a second answer is how a figure drifts.
canonical() itself is not called: it runs the whole benchmark, which this clip quotes nothing from.
The hook count uses canonical()'s own rule (one hook per stem with a .sh or .ps1 file). The lists
(purpose profiles, routing tiers, rubric rules) are read from the files that define them.

    py -3.13 video/intro/derive_figures.py           # write
    py -3.13 video/intro/derive_figures.py --check   # exit 1 if any output is stale
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FIGURES = HERE / "src" / "figures.json"
SCRIPTS = {"en": HERE / "SCRIPT.md", "ja": HERE / "SCRIPT.ja.md"}
BEGIN, END = "[//]: # (figures:begin)", "[//]: # (figures:end)"
RUBRIC = ROOT / "tools/harness-view/RUBRIC.md"
RUBRIC_JA = ROOT / "tools/harness-view/RUBRIC.ja.md"
# The worklist on screen shows these rules, in the order the worklist would put them for one
# finding each. They are the three rules whose fix the Assess tab can apply in one click (strip
# write tools from a reviewer, give a seat a tool list, pin a model).
WORKLIST = ("SAF-01", "COST-01", "COST-02")

sys.path.insert(0, str(ROOT / "scripts"))
import check_numbers  # noqa: E402


def profiles() -> list[str]:
    src = (ROOT / "harness-bootstrap/scripts/scaffold.py").read_text(encoding="utf-8")
    m = re.search(r"^(?:PURPOSE|PROFILE)_FLAGS\s*=\s*\(([^)]*)\)", src, re.M)
    if not m:
        sys.exit("scaffold.py no longer defines PURPOSE_FLAGS; the team scene cannot be derived.")
    # The flag is `purpose_code`; the card on screen reads `code`.
    return [f.removeprefix("purpose_") for f in re.findall(r'"([a-z_]+)"', m.group(1))]


def tiers() -> list[dict[str, str]]:
    """The routing tiers, in table order, with who runs each one."""
    src = (ROOT / "harness-bootstrap/assets/root/AGENTS.md").read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"^\| \*\*(\w+)\*\* \|[^|]*\|\s*([^|]+?)\s*\|", src, re.M):
        who = m.group(2)
        who = "orchestrator" if "orchestrator`" in who else \
              "main session" if "main session" in who else "owning agent"
        out.append({"name": m.group(1), "who": who})
    if len(out) < 2:
        sys.exit("AGENTS.md tier table not found; the loop scene cannot be derived.")
    return out


def settings_env(name: str) -> int:
    """An integer from the env block of the shipped settings.json (a template, so not JSON)."""
    src = (check_numbers.ASSETS / "settings.json").read_text(encoding="utf-8")
    m = re.search(rf'"{name}"\s*:\s*"(\d+)"', src)
    if not m:
        sys.exit(f"settings.json no longer sets {name}; the lean scene cannot be derived.")
    return int(m.group(1))


def rubric() -> dict:
    en = RUBRIC.read_text(encoding="utf-8")
    ja = RUBRIC_JA.read_text(encoding="utf-8")
    rules = re.findall(r"^### ([A-Z]+-\d+) `", en, re.M)
    # A category is a `##` heading that owns at least one rule.
    cats = [m.group(1) for m in re.finditer(r"^## (.+)\n(?:(?!^## )[\s\S])*?^### [A-Z]+-\d+", en, re.M)]
    weights = dict(re.findall(r"^\| (high|medium|low|info) \| (\d+) \|", en, re.M))
    if len(rules) < 10 or len(cats) < 3 or "high" not in weights:
        sys.exit("RUBRIC.md no longer parses; the assess scene cannot be derived.")

    def rule(rid: str) -> dict:
        def block(text: str) -> str:
            m = re.search(rf"^### {rid} `([^`]+)`\n([\s\S]*?)(?=^### |^## |\Z)", text, re.M)
            if not m:
                sys.exit(f"RUBRIC no longer has {rid}; the assess scene cannot be derived.")
            return m.group(0)
        b, bj = block(en), block(ja)
        sev = re.search(r"severity: (\w+) \(weight (\d+)\) · effort: (\d)", b)
        full = re.search(r"^- full marks: (.+)$", b, re.M).group(1)
        full_ja = re.search(r"^- 満点の条件: (.+)$", bj, re.M).group(1)
        return {"id": rid, "slug": re.search(r"`([^`]+)`", b).group(1), "severity": sev.group(1),
                "weight": int(sev.group(2)), "effort": int(sev.group(3)),
                "full": full, "full_ja": full_ja}

    return {"rules": len(rules), "categories": len(cats), "weight_high": int(weights["high"]),
            "worklist": [rule(r) for r in WORKLIST]}


def derive() -> dict:
    lo, hi = check_numbers.roster_range()
    core, optional = check_numbers.spec_sections()
    assets = check_numbers.ASSETS
    cap = json.loads((ROOT / "docs/assets/CAPTURED.json").read_text(encoding="utf-8"))
    return {
        "eval_cases": check_numbers._const("eval/guardrail_eval.py", "CASES_PER_FLAVOR"),
        # canonical()["hooks"]: one hook per stem that ships a .sh or a .ps1.
        "hooks": len({p.stem for p in (assets / "hooks").glob("*.*") if p.suffix in (".sh", ".ps1")}),
        "roster_min": lo,
        "roster_max": hi,
        # Same rule as canonical()["agents"]: dev-agent is a per-module template, not a seat.
        "seats": len([p for p in (assets / "agents").glob("*.md") if p.stem != "dev-agent"]),
        "review_rounds": check_numbers._const("harness-bootstrap/assets/scripts/verify-plan.py",
                                              "REVIEW_ROUNDS"),
        "spawn_depth": settings_env("CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"),
        "max_subagents": settings_env("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS"),
        "spec_core": core,
        "spec_optional": optional,
        "rubric": rubric(),
        "cap_nodes": cap["nodes"],
        "cap_edges": cap["edges"],
        "cap_score": cap["score"],
        "profiles": profiles(),
        "tiers": tiers(),
    }


def block(f: dict, lang: str) -> str:
    r = f["rubric"]
    n = f["eval_cases"]
    if lang == "ja":
        tier_line = "、".join(t["name"] for t in f["tiers"])
        lines = [
            f"- team: {f['seats']} 席のうち 1 回の実行で入るのは {f['roster_min']} から "
            f"{f['roster_max']} 席。目的プロファイル: {', '.join(f['profiles'])}",
            f"- safe: フックは全 {f['hooks']} 本。ガードレール評価は厳格な構成で、"
            f"フックの系統ごとに {n}/{n}",
            f"- lean: レビューは {f['review_rounds']} ラウンドまで。サブエージェントの起動の深さは "
            f"{f['spawn_depth']}、同時実行は {f['max_subagents']}",
            f"- loop: ティア {tier_line}",
            f"- spec: コア {f['spec_core']} セクションと、最大{f['spec_optional']}セクションは任意",
            f"- assess: 採点表のルール {r['rules']} 件、カテゴリ {r['categories']} 個、"
            f"high の重み {r['weight_high']}。作業リストの例: {', '.join(x['id'] for x in r['worklist'])}",
        ]
    else:
        tier_line = ", ".join(f"{t['name']} ({t['who']})" for t in f["tiers"])
        lines = [
            f"- team scene: a run installs {f['roster_min']} to {f['roster_max']} of the "
            f"{f['seats']} seats; purpose profiles {', '.join(f['profiles'])}",
            f"- safe scene: {f['hooks']} hooks; guardrail eval {n}/{n} per hook flavour, "
            f"on a strict scaffold",
            f"- lean scene: review bounded at {f['review_rounds']} rounds; spawn depth "
            f"{f['spawn_depth']}, at most {f['max_subagents']} concurrent subagents",
            f"- loop scene: tiers {tier_line}",
            f"- spec scene: {f['spec_core']} core sections, up to {f['spec_optional']} optional",
            f"- assess scene: {r['rules']} rubric rules in {r['categories']} categories, a high "
            f"finding weighs {r['weight_high']}; worklist shows "
            f"{', '.join(x['id'] for x in r['worklist'])}; a real harness, {f['cap_nodes']} nodes, "
            f"{f['cap_edges']} edges, scored {f['cap_score']}/100",
        ]
    return "\n".join([BEGIN, *lines, END])


def main(argv: list[str]) -> int:
    f = derive()
    want_json = json.dumps(f, indent=2, ensure_ascii=False) + "\n"
    outputs = [(FIGURES, FIGURES.read_text(encoding="utf-8") if FIGURES.is_file() else "", want_json)]
    for lang, path in SCRIPTS.items():
        text = path.read_text(encoding="utf-8")
        if BEGIN not in text or END not in text:
            sys.exit(f"{path.name} has no figures block; add the begin/end markers back.")
        want = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: block(f, lang), text,
                      flags=re.S)
        outputs.append((path, text, want))
    if "--check" in argv:
        stale = [p.name for p, have, want in outputs if have != want]
        if stale:
            print(f"  FAIL  stale: {', '.join(stale)} - run derive_figures.py, then re-render")
            return 1
        print("  ok    intro figures match the repository")
        return 0
    for p, have, want in outputs:
        if have != want:
            p.write_text(want, encoding="utf-8", newline="\n")
    print(want_json, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
