// The viewer's whole UI. It lives in a real .js file rather than inside the
// script block of ui.html, and serve.rs splices it back in at the UI-script
// placeholder comment there, so the page still ships as one self-contained
// response. (That placeholder token is deliberately not spelled out in this
// file: it would survive the splice and land in the served page, where the test
// that proves the replacement happened would then find it and think it had not.)
//
// The split is not tidiness. GitHub decides which languages CodeQL analyses by
// what it detects in the tree, and it detected none: 202,543 bytes of this
// repo's JavaScript sat inside <script> blocks and only two standalone .js
// files existed, so the CodeQL matrix ran actions, python and rust and nothing
// ever looked at the one file that renders a scanned repository's own text into
// the DOM. `node --check` proved the syntax parsed; no analysis proved an
// innerHTML sink was safe. A file with a .js extension is what makes the
// javascript-typescript extractor pick this up.
//
// Consequences of that splice, both load-bearing:
//   - a literal closing script tag must never appear in this file, in a string
//     or in a comment, or it ends the block early once inlined and silently
//     deletes everything after it. tests/ui_test.rs asserts its absence.
//   - scripts/check_js.py checks this file by path, not by finding a <script>
//     block in ui.html. There is no longer a block there to find.
"use strict";
const COLORS = {
  agent: "#2563eb", rule: "#ea580c", command: "#16a34a", hook: "#ca8a04",
  settings: "#e11d48", state: "#64748b", script: "#7c3aed", module: "#0891b2",
  task: "#475569", doc: "#0d9488", gate: "#c2410c", human: "#0f766e",
  skill: "#9333ea"
};
const FLOW_COL = { rule: 0, hook: 1, settings: 1, skill: 1, agent: 2, gate: 3, human: 4, command: 5, script: 6, module: 6, task: 7 };
const HIDE_DEFAULT = new Set(["module", "task", "script"]);
// Hook event -> short badge. The scan carries the full event name; the node is
// too small for "PostToolUse", and Pre/Post is the distinction that matters.
const EVENT_BADGE = { PreToolUse: "PRE", PostToolUse: "POST", SubagentStop: "STOP",
                      UserPromptSubmit: "PROMPT", SessionStart: "START", Stop: "STOP" };
const STATUS_COLOR = { Active: "#1d4ed8", Blocked: "#b91c1c", Pending: "#a16207", Done: "#15803d" };
let graph = { nodes: [], edges: [] };
let view = localStorage.getItem("hv-view") || "flow";
let hidden = new Set(JSON.parse(localStorage.getItem("hv-hidden") || "null") || [...HIDE_DEFAULT]);
let pos = {}, sel = null, drag = null, panzoom = { x: 0, y: 0, k: 1 };
let lineStyle = localStorage.getItem("hv-line") || "curved";
// Selection highlight: the ids in the connected set, and the edges that join
// them. Empty when nothing is selected, which is also what stops the animation.
let hi = { nodes: new Set(), edges: new Set() };
let dashPhase = 0, anim = null;
const cv = document.getElementById("cv"), ctx = cv.getContext("2d");

// Measure what the panel actually occupies rather than assuming a constant:
// the panel is resizable, so a hardcoded width desynchronises the canvas from
// the layout the moment anyone drags the grip.
function panelWidth() {
  const d = document.getElementById("detail");
  if (!d.classList.contains("open")) return 0;
  return d.getBoundingClientRect().width + document.getElementById("grip").getBoundingClientRect().width;
}
function fit() {
  const r = cv.parentElement.getBoundingClientRect();
  cv.width = Math.max(100, r.width - panelWidth()); cv.height = r.height; draw();
}
window.addEventListener("resize", () => { applySide(); fit(); });

let sideW = Number(localStorage.getItem("hv-side")) || 320;
function applySide() {
  const max = Math.max(260, Math.round(window.innerWidth * 0.6));
  sideW = Math.max(240, Math.min(max, sideW));
  document.getElementById("detail").style.width = sideW + "px";
  localStorage.setItem("hv-side", String(sideW));
}
function setPanel(open) {
  document.getElementById("detail").classList.toggle("open", open);
  document.getElementById("grip").classList.toggle("open", open);
}

// The root the server was pointed at wins on a fresh page load: someone who ran
// `harness-view serve D:/foo` means D:/foo, and silently showing a different repo
// remembered from a previous session is a genuine surprise. The remembered roots
// stay in the datalist for one-click switching.
let currentRoot = "";

function banner(text) {
  const b = document.getElementById("banner");
  b.textContent = text || "";
  b.classList.toggle("on", !!text);
}

function recentRoots() {
  try { return JSON.parse(localStorage.getItem("hv-recent") || "[]"); } catch (e) { return []; }
}
function rememberRoot(p) {
  if (!p) return;
  const list = [p, ...recentRoots().filter(x => x !== p)].slice(0, 12);
  localStorage.setItem("hv-recent", JSON.stringify(list));
  localStorage.setItem("hv-root", p);
  buildRoots();
}
function forgetRoot(p) {
  localStorage.setItem("hv-recent", JSON.stringify(recentRoots().filter(x => x !== p)));
  buildRoots();
}
// The build version, reported by the server so the page cannot claim a version
// the binary does not have.
async function showVersion() {
  try {
    const r = await fetch("roots");
    if (!r.ok) return;
    const b = await r.json();
    if (b.version) document.getElementById("ver").textContent = "v" + b.version;
  } catch (e) { /* the footer simply stays blank */ }
}

function buildRoots() {
  const dl = document.getElementById("roots");
  dl.textContent = "";
  for (const p of recentRoots()) { const o = document.createElement("option"); o.value = p; dl.append(o); }
}

// --- busy reporting ---------------------------------------------------------
// Shown only once an operation has run long enough to be worth reporting. A
// spinner that flashes for a 20ms fetch reads as a glitch, so the indicator is
// scheduled rather than shown, and any op that finishes first cancels it.
// Counted, because a root switch runs the graph fetch and the plan fetch.
const BUSY_DELAY_MS = 150;
let busyN = 0, busyTimer = null;
function busyShow(what) {
  const el = document.getElementById("busy");
  document.getElementById("busy-what").textContent = what || "loading";
  el.classList.add("on");
}
function busyHide() { document.getElementById("busy").classList.remove("on"); }
function busyStart(what) {
  busyN++;
  if (busyN === 1 && busyTimer === null) {
    busyTimer = setTimeout(() => { busyTimer = null; busyShow(what); }, BUSY_DELAY_MS);
  }
}
function busyEnd() {
  busyN = Math.max(0, busyN - 1);
  if (busyN === 0) {
    if (busyTimer !== null) { clearTimeout(busyTimer); busyTimer = null; }
    busyHide();
  }
}
// Every caller goes through this so the counter can never be left raised by an
// early return or a throw - a stuck spinner is worse than no spinner.
async function withBusy(what, el, fn) {
  busyStart(what);
  if (el) { el.setAttribute("aria-busy", "true"); el.disabled = true; }
  try { return await fn(); }
  finally {
    busyEnd();
    if (el) { el.removeAttribute("aria-busy"); el.disabled = false; }
  }
}

// --- markdown view mode -----------------------------------------------------
// Two surfaces, two remembered choices (hv-md-side, hv-md-plan). They are kept
// apart deliberately: inspecting an agent file often calls for raw, to read the
// frontmatter and syntax exactly as written, while the master plan is a report
// people read formatted. One shared setting would let a choice made in the
// sidebar silently change how the plan renders.
const ICON_DOC = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">' +
  '<path d="M3 2.5h10v11H3z"/><path d="M5 5.5h6M5 8h6M5 10.5h4"/></svg>';
const ICON_CODE = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">' +
  '<path d="M5.5 4.5 2 8l3.5 3.5M10.5 4.5 14 8l-3.5 3.5"/></svg>';
// Header button icons. Inline SVG so the page stays self-contained; the text
// label stays beside each one because the glyphs alone do not say "Master plan".
const ICONS = {
  flow: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="1" y="2" width="4.5" height="3.5" rx="1"/><rect x="10.5" y="2" width="4.5" height="3.5" rx="1"/><rect x="10.5" y="10.5" width="4.5" height="3.5" rx="1"/><path d="M5.5 3.75h5M8 3.75v8.5h2.5"/></svg>',
  graph: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="3" cy="4" r="2"/><circle cx="13" cy="6" r="2"/><circle cx="7" cy="13" r="2"/><path d="M4.8 4.9 11 5.7M4.2 5.7 6.2 11.2M11.9 7.7 8.3 11.6"/></svg>',
  plan: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M3 2h10v12H3z"/><path d="M5.5 5.5h5M5.5 8h5M5.5 10.5h3"/></svg>',
  reload: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M13.5 8a5.5 5.5 0 1 1-1.7-4"/><path d="M13.5 2v3.5H10"/></svg>',
  load: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M8 2v8"/><path d="M4.75 6.75 8 10l3.25-3.25"/><path d="M2.5 12.5h11"/></svg>',
  browse: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M1.5 12.5v-9h4l1.5 2h7.5v7z"/></svg>',
  assess: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M2 13.5h12"/><path d="M4 13.5V8M8 13.5V3.5M12 13.5V6"/></svg>',
  eye: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M1 8s2.5-4.5 7-4.5S15 8 15 8s-2.5 4.5-7 4.5S1 8 1 8z"/><circle cx="8" cy="8" r="1.8"/></svg>',
  eyeoff: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M2.5 5.2C1.6 6.3 1 8 1 8s2.5 4.5 7 4.5c1.3 0 2.4-.4 3.4-.9"/><path d="M6.3 3.7A7.6 7.6 0 0 1 8 3.5c4.5 0 7 4.5 7 4.5s-.7 1.3-2 2.5"/><path d="M2 2l12 12"/></svg>',
  off: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M8 2v6"/><path d="M4.2 4.4a5.5 5.5 0 1 0 7.6 0"/></svg>',
  on: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M2.5 8.5 6 12l7.5-8"/></svg>',
};

// Icons for metadata KEYS, only where the icon adds meaning. A row that is just
// a string (id, file, title) gets none: decorating every row would make the
// ones that carry state stop standing out, which is the whole point.
const FIELD_ICONS = {
  state:  '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="8" cy="8" r="5.5"/></svg>',
  status: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="8" cy="8" r="5.5"/><path d="M8 5v3.2l2 1.3"/></svg>',
  owner:  '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="8" cy="5.5" r="2.5"/><path d="M3 13.5c0-2.5 2.2-4 5-4s5 1.5 5 4"/></svg>',
  model:  '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="3" y="3" width="10" height="10" rx="2"/><path d="M6.5 6.5h3v3h-3z"/></svg>',
  effort: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M2 13h3V8H2zM6.5 13h3V5h-3zM11 13h3V2h-3z"/></svg>',
  deps:   '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M6.5 9.5 4 12a2.5 2.5 0 0 1-3.5-3.5L3 6"/><path d="M9.5 6.5 12 4a2.5 2.5 0 0 1 3.5 3.5L13 10"/><path d="M6 10l4-4"/></svg>',
  fr:     '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M4 2h6l2.5 2.5V14H4z"/><path d="M6 7h4M6 10h4"/></svg>',
  tools:  '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M10.5 2.5a3 3 0 0 0-4 4L2 11v3h3l4.5-4.5a3 3 0 0 0 4-4l-2 2-2-2z"/></svg>',
  event:  '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M8 2v5l3 2"/><circle cx="8" cy="8" r="6"/></svg>',
};

// A cheap seat and an expensive seat should be distinguishable at a glance:
// cost control is one of the things this project measures, so the panel should
// not render "opus" and "haiku" as the same grey text.
const MODEL_TONE = { opus: "hot", sonnet: "mid", haiku: "cool", inherit: "warnv" };
const EFFORT_TONE = { high: "hot", medium: "mid", low: "cool" };
// Put the icon in front of the existing label without disturbing the text.
// Label plus icon, for buttons built at run time. The icon is decoration beside
// text that already says the action, so it stays out of the accessibility tree.
function setBtn(btn, iconKey, text) {
  btn.textContent = "";
  if (ICONS[iconKey]) {
    const i = document.createElement("span");
    i.className = "bicon"; i.innerHTML = ICONS[iconKey];
    btn.append(i);
  }
  btn.append(document.createTextNode(text));
  btn.setAttribute("aria-label", text);
}

function iconize(id, key) {
  const b = document.getElementById(id);
  if (!b) return;
  const text = b.textContent;
  b.textContent = "";
  const s = document.createElement("span");
  s.innerHTML = ICONS[key];           // our own constant, never repo content
  b.append(s.firstChild, document.createTextNode(text));
  if (!b.getAttribute("aria-label")) b.setAttribute("aria-label", b.title || text);
}

// GFM on for tables and task lists; no mangling, and headings get no auto ids
// we do not use. Configured once rather than per render.
window.marked.setOptions({ gfm: true, breaks: false });
// An allow-list, not a deny-list: anything the markdown subset does not need is
// simply not permitted, so a new HTML trick in a repo file has nothing to land on.
const PURIFY_OPTS = {
  // No form controls: a viewer never needs one, and DOMPurify strips `type` off
  // an input as DOM-clobbering protection anyway, which silently turned every
  // GFM task checkbox into a bare (therefore text) input 170px wide. Task items
  // become inert glyphs in taskGlyphs() below instead.
  ALLOWED_TAGS: ["p","br","hr","strong","em","del","code","pre","blockquote",
                 "h1","h2","h3","h4","h5","h6","ul","ol","li",
                 "table","thead","tbody","tr","th","td","a","span"],
  ALLOWED_ATTR: ["href","title","align","class"],
  ALLOWED_URI_REGEXP: /^(?:https?:|mailto:|#|\/|\.)/i,
  FORBID_TAGS: ["script","style","iframe","object","embed","form"],
  FORBID_ATTR: ["srcset","src","onerror","onload","onclick","style"],
};

function mdMode(key) { return localStorage.getItem(key) === "raw" ? "raw" : "formatted"; }
// The button reports the mode it will switch TO, and its pressed state reports
// whether raw is currently on.
// `file` is optional and only names the format in the tooltip: the sidebar now
// previews JSON and YAML too, so "raw markdown" was wrong for most files.
function makeModeButton(key, onChange, file) {
  const b = document.createElement("button");
  b.className = "icon-btn";
  const paint = () => {
    const raw = mdMode(key) === "raw";
    b.innerHTML = raw ? ICON_DOC : ICON_CODE;
    b.setAttribute("aria-pressed", raw ? "true" : "false");
    const what = { json: "JSON", yaml: "YAML", md: "markdown" }[fileKind(file)];
    const t = raw ? "Showing the raw file. Switch to formatted " + what + "."
                  : "Showing formatted " + what + ". Switch to the raw file.";
    b.title = t; b.setAttribute("aria-label", t);
  };
  b.onclick = () => {
    localStorage.setItem(key, mdMode(key) === "raw" ? "formatted" : "raw");
    paint(); onChange();
  };
  paint();
  return b;
}

// A load failure must never leave a blank page: the error goes in the banner,
// the previous graph stays on screen, and the canvas is already sized because
// fit() runs before the first load rather than after it.
async function load(rootOverride) {
  const target = rootOverride !== undefined ? rootOverride : currentRoot;
  const url = "graph.json" + (target ? "?root=" + encodeURIComponent(target) : "");
  let res, body;
  try {
    // scanning a big tree is the slowest thing this page does, so it is the
    // operation the indicator exists for
    [res, body] = await withBusy("scanning", null, async () => {
      const r = await fetch(url);
      return [r, await r.json()];
    });
  } catch (e) {
    banner("could not reach the server: " + e);
    return false;
  }
  if (!res.ok || body.error) {
    // "nothing is loaded yet" is not a failure. `harness-view serve` runs in a
    // directory with no harness on purpose, so that double-clicking the binary
    // wherever it was copied to opens a usable window; the server flags that
    // case with noRoot and the page answers it with an instruction rather than
    // a red banner saying something went wrong, because nothing did.
    if (body && body.noRoot) {
      banner("");
      graph = { nodes: [], edges: [] };
      pos = {}; clearSel();
      currentRoot = "";
      document.getElementById("root").value = "";
      document.getElementById("rootnow").textContent = "";
      document.getElementById("stats").textContent = "no folder loaded";
      // hint() too: it is the only line that tells the reader what to do next,
      // and it is otherwise painted once by sync() and never revisited
      buildLegend(); await checkPlan(); layout(); hint(); draw();
      return false;
    }
    banner(body.error || ("server returned " + res.status));
    return false;
  }
  banner("");
  const changedRoot = (body.root || target || "") !== currentRoot;
  graph = body;
  // Positions are keyed by node id, and two repos share ids like
  // "agent:orchestrator". Carrying them across a root change lays the new
  // graph out at the old one's scale, pushing nodes off the canvas.
  if (changedRoot) { pos = {}; clearSel(); }
  currentRoot = body.root || target || "";
  document.getElementById("root").value = currentRoot;
  document.getElementById("rootnow").textContent = currentRoot ? "root: " + currentRoot : "";
  rememberRoot(currentRoot);
  document.getElementById("stats").textContent = graph.nodes.length + " nodes, " + graph.edges.length + " edges";
  buildLegend(); await checkPlan(); layout(); fitView(graph.nodes.filter(visible)); hint(); draw();
  return true;
}
function types() { return [...new Set(graph.nodes.map(n => n.type))].sort(); }
function visible(n) { return !hidden.has(n.type); }
function label(n) { return n.label || n.id.split(":").slice(1).join(":") || n.id; }
// What the NODE shows, which is not always the full name. A task file stem like
// "TASK-023-ooxml-bound-xlsx-scan" measures 378px, and 115 of those cannot be
// arranged without overlapping whatever the lane maths does. The task id is the
// handle everything else uses (deps read "TASK-027"), it is unique, and the full
// title is one click away in the sidebar, so the node carries the id alone.
const STATUS_ORDER = { Active: 0, Blocked: 1, Pending: 2, Done: 3 };
function nodeLabel(n) {
  const full = label(n);
  if (n.type === "task") {
    const m = full.match(/^(TASK-\d+)/i);
    if (m) return m[1].toUpperCase();
  }
  return full.length > 34 ? full.slice(0, 33) + "…" : full;
}
function meta(n, k) { return (n.meta || {})[k]; }

function buildLegend() {
  const el = document.getElementById("legend"); el.textContent = "";
  for (const t of types()) {
    const l = document.createElement("label");
    const c = document.createElement("input"); c.type = "checkbox"; c.checked = !hidden.has(t);
    c.onchange = () => { c.checked ? hidden.delete(t) : hidden.add(t); localStorage.setItem("hv-hidden", JSON.stringify([...hidden])); layout(); fitView(graph.nodes.filter(visible)); draw(); };
    const i = document.createElement("i"); i.style.background = COLORS[t] || "#94a3b8";
    l.append(c, i, t); el.append(l);
  }
}

function layout() {
  // widths must be known BEFORE the layout runs: the separation pass sizes its
  // push from the real box width, and draw() measuring them afterwards is too late
  measureNodes();
  const vis = graph.nodes.filter(visible);
  if (view === "flow") {
    const cols = {};
    for (const n of vis) { const c = FLOW_COL[n.type] ?? 7; (cols[c] = cols[c] || []).push(n); }
    // Columns are placed left to right using the width each one actually needs,
    // so a column of wide boxes cannot be laid on top of its neighbour. The old
    // code spaced columns by a single average and spaced wrapped sub-lanes by
    // `cw / lanes`, neither of which had ever seen a node width: on msboost that
    // put 378px task boxes into lanes 16px apart, 190 overlapping pairs.
    const colX = {};
    let cursor = 60;
    const keys = Object.keys(cols).map(Number).sort((a, b) => a - b);
    const gap = 34;
    const perLane = Math.max(1, Math.floor((cv.height - 80) / gap));
    for (const c of keys) {
      const ns = cols[c];
      // Tasks read as a board: grouped by status, then by id inside a status.
      // Sorting this way makes each wrapped sub-lane hold one status, so the
      // colour bands are the grouping and no extra chrome is needed.
      if (ns.every(n => n.type === "task")) {
        ns.sort((a, b) => {
          const sa = STATUS_ORDER[meta(a, "status")] ?? 9, sb = STATUS_ORDER[meta(b, "status")] ?? 9;
          return sa !== sb ? sa - sb : a.id.localeCompare(b.id);
        });
      } else {
        ns.sort((a, b) => a.id.localeCompare(b.id));
        const orch = ns.findIndex(n => n.id === "agent:orchestrator");
        if (orch > 0) { const [o] = ns.splice(orch, 1); ns.splice(Math.floor(ns.length / 2), 0, o); }
      }
      const wMax = Math.max(...ns.map(n => n._w || 80));
      const lanes = Math.ceil(ns.length / perLane);
      const laneW = wMax + 26;                 // real width plus breathing room
      colX[c] = cursor;
      ns.forEach((n, i) => {
        const lane = Math.floor(i / perLane), row = i % perLane;
        const inLane = Math.min(perLane, ns.length - lane * perLane);
        const spread = lanes > 1 ? gap : Math.max(gap, (cv.height - 60) / (inLane + 1));
        pos[n.id] = { x: cursor + lane * laneW, y: 40 + (row + 1) * spread };
      });
      cursor += lanes * laneW + 90;            // clear the next column entirely
    }
  } else {
    const N = vis.length || 1, R = Math.min(cv.width, cv.height) / 2 - 60;
    vis.forEach((n, i) => {
      if (!pos[n.id] || pos[n.id].flow) pos[n.id] = { x: cv.width / 2 + R * Math.cos(2 * Math.PI * i / N), y: cv.height / 2 + R * Math.sin(2 * Math.PI * i / N) };
    });
    forceSim(vis, 200);
  }
  if (view === "flow") for (const n of vis) pos[n.id].flow = true; else for (const n of vis) pos[n.id].flow = false;
}

// Scale and centre so the whole layout is on screen. Without this a real board
// silently loses most of itself off the bottom edge: msboost lays 115 task nodes
// into one column 3950px tall inside a 1018px canvas, so 87 of 172 nodes were
// unreachable with no hint that they existed. Content you cannot see is the same
// failure as a blank page.
function fitView(vis) {
  if (!vis.length) { panzoom = { x: 0, y: 0, k: 1 }; return; }
  const xs = vis.map(n => pos[n.id].x), ys = vis.map(n => pos[n.id].y);
  const pad = 90;  // room for the widest node label and its badge
  const w = Math.max(...xs) - Math.min(...xs) + pad * 2;
  const h = Math.max(...ys) - Math.min(...ys) + pad * 2;
  const k = Math.max(0.15, Math.min(1, cv.width / w, cv.height / h));
  panzoom.k = k;
  panzoom.x = (cv.width - (Math.min(...xs) + Math.max(...xs)) * k) / 2;
  panzoom.y = (cv.height - (Math.min(...ys) + Math.max(...ys)) * k) / 2;
}
function forceSim(vis, iters) {
  const ids = new Set(vis.map(n => n.id));
  const es = graph.edges.filter(e => ids.has(e.from) && ids.has(e.to));
  for (let it = 0; it < iters; it++) {
    for (const a of vis) for (const b of vis) {
      if (a.id >= b.id) continue;
      const pa = pos[a.id], pb = pos[b.id];
      let dx = pb.x - pa.x, dy = pb.y - pa.y, d2 = dx * dx + dy * dy + 0.01, d = Math.sqrt(d2);
      const rep = 2600 / d2, fx = dx / d * rep, fy = dy / d * rep;
      pa.x -= fx; pa.y -= fy; pb.x += fx; pb.y += fy;
    }
    for (const e of es) {
      const pa = pos[e.from], pb = pos[e.to];
      let dx = pb.x - pa.x, dy = pb.y - pa.y, d = Math.sqrt(dx * dx + dy * dy) + 0.01;
      const f = (d - 130) * 0.015, fx = dx / d * f, fy = dy / d * f;
      pa.x += fx; pa.y += fy; pb.x -= fx; pb.y -= fy;
    }
    for (const n of vis) { const p = pos[n.id]; p.x = Math.max(40, Math.min(cv.width - 40, p.x)); p.y = Math.max(30, Math.min(cv.height - 30, p.y)); }
  }
  separate(vis, 400);
}

// The repulsion above treats every node as a point, but a node is a BOX and the
// labels make them wide: "conventional-commits" is ~180px across. Point repulsion
// let 76 pairs of boxes overlap on a 57-node graph, which is what made the graph
// view look like a pile. This pushes overlapping rectangles apart along their
// smallest escape direction, which is cheap and converges in a few passes.
function separate(vis, iters) {
  const pad = 6;
  for (let it = 0; it < iters; it++) {
    let moved = false;
    for (let i = 0; i < vis.length; i++) {
      for (let j = i + 1; j < vis.length; j++) {
        const a = vis[i], b = vis[j], pa = pos[a.id], pb = pos[b.id];
        const hw = (a._w || 80) / 2 + (b._w || 80) / 2 + pad, hh = 24 + pad;
        const dx = pb.x - pa.x, dy = pb.y - pa.y;
        const ox = hw - Math.abs(dx), oy = hh - Math.abs(dy);
        if (ox <= 0 || oy <= 0) continue;      // boxes already clear
        moved = true;
        if (ox < oy) {                          // shorter escape is sideways
          const s = (dx < 0 ? -1 : 1) * ox / 2;
          pa.x -= s; pb.x += s;
        } else {
          const s = (dy < 0 ? -1 : 1) * oy / 2;
          pa.y -= s; pb.y += s;
        }
      }
    }
    // a margin well outside the canvas: pinning nodes to the visible edge left
    // them nothing to escape into, so dense graphs never stopped overlapping
    const mx = cv.width * 1.5, my = cv.height * 1.5;
    for (const n of vis) { const p = pos[n.id]; p.x = Math.max(-mx, Math.min(cv.width + mx, p.x)); p.y = Math.max(-my, Math.min(cv.height + my, p.y)); }
    if (!moved) break;
  }
}

// The connected set for a selection: the node, its direct neighbours, and the
// edges BETWEEN any two members - so you also see how the neighbours relate to
// each other, not just how they hang off the selection.
function computeHighlight(id) {
  const nodes = new Set([id]), edges = new Set();
  for (const e of graph.edges) {
    if (e.from === id) nodes.add(e.to);
    else if (e.to === id) nodes.add(e.from);
  }
  graph.edges.forEach((e, i) => { if (nodes.has(e.from) && nodes.has(e.to)) edges.add(i); });
  return { nodes, edges };
}
function startAnim() {
  if (anim) return;
  const tick = () => { dashPhase = (dashPhase + 0.7) % 24; draw(); anim = requestAnimationFrame(tick); };
  anim = requestAnimationFrame(tick);
}
function stopAnim() { if (anim) { cancelAnimationFrame(anim); anim = null; } }
function clearSel() {
  sel = null; hi = { nodes: new Set(), edges: new Set() };
  stopAnim();
  setPanel(false);
}

// --- edge routing -----------------------------------------------------------
// Nodes are 24px tall and their width is measured before any edge is drawn, so
// a line can stop at the box boundary. Anchoring at the centre (the old
// behaviour) ran every line under the node and hid every arrowhead behind the
// target, because nodes paint after edges.
const NODE_HH = 12;
function measureNodes() {
  ctx.font = "12px ui-monospace, Consolas, monospace";
  for (const n of graph.nodes) {
    if (!visible(n)) continue;
    const badge = nodeBadge(n);
    const bw = badge ? ctx.measureText(badge.text).width + 10 : 0;
    n._w = Math.max(60, ctx.measureText(nodeLabel(n)).width + 18 + bw);
  }
}
// The point on a node's box in the direction of (tx,ty).
function anchor(p, hw, tx, ty) {
  const dx = tx - p.x, dy = ty - p.y;
  if (!dx && !dy) return { x: p.x, y: p.y };
  const s = Math.min(dx ? hw / Math.abs(dx) : Infinity, dy ? NODE_HH / Math.abs(dy) : Infinity);
  return { x: p.x + dx * s, y: p.y + dy * s };
}
function face(p, hw, right) { return { x: p.x + (right ? hw : -hw), y: p.y }; }

// Orthogonal routing gives every source its own vertical channel. Without that
// each column pair shares one channel and the parallel runs merge into a single
// thick line, which is worse than the curves it replaced.
function channelIndex(vis) {
  const byCol = {};
  for (const n of vis) { const c = FLOW_COL[n.type] ?? 7; (byCol[c] = byCol[c] || []).push(n); }
  const idx = {};
  for (const c of Object.keys(byCol)) {
    const ns = byCol[c].slice().sort((p, q) => pos[p.id].y - pos[q.id].y);
    ns.forEach((n, i) => { idx[n.id] = i - (ns.length - 1) / 2; });
  }
  return idx;
}

// One edge's geometry: what to stroke, where the arrow lands, and a sampler for
// the label. `ortho` has no sensible reading in the force-directed view, so it
// falls back to straight there rather than drawing right angles through nodes.
function edgeGeom(a, b, pa, pb, chanOff) {
  const aw = (a._w || 80) / 2, bw = (b._w || 80) / 2;
  const style = (view === "graph" && lineStyle === "ortho") ? "straight" : lineStyle;
  if (view === "flow" && style !== "straight") {
    const right = pb.x >= pa.x;
    const s = face(pa, aw, right), e = face(pb, bw, !right);
    if (style === "ortho") {
      const mid = (s.x + e.x) / 2;
      const lo = Math.min(s.x, e.x) + 10, hi = Math.max(s.x, e.x) - 10;
      let cx = mid + (chanOff || 0) * 11;
      if (hi > lo) cx = Math.max(lo, Math.min(hi, cx));
      return { type: "poly", pts: [s, { x: cx, y: s.y }, { x: cx, y: e.y }, e] };
    }
    const mx = (s.x + e.x) / 2;
    return { type: "bezier", s, c1: { x: mx, y: s.y }, c2: { x: mx, y: e.y }, e };
  }
  const s = anchor(pa, aw, pb.x, pb.y), e = anchor(pb, bw, pa.x, pa.y);
  if (style === "curved") {
    // a gentle bow so two edges between the same neighbourhood stay distinct
    const dx = e.x - s.x, dy = e.y - s.y, len = Math.hypot(dx, dy) || 1;
    const bow = Math.min(40, len * 0.12);
    return { type: "quad", s, e, c: { x: (s.x + e.x) / 2 - dy / len * bow, y: (s.y + e.y) / 2 + dx / len * bow } };
  }
  return { type: "poly", pts: [s, e] };
}
function strokeGeom(g) {
  ctx.beginPath();
  if (g.type === "bezier") { ctx.moveTo(g.s.x, g.s.y); ctx.bezierCurveTo(g.c1.x, g.c1.y, g.c2.x, g.c2.y, g.e.x, g.e.y); }
  else if (g.type === "quad") { ctx.moveTo(g.s.x, g.s.y); ctx.quadraticCurveTo(g.c.x, g.c.y, g.e.x, g.e.y); }
  else { ctx.moveTo(g.pts[0].x, g.pts[0].y); for (let i = 1; i < g.pts.length; i++) ctx.lineTo(g.pts[i].x, g.pts[i].y); }
  ctx.stroke();
}
function geomPoint(g, t) {
  if (g.type === "bezier") {
    const u = 1 - t;
    return { x: u * u * u * g.s.x + 3 * u * u * t * g.c1.x + 3 * u * t * t * g.c2.x + t * t * t * g.e.x,
             y: u * u * u * g.s.y + 3 * u * u * t * g.c1.y + 3 * u * t * t * g.c2.y + t * t * t * g.e.y };
  }
  if (g.type === "quad") {
    const u = 1 - t;
    return { x: u * u * g.s.x + 2 * u * t * g.c.x + t * t * g.e.x, y: u * u * g.s.y + 2 * u * t * g.c.y + t * t * g.e.y };
  }
  const pts = g.pts, seg = [];
  let total = 0;
  for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y); seg.push(d); total += d; }
  let want = total * t;
  for (let i = 0; i < seg.length; i++) {
    if (want <= seg[i] || i === seg.length - 1) {
      const f = seg[i] ? want / seg[i] : 0;
      return { x: pts[i].x + (pts[i + 1].x - pts[i].x) * f, y: pts[i].y + (pts[i + 1].y - pts[i].y) * f };
    }
    want -= seg[i];
  }
  return pts[pts.length - 1];
}
// The arrow follows the real tangent at the end. The old expression reduced to
// atan2(0, ...) in flow view, so the head always pointed due east.
function geomEnd(g) {
  if (g.type === "bezier") return { p: g.e, ang: Math.atan2(g.e.y - g.c2.y, g.e.x - g.c2.x) };
  if (g.type === "quad") return { p: g.e, ang: Math.atan2(g.e.y - g.c.y, g.e.x - g.c.x) };
  const p = g.pts[g.pts.length - 1], q = g.pts[g.pts.length - 2];
  return { p, ang: Math.atan2(p.y - q.y, p.x - q.x) };
}

// Labels are only worth drawing when they can be read. What limits them is not
// the edge count but whether a pill fits somewhere free, so the collision test
// below does the rationing: on this board it keeps 133 of 387 candidates and
// drops the rest. The only extra gate is a zoom floor, because below it the
// text is too small to read whether it collides or not. Lit edges are exempt:
// tracing a connection is exactly when the edge type matters.
const LABEL_MIN_ZOOM = 0.5;
let labelRects = [];

// The empty state, painted on the canvas rather than left blank. A viewer that
// starts with nothing loaded - which it now can, from any directory - used to
// show a correctly sized but entirely empty canvas, and an empty canvas is
// indistinguishable from a broken one. This says which it is and what to do.
// Drawn in screen space, ignoring pan and zoom: a message the user cannot find
// because they scrolled away from it is no message.
function drawEmptyState() {
  // fit() sets cv.width/height in CSS pixels (there is no devicePixelRatio
  // scaling anywhere here), so the backing store IS the screen space.
  const w = cv.width, h = cv.height;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.textAlign = "center";
  ctx.fillStyle = "#334155";
  ctx.font = "600 15px ui-sans-serif, system-ui, sans-serif";
  ctx.fillText("No folder loaded", w / 2, h / 2 - 12);
  ctx.fillStyle = "#64748b";
  ctx.font = "13px ui-sans-serif, system-ui, sans-serif";
  ctx.fillText("Choose a repository with the Browse button above, or type its path and press Load.",
               w / 2, h / 2 + 12);
  ctx.fillText("It needs a .claude/ directory - that is what harness-bootstrap creates.",
               w / 2, h / 2 + 32);
  ctx.textAlign = "left";
}

function draw() {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (!graph.nodes.length) { drawEmptyState(); return; }
  ctx.translate(panzoom.x, panzoom.y); ctx.scale(panzoom.k, panzoom.k);
  ctx.font = "12px ui-monospace, Consolas, monospace";
  measureNodes();
  const byId = Object.fromEntries(graph.nodes.map(n => [n.id, n]));
  const active = hi.nodes.size > 0;
  const vis = graph.nodes.filter(visible);
  const chan = (view === "flow" && lineStyle === "ortho") ? channelIndex(vis) : null;
  const roomy = panzoom.k >= LABEL_MIN_ZOOM;
  const cand = [];

  graph.edges.forEach((e, i) => {
    const a = byId[e.from], b = byId[e.to];
    if (!a || !b || !visible(a) || !visible(b)) return;
    const pa = pos[a.id], pb = pos[b.id]; if (!pa || !pb) return;
    const lit = hi.edges.has(i);
    const off = a.disabled || b.disabled;
    if (active && !lit) { ctx.globalAlpha = 0.12; ctx.strokeStyle = "#94a3b8"; ctx.lineWidth = 1; }
    else if (lit) { ctx.globalAlpha = 1; ctx.strokeStyle = "#1d4ed8"; ctx.lineWidth = 2.2; }
    else { ctx.globalAlpha = 1; ctx.strokeStyle = off ? "#cbd5e1" : "#94a3b8"; ctx.lineWidth = 1.2; }
    // A lit edge animates by marching its dash pattern along the path; an
    // ordinary disabled edge keeps the static dash it always had.
    if (lit) { ctx.setLineDash([9, 6]); ctx.lineDashOffset = -dashPhase; }
    else ctx.setLineDash(off ? [4, 3] : []);
    const g = edgeGeom(a, b, pa, pb, chan ? chan[a.id] : 0);
    strokeGeom(g);
    ctx.setLineDash([]); ctx.lineDashOffset = 0;
    const { p: ep, ang } = geomEnd(g);
    ctx.beginPath();
    ctx.moveTo(ep.x - 10 * Math.cos(ang - 0.4), ep.y - 10 * Math.sin(ang - 0.4));
    ctx.lineTo(ep.x, ep.y);
    ctx.lineTo(ep.x - 10 * Math.cos(ang + 0.4), ep.y - 10 * Math.sin(ang + 0.4));
    ctx.stroke();
    ctx.globalAlpha = 1;
    if (lit || (!active && roomy)) {
      // spread the anchor along the path so parallel edges do not all label at
      // the same midpoint, then let the collision test drop what still clashes
      const t = 0.34 + 0.32 * ((i % 5) / 4);
      const q = geomPoint(g, t);
      cand.push({ x: q.x, y: q.y, w: ctx.measureText(e.type).width + 8, h: 14, text: e.type, lit });
    }
  });

  // lit labels claim their space first, so a traced connection is never the one
  // that gets dropped
  labelRects = [];
  cand.sort((p, q) => (q.lit ? 1 : 0) - (p.lit ? 1 : 0));
  for (const L of cand) {
    const clash = labelRects.some(r =>
      Math.abs(r.x - L.x) < (r.w + L.w) / 2 && Math.abs(r.y - L.y) < (r.h + L.h) / 2);
    if (clash) continue;
    labelRects.push(L);
    ctx.fillStyle = "#ffffff"; ctx.strokeStyle = L.lit ? "#bfdbfe" : "#e2e8f0"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.roundRect(L.x - L.w / 2, L.y - 8, L.w, 14, 7); ctx.fill(); ctx.stroke();
    ctx.fillStyle = L.lit ? "#1d4ed8" : "#64748b"; ctx.textAlign = "center"; ctx.fillText(L.text, L.x, L.y + 3);
  }
  ctx.textAlign = "left";

  for (const n of graph.nodes) {
    if (!visible(n)) continue;
    const p = pos[n.id]; if (!p) continue;
    const text = nodeLabel(n);
    const badge = nodeBadge(n);
    const lit = !active || hi.nodes.has(n.id);
    ctx.globalAlpha = lit ? (n.disabled ? 0.75 : 1) : 0.16;
    const bw = badge ? ctx.measureText(badge.text).width + 10 : 0;
    const w = n._w || Math.max(60, ctx.measureText(text).width + 18 + bw);
    ctx.fillStyle = n.disabled ? "#9ca3af" : (COLORS[n.type] || "#94a3b8");
    ctx.strokeStyle = sel === n.id ? "#0f172a" : (n.disabled ? "#b91c1c" : "rgba(0,0,0,0.15)");
    ctx.lineWidth = sel === n.id ? 2.5 : (n.disabled ? 1.6 : 1);
    ctx.setLineDash(n.disabled ? [4, 3] : []);
    ctx.beginPath(); ctx.roundRect(p.x - w / 2, p.y - 12, w, 24, 6); ctx.fill(); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#ffffff"; ctx.textAlign = "left";
    const tx = p.x - w / 2 + 9;
    ctx.fillText(text, tx, p.y + 4);
    if (badge) {
      const bx = p.x + w / 2 - bw - 4, tw = ctx.measureText(badge.text).width;
      ctx.fillStyle = badge.bg;
      ctx.beginPath(); ctx.roundRect(bx, p.y - 8, tw + 8, 16, 4); ctx.fill();
      ctx.fillStyle = badge.fg; ctx.fillText(badge.text, bx + 4, p.y + 4);
    }
    // A disabled item reads as OFF at a glance: dashed red border, greyed
    // fill, and the label struck through. Opacity alone did not register.
    if (n.disabled) {
      ctx.strokeStyle = "#7f1d1d"; ctx.lineWidth = 1.4;
      ctx.beginPath(); ctx.moveTo(tx - 2, p.y); ctx.lineTo(tx + ctx.measureText(text).width + 2, p.y); ctx.stroke();
    }
    ctx.globalAlpha = 1;
    n._w = w;
  }
  ctx.textAlign = "left";
}

// Badges: hooks show the event they fire on, blocking ones in red because a
// PreToolUse hook can exit 2 and stop the call; tasks show their board status.
function nodeBadge(n) {
  if (n.type === "hook") {
    const ev = meta(n, "event");
    if (!ev) return { text: "OFF", bg: "#fecaca", fg: "#7f1d1d" };
    const text = EVENT_BADGE[ev] || ev.slice(0, 5).toUpperCase();
    return meta(n, "blocking")
      ? { text, bg: "#7f1d1d", fg: "#fff" }
      : { text, bg: "#fef3c7", fg: "#78350f" };
  }
  if (n.type === "task") {
    const st = meta(n, "status");
    if (!st) return null;
    const c = STATUS_COLOR[st];
    return c ? { text: st.toUpperCase().slice(0, 7), bg: c, fg: "#fff" } : null;
  }
  return null;
}

function hit(mx, my) {
  const x = (mx - panzoom.x) / panzoom.k, y = (my - panzoom.y) / panzoom.k;
  for (const n of [...graph.nodes].reverse()) {
    if (!visible(n)) continue;
    const p = pos[n.id]; if (!p) continue;
    const w = n._w || 80;
    if (x >= p.x - w / 2 && x <= p.x + w / 2 && y >= p.y - 12 && y <= p.y + 12) return n;
  }
  return null;
}
cv.addEventListener("mousedown", ev => {
  const n = hit(ev.offsetX, ev.offsetY);
  if (n) { drag = { id: n.id, dx: ev.offsetX, dy: ev.offsetY, moved: 0 }; select(n); }
  // A pan must not disturb the selection. Deselecting belongs to a CLICK - a
  // press and release that did not move - so the decision waits for mouseup.
  else drag = { pan: true, dx: ev.offsetX, dy: ev.offsetY, moved: 0 };
});
cv.addEventListener("mousemove", ev => {
  if (!drag) return;
  const ddx = ev.offsetX - drag.dx, ddy = ev.offsetY - drag.dy;
  drag.moved += Math.abs(ddx) + Math.abs(ddy);
  if (drag.pan) { panzoom.x += ddx; panzoom.y += ddy; }
  else { const p = pos[drag.id]; p.x += ddx / panzoom.k; p.y += ddy / panzoom.k; }
  drag.dx = ev.offsetX; drag.dy = ev.offsetY; draw();
});
window.addEventListener("mouseup", () => {
  // fit() belongs here, not in mousedown: it is needed only because clearing
  // the selection closes the side panel and so changes the canvas width.
  if (drag && drag.pan && drag.moved < 4) { clearSel(); fit(); }
  drag = null;
});
cv.addEventListener("wheel", ev => {
  ev.preventDefault();
  const k = Math.max(0.3, Math.min(3, panzoom.k * (ev.deltaY < 0 ? 1.1 : 0.9)));
  panzoom.x = ev.offsetX - (ev.offsetX - panzoom.x) * k / panzoom.k;
  panzoom.y = ev.offsetY - (ev.offsetY - panzoom.y) * k / panzoom.k;
  panzoom.k = k; draw();
});

function row(table, k, v, cls) {
  const tr = document.createElement("tr");
  const tdk = document.createElement("td"); tdk.className = "k";
  // The flex row lives in this wrapper, never on the td itself (see the .kwrap
  // rule): a flex table cell is no longer a table cell, and the column widths
  // and row borders collapse with it.
  const kwrap = document.createElement("span"); kwrap.className = "kwrap";
  // The icon is decoration next to a key that already reads as words, so it is
  // aria-hidden: a screen reader announcing "circle status" helps nobody.
  if (FIELD_ICONS[k]) {
    const i = document.createElement("span");
    i.className = "kicon"; i.innerHTML = FIELD_ICONS[k];
    kwrap.append(i);
  }
  kwrap.append(document.createTextNode(k));
  tdk.append(kwrap);
  const tdv = document.createElement("td"); tdv.className = "v";
  if (cls) { const s = document.createElement("span"); s.className = cls; s.textContent = v; tdv.append(s); }
  else tdv.textContent = v;
  tr.append(tdk, tdv); table.append(tr);
  return tdv;
}

/// A value that names another node becomes a button to it. Colour alone never
/// carries the meaning: the text is always the identifier itself.
function nodeLink(cell, id, text) {
  const target = graph.nodes.find(x => x.id === id);
  if (!target) return false;
  const a = document.createElement("button");
  a.className = "vlink";
  a.textContent = text;
  a.title = "select " + id;
  a.onclick = () => { select(target); draw(); };
  cell.append(a);
  return true;
}

// The Command Steps panel. Parsing and serialization live in ui-steps.js (and
// are tested there); this is the DOM half. Every byte of the command file lands
// via textContent, so no repository text reaches innerHTML on this path and the
// panel needs no sanitiser pass at all.
//
// The panel edits: steps can be dragged into a new order, switched off, and
// retitled, and Save writes the file back through POST /command. Two things keep
// that honest. Nothing is written until Save - a drag is a local rearrangement,
// so a mis-drop costs a Revert and not a file. And Save serializes the parse
// this panel was built from, which rewrites only the step spans, so a save can
// never damage the parts of the file the panel never showed.
let stepEdit = null;   // { name, host, md, parsed } for the command on screen

function renderCommandSteps(host, md, name) {
  stepEdit = { name: name, host: host, md: md, parsed: parseCommandSteps(md) };
  paintCommandSteps();
}

/// Throw away every local change and go back to the file as last read.
function revertCommandSteps() {
  if (!stepEdit) return;
  stepEdit.parsed = parseCommandSteps(stepEdit.md);
  paintCommandSteps();
}

function stepsDirty() {
  return !!stepEdit && stepEdit.parsed.groups.some(g => g.dirty ||
    g.steps.some(s => s.edited));
}

function paintCommandSteps() {
  const host = stepEdit.host, parsed = stepEdit.parsed;
  host.textContent = "";
  const ids = new Set(graph.nodes.map(x => x.id));
  const lbl = document.createElement("div");
  lbl.className = "lbl";
  host.append(lbl);

  if (!parsed.hasSteps) {
    // Not an error and not an empty state: some commands are a description of a
    // job rather than a procedure. Show what the file says, exactly as written.
    lbl.textContent = "This command has no numbered steps. Its text, as written:";
    const p = document.createElement("div");
    p.className = "stepprose";
    p.textContent = parsed.body;
    host.append(p);
    return;
  }

  lbl.textContent = "Steps, read from the command file - drag a number to reorder";
  if (stepsDirty()) host.append(buildSaveBar());

  for (const g of parsed.groups) {
    const box = document.createElement("div");
    box.className = "stepgrp";
    if (g.heading) {
      const h = document.createElement("div");
      h.className = "gh"; h.textContent = g.heading; box.append(h);
    }
    if (g.intro) {
      const i = document.createElement("div");
      i.className = "gintro"; i.textContent = g.intro; box.append(i);
    }
    if (g.steps.length) {
      const ol = document.createElement("ol");
      ol.className = "steps flow";
      let shown = 0;
      g.steps.forEach((st, i) => {
        if (!st.disabled) shown++;
        ol.append(buildStepCard(g, st, i, shown, ids));
      });
      box.append(ol);
    }
    host.append(box);
  }
}

/// One step, as a card in the chain.
function buildStepCard(g, st, index, shown, ids) {
  const li = document.createElement("li");
  const card = document.createElement("div");
  card.className = "stepcard" + (st.disabled ? " off" : "");
  li.append(card);

  const num = document.createElement("div");
  num.className = "stepnum";
  // A dirty group has been renumbered by the serializer, so showing the file's
  // original number would name a step that is about to stop existing. An
  // untouched group keeps the file's own numbering, which is the existing
  // behaviour and the reason test.md's 1,2,3,5 still reads as 1,2,3,5.
  num.textContent = st.disabled ? "-" : (g.dirty ? String(shown) : st.num);
  num.title = "drag to reorder";
  num.draggable = true;
  card.append(num);

  const bodyBox = document.createElement("div");
  bodyBox.className = "stepbody";
  card.append(bodyBox);

  if (st.editing) {
    const ta = document.createElement("textarea");
    ta.className = "stepedit";
    ta.value = st.textBody;
    ta.spellcheck = false;
    bodyBox.append(ta);
    const bar = document.createElement("div");
    bar.className = "stepacts"; bar.style.marginTop = "4px";
    const ok = document.createElement("button");
    ok.textContent = "Apply";
    ok.onclick = () => {
      // Apply is local: it marks the step edited and repaints. The file is not
      // touched until Save, so an edit and a reorder land as one write.
      if (ta.value.trim()) setStepText(st, ta.value.replace(/\s+$/, ""));
      st.editing = false;
      paintCommandSteps();
    };
    const no = document.createElement("button");
    no.textContent = "Cancel";
    no.onclick = () => { st.editing = false; paintCommandSteps(); };
    bar.append(ok, no);
    bodyBox.append(bar);
  } else {
    const t = document.createElement("div");
    t.className = "steptext";
    t.textContent = st.textBody;
    bodyBox.append(t);
    const ts = touches(st.textBody, ids);
    if (ts.length) {
      const row = document.createElement("div");
      row.className = "steptouch";
      for (const tk of ts) {
        // nodeLink returns false when the graph has no such node - a rule file
        // with no rule node, a script that was deleted - and the reference is
        // then still shown, just not as a control that lies about where it
        // would take you.
        if (!tk.id || !nodeLink(row, tk.id, tk.label)) {
          const s = document.createElement("span");
          s.className = "vflat"; s.textContent = tk.label;
          s.title = "nothing in this graph to select";
          row.append(s);
        }
      }
      bodyBox.append(row);
    }
    if (st.tail && st.tail.length) {
      const nt = document.createElement("div");
      nt.className = "stepnote";
      nt.textContent = "the section's closing prose follows this step and stays at the end";
      bodyBox.append(nt);
    }
  }

  const acts = document.createElement("div");
  acts.className = "stepacts";
  const ed = document.createElement("button");
  ed.textContent = "Edit";
  ed.title = "edit this step's wording";
  ed.onclick = () => {
    for (const gg of stepEdit.parsed.groups) for (const s of gg.steps) s.editing = false;
    st.editing = true;
    paintCommandSteps();
  };
  const off = document.createElement("button");
  off.textContent = st.disabled ? "On" : "Off";
  const blocked = !st.disabled && !canDisableStep(st);
  off.disabled = blocked;
  off.title = blocked
    // Refused up front rather than at save time: the wrapper is an HTML comment
    // and this step already contains its terminator, so wrapping it would close
    // the block early and drop the tail back into the file as live prose.
    ? "cannot switch off: this step's text contains `-->`, which would end the comment early"
    : (st.disabled ? "put this step back into the procedure"
                   : "comment this step out of the procedure");
  off.onclick = () => {
    st.disabled = !st.disabled;
    st.editing = false;
    g.dirty = true;
    paintCommandSteps();
  };
  acts.append(ed, off);
  card.append(acts);

  wireStepDrag(li, card, num, g, index);
  return li;
}

// Which card is in flight. Held in a module variable rather than in the
// dataTransfer payload: the drop target needs to know the source on dragover to
// draw the insertion line, and dataTransfer is unreadable until drop.
let stepDrag = null;   // { group, from }

function wireStepDrag(li, card, handle, g, index) {
  handle.addEventListener("dragstart", ev => {
    stepDrag = { group: g, from: index };
    card.classList.add("dragging");
    // Firefox starts no drag at all without payload; the value is unused.
    if (ev.dataTransfer) { ev.dataTransfer.effectAllowed = "move"; ev.dataTransfer.setData("text/plain", String(index)); }
  });
  handle.addEventListener("dragend", () => {
    stepDrag = null;
    card.classList.remove("dragging");
    clearDropMarks();
  });
  li.addEventListener("dragover", ev => {
    // A step only reorders inside its own group. Dragging a precondition into
    // the Steps list would move a check into the procedure as an action, which
    // is exactly the confusion the grouping exists to prevent.
    if (!stepDrag || stepDrag.group !== g || stepDrag.from === index) return;
    ev.preventDefault();
    if (ev.dataTransfer) ev.dataTransfer.dropEffect = "move";
    clearDropMarks();
    card.classList.add(index < stepDrag.from ? "drop-above" : "drop-below");
  });
  li.addEventListener("dragleave", () => card.classList.remove("drop-above", "drop-below"));
  li.addEventListener("drop", ev => {
    if (!stepDrag || stepDrag.group !== g || stepDrag.from === index) return;
    ev.preventDefault();
    const moved = g.steps.splice(stepDrag.from, 1)[0];
    g.steps.splice(index, 0, moved);
    g.dirty = true;
    stepDrag = null;
    paintCommandSteps();
  });
}

function clearDropMarks() {
  for (const el of document.querySelectorAll(".stepcard.drop-above, .stepcard.drop-below")) {
    el.classList.remove("drop-above", "drop-below");
  }
}

/// The unsaved-changes bar. It exists only while something is unsaved, so its
/// presence IS the dirty indicator and there is no second piece of state to
/// keep in step with the first.
function buildSaveBar() {
  const bar = document.createElement("div");
  bar.className = "stepsave";
  const txt = document.createElement("div");
  txt.className = "grow";
  txt.textContent = "Unsaved changes to " + stepEdit.name + ".md";
  const save = document.createElement("button");
  save.textContent = "Save";
  const revert = document.createElement("button");
  revert.textContent = "Revert";
  revert.onclick = () => revertCommandSteps();
  save.onclick = async () => {
    save.disabled = revert.disabled = true;
    txt.textContent = "saving ...";
    let content;
    try {
      content = serializeCommandSteps(stepEdit.parsed);
    } catch (e) {
      txt.textContent = "could not rebuild the file: " + e;
      save.disabled = revert.disabled = false;
      return;
    }
    try {
      const r = await fetch("command", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: stepEdit.name, content: content, root: currentRoot }),
      });
      const t = await r.text();
      if (!r.ok) {
        txt.textContent = t;
        save.disabled = revert.disabled = false;
        return;
      }
      // Re-read from what was actually written rather than assuming the parse
      // in hand now matches the file: a save that renumbered has moved every
      // line index the current parse holds.
      stepEdit.md = content;
      stepEdit.parsed = parseCommandSteps(content);
      paintCommandSteps();
    } catch (e) {
      txt.textContent = "save failed: " + e;
      save.disabled = revert.disabled = false;
    }
  };
  bar.append(txt, save, revert);
  return bar;
}

function select(n) {
  // Selecting another node rebuilds the panel and the step editor with it, so
  // anything unsaved would go without being mentioned. Ask first, and keep the
  // current selection when the answer is no.
  if (stepsDirty() && stepEdit && n.id !== sel &&
      !window.confirm("There are unsaved step changes to " + stepEdit.name +
                      ".md.\n\nLeave without saving?")) {
    return;
  }
  stepEdit = null;
  sel = n.id;
  hi = computeHighlight(n.id);
  startAnim();
  const d = document.getElementById("detail");
  setPanel(true);
  d.textContent = "";
  // the panel is a column: this block takes the height it needs, the preview
  // below it stretches into the rest instead of being a fixed 340px box
  const head = document.createElement("div");
  head.className = "head";
  d.append(head);
  const h3 = document.createElement("h3");
  h3.textContent = label(n);
  head.append(h3);

  const desc = meta(n, "description");
  if (desc) { const p = document.createElement("div"); p.className = "desc"; p.textContent = desc; head.append(p); }

  const table = document.createElement("table");
  table.className = "meta";
  row(table, "id", n.id);
  row(table, "type", n.type);
  // enabled/disabled first and as a badge: it is the thing a reader scans for
  row(table, "state", n.disabled ? "DISABLED" : "enabled", n.disabled ? "state off" : "state on");
  if (n.file) row(table, "file", n.file);
  for (const [k, v] of Object.entries(n.meta || {})) {
    if (k === "description") continue;
    const val = Array.isArray(v) ? v.join(", ") : String(v);
    if (k === "status") {
      const cell = row(table, k, "");
      const s = document.createElement("span");
      s.className = "state"; s.textContent = val;
      s.style.background = (STATUS_COLOR[val] || "#64748b") + "22";
      s.style.color = STATUS_COLOR[val] || "#334155";
      cell.append(s);
    } else if (k === "owner") {
      const cell = row(table, k, val);
      // a task can name more than one seat (`a+b`), and each is its own node
      const seats = val.split("+").map(x => x.trim()).filter(Boolean);
      const linked = seats.filter(x => graph.nodes.some(n2 => n2.id === "agent:" + x));
      if (linked.length) {
        cell.textContent = "";
        seats.forEach((seat, i) => {
          if (i) cell.append(document.createTextNode(" "));
          if (!nodeLink(cell, "agent:" + seat, seat)) {
            // a seat that is not on the roster: say so rather than linking nowhere
            const miss = document.createElement("span");
            miss.className = "vmiss"; miss.textContent = seat + " (not on roster)";
            cell.append(miss);
          }
        });
      }
    } else if (k === "deps") {
      const cell = row(table, k, val);
      const ids = val.split(",").map(x => x.trim()).filter(Boolean);
      const nodes = graph.nodes.filter(x => x.type === "task");
      const any = ids.some(id => nodes.some(t => t.id.includes(id)));
      if (any) {
        cell.textContent = "";
        ids.forEach((id, i) => {
          if (i) cell.append(document.createTextNode(" "));
          const t = nodes.find(x => x.id.includes(id));
          if (!t || !nodeLink(cell, t.id, id)) {
            const plain = document.createElement("span");
            plain.className = "vmono"; plain.textContent = id; cell.append(plain);
          }
        });
      }
    } else if (k === "model" || k === "effort") {
      // cost signal, with the word still present for anyone who cannot see it
      const cell = row(table, k, "");
      const tone = (k === "model" ? MODEL_TONE : EFFORT_TONE)[val] || "mid";
      const s2 = document.createElement("span");
      s2.className = "tone " + tone; s2.textContent = val;
      cell.append(s2);
    } else if (k === "fr") {
      const cell = row(table, k, "");
      const s2 = document.createElement("span");
      s2.className = "vmono"; s2.textContent = val;
      cell.append(s2);
    } else if (k === "blocking") {
      const cell = row(table, k, "");
      const s2 = document.createElement("span");
      s2.className = "tone " + (val === "true" ? "hot" : "cool");
      s2.textContent = val === "true" ? "true (blocks the call)" : "false (advisory)";
      cell.append(s2);
    } else {
      row(table, k, val);
    }
  }
  head.append(table);

  // A command's steps are the thing a reader opened it for, so they go above the
  // preview and get their own scroller. This is a sibling of the preview host,
  // not part of .head, because .head is capped at 60% of the panel height.
  if (n.type === "command" && n.file) {
    const box = document.createElement("div");
    box.className = "stepbox";
    const wait = document.createElement("div");
    wait.className = "lbl";
    wait.textContent = "reading " + n.file + " ...";
    box.append(wait);
    d.append(box);
    const want = n.id;
    (async () => {
      let text = null, err = null;
      try {
        const u = "file?path=" + encodeURIComponent(n.file) +
          (currentRoot ? "&root=" + encodeURIComponent(currentRoot) : "");
        const r = await fetch(u);
        const t = await r.text();
        if (r.ok) text = t; else err = "could not read " + n.file + ": " + t;
      } catch (e) { err = "could not read " + n.file + ": " + e; }
      // The user can click a second node before this resolves. Repainting then
      // would drop one command's steps into another command's panel, and both
      // panels look equally plausible, so the wrong one would be believed.
      if (sel !== want) return;
      if (err !== null) {
        box.textContent = "";
        const p = document.createElement("div");
        p.className = "lbl"; p.textContent = err; box.append(p);
        return;
      }
      renderCommandSteps(box, text, n.id.split(":").slice(1).join(":"));
    })();
  }

  if (n.file) {
    const bar = document.createElement("div");
    bar.className = "md-bar";
    const btn = document.createElement("button");
    btn.className = "prev-btn";
    setBtn(btn, "eye", "Preview file");
    const host = document.createElement("div");
    host.className = "filehost";
    host.style.display = "none";
    let text = null, err = null;
    const paint = () => {
      host.textContent = "";
      if (err !== null) { host.className = "filehost"; const p = document.createElement("pre"); p.className = "preview"; p.textContent = err; host.append(p); return; }
      if (text === null) return;
      // the .md frame belongs to formatted output only; raw already ships its
      // own <pre> and would otherwise sit in a box inside a box
      // keep `filehost`: it is what makes the preview claim the rest of the
      // panel. Overwriting className here silently dropped that, and the box
      // only looked right because the file happened to be long enough.
      if (mdMode("hv-md-side") === "raw") { host.className = "filehost"; renderRaw(host, text); }
      else {
        // JSON and YAML bring their own frame (.code), so only the markdown
        // path wants the .md box: nesting a dark code block inside it reads as
        // a box in a box.
        const kind = renderFormatted(host, text, n.file);
        host.className = kind === "md" ? "filehost md" : "filehost";
      }
    };
    const modeBtn = makeModeButton("hv-md-side", paint, n.file);
    modeBtn.style.display = "none";
    btn.onclick = () => withBusy("reading file", btn, async () => {
      if (host.style.display === "block") {
        host.style.display = "none"; modeBtn.style.display = "none";
        setBtn(btn, "eye", "Preview file"); return;
      }
      if (text === null && err === null) {
        try {
          const u = "file?path=" + encodeURIComponent(n.file) + (currentRoot ? "&root=" + encodeURIComponent(currentRoot) : "");
          const r = await fetch(u);
          const t = await r.text();
          if (r.ok) text = t; else err = "could not read file: " + t;
        } catch (e) { err = "could not read file: " + e; }
      }
      paint();
      host.style.display = "block";
      if (err === null) modeBtn.style.display = "";
      setBtn(btn, "eyeoff", "Hide file");
    });
    bar.append(btn, modeBtn);
    head.append(bar);
    d.append(host);
  }

  // Agents are in this list now. Parking a seat quarantines its file exactly
  // like a rule's, and the seats the harness structurally assumes - the sole
  // spawner, the review gates - are HARD-protected server-side rather than
  // hidden here, so the refusal states its reason instead of the control simply
  // not existing.
  if (["rule", "command", "hook", "agent"].includes(n.type)) {
    const b = document.createElement("button");
    // Disabling removes a control and Enabling restores one; they should not
    // look like the same neutral action.
    b.className = "toggle-btn " + (n.disabled ? "restore" : "danger");
    setBtn(b, n.disabled ? "on" : "off",
           (n.disabled ? "Enable " : "Disable ") + label(n));
    b.onclick = async () => {
      const bare = n.id.split(":").slice(1).join(":");
      // always name the root being viewed, so a toggle can never land on the
      // server's CLI default while the page is showing a different repo
      const payload = { kind: n.type, name: bare, enable: !!n.disabled, root: currentRoot };
      const post = async () => {
        const r = await fetch("toggle", { method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify(payload) });
        return { res: r, txt: await r.text() };
      };
      let { res, txt } = await post();
      if (res.status === 403 && !payload.enable) {
        // HARD-protected. The CLI makes the user type `disable <name>` and
        // forbids the model from composing it; there is no model here, so the
        // page asks the human for the same phrase and sends what they typed.
        // Nothing is normalized on the way: a near miss is refused again.
        const typed = window.prompt(
          txt + "\n\nType the phrase exactly to confirm:", "");
        if (typed !== null && typed !== "") {
          payload.confirm_hard = typed;
          ({ res, txt } = await post());
        }
      }
      if (res.status === 409 && !payload.enable) {
        // SOFT-protected: the server refused pending an explicit confirmation
        if (window.confirm(txt + "\n\nDisable it anyway?")) {
          payload.confirm_soft = true;
          ({ res, txt } = await post());
        }
      }
      if (!res.ok) { const m = document.createElement("div"); m.id = "msg"; m.textContent = txt; d.append(m); }
      else { clearSel(); await load(); }
      fit();
    };
    head.append(b);
  }
  fit(); draw();
}

// --- master plan (optional) -------------------------------------------------
// The tab only exists when docs/tasks/master-plan.md does. Projects that do not
// run a board must not be shown an empty tab implying they should.
let planText = null;
async function checkPlan() {
  planText = null;
  try {
    const u = "file?path=" + encodeURIComponent("docs/tasks/master-plan.md") +
      (currentRoot ? "&root=" + encodeURIComponent(currentRoot) : "");
    planText = await withBusy("reading plan", null, async () => {
      const r = await fetch(u);
      return r.ok ? await r.text() : null;
    });
  } catch (e) { planText = null; }
  const btn = document.getElementById("btn-plan");
  btn.style.display = planText === null ? "none" : "";
  if (planText === null && view === "plan") { view = "flow"; localStorage.setItem("hv-view", view); }
}
// Raw mode: the file exactly as it sits on disk, frontmatter included, placed
// with textContent so repository text can never execute.
// ---------------------------------------------------------------- structured
// JSON and YAML get real views instead of one wrapped run of text. Both are
// built with DOM APIs and textContent only: no repository byte ever reaches
// innerHTML on these paths, so they need no sanitiser pass at all.

/// Which viewer a file gets, decided by extension. Anything unrecognised is
/// markdown, which is what every .md in the harness is and a safe default for
/// the rest since the markdown path already sanitises.
function fileKind(file) {
  const f = (file || "").toLowerCase();
  if (f.endsWith(".json")) return "json";
  if (f.endsWith(".yml") || f.endsWith(".yaml")) return "yaml";
  return "md";
}

function span(cls, text) {
  const e = document.createElement("span");
  if (cls) e.className = cls;
  e.textContent = text;
  return e;
}

// Collapse anything big enough to bury the rest of the file. settings.json is
// one object whose "permissions" array runs to dozens of entries; opening that
// expanded is the wall of text this view exists to replace.
const JSON_COLLAPSE_OVER = 6;

/// One JSON value as DOM. `key` is the property name when this value sits in an
/// object, so the key and its value stay on one line.
function jsonNode(value, key, depth) {
  const line = document.createElement("span");
  const label = () => {
    if (key === null) return;
    line.append(span("jk", JSON.stringify(key)), span("jp", ": "));
  };

  if (value === null) { label(); line.append(span("ju", "null")); return line; }
  const t = typeof value;
  if (t === "string") { label(); line.append(span("js", JSON.stringify(value))); return line; }
  if (t === "number") { label(); line.append(span("jn", String(value))); return line; }
  if (t === "boolean") { label(); line.append(span("jb", String(value))); return line; }

  const isArr = Array.isArray(value);
  const entries = isArr ? value.map((v, i) => [i, v]) : Object.entries(value);
  const open = isArr ? "[" : "{";
  const close = isArr ? "]" : "}";

  if (entries.length === 0) { label(); line.append(span("jp", open + close)); return line; }

  const det = document.createElement("details");
  // depth 0 always opens: a collapsed root shows the reader nothing.
  if (depth === 0 || entries.length <= JSON_COLLAPSE_OVER) det.open = true;
  const sum = document.createElement("summary");
  if (key !== null) sum.append(span("jk", JSON.stringify(key)), span("jp", ": "));
  sum.append(span("jp", open));
  sum.append(span("count", " " + entries.length + (isArr ? " items" : " keys") + " "));
  sum.append(span("jp", close));
  det.append(sum);

  const kids = document.createElement("span");
  kids.className = "kids";
  entries.forEach(([k, v], i) => {
    const child = jsonNode(v, isArr ? null : k, depth + 1);
    kids.append(child);
    if (i < entries.length - 1) kids.append(span("jp", ","));
    kids.append(document.createTextNode("\n"));
  });
  det.append(kids);
  det.append(span("jp", close));
  line.append(det);
  return line;
}

/// Pretty, collapsible JSON. Malformed input is never swallowed: it falls back
/// to the raw bytes with the parser's own message, because a viewer that shows
/// nothing for a broken file is worse than one that shows the file.
function renderJson(host, text, file) {
  let data;
  try {
    data = JSON.parse(text);
  } catch (e) {
    // renderRaw clears the host first, so the notice has to go in AFTER it or
    // it is wiped before anyone sees it.
    renderRaw(host, text);
    const warn = document.createElement("div");
    warn.className = "mdwarn";
    warn.textContent = (file || "this file") + " is not valid JSON, so it is shown as text. "
      + String(e.message || e);
    host.prepend(warn);
    return;
  }
  const pre = document.createElement("pre");
  pre.className = "code";
  pre.append(jsonNode(data, null, 0));
  host.append(pre);
}

// YAML is highlight-only and deliberately not parsed. Colouring is all this
// view needs, and a real YAML parser is a large dependency with anchors, alias
// expansion and implicit type coercion behind it - security surface bought for
// nothing. Line-based highlighting cannot misread a document into the wrong
// shape because it never claims to know the shape.
function yamlLine(line) {
  const out = document.createDocumentFragment();
  const indentLen = line.length - line.trimStart().length;
  const indent = line.slice(0, indentLen);
  let rest = line.slice(indentLen);
  if (indent) out.append(document.createTextNode(indent));

  if (rest === "") return out;
  if (rest.startsWith("#")) { out.append(span("jc", rest)); return out; }
  // document markers and directives
  if (rest === "---" || rest === "..." || rest.startsWith("%")) {
    out.append(span("ja", rest));
    return out;
  }
  // a list item keeps its dash, then the remainder is scanned as a value
  if (rest.startsWith("- ")) {
    out.append(span("jp", "- "));
    rest = rest.slice(2);
  } else if (rest === "-") {
    out.append(span("jp", "-"));
    return out;
  }

  // split a trailing comment off first so a "#" inside a quoted value survives
  let comment = "";
  const hash = rest.search(/(^|\s)#/);
  if (hash >= 0 && !/^["']/.test(rest.slice(hash).trim())) {
    comment = rest.slice(hash);
    rest = rest.slice(0, hash);
  }

  const kv = rest.match(/^([A-Za-z0-9_.$\-"'\[\]]+)(\s*:)(\s*)([\s\S]*)$/);
  if (kv) {
    out.append(span("jk", kv[1]), span("jp", kv[2]), document.createTextNode(kv[3]));
    rest = kv[4];
  }
  if (rest) {
    const v = rest.trim();
    let cls = null;
    if (/^(true|false|yes|no|on|off)$/i.test(v)) cls = "jb";
    else if (/^-?\d[\d_]*(\.\d+)?([eE][+-]?\d+)?$/.test(v)) cls = "jn";
    else if (/^(null|~)$/i.test(v)) cls = "ju";
    else if (/^["'].*["']$/.test(v)) cls = "js";
    else if (/^[&*]/.test(v)) cls = "ja";
    out.append(cls ? span(cls, rest) : document.createTextNode(rest));
  }
  if (comment) out.append(span("jc", comment));
  return out;
}

function renderYaml(host, text) {
  const pre = document.createElement("pre");
  pre.className = "code";
  const lines = text.split(/\r?\n/);
  lines.forEach((ln, i) => {
    pre.append(yamlLine(ln));
    if (i < lines.length - 1) pre.append(document.createTextNode("\n"));
  });
  host.append(pre);
}

/// Formatted view for any file: the right viewer for its extension.
function renderFormatted(host, text, file) {
  const kind = fileKind(file);
  if (kind === "json") { renderJson(host, text, file); return "code"; }
  if (kind === "yaml") { renderYaml(host, text); return "code"; }
  renderMarkdown(host, text, { frontmatter: "render", file: file });
  return "md";
}

function renderRaw(host, md) {
  host.textContent = "";
  const pre = document.createElement("pre");
  pre.className = "preview";
  pre.textContent = md;
  host.append(pre);
}

// A deliberately small markdown subset rendered through DOM APIs. No library,
// and no raw HTML from the file: every value lands via textContent.
// One renderer serves both the plan tab and the sidebar; they differ only in
// what they do with frontmatter, which is the `frontmatter` option:
//   "strip"  - drop it (the plan tab: metadata about the file is not the plan)
//   "render" - show it as a keyed block (the sidebar: model, tools and
//              description are the most useful lines in an agent file)
// GFM task items arrive from marked as `<li><input type="checkbox" ...>text`.
// The sanitiser strips the input (see PURIFY_OPTS), so we convert the item to an
// inert glyph BEFORE sanitising and mark it with a class the CSS can style.
function taskGlyphs(html) {
  return html.replace(
    /<li([^>]*)>\s*<input([^>]*?)type="checkbox"([^>]*?)>\s*/gi,
    (m, liAttr, a, b) => {
      const checked = /checked/i.test(a + b);
      const cls = checked ? "tick done" : "tick todo";
      const glyph = checked ? "☑" : "☐";
      return `<li${liAttr} class="taskitem"><span class="${cls}">${glyph}</span> `;
    });
}

// GFM ends a table at the first blank line. A file that puts one in the middle of
// a table therefore renders the remaining rows as a paragraph of pipes - correct
// per spec and identical on GitHub, but baffling on screen. Rather than diverge
// from the spec we name the defect where it shows, and report it in the
// assessment tab as a docs-quality finding.
const PIPE_ROW = /^\s*\|.*\|\s*$/;
function markBrokenTables(body, fileLabel) {
  let found = 0;
  for (const p of [...body.querySelectorAll("p")]) {
    const lines = (p.textContent || "").split("\n").filter(l => l.trim());
    if (lines.length < 1 || !lines.every(l => PIPE_ROW.test(l))) continue;
    const prev = p.previousElementSibling;
    const afterTable = prev && (prev.tagName === "TABLE" ||
      (prev.classList && prev.classList.contains("tw")));
    if (!afterTable) continue;
    found++;
    const note = document.createElement("div");
    note.className = "mdwarn";
    note.textContent = "This table ended early: there is a blank line inside it in " +
      (fileLabel || "the source file") + ", and a blank line terminates a table in " +
      "GitHub-flavoured Markdown. The rows below are shown as written. Remove the " +
      "blank line to join them back into the table.";
    p.parentNode.insertBefore(note, p);
    p.classList.add("mdraw");
  }
  return found;
}

function renderMarkdown(host, md, opts) {
  const mode = (opts && opts.frontmatter) || "strip";
  host.textContent = "";
  let src = md;
  if (/^---\s*\n/.test(src)) {
    const end = src.indexOf("\n---", 3);
    if (end !== -1) {
      const fmText = src.slice(4, end);
      src = src.slice(src.indexOf("\n", end + 1) + 1);
      if (mode === "render") {
        const box = document.createElement("div");
        box.className = "fm";
        for (const line of fmText.split(/\r?\n/)) {
          if (!line.trim() || /^\s/.test(line)) continue;
          const i = line.indexOf(":");
          if (i === -1) continue;
          const row = document.createElement("div");
          const k = document.createElement("b"), v = document.createElement("span");
          k.textContent = line.slice(0, i).trim();
          v.textContent = line.slice(i + 1).trim();
          row.append(k, v); box.append(row);
        }
        if (box.children.length) host.append(box);
      }
    }
  }
  // marked renders the markdown (GFM tables included, which is what the
  // hand-rolled parser got wrong); DOMPurify makes the result safe to insert,
  // because this HTML is built from a file in the repository being inspected
  // and the page it lands in is same-origin with the mutating /toggle endpoint.
  const body = document.createElement("div");
  body.innerHTML = window.DOMPurify.sanitize(
    taskGlyphs(window.marked.parse(src)), PURIFY_OPTS);
  // A wide table keeps its natural width and scrolls in its own container
  // instead of being crushed to fit the panel it happens to be in.
  for (const t of [...body.querySelectorAll("table")]) {
    const wrap = document.createElement("div");
    wrap.className = "tw";
    t.replaceWith(wrap); wrap.append(t);
  }
  mdBrokenTables = markBrokenTables(body, (opts && opts.file) || null);
  while (body.firstChild) host.append(body.firstChild);
}
let mdBrokenTables = 0;

// The plan tab keeps its toolbar outside the rendered body, so switching mode
// does not destroy the control that switched it.
function renderPlan(md) {
  const bar = document.getElementById("plan-bar");
  const body = document.getElementById("plan-body");
  if (!bar.children.length) {
    const lbl = document.createElement("span");
    lbl.className = "lbl"; lbl.textContent = "docs/tasks/master-plan.md";
    bar.append(makeModeButton("hv-md-plan", () => renderPlan(planText)), lbl);
  }
  if (mdMode("hv-md-plan") === "raw") renderRaw(body, md);
  else renderMarkdown(body, md, { frontmatter: "strip", file: "docs/tasks/master-plan.md" });
}

// ---- Assess tab -----------------------------------------------------------
// The rules engine is in Rust (src/assess.rs) and is the same one
// `harness-view assess` runs, so the browser and CI can never disagree about a
// harness. This code only renders what it returns.
let assessCache = null, assessRoot = null;

async function loadAssessment(force) {
  const host = document.getElementById("assess");
  if (!force && assessCache && assessRoot === currentRoot) { renderAssessment(assessCache); return; }
  host.textContent = "";
  const p = document.createElement("p"); p.className = "amuted";
  p.textContent = "assessing " + (currentRoot || "this harness") + "...";
  host.append(p);
  await withBusy("assessing", document.getElementById("btn-assess"), async () => {
    const url = "assess" + (currentRoot ? "?root=" + encodeURIComponent(currentRoot) : "");
    try {
      const res = await fetch(url);
      const body = await res.json();
      if (!res.ok || body.error) {
        host.textContent = "";
        banner(body.error || ("server returned " + res.status));
        return;
      }
      assessCache = body; assessRoot = currentRoot;
      renderAssessment(body);
    } catch (e) { host.textContent = ""; banner("could not assess: " + e); }
  });
}

function abar(pct, cls) {
  const outer = document.createElement("div"); outer.className = "abar";
  const inner = document.createElement("i"); inner.className = cls || "";
  inner.style.width = Math.max(0, Math.min(100, pct)) + "%";
  outer.append(inner); return outer;
}

function scoreClass(v) { return v >= 85 ? "good" : v >= 60 ? "warn" : "bad"; }

// Selecting the offending node and switching to the graph is the whole point of
// linking findings back to the graph: a finding you cannot locate is a complaint.
function gotoNode(id) {
  const n = graph.nodes.find(x => x.id === id);
  if (!n) { banner("that node is not in the current graph: " + id); return; }
  if (hidden.has(n.type)) {
    hidden.delete(n.type);
    localStorage.setItem("hv-hidden", JSON.stringify([...hidden]));
    buildLegend();
  }
  if (view !== "graph") view = "flow";
  localStorage.setItem("hv-view", view);
  sync();
  select(n);
  fitView(graph.nodes.filter(visible));
  draw();
}

function renderAssessment(a) {
  const host = document.getElementById("assess");
  host.textContent = "";

  const head = document.createElement("div"); head.className = "ahead";
  const left = document.createElement("div");
  const h = document.createElement("h2"); h.textContent = "Harness assessment";
  const sub = document.createElement("div"); sub.className = "amuted";
  sub.textContent = a.root + "  -  " + a.counts.high + " high, " + a.counts.medium +
                    " medium, " + a.counts.low + " low";
  left.append(h, sub);
  const overall = document.createElement("div"); overall.className = "aoverall";
  const big = document.createElement("b"); big.className = scoreClass(a.scores.overall);
  big.textContent = a.scores.overall;
  const of = document.createElement("span"); of.className = "amuted"; of.textContent = "/100";
  overall.append(big, of);
  head.append(left, overall);
  host.append(head);

  const cats = document.createElement("div"); cats.className = "acats";
  for (const [name, v] of Object.entries(a.scores.categories)) {
    const card = document.createElement("div"); card.className = "acat";
    const t = document.createElement("div"); t.className = "acat-t";
    const nm = document.createElement("span"); nm.textContent = name;
    const sc = document.createElement("b"); sc.className = scoreClass(v.score); sc.textContent = v.score;
    t.append(nm, sc);
    const f = document.createElement("div"); f.className = "amuted";
    f.textContent = v.findings + (v.findings === 1 ? " finding" : " findings");
    card.append(t, abar(v.score, scoreClass(v.score)), f);
    cats.append(card);
  }
  host.append(cats);

  const note = document.createElement("div"); note.className = "anote";
  note.textContent = a.scores.method;
  host.append(note);

  const notm = document.createElement("details"); notm.className = "anotm";
  const nsum = document.createElement("summary");
  nsum.textContent = "What this score does NOT measure";
  notm.append(nsum);
  const ul = document.createElement("ul");
  for (const line of a.scores.not_measured) {
    const li = document.createElement("li"); li.textContent = line; ul.append(li);
  }
  notm.append(ul); host.append(notm);

  const sh = document.createElement("h3"); sh.textContent = "Statistics"; host.append(sh);
  const st = a.statistics;
  const grid = document.createElement("div"); grid.className = "astats";
  const addStat = (label, pairs, filterable) => {
    const box = document.createElement("div"); box.className = "astat";
    const b = document.createElement("div"); b.className = "astat-h"; b.textContent = label;
    box.append(b);
    for (const [k, v] of Object.entries(pairs)) {
      const row = document.createElement("div"); row.className = "astat-r";
      const kk = document.createElement("span"); kk.textContent = k;
      const vv = document.createElement("b"); vv.textContent = v;
      if (filterable) {
        kk.className = "alink";
        kk.title = "show only this type in the graph";
        kk.onclick = () => {
          for (const t of Object.keys(st.nodes_by_type)) { if (t !== k) hidden.add(t); }
          hidden.delete(k);
          localStorage.setItem("hv-hidden", JSON.stringify([...hidden]));
          buildLegend();
          view = "flow"; localStorage.setItem("hv-view", view); sync();
        };
      }
      row.append(kk, vv); box.append(row);
    }
    grid.append(box);
  };
  addStat("Nodes by type", st.nodes_by_type, true);
  addStat("Edges by type", st.edges_by_type, false);
  addStat("Agents by model", st.agents_by_model, false);
  if (Object.keys(st.tasks_by_status).length) addStat("Tasks by status", st.tasks_by_status, false);
  addStat("Hooks", { total: st.hooks.total, blocking: st.hooks.blocking, advisory: st.hooks.advisory }, false);
  addStat("Rules (session tax)", {
    "always on": st.rules.always_on,
    "always-on bytes": st.rules.always_on_bytes,
    "path scoped": st.rules.path_scoped,
    "kept out of session %": st.rules.percent_kept_out_of_session
  }, false);
  host.append(grid);

  const fh = document.createElement("h3");
  fh.textContent = "Findings (" + a.findings.length + ", worst first)";
  host.append(fh);
  if (!a.findings.length) {
    const ok = document.createElement("p"); ok.className = "amuted";
    ok.textContent = "No findings. That means every rule this engine checks passed, " +
                     "not that the harness is good.";
    host.append(ok);
  }
  const list = document.createElement("div"); list.className = "afind";
  for (const f of a.findings) {
    const row = document.createElement("div"); row.className = "afind-r sev-" + f.severity;
    const top = document.createElement("div"); top.className = "afind-t";
    const sev = document.createElement("span"); sev.className = "sevtag " + f.severity;
    sev.textContent = f.severity;
    const title = document.createElement("span"); title.textContent = f.title;
    top.append(sev, title);
    if (f.node) {
      const go = document.createElement("button"); go.className = "agoto";
      go.textContent = "show in graph";
      go.onclick = () => gotoNode(f.node);
      top.append(go);
    }
    const why = document.createElement("div"); why.className = "afind-w"; why.textContent = f.why;
    row.append(top, why);
    if (f.file) {
      const fl = document.createElement("div"); fl.className = "afind-f"; fl.textContent = f.file;
      row.append(fl);
    }
    list.append(row);
  }
  host.append(list);
}

document.getElementById("btn-flow").onclick = () => { view = "flow"; localStorage.setItem("hv-view", view); sync(); };
document.getElementById("btn-graph").onclick = () => { view = "graph"; localStorage.setItem("hv-view", view); sync(); };
document.getElementById("btn-plan").onclick = () => { view = "plan"; localStorage.setItem("hv-view", view); sync(); };
document.getElementById("btn-assess").onclick = () => { view = "assess"; localStorage.setItem("hv-view", view); sync(); };
const btnReload = document.getElementById("btn-reload");
btnReload.onclick = () => withBusy("scanning", btnReload, () => load());
const lineSel = document.getElementById("linestyle");
lineSel.value = lineStyle;
lineSel.onchange = () => {
  lineStyle = lineSel.value; localStorage.setItem("hv-line", lineStyle);
  hint(); draw();
};
// Drag the grip to resize the panel. The canvas is refitted on every move so
// the two never disagree about how much room is left.
const grip = document.getElementById("grip");
grip.addEventListener("mousedown", ev => {
  ev.preventDefault();
  const startX = ev.clientX, startW = sideW;
  document.body.classList.add("resizing"); grip.classList.add("dragging");
  const move = e => { sideW = startW + (startX - e.clientX); applySide(); fit(); };
  const up = () => {
    document.body.classList.remove("resizing"); grip.classList.remove("dragging");
    window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up);
  };
  window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
});
const rootInput = document.getElementById("root");
const btnLoad = document.getElementById("btn-load");
function loadTyped() { return withBusy("scanning", btnLoad, () => load(rootInput.value.trim())); }
btnLoad.onclick = loadTyped;
rootInput.addEventListener("keydown", ev => { if (ev.key === "Enter") { ev.preventDefault(); loadTyped(); } });
const auto = document.getElementById("auto");
auto.checked = localStorage.getItem("hv-auto") === "1";
let timer = null;
// wrapped, not passed by reference: setInterval hands its callback a tick
// argument, which load() would read as a root override
const every = document.getElementById("every");
every.value = localStorage.getItem("hv-every") || "10";
function syncAuto() {
  if (timer) clearInterval(timer);
  const secs = Math.max(1, Number(every.value) || 10);
  // rebuilt on every change, so a new interval takes effect at once rather
  // than after the next reload
  if (auto.checked) timer = setInterval(() => load(), secs * 1000);
  localStorage.setItem("hv-auto", auto.checked ? "1" : "0");
  localStorage.setItem("hv-every", String(secs));
}
auto.onchange = syncAuto;
every.onchange = syncAuto;

// --- folder browser ---------------------------------------------------------
// The server lists directories because the browser cannot tell the page a real
// path: showDirectoryPicker() yields a handle with no path and webkitdirectory
// yields relative names, so neither can fill the root box.
const modal = document.getElementById("modal");
let browsePath = "";
function closeModal() { modal.classList.remove("on"); }
document.getElementById("m-close").onclick = closeModal;
modal.addEventListener("click", ev => { if (ev.target === modal) closeModal(); });
window.addEventListener("keydown", ev => { if (ev.key === "Escape" && modal.classList.contains("on")) closeModal(); });

async function openBrowse(path) {
  const body = document.getElementById("m-body");
  const note = document.getElementById("m-note");
  body.textContent = ""; note.textContent = "";
  let data;
  try {
    const r = await fetch("browse" + (path !== undefined && path !== null ? "?path=" + encodeURIComponent(path) : ""));
    data = await r.json();
    if (!r.ok || data.error) { note.textContent = data.error || ("server returned " + r.status); return; }
  } catch (e) { note.textContent = "could not reach the server: " + e; return; }

  browsePath = data.path || "";
  document.getElementById("m-cur").textContent = data.drives ? "This computer" : browsePath;
  document.getElementById("m-pick").disabled = !!data.drives;
  document.getElementById("m-up").disabled = data.parent === null;
  document.getElementById("m-up").onclick = () => { if (data.parent !== null) openBrowse(data.parent); };
  if (!data.drives) note.textContent = data.harness ? "this folder is a harness" : "no .claude/ here - open a child folder";

  const recents = recentRoots();
  if (recents.length) {
    const h = document.createElement("h4"); h.textContent = "Recent folders"; body.append(h);
    for (const p of recents) {
      const row = document.createElement("div"); row.className = "recent";
      const a = document.createElement("span"); a.className = "p"; a.textContent = p;
      a.onclick = () => { closeModal(); rootInput.value = p; loadTyped(); };
      const x = document.createElement("button");
      x.className = "x"; x.textContent = "x"; x.title = "Forget this folder";
      x.onclick = ev => { ev.stopPropagation(); forgetRoot(p); openBrowse(browsePath); };
      row.append(a, x); body.append(row);
    }
    const clr = document.createElement("div"); clr.className = "recent";
    const cb = document.createElement("button");
    cb.textContent = "Clear history"; cb.style.padding = "2px 8px";
    cb.onclick = () => { localStorage.removeItem("hv-recent"); buildRoots(); openBrowse(browsePath); };
    clr.append(cb); body.append(clr);
    const h2 = document.createElement("h4"); h2.textContent = "Folders"; body.append(h2);
  }

  if (data.parent !== null && !data.drives) {
    const up = document.createElement("div"); up.className = "dirrow up";
    up.textContent = ".. parent folder";
    up.onclick = () => openBrowse(data.parent);
    body.append(up);
  }
  for (const e of data.entries) {
    const row = document.createElement("div"); row.className = "dirrow";
    const nm = document.createElement("span"); nm.className = "nm"; nm.textContent = e.name;
    row.append(nm);
    if (e.harness) { const t = document.createElement("span"); t.className = "tag"; t.textContent = "harness"; row.append(t); }
    row.onclick = () => openBrowse(e.path);
    body.append(row);
  }
  if (!data.entries.length) {
    const em = document.createElement("div"); em.className = "dirrow up";
    em.textContent = "(no subfolders)"; body.append(em);
  }
  modal.classList.add("on");
}
document.getElementById("m-pick").onclick = () => {
  if (!browsePath) return;
  closeModal(); rootInput.value = browsePath; loadTyped();
};
const btnBrowse = document.getElementById("btn-browse");
btnBrowse.onclick = () => withBusy("listing folders", btnBrowse, () => openBrowse(currentRoot || undefined));
function hint() {
  const el = document.getElementById("hint");
  if (view === "plan") { el.textContent = "docs/tasks/master-plan.md"; return; }
  // "click a node" is bad advice when there are no nodes to click
  if (!graph.nodes.length) { el.textContent = "no folder loaded - use Browse to choose one"; return; }
  el.textContent = (view === "graph" && lineStyle === "ortho")
    ? "orthogonal routing applies to Flow view; drawn straight here"
    : "click a node to trace its connections";
}
function sync() {
  const plan = view === "plan", asses = view === "assess";
  document.getElementById("btn-flow").classList.toggle("active", view === "flow");
  document.getElementById("btn-graph").classList.toggle("active", view === "graph");
  document.getElementById("btn-plan").classList.toggle("active", plan);
  document.getElementById("btn-assess").classList.toggle("active", asses);
  document.getElementById("plan").classList.toggle("open", plan);
  document.getElementById("assess").classList.toggle("open", asses);
  cv.style.display = (plan || asses) ? "none" : "block";
  hint();
  if (plan) { stopAnim(); if (planText !== null) renderPlan(planText); return; }
  if (asses) { stopAnim(); loadAssessment(); return; }
  layout(); fitView(graph.nodes.filter(visible)); draw();
}
// Size the canvas and paint the chrome BEFORE the first fetch. When load()
// used to run first, any failure skipped fit() and left a 300x150 canvas
// stretched over the window - a blank page with no explanation.
iconize("btn-flow", "flow");
iconize("btn-graph", "graph");
iconize("btn-plan", "plan");
iconize("btn-assess", "assess");
iconize("btn-reload", "reload");
iconize("btn-browse", "browse");
iconize("btn-load", "load");
buildRoots();
applySide();
fit();
syncAuto();
showVersion();
// Fall back to the server's own root if the remembered one no longer resolves.
load().then(ok => { if (!ok && currentRoot) { currentRoot = ""; localStorage.removeItem("hv-root"); return load(); } })
      .then(() => sync());
