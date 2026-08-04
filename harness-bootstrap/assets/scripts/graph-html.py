#!/usr/bin/env python3
"""Export the harness's knowledge graphs as two self-contained interactive HTML files.

  docs/context/specs-graph.html    the DOCS graph: spec sections, requirements, ADRs, tasks,
                                   and the ID references that tie them together (traceability)
  docs/context/harness-graph.html  the HARNESS graph: agents, hooks, rules, commands,
                                   settings.json, code modules, and the wiring between them -
                                   including the code<->docs edges (which seat owns which module,
                                   which module the active tasks talk about)

Both files are single-file HTML with inline vanilla-JS force layout: no CDN, no network, they
open from disk anywhere. Stdlib only to generate.

Inputs (build them first):
  .claude/state/docs-graph.json    from docs-graph.py       (specs graph)
  .claude/state/code-graph.json    from code-graph.py       (harness graph, module part)
  .claude/ itself                  scanned live             (harness graph, wiring part)

Usage:
  python .claude/scripts/graph-html.py             # writes both files (skips one if its input is missing)
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

CAT_COLORS = {
    "agent": "#35348f", "hook": "#b3261e", "rule": "#1e6f50", "command": "#8a6d00",
    "settings": "#5f3dc4", "module": "#0b6bcb", "doc": "#666666", "script": "#9c27b0",
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  body { margin:0; font:14px/1.4 system-ui, sans-serif; background:#fafafa; color:#222; }
  header { padding:10px 16px; background:#35348f; color:#fff; display:flex; gap:16px; align-items:baseline; flex-wrap:wrap; }
  header h1 { font-size:16px; margin:0; }
  header span { font-size:12px; opacity:.85; }
  #legend { display:flex; gap:12px; padding:6px 16px; flex-wrap:wrap; font-size:12px; background:#fff; border-bottom:1px solid #ddd; }
  .lg { display:flex; align-items:center; gap:4px; }
  .dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
  #wrap { position:relative; }
  canvas { display:block; width:100vw; height:calc(100vh - 92px); cursor:grab; }
  #info { position:absolute; right:12px; top:12px; max-width:340px; background:#fff; border:1px solid #ccc;
          border-radius:6px; padding:10px 12px; font-size:12px; display:none; box-shadow:0 2px 8px rgba(0,0,0,.15); }
  #info h2 { font-size:13px; margin:0 0 6px; }
  #info ul { margin:4px 0 0 16px; padding:0; }
</style>
</head>
<body>
<header><h1>__TITLE__</h1><span>__SUBTITLE__</span><span>drag nodes | wheel zooms | click a node for details</span></header>
<div id="legend">__LEGEND__</div>
<div id="wrap"><canvas id="c"></canvas><div id="info"></div></div>
<script>
const GRAPH = __DATA__;
const COLORS = __COLORS__;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
let W, H, scale = 1, ox = 0, oy = 0;
function resize(){ W = cv.width = cv.clientWidth * devicePixelRatio; H = cv.height = cv.clientHeight * devicePixelRatio; }
window.addEventListener('resize', () => { resize(); });
resize();
const N = GRAPH.nodes, E = GRAPH.edges;
const idx = {}; N.forEach((n,i)=>{ idx[n.id]=i;
  n.x = (Math.cos(i*2.399963)*0.35+0.5)*W; n.y = (Math.sin(i*2.399963)*0.35+0.5)*H;
  n.vx = 0; n.vy = 0; n.deg = 0; });
E.forEach(e => { e.s = idx[e.from]; e.t = idx[e.to];
  if (e.s !== undefined) N[e.s].deg++; if (e.t !== undefined) N[e.t].deg++; });
const links = E.filter(e => e.s !== undefined && e.t !== undefined);
function r(n){ return (6 + Math.min(14, Math.sqrt(n.deg)*3)) * devicePixelRatio; }
let ticks = 0;
function step(){
  const K = 0.02, REP = 5200 * devicePixelRatio * devicePixelRatio, CEN = 0.004;
  for (let i=0;i<N.length;i++) for (let j=i+1;j<N.length;j++){
    const a=N[i], b=N[j]; let dx=a.x-b.x, dy=a.y-b.y; let d2=dx*dx+dy*dy || 1;
    if (d2 < 640000*devicePixelRatio){ const f = REP/d2; const d=Math.sqrt(d2);
      dx/=d; dy/=d; a.vx+=dx*f; a.vy+=dy*f; b.vx-=dx*f; b.vy-=dy*f; } }
  links.forEach(e => { const a=N[e.s], b=N[e.t]; const dx=b.x-a.x, dy=b.y-a.y;
    const d=Math.sqrt(dx*dx+dy*dy)||1; const want=(120+8*Math.min(e.refs||1,6))*devicePixelRatio;
    const f=K*(d-want)/d; a.vx+=dx*f; a.vy+=dy*f; b.vx-=dx*f; b.vy-=dy*f; });
  N.forEach(n => { n.vx += (W/2-n.x)*CEN; n.vy += (H/2-n.y)*CEN;
    if (n !== drag.node){ n.x += n.vx*0.85; n.y += n.vy*0.85; } n.vx*=0.6; n.vy*=0.6; });
  ticks++;
}
function draw(){
  ctx.setTransform(1,0,0,1,0,0); ctx.clearRect(0,0,W,H);
  ctx.setTransform(scale,0,0,scale,ox,oy);
  ctx.lineWidth = 1*devicePixelRatio;
  links.forEach(e => { const a=N[e.s], b=N[e.t];
    ctx.strokeStyle = 'rgba(80,80,120,'+Math.min(0.15+0.08*(e.refs||1),0.6)+')';
    ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke(); });
  ctx.font = (11*devicePixelRatio)+'px system-ui, sans-serif';
  N.forEach(n => { const rr=r(n);
    ctx.fillStyle = COLORS[n.cat] || '#444';
    ctx.beginPath(); ctx.arc(n.x,n.y,rr,0,7); ctx.fill();
    ctx.fillStyle = '#222'; ctx.fillText(n.label, n.x+rr+3*devicePixelRatio, n.y+4*devicePixelRatio); });
}
const drag = { node:null, panning:false, px:0, py:0 };
function pick(mx,my){ const x=(mx*devicePixelRatio-ox)/scale, y=(my*devicePixelRatio-oy)/scale;
  return N.find(n => { const dx=n.x-x, dy=n.y-y; const rr=r(n)+4; return dx*dx+dy*dy < rr*rr; }); }
cv.addEventListener('mousedown', ev => { const n = pick(ev.offsetX, ev.offsetY);
  if (n){ drag.node = n; } else { drag.panning = true; } drag.px = ev.offsetX; drag.py = ev.offsetY; });
window.addEventListener('mouseup', () => { drag.node = null; drag.panning = false; });
cv.addEventListener('mousemove', ev => {
  if (drag.node){ drag.node.x = (ev.offsetX*devicePixelRatio-ox)/scale; drag.node.y = (ev.offsetY*devicePixelRatio-oy)/scale; ticks = 0; }
  else if (drag.panning){ ox += (ev.offsetX-drag.px)*devicePixelRatio; oy += (ev.offsetY-drag.py)*devicePixelRatio;
    drag.px = ev.offsetX; drag.py = ev.offsetY; } });
cv.addEventListener('wheel', ev => { ev.preventDefault();
  const f = ev.deltaY < 0 ? 1.1 : 0.9; const mx = ev.offsetX*devicePixelRatio, my = ev.offsetY*devicePixelRatio;
  ox = mx - (mx-ox)*f; oy = my - (my-oy)*f; scale *= f; }, { passive:false });
const info = document.getElementById('info');
cv.addEventListener('click', ev => { const n = pick(ev.offsetX, ev.offsetY);
  if (!n){ info.style.display='none'; return; }
  const out = links.filter(e=>e.s===idx[n.id]).map(e=>N[e.t].label+' ('+(e.refs||1)+')');
  const inn = links.filter(e=>e.t===idx[n.id]).map(e=>N[e.s].label+' ('+(e.refs||1)+')');
  info.innerHTML = '<h2>'+n.label+'</h2><div>'+(n.detail||n.cat)+'</div>'
    + (out.length ? '<div><b>references:</b><ul><li>'+out.join('</li><li>')+'</li></ul></div>' : '')
    + (inn.length ? '<div><b>referenced by:</b><ul><li>'+inn.join('</li><li>')+'</li></ul></div>' : '');
  info.style.display='block'; });
(function loop(){ if (ticks < 300) step(); draw(); requestAnimationFrame(loop); })();
</script>
</body>
</html>
"""


def render(title: str, subtitle: str, nodes: list, edges: list, cats: list[str]) -> str:
    legend = "".join(
        f'<span class="lg"><span class="dot" style="background:{CAT_COLORS[c]}"></span>{c}</span>'
        for c in cats)
    return (HTML_TEMPLATE
            .replace("__TITLE__", title)
            .replace("__SUBTITLE__", subtitle)
            .replace("__LEGEND__", legend)
            .replace("__COLORS__", json.dumps(CAT_COLORS))
            .replace("__DATA__", json.dumps({"nodes": nodes, "edges": edges})))


def specs_graph(root: pathlib.Path) -> str | None:
    src = root / ".claude" / "state" / "docs-graph.json"
    if not src.exists():
        return None
    g = json.loads(src.read_text(encoding="utf-8"))
    linked = {e["from"] for e in g["edges"]} | {e["to"] for e in g["edges"]}
    nodes = [{"id": d, "label": d.split("/")[-1], "cat": "doc", "detail": d}
             for d in sorted(linked)]
    edges = [{"from": e["from"], "to": e["to"], "refs": e["refs"]} for e in g["edges"]]
    out = root / "docs" / "context" / "specs-graph.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render("Specs graph", "documents linked by shared requirement / decision / task IDs",
                          nodes, edges, ["doc"]), encoding="utf-8")
    return out.relative_to(root).as_posix()


def harness_graph(root: pathlib.Path) -> str | None:
    claude = root / ".claude"
    if not claude.exists():
        return None
    nodes, edges = [], []

    def add(id_, label, cat, detail=""):
        nodes.append({"id": id_, "label": label, "cat": cat, "detail": detail})

    add("settings", "settings.json", "settings", "permissions + hook registration")

    agents = sorted((claude / "agents").glob("*.md")) if (claude / "agents").exists() else []
    for a in agents:
        head = a.read_text(encoding="utf-8", errors="replace")[:700]
        model = re.search(r"^model:\s*(\S+)", head, re.M)
        add(f"agent:{a.stem}", a.stem, "agent",
            f"model {model.group(1) if model else 'inherit'}")
    if any(a.stem == "orchestrator" for a in agents):
        for a in agents:
            if a.stem != "orchestrator":
                edges.append({"from": "agent:orchestrator", "to": f"agent:{a.stem}", "refs": 1})

    hooks = sorted({p.stem for p in (claude / "hooks").glob("*.sh")} |
                   {p.stem for p in (claude / "hooks").glob("*.ps1")}) if (claude / "hooks").exists() else []
    for h in hooks:
        add(f"hook:{h}", h, "hook")
        edges.append({"from": "settings", "to": f"hook:{h}", "refs": 1})

    rules = sorted((claude / "rules").glob("*.md")) if (claude / "rules").exists() else []
    for rl in rules:
        head = rl.read_text(encoding="utf-8", errors="replace")[:200]
        scoped = head.startswith("---") and "paths:" in head
        add(f"rule:{rl.stem}", rl.stem, "rule", "path-scoped" if scoped else "always loaded")
        if not scoped:
            for a in agents:
                edges.append({"from": f"agent:{a.stem}", "to": f"rule:{rl.stem}", "refs": 1})

    cmds = sorted((claude / "commands").glob("*.md")) if (claude / "commands").exists() else []
    for c in cmds:
        add(f"cmd:{c.stem}", "/" + c.stem, "command")
        body = c.read_text(encoding="utf-8", errors="replace")
        for s in re.findall(r"\.claude/scripts/([\w-]+)\.py", body):
            sid = f"script:{s}"
            if not any(n["id"] == sid for n in nodes):
                add(sid, s + ".py", "script")
            edges.append({"from": f"cmd:{c.stem}", "to": sid, "refs": 1})

    cg = claude / "state" / "code-graph.json"
    if cg.exists():
        g = json.loads(cg.read_text(encoding="utf-8"))
        for mod, info in g.get("modules", {}).items():
            add(f"mod:{mod}", mod, "module", f"{len(info.get('files', []))} files")
            owner = info.get("owner", "-")
            if owner != "-" and any(n["id"] == f"agent:{owner}" for n in nodes):
                edges.append({"from": f"agent:{owner}", "to": f"mod:{mod}", "refs": 2})
        for e in g.get("edges", []):
            edges.append({"from": f"mod:{e['from']}", "to": f"mod:{e['to']}", "refs": e["refs"]})

    # code<->docs: active tasks referencing modules
    tasks = sorted((root / "docs" / "tasks").rglob("TASK-*.md")) if (root / "docs" / "tasks").exists() else []
    mod_names = [n["id"][4:] for n in nodes if n["cat"] == "module"]
    for t in tasks[:60]:
        body = t.read_text(encoding="utf-8", errors="replace")
        tid = f"doc:{t.stem}"
        hits = [m for m in mod_names if m.split("/")[-1] in body]
        if hits:
            add(tid, t.stem, "doc", t.relative_to(root).as_posix())
            for m in hits:
                edges.append({"from": tid, "to": f"mod:{m}", "refs": 1})

    out = root / "docs" / "context" / "harness-graph.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    cats = ["agent", "hook", "rule", "command", "settings", "module", "doc", "script"]
    out.write_text(render("Harness graph",
                          "agents, hooks, rules, commands, settings, code modules, and the docs that bind them",
                          nodes, edges, cats), encoding="utf-8")
    return out.relative_to(root).as_posix()


def main() -> int:
    root = pathlib.Path(sys.argv[sys.argv.index("--target") + 1]).resolve() \
        if "--target" in sys.argv else pathlib.Path(".").resolve()
    wrote = []
    for fn in (specs_graph, harness_graph):
        res = fn(root)
        if res:
            wrote.append(res)
        else:
            print(f"graph-html: skipped {fn.__name__} (input missing - build the JSON first)")
    for w in wrote:
        print(f"graph-html: wrote {w}")
    return 0 if wrote else 1


if __name__ == "__main__":
    sys.exit(main())
