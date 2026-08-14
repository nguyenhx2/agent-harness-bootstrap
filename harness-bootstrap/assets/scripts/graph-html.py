#!/usr/bin/env python3
"""Export the harness's knowledge graphs as two self-contained interactive HTML files.

  docs/context/specs-graph.html    the DOCS graph: spec sections, requirements, ADRs, tasks,
                                   and the ID references that tie them together (traceability)
  docs/context/harness-graph.html  the HARNESS graph: agents, hooks, rules, commands,
                                   settings.json, code modules, tasks, and the wiring between
                                   them - rendered from the canonical
                                   .claude/state/harness-graph.json (built by harness-graph.py)

The harness page has TWO views: Flow (deterministic layered left-to-right lanes with labeled
edges - gates, triggers, enforces, reviews, owns) and Graph (force layout). Both files are
single-file HTML with inline vanilla JS: no CDN, no network, they open from disk anywhere.
Stdlib only to generate.

Inputs (build them first):
  .claude/state/docs-graph.json      from docs-graph.py     (specs graph)
  .claude/state/harness-graph.json   from harness-graph.py  (harness graph; if missing, the
                                     scanner is invoked in-process as a fallback)

Usage:
  python .claude/scripts/graph-html.py             # writes both files (skips one if its input is missing)
"""
from __future__ import annotations

import json
import pathlib
import sys

CAT_COLORS = {
    "agent": "#35348f", "hook": "#b3261e", "rule": "#1e6f50", "command": "#8a6d00",
    "settings": "#5f3dc4", "module": "#0b6bcb", "doc": "#666666", "script": "#9c27b0",
    "task": "#666666", "gate": "#c2410c", "human": "#0f766e",
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  body { margin:0; font:14px/1.4 system-ui, sans-serif; background:#fafafa; color:#222; }
  header { padding:10px 16px; background:#35348f; color:#fff; display:flex; gap:14px; align-items:center; flex-wrap:wrap; }
  header h1 { font-size:16px; margin:0; }
  header span { font-size:12px; opacity:.85; }
  header button { font:12px system-ui, sans-serif; padding:3px 12px; border:1px solid #fff;
                  border-radius:4px; background:transparent; color:#fff; cursor:pointer; }
  header button.on { background:#fff; color:#35348f; font-weight:600; }
  header label { font-size:12px; display:flex; align-items:center; gap:4px; cursor:pointer; }
  #legend { display:flex; gap:12px; padding:6px 16px; flex-wrap:wrap; font-size:12px; background:#fff; border-bottom:1px solid #ddd; }
  .lg { display:flex; align-items:center; gap:4px; cursor:pointer; user-select:none; }
  .lg.off { opacity:.35; text-decoration:line-through; }
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
<header><h1>__TITLE__</h1><span>__SUBTITLE__</span>__VIEWBTNS__
<span>drag nodes | wheel zooms | click a node for details | click legend to filter</span></header>
<div id="legend">__LEGEND__</div>
<div id="wrap"><canvas id="c"></canvas><div id="info"></div></div>
<script>
const GRAPH = __DATA__;
const COLORS = __COLORS__;
const HAS_FLOW = __FLOW__;
const LS = 'hg:' + document.title + ':';
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
let W, H, scale = 1, ox = 0, oy = 0;
function resize(){ W = cv.width = cv.clientWidth * devicePixelRatio; H = cv.height = cv.clientHeight * devicePixelRatio; layoutFlow(); }
window.addEventListener('resize', () => { resize(); });
const N = GRAPH.nodes, E = GRAPH.edges;
const idx = {}; N.forEach((n,i)=>{ idx[n.id]=i; });
// An edge may reference a node that does not exist on disk (e.g. a command
// running a script that was never installed). The scanner keeps such edges on
// purpose; render the missing endpoint as a visible stub so it is diagnosable.
const PREFIX_CAT = { cmd: 'command' };
E.forEach(e => { [e.from, e.to].forEach(id => { if (idx[id] === undefined){
  const p = id.split(':')[0];
  N.push({ id: id, label: id.split(':').slice(1).join(':') + ' (missing)',
           cat: PREFIX_CAT[p] || p, disabled: true, missing: true, meta: {}, file: '' });
  idx[id] = N.length - 1;
} }); });
N.forEach((n,i)=>{
  n.x = (Math.cos(i*2.399963)*0.35+0.5)*innerWidth*devicePixelRatio;
  n.y = (Math.sin(i*2.399963)*0.35+0.5)*innerHeight*devicePixelRatio;
  n.vx = 0; n.vy = 0; n.deg = 0; });
E.forEach(e => { e.s = idx[e.from]; e.t = idx[e.to];
  if (e.s !== undefined) N[e.s].deg++; if (e.t !== undefined) N[e.t].deg++; });
const links = E.filter(e => e.s !== undefined && e.t !== undefined);

const FLOW_HIDDEN = ['module','task','script'];
let view = HAS_FLOW ? (localStorage.getItem(LS+'view') || 'flow') : 'graph';
function loadSet(key, dflt){ try { const v = JSON.parse(localStorage.getItem(key)); return new Set(Array.isArray(v)?v:dflt); } catch(e){ return new Set(dflt); } }
const hiddenFlow = loadSet(LS+'hf', FLOW_HIDDEN);
const hiddenGraph = loadSet(LS+'hg', []);
function hiddenSet(){ return view==='flow' ? hiddenFlow : hiddenGraph; }
function visible(n){ return !hiddenSet().has(n.cat); }
function saveSets(){ localStorage.setItem(LS+'hf', JSON.stringify([...hiddenFlow]));
  localStorage.setItem(LS+'hg', JSON.stringify([...hiddenGraph])); }

// ---- Flow layout: fixed left-to-right lanes, no physics ----
// Column order follows the edge story so arrows read left to right:
// settings triggers hooks, hooks enforce rules, rules gate agents, agents
// review the merge-request gate, the human approves and invokes commands.
const COLS = { settings:0, hook:1, rule:2, agent:3, gate:4, human:5, command:6, script:7, module:7, task:8 };
function layoutFlow(){
  if (!HAS_FLOW) return;
  const vis = N.filter(visible);
  const byCol = {};
  vis.forEach(n => { const c = (COLS[n.cat] !== undefined) ? COLS[n.cat] : 8;
    (byCol[c] = byCol[c] || []).push(n); });
  const cols = Object.keys(byCol).map(Number).sort((a,b)=>a-b);
  const colW = Math.max(200*devicePixelRatio, (W - 120*devicePixelRatio) / Math.max(cols.length,1));
  cols.forEach((c,ci) => {
    let list = byCol[c].slice().sort((a,b)=> a.id < b.id ? -1 : 1);
    const oi = list.findIndex(n => n.label === 'orchestrator');
    if (oi >= 0){ const o = list.splice(oi,1)[0]; list.splice(Math.floor(list.length/2),0,o); }
    const usable = H - 100*devicePixelRatio;
    const gap = Math.min(52*devicePixelRatio, usable / Math.max(list.length,1));
    const y0 = 60*devicePixelRatio + (usable - gap*(list.length-1)) / 2;
    list.forEach((n,i) => { if (n.fx === undefined || n.userMoved !== view){ n.fx = 70*devicePixelRatio + ci*colW; n.fy = y0 + i*gap; } });
  });
}
function boxW(n){ ctx.font = (11*devicePixelRatio)+'px system-ui, sans-serif';
  return ctx.measureText(n.label).width + 18*devicePixelRatio; }
const BH = () => 24*devicePixelRatio;

// ---- force step (Graph view only) ----
let ticks = 0;
const drag = { node:null, panning:false, px:0, py:0 };
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
function r(n){ return (6 + Math.min(14, Math.sqrt(n.deg)*3)) * devicePixelRatio; }

function arrow(x, y, dx, dy, color){
  const len = Math.sqrt(dx*dx+dy*dy) || 1; dx/=len; dy/=len;
  const s = 6*devicePixelRatio;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x - s*dx - s*0.5*dy, y - s*dy + s*0.5*dx);
  ctx.lineTo(x - s*dx + s*0.5*dy, y - s*dy - s*0.5*dx);
  ctx.closePath(); ctx.fill();
}
function pill(x, y, text){
  ctx.font = (10*devicePixelRatio)+'px system-ui, sans-serif';
  const w = ctx.measureText(text).width + 10*devicePixelRatio, h = 14*devicePixelRatio;
  ctx.fillStyle = 'rgba(255,255,255,0.92)';
  ctx.strokeStyle = '#ccc'; ctx.lineWidth = 1;
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(x-w/2, y-h/2, w, h, h/2); else ctx.rect(x-w/2, y-h/2, w, h);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = '#555';
  ctx.fillText(text, x-w/2+5*devicePixelRatio, y+3.5*devicePixelRatio);
}
function bez(t, p0, p1, p2, p3){ const u = 1-t;
  return u*u*u*p0 + 3*u*u*t*p1 + 3*u*t*t*p2 + t*t*t*p3; }

function drawFlow(){
  const vis = N.filter(visible);
  const visIds = new Set(vis.map(n=>n.id));
  vis.forEach(n => { n.w = boxW(n); });
  links.filter(e => visIds.has(e.from) && visIds.has(e.to)).forEach(e => {
    const a = N[e.s], b = N[e.t];
    const y0 = a.fy + BH()/2, y3 = b.fy + BH()/2;
    // Anchor sides follow the actual direction: a rightward edge leaves the
    // source's right side; a leftward or same-column edge leaves its left
    // side, and the arrowhead follows the real vector - never hardcoded.
    let x0, x3, dir;
    if (b.fx >= a.fx + a.w){ x0 = a.fx + a.w; x3 = b.fx; dir = 1; }
    else { x0 = a.fx; x3 = b.fx + b.w; dir = -1; }
    const bend = Math.max(50*devicePixelRatio, Math.abs(x3-x0)*0.45);
    const x1 = x0 + dir*bend, x2 = x3 - dir*bend;
    const dis = N[e.s].disabled || N[e.t].disabled;
    ctx.globalAlpha = dis ? 0.35 : 1;
    ctx.strokeStyle = 'rgba(90,90,120,0.55)'; ctx.lineWidth = 1.2*devicePixelRatio;
    ctx.setLineDash(dis ? [4*devicePixelRatio,3*devicePixelRatio] : []);
    ctx.beginPath(); ctx.moveTo(x0,y0); ctx.bezierCurveTo(x1,y0,x2,y3,x3,y3); ctx.stroke();
    ctx.setLineDash([]);
    arrow(x3, y3, dir, 0, 'rgba(90,90,120,0.8)');
    if (e.type){ pill(bez(0.5,x0,x1,x2,x3), bez(0.5,y0,y0,y3,y3), e.type); }
    ctx.globalAlpha = 1;
  });
  vis.forEach(n => {
    const w = n.w, h = BH();
    ctx.globalAlpha = n.disabled ? 0.45 : 1;
    ctx.fillStyle = n.disabled ? '#9ca3af' : (COLORS[n.cat] || '#444');
    ctx.setLineDash(n.disabled ? [4*devicePixelRatio,3*devicePixelRatio] : []);
    ctx.strokeStyle = n.disabled ? '#666' : 'rgba(0,0,0,0.25)';
    ctx.lineWidth = 1*devicePixelRatio;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(n.fx, n.fy, w, h, 5*devicePixelRatio); else ctx.rect(n.fx, n.fy, w, h);
    ctx.fill(); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = '#fff';
    ctx.font = (11*devicePixelRatio)+'px system-ui, sans-serif';
    ctx.fillText(n.label, n.fx + 9*devicePixelRatio, n.fy + h/2 + 4*devicePixelRatio);
    ctx.globalAlpha = 1;
  });
}
function drawGraph(){
  const visIds = new Set(N.filter(visible).map(n=>n.id));
  ctx.lineWidth = 1*devicePixelRatio;
  links.filter(e => visIds.has(e.from) && visIds.has(e.to)).forEach(e => {
    const a=N[e.s], b=N[e.t];
    ctx.strokeStyle = 'rgba(80,80,120,'+Math.min(0.15+0.08*(e.refs||1),0.6)+')';
    ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
    const rr = r(b); const dx=b.x-a.x, dy=b.y-a.y; const d=Math.sqrt(dx*dx+dy*dy)||1;
    arrow(b.x - dx/d*rr, b.y - dy/d*rr, dx, dy, 'rgba(80,80,120,0.5)');
    if (e.type && scale >= 1.2){ pill((a.x+b.x)/2, (a.y+b.y)/2, e.type); }
  });
  ctx.font = (11*devicePixelRatio)+'px system-ui, sans-serif';
  N.filter(visible).forEach(n => { const rr=r(n);
    ctx.globalAlpha = n.disabled ? 0.45 : 1;
    ctx.fillStyle = n.disabled ? '#9ca3af' : (COLORS[n.cat] || '#444');
    ctx.setLineDash(n.disabled ? [4*devicePixelRatio,3*devicePixelRatio] : []);
    ctx.beginPath(); ctx.arc(n.x,n.y,rr,0,7); ctx.fill();
    if (n.disabled){ ctx.strokeStyle = '#666'; ctx.stroke(); }
    ctx.setLineDash([]);
    ctx.fillStyle = '#222';
    ctx.fillText(n.label + (n.disabled ? ' (disabled)' : ''), n.x+rr+3*devicePixelRatio, n.y+4*devicePixelRatio);
    ctx.globalAlpha = 1;
  });
}
function draw(){
  ctx.setTransform(1,0,0,1,0,0); ctx.clearRect(0,0,W,H);
  ctx.setTransform(scale,0,0,scale,ox,oy);
  if (view === 'flow') drawFlow(); else drawGraph();
}
function pick(mx,my){ const x=(mx*devicePixelRatio-ox)/scale, y=(my*devicePixelRatio-oy)/scale;
  if (view === 'flow'){
    return N.filter(visible).find(n => n.fx !== undefined &&
      x >= n.fx && x <= n.fx + (n.w || boxW(n)) && y >= n.fy && y <= n.fy + BH());
  }
  return N.filter(visible).find(n => { const dx=n.x-x, dy=n.y-y; const rr=r(n)+4; return dx*dx+dy*dy < rr*rr; });
}
cv.addEventListener('mousedown', ev => { const n = pick(ev.offsetX, ev.offsetY);
  if (n){ drag.node = n; } else { drag.panning = true; } drag.px = ev.offsetX; drag.py = ev.offsetY; });
window.addEventListener('mouseup', () => { drag.node = null; drag.panning = false; });
cv.addEventListener('mousemove', ev => {
  if (drag.node){
    const x = (ev.offsetX*devicePixelRatio-ox)/scale, y = (ev.offsetY*devicePixelRatio-oy)/scale;
    if (view === 'flow'){ drag.node.fx = x - (drag.node.w||0)/2; drag.node.fy = y - BH()/2; drag.node.userMoved = view; }
    else { drag.node.x = x; drag.node.y = y; ticks = 0; }
  }
  else if (drag.panning){ ox += (ev.offsetX-drag.px)*devicePixelRatio; oy += (ev.offsetY-drag.py)*devicePixelRatio;
    drag.px = ev.offsetX; drag.py = ev.offsetY; } });
cv.addEventListener('wheel', ev => { ev.preventDefault();
  const f = ev.deltaY < 0 ? 1.1 : 0.9; const mx = ev.offsetX*devicePixelRatio, my = ev.offsetY*devicePixelRatio;
  ox = mx - (mx-ox)*f; oy = my - (my-oy)*f; scale *= f; }, { passive:false });
const info = document.getElementById('info');
cv.addEventListener('click', ev => { const n = pick(ev.offsetX, ev.offsetY);
  if (!n){ info.style.display='none'; return; }
  const out = links.filter(e=>e.s===idx[n.id]).map(e=>N[e.t].label+(e.type?' ['+e.type+']':'')+(e.refs?' ('+e.refs+')':''));
  const inn = links.filter(e=>e.t===idx[n.id]).map(e=>N[e.s].label+(e.type?' ['+e.type+']':'')+(e.refs?' ('+e.refs+')':''));
  info.textContent = '';
  const h2 = document.createElement('h2');
  h2.textContent = n.label + (n.disabled ? ' (disabled)' : '');
  info.appendChild(h2);
  const dv = document.createElement('div');
  dv.textContent = (n.detail || n.cat);
  info.appendChild(dv);
  [['outgoing:', out], ['incoming:', inn]].forEach(([lbl, arr]) => {
    if (!arr.length) return;
    const box = document.createElement('div');
    const b = document.createElement('b'); b.textContent = lbl; box.appendChild(b);
    const ul = document.createElement('ul');
    arr.forEach(t => { const li = document.createElement('li'); li.textContent = t; ul.appendChild(li); });
    box.appendChild(ul); info.appendChild(box);
  });
  info.style.display='block'; });

// legend filtering
document.querySelectorAll('.lg').forEach(el => {
  const cat = el.dataset.cat;
  const sync = () => el.classList.toggle('off', hiddenSet().has(cat));
  el.addEventListener('click', () => {
    const s = hiddenSet();
    if (s.has(cat)) s.delete(cat); else s.add(cat);
    saveSets(); layoutFlow(); sync();
  });
  el._sync = sync; sync();
});
function syncLegend(){ document.querySelectorAll('.lg').forEach(el => el._sync && el._sync()); }

// view buttons + auto-reload
function setView(v){ view = v; localStorage.setItem(LS+'view', v);
  const bf = document.getElementById('btnFlow'), bg = document.getElementById('btnGraph');
  if (bf){ bf.classList.toggle('on', v==='flow'); bg.classList.toggle('on', v==='graph'); }
  ticks = 0; layoutFlow(); syncLegend(); }
const bf = document.getElementById('btnFlow');
if (bf){ bf.addEventListener('click', () => setView('flow'));
  document.getElementById('btnGraph').addEventListener('click', () => setView('graph')); }
const ar = document.getElementById('ar');
if (ar){ ar.checked = localStorage.getItem(LS+'ar') === '1';
  if (ar.checked) setInterval(() => location.reload(), 10000);
  ar.addEventListener('change', () => { localStorage.setItem(LS+'ar', ar.checked ? '1' : '0');
    if (ar.checked) location.reload(); }); }
resize();
setView(view);
(function loop(){ if (view === 'graph' && ticks < 300) step(); draw(); requestAnimationFrame(loop); })();
</script>
</body>
</html>
"""

VIEW_BTNS = ('<button id="btnFlow">Flow</button><button id="btnGraph">Graph</button>'
             '<label><input type="checkbox" id="ar">auto-reload</label>')


def embed_json(obj) -> str:
    """json.dumps for embedding INSIDE a <script> block: escape the sequences
    that could terminate the block or open a comment. Repo frontmatter is
    attacker-influencable (any file in the repo), so this is load-bearing."""
    return (json.dumps(obj)
            .replace("</", "<\\/")
            .replace("<!--", "<\\u0021--"))


def render(title: str, subtitle: str, nodes: list, edges: list, cats: list[str],
           flow: bool = False) -> str:
    legend = "".join(
        f'<span class="lg" data-cat="{c}"><span class="dot" style="background:{CAT_COLORS[c]}">'
        f'</span>{c}</span>'
        for c in cats)
    return (HTML_TEMPLATE
            .replace("__TITLE__", title)
            .replace("__SUBTITLE__", subtitle)
            .replace("__VIEWBTNS__", VIEW_BTNS if flow else "")
            .replace("__LEGEND__", legend)
            .replace("__COLORS__", json.dumps(CAT_COLORS))
            .replace("__FLOW__", "true" if flow else "false")
            .replace("__DATA__", embed_json({"nodes": nodes, "edges": edges})))


def specs_graph(root: pathlib.Path) -> str | None:
    src = root / ".claude" / "state" / "docs-graph.json"
    if not src.exists():
        return None
    try:
        g = json.loads(src.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        # contract: never fail the caller - a broken input narrows the output
        print(f"graph-html: {src} unreadable ({e}); skipping the specs graph",
              file=sys.stderr)
        return None
    linked = {e["from"] for e in g["edges"]} | {e["to"] for e in g["edges"]}
    nodes = [{"id": d, "label": d.split("/")[-1], "cat": "doc", "detail": d}
             for d in sorted(linked)]
    edges = [{"from": e["from"], "to": e["to"], "refs": e["refs"]} for e in g["edges"]]
    out = root / "docs" / "context" / "specs-graph.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render("Specs graph", "documents linked by shared requirement / decision / task IDs",
                          nodes, edges, ["doc"]), encoding="utf-8")
    return out.relative_to(root).as_posix()


def _node_detail(n: dict) -> str:
    meta = n.get("meta") or {}
    parts = []
    if "detail" in meta:
        parts.append(str(meta["detail"]))
    if "model" in meta:
        parts.append(f"model {meta['model']}")
    if "effort" in meta:
        parts.append(f"effort {meta['effort']}")
    if "event" in meta:
        parts.append(f"{meta['event']} ({meta.get('matcher', '*')})")
    if meta.get("registered") is False:
        parts.append("NOT registered in settings.json")
    if "scoped" in meta:
        parts.append("path-scoped" if meta["scoped"] else "always loaded")
    if "files" in meta:
        parts.append(f"{meta['files']} files")
    if n.get("file"):
        parts.append(n["file"])
    return " | ".join(parts) or n["type"]


def harness_graph(root: pathlib.Path) -> str | None:
    """Render docs/context/harness-graph.html from the canonical JSON.

    The scanner (harness-graph.py) owns the scan; this function only renders.
    If the JSON is missing it invokes the scanner in-process as a fallback.
    """
    claude = root / ".claude"
    if not claude.exists():
        return None
    src = claude / "state" / "harness-graph.json"
    if not src.exists():
        import importlib.util
        hg = pathlib.Path(__file__).with_name("harness-graph.py")
        if not hg.is_file():
            return None
        spec = importlib.util.spec_from_file_location("harness_graph_scan", hg)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        graph = mod.build(root)
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    try:
        g = json.loads(src.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        # contract: never fail the caller - a broken input narrows the output
        print(f"graph-html: {src} unreadable ({e}); skipping the harness graph",
              file=sys.stderr)
        return None

    nodes = [{"id": n["id"], "label": n["label"], "cat": n["type"],
              "detail": _node_detail(n), "disabled": bool(n.get("disabled"))}
             for n in g.get("nodes", [])]
    edges = [{"from": e["from"], "to": e["to"], "type": e.get("type", ""),
              "refs": e.get("refs", 0)}
             for e in g.get("edges", [])]

    out = root / "docs" / "context" / "harness-graph.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    cats = ["agent", "hook", "rule", "command", "settings", "gate", "human",
            "script", "module", "task"]
    present = {n["cat"] for n in nodes}
    cats = [c for c in cats if c in present]
    out.write_text(render("Harness graph",
                          "agents, hooks, rules, commands, settings, code modules, and the docs that bind them",
                          nodes, edges, cats, flow=True), encoding="utf-8")
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
