// The roster editor: an agent's model, effort, tools and description, and CRUD
// on the model/tool reference those pickers are built from.
//
// NOTHING HERE TOUCHES THE DOM AT LOAD TIME, exactly as in ui-steps.js and for
// the same reason: node can require this file, so the logic worth testing is
// testable, while ui.js reaches for `document` on its first line and cannot be
// required at all. The one function that touches the document is the guarded
// `installAgentEditor()` at the bottom, which no-ops when there is no document.
// serve.rs splices this file into the page directly after ui-steps.js.
//
// THIS FILE ADDS NOTHING TO ui.js AND NEEDS NO HOOK IN IT. The detail panel is
// ui.js's DOM. This attaches to it by observing repaints of `#detail` and
// appending one bar; everything else happens inside `ui.modal`, which ui.js
// publishes on `window.ui` precisely so panels built elsewhere can use it. Two
// consequences worth stating, because they are the whole reason it is built this
// way: ui.js and this file can be edited at the same time without conflict, and
// if ui.js ever changes the panel's shape or stops publishing `ui`,
// `agentPanelState()`/`agUi()` return null, the bar simply does not appear, and
// the viewer degrades to the read-only panel that shipped before rather than
// throwing inside someone else's click handler.
//
// NO SECOND DIALOG SYSTEM. Everything visible here is `ui.modal`, `ui.toast`,
// `ui.icon`, `setBtn` and `setIconBtn` - one visual language, one focus trap,
// one accessibility implementation. The dialog contract has `body: Node`, so the
// parts a spec-driven form cannot express - a tool list where every row carries
// a description, a category and a permission flag - are built as a Node and
// handed over, and their values are read back out of that Node (which this file
// still holds) when the dialog resolves. `fields:` is used wherever the form
// really is just labelled text inputs, which is all of the reference CRUD.
//
// WHY A DIALOG AND NOT THE PANEL. The panel is 320px wide by default. The tools
// picker is the part the user actually asked for - every tool with its one-line
// description, its category and whether it prompts for permission - and that
// does not fit in a sidebar without hiding the descriptions it exists to show.
//
// WHAT IS EDITABLE, AND WHAT IS NOT. Four frontmatter keys: model, effort, tools
// and description. Not `name` - that is the seat's identity and the graph keys
// on it. The server enforces the same list; this is the second copy of a rule,
// not the only one.
//
// THE `verified` MARK IS NOT DECORATION. The reference ships with a `verified`
// flag on every model and every tool, and one Z.AI model is `verified: false`
// because it could not be confirmed against a first-party source. That honesty
// is the reason the file is worth trusting, so an unverified entry is SHOWN and
// marked, never filtered out and never quietly promoted. An entry the user added
// is marked `custom` for the same reason: the two must never look alike.
//
// A USER'S REFERENCE EDITS NEVER TOUCH THE SHIPPED ASSET. They go to
// `<root>/.claude/state/references.json` and are merged over the seed by the
// server on every read, so upgrading the skill cannot clobber them. See the
// header of src/agentedit.rs.

// ---------------------------------------------------------------------------
// 1. pure logic - no DOM, no fetch, testable under node
// ---------------------------------------------------------------------------

// Tools arrive from the graph as the raw frontmatter string ("Read, Grep, Bash")
// or, if a repo wrote a block list, as an array. Both become an array in the
// order the file had them, because that order is a choice someone made and the
// editor's job is to preserve it, not to tidy it.
function agentToolList(value) {
  if (Array.isArray(value)) return value.map(x => String(x).trim()).filter(Boolean);
  if (typeof value !== "string") return [];
  return value.replace(/^\[|\]$/g, "").split(",").map(x => x.trim()).filter(Boolean);
}

function agentVendorList(reference) {
  const v = (reference && reference.vendors) || {};
  return Object.keys(v).sort().map(id => ({
    id,
    label: v[id].label || id,
    custom: v[id].custom === true,
    edited: v[id].edited === true,
  }));
}

// Which vendor a seat is already on. Inferred from the model it names rather
// than stored in the file: writing a `vendor:` key would put a field in an agent
// file that no agent runner reads, and an unread field in a prompt file is
// litter. If nothing matches - a hand-typed model, or one the reference has not
// heard of yet - fall back to the caller's remembered choice, then to Claude
// Code, then to whatever vendor exists.
function agentGuessVendor(reference, model, remembered) {
  const vendors = (reference && reference.vendors) || {};
  if (model) {
    for (const id of Object.keys(vendors).sort()) {
      const list = vendors[id].models || [];
      if (list.some(m => m.id === model)) return id;
    }
  }
  if (remembered && vendors[remembered]) return remembered;
  if (vendors["claude-code"]) return "claude-code";
  const first = Object.keys(vendors).sort()[0];
  return first || "";
}

// The editor's whole state, derived once from the node and the reference. Kept
// as data rather than read back out of the DOM so that "what will be saved" is
// answerable without a browser - which is what makes it testable.
//
// `remembered` is a HINT - last time this seat was edited the user was looking
// at this vendor - and it loses to what the file's model actually says.
// `forced` is a CHOICE - the user just moved the vendor picker - and it wins
// outright. Passing a choice as a hint is precisely the bug this signature
// exists to prevent, and it is not a hypothetical: the picker moved, the
// catalogue underneath it did not, and the dialog showed one vendor's name over
// another vendor's tools.
function agentEditorModel(node, reference, remembered, forced) {
  const meta = (node && node.meta) || {};
  const model = meta.model ? String(meta.model) : "";
  const effort = meta.effort ? String(meta.effort) : "";
  const chosen = agentToolList(meta.tools);
  const vendors = (reference && reference.vendors) || {};
  const vendorId = (forced && vendors[forced]) ? forced : agentGuessVendor(reference, model, remembered);
  const vendor = vendors[vendorId] || {};
  const catalogue = vendor.tools || [];
  const known = catalogue.map(t => t.name);
  return {
    name: node && node.id ? String(node.id).split(":").slice(1).join(":") : "",
    file: (node && node.file) || "",
    vendor: vendorId,
    vendors: agentVendorList(reference),
    models: (vendor.models || []).map(m => Object.assign({}, m, { selected: m.id === model })),
    efforts: vendor.efforts || [],
    hasEfforts: (vendor.efforts || []).length > 0,
    // The catalogue, in the researched order, with what this seat already holds
    // ticked. Nothing is pre-ticked that the file did not name.
    tools: catalogue.map(t => Object.assign({}, t, { checked: chosen.indexOf(t.name) !== -1 })),
    // A tool the file names that this vendor's list does not carry. It is shown
    // and kept ticked: a reference that has gone stale must not be able to
    // silently strip a grant out of someone's agent file.
    strangers: chosen.filter(n => known.indexOf(n) === -1),
    chosen: chosen,
    model: model,
    effort: effort,
    description: meta.description ? String(meta.description) : "",
  };
}

// The new tools list, in the order that keeps a human's file recognisable:
// everything still ticked stays exactly where it was, and anything newly ticked
// is appended in catalogue order. Nothing is ever added that was not picked.
function agentToolSelection(current, picked, catalogueOrder) {
  const want = {};
  picked.forEach(n => { want[n] = true; });
  const out = current.filter(n => want[n] === true);
  catalogueOrder.forEach(n => {
    if (want[n] === true && out.indexOf(n) === -1) out.push(n);
  });
  // A picked name in neither list (a stranger the user re-ticked) still belongs.
  picked.forEach(n => { if (out.indexOf(n) === -1) out.push(n); });
  return out;
}

// Only what actually changed. The server refuses to write an unchanged key
// anyway, but sending one would still be a lie about what the user did, and the
// toast that comes back names the keys it wrote.
function agentChangedKeys(before, after) {
  const out = {};
  ["model", "effort", "description"].forEach(k => {
    if (typeof after[k] === "string" && after[k] !== before[k]) out[k] = after[k];
  });
  if (Array.isArray(after.tools)) {
    const a = (before.tools || []).join("\u0000");
    if (a !== after.tools.join("\u0000")) out.tools = after.tools;
  }
  return out;
}

// The words next to an entry that say where it came from. An unverified entry
// says so; an entry the user added says so; a seed entry the user corrected says
// so. Silence means "researched and confirmed", and it has to stay meaning that.
function agentProvenance(entry) {
  const out = [];
  if (entry.custom === true) out.push("added here");
  else if (entry.edited === true) out.push("edited here");
  if (entry.verified === false) out.push("unverified");
  return out;
}

// ---------------------------------------------------------------------------
// 2. the browser layer
// ---------------------------------------------------------------------------
// Everything below is DOM. It is reached only from `installAgentEditor()` at
// the very bottom, which no-ops when there is no document.

const AG_PREFS = "harness-view:agent-vendor";

function agRemembered(name) {
  try { return JSON.parse(localStorage.getItem(AG_PREFS) || "{}")[name] || ""; }
  catch (e) { return ""; }
}

function agRemember(name, vendor) {
  try {
    const all = JSON.parse(localStorage.getItem(AG_PREFS) || "{}");
    all[name] = vendor;
    localStorage.setItem(AG_PREFS, JSON.stringify(all));
  } catch (e) { /* private mode: the default is still right, just not sticky */ }
}

// ui.js publishes its dialog and toast layer on `window.ui`. Reaching for it
// through a guard rather than at load time is what lets this file be spliced in
// BEFORE ui.js has run, and what makes a rename degrade to "the editor is not
// offered" instead of a thrown error inside somebody else's click handler.
let agWarned = false;
function agUi() {
  const u = typeof window !== "undefined" ? window.ui : null;
  if (u && typeof u.modal === "function" && typeof u.toast === "function") return u;
  if (!agWarned) {
    agWarned = true;
    console.warn("harness-view: window.ui is not there - the roster editor is off");
  }
  return null;
}

// THE HANDSHAKE WITH ui.js, and the only thing this file assumes about its
// internals: three top-level bindings - `graph`, `sel`, `currentRoot`. They are
// `let` at the top of a classic script, so they live in the shared global
// lexical scope and are readable from here once ui.js has run. If any is
// renamed this returns null and the editor stays out of the way.
function agentPanelState() {
  try {
    /* eslint-disable no-undef */
    const g = graph, id = sel, root = currentRoot;
    /* eslint-enable no-undef */
    if (!g || !Array.isArray(g.nodes) || !id) return null;
    const node = g.nodes.find(n => n.id === id);
    if (!node || node.type !== "agent") return null;
    return { node: node, root: root || "" };
  } catch (e) {
    if (!agWarned) {
      agWarned = true;
      console.warn("harness-view: the agent editor cannot read the panel state" +
                   " (ui.js renamed graph/sel/currentRoot?) - editing is off", e);
    }
    return null;
  }
}

// Rescan and re-select, after a write changed what the graph says. Guarded in
// both directions: if ui.js does not expose `load`/`select`/`draw` under those
// names any more, the write still happened and the page is simply stale until
// the next scan - a worse page, not a broken one.
async function agRefreshNode(id) {
  try {
    /* eslint-disable no-undef */
    if (typeof load !== "function") return;
    await load();
    const n = graph.nodes.find(x => x.id === id);
    if (n && typeof select === "function") { select(n, true); if (typeof draw === "function") draw(); }
    /* eslint-enable no-undef */
  } catch (e) { /* a stale panel is not worth throwing over */ }
}

// --- small DOM helpers ------------------------------------------------------

function agEl(tag, css, text) {
  const el = document.createElement(tag);
  if (css) for (const k in css) el.style[k] = css[k];
  if (text !== undefined && text !== null) el.textContent = String(text);
  return el;
}

// A button in ui.js's own visual language: its `setBtn`/`setIconBtn` set the
// icon, the label and - for an icon-only control - the accessible name. Every
// button this file creates goes through one of these two, which is the point.
function agBtn(iconName, label, onclick) {
  const b = document.createElement("button");
  b.type = "button";
  if (typeof setBtn === "function") setBtn(b, iconName, label);
  else b.textContent = label;
  b.onclick = onclick;
  return b;
}

function agIconBtn(iconName, label, onclick) {
  const b = document.createElement("button");
  b.type = "button";
  if (typeof setIconBtn === "function") setIconBtn(b, iconName, label);
  else { b.textContent = label; b.title = label; }
  b.onclick = onclick;
  return b;
}

// A dialog is 560px wide, so a tool row is two lines: identity and flags on the
// first, the description on the second. Chips carry the category and the
// permission flag, and the permission flag is warm-coloured when the tool
// prompts - that is the one property of a grant a reader scans for.
const AG_CHIP = {
  fontSize: "10px", padding: "1px 6px", borderRadius: "999px",
  border: "1px solid var(--line)", color: "var(--dim)", whiteSpace: "nowrap",
};
const AG_CHIP_WARM = { borderColor: "#f59e0b", color: "#b45309" };

function agChip(text, warm) {
  return agEl("span", warm ? Object.assign({}, AG_CHIP, AG_CHIP_WARM) : AG_CHIP, text);
}

// The provenance marks, as chips. `unverified` is warm because it is the one
// the reader must not miss.
function agMarks(host, entry) {
  agentProvenance(entry).forEach(w => host.append(agChip(w, w === "unverified")));
}

// --- server -----------------------------------------------------------------

function agRootQuery(root) { return root ? "?root=" + encodeURIComponent(root) : ""; }

async function agGetReference(root) {
  const r = await fetch("reference" + agRootQuery(root));
  const t = await r.text();
  if (!r.ok) throw new Error(t || ("reference: HTTP " + r.status));
  return JSON.parse(t);
}

async function agPost(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const t = await r.text();
  if (!r.ok) throw new Error(t || (path + ": HTTP " + r.status));
  return t;
}

function agFail(e) {
  const u = agUi();
  if (u) u.toast({ kind: "error", title: "That did not happen", body: String((e && e.message) || e) });
  else console.error(e);
}

// --- driving ui.modal from inside its own body ------------------------------
//
// `ui.modal` resolves on a FOOTER action or on dismissal. A list where each row
// carries its own Edit and Delete is not expressible as footer actions, so a row
// button resolves the dialog itself through the `close` handle ui.js hands to
// `onReady`. The result it passes has the same shape a footer action produces -
// an `action` plus what the row was about - so every caller reads one answer.
async function agModal(spec, ctx) {
  const u = agUi();
  if (!u) return null;
  ctx.close = null;
  const withReady = Object.assign({}, spec, {
    onReady: api => { ctx.close = api.close; },
  });
  const answer = await u.modal(withReady);
  ctx.close = null;
  return answer;
}

function agRowIntent(ctx, action, payload) {
  const intent = Object.assign({ action: action }, payload);
  // No close handle means the dialog is not open (or ui.js is older than this
  // file). Saying so beats a click that silently does nothing.
  if (!ctx.close) { console.error("agRowIntent with no open dialog", action); return; }
  ctx.close({ action: action, intent: intent });
}

// --- the agent editor -------------------------------------------------------

// Builds the dialog body and returns it together with a `read()` that answers
// "what would be saved". The Node stays in this closure, so the values come back
// out of the controls this file created - no dependency on ui.js's `fields`,
// which are text inputs and cannot express a tool catalogue.
function agAgentBody(node, reference, ctx) {
  const name = String(node.id).split(":").slice(1).join(":");
  let state = agentEditorModel(node, reference, agRemembered(name));
  const host = agEl("div");
  let readTools = () => state.chosen;
  let readModel = () => state.model;
  let readEffort = () => state.effort;
  let dta = null;

  const paint = () => {
    const carried = dta ? dta.value : state.description;
    host.textContent = "";

    const grid = agEl("div", { display: "grid", gridTemplateColumns: "82px 1fr", gap: "8px 10px", alignItems: "start" });
    const lab = t => agEl("label", { color: "var(--dim)", paddingTop: "5px", fontSize: "12px" }, t);
    const field = () => agEl("select", { font: "inherit", fontSize: "12px", width: "100%", padding: "5px 6px", borderRadius: "6px", border: "1px solid var(--line)", background: "var(--panel)", color: "inherit" });

    // vendor - the repo's own port.py targets Cursor and Codex too, so the
    // roster is not assumed to be Claude's.
    grid.append(lab("vendor"));
    const vsel = field();
    state.vendors.forEach(v => {
      const o = agEl("option", null, v.label + (v.custom ? "  (added here)" : ""));
      o.value = v.id;
      if (v.id === state.vendor) o.selected = true;
      vsel.append(o);
    });
    // A vendor switch changes what is ON OFFER; it does not change what the file
    // says, so the editor is rebuilt from the file's values under the new
    // catalogue rather than from whatever is half-picked on screen.
    vsel.onchange = () => {
      agRemember(name, vsel.value);
      state = agentEditorModel(
        { id: node.id, file: node.file, meta: { model: state.model, effort: state.effort, tools: state.chosen, description: carried } },
        reference, "", vsel.value);
      paint();
    };
    grid.append(vsel);

    // model
    grid.append(lab("model"));
    const mwrap = agEl("div");
    const msel = field();
    const keep = agEl("option", null,
      state.model ? "keep " + state.model + " (not in this vendor's list)" : "(not set)");
    keep.value = "";
    msel.append(keep);
    let matched = false;
    state.models.forEach(m => {
      const marks = agentProvenance(m);
      const o = agEl("option", null,
        m.label + " (" + m.id + ")" + (marks.length ? "  [" + marks.join(", ") + "]" : ""));
      o.value = m.id;
      if (m.selected) { o.selected = true; matched = true; }
      msel.append(o);
    });
    if (!matched) keep.selected = true;
    const mnote = agEl("div", { fontSize: "11px", color: "var(--dim)", marginTop: "4px", lineHeight: "1.45", display: "flex", gap: "5px", flexWrap: "wrap", alignItems: "center" });
    const showNote = () => {
      mnote.textContent = "";
      const m = state.models.find(x => x.id === msel.value);
      if (!m) {
        mnote.append(document.createTextNode(state.model ? "left exactly as the file has it" : "no model set"));
        return;
      }
      if (m.note) mnote.append(document.createTextNode(m.note));
      agMarks(mnote, m);
    };
    msel.onchange = showNote;
    showNote();
    mwrap.append(msel, mnote);
    grid.append(mwrap);
    readModel = () => msel.value || state.model;

    // effort - offered only where the vendor lists any
    grid.append(lab("effort"));
    if (state.hasEfforts) {
      const esel = field();
      const none = agEl("option", null, state.effort ? "keep " + state.effort : "(not set)");
      none.value = "";
      esel.append(none);
      let hit = false;
      state.efforts.forEach(e => {
        const o = agEl("option", null, e);
        o.value = e;
        if (e === state.effort) { o.selected = true; hit = true; }
        esel.append(o);
      });
      if (!hit) none.selected = true;
      grid.append(esel);
      readEffort = () => esel.value || state.effort;
    } else {
      grid.append(agEl("div", { color: "var(--dim)", fontSize: "12px", paddingTop: "6px" },
        "this vendor lists no effort levels, so the field is not offered"));
      readEffort = () => state.effort;
    }

    // description
    grid.append(lab("description"));
    dta = agEl("textarea", {
      font: "inherit", fontSize: "12px", width: "100%", minHeight: "76px", padding: "6px 8px",
      borderRadius: "6px", border: "1px solid var(--line)", background: "var(--panel)",
      color: "inherit", lineHeight: "1.45", resize: "vertical", boxSizing: "border-box",
    });
    dta.value = carried;
    dta.spellcheck = false;
    grid.append(dta);
    host.append(grid);

    // tools
    const th = agEl("div", { display: "flex", alignItems: "center", gap: "8px", margin: "14px 0 6px" });
    th.append(agEl("strong", { fontSize: "12px" }, "tools"));
    const count = agEl("span", { color: "var(--dim)", fontSize: "11px" }, "");
    th.append(count);
    host.append(th);

    const boxes = [];
    const list = agEl("div", { border: "1px solid var(--line)", borderRadius: "8px", maxHeight: "230px", overflowY: "auto" });
    const addRow = (t, stranger) => {
      const row = agEl("label", {
        display: "grid", gridTemplateColumns: "20px 1fr", gap: "8px", alignItems: "start",
        padding: "7px 9px", cursor: "pointer",
        borderTop: boxes.length ? "1px solid var(--line)" : "none",
      });
      const cb = agEl("input");
      cb.type = "checkbox";
      cb.checked = t.checked === true;
      cb.value = t.name;
      cb.style.marginTop = "2px";
      boxes.push(cb);
      cb.onchange = () => { count.textContent = boxes.filter(b => b.checked).length + " of " + boxes.length + " selected"; };
      row.append(cb);
      const right = agEl("div");
      const top2 = agEl("div", { display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" });
      top2.append(agEl("code", { fontSize: "12px", wordBreak: "break-all" }, t.name));
      if (t.category) top2.append(agChip(t.category));
      if (t.permission) {
        const asks = String(t.permission) === "yes";
        top2.append(agChip(asks ? "asks permission" : "no prompt", asks));
      }
      if (stranger) top2.append(agChip("unknown to the reference", true));
      agMarks(top2, t);
      right.append(top2);
      right.append(agEl("div", { fontSize: "11px", color: "var(--dim)", lineHeight: "1.45", marginTop: "2px" },
        t.desc || (stranger ? "this seat names it, but this vendor's list does not carry it - it is kept ticked so the edit cannot silently drop a grant" : "")));
      row.append(right);
      list.append(row);
    };
    state.strangers.forEach(n => addRow({ name: n, checked: true }, true));
    state.tools.forEach(t => addRow(t, false));
    if (!boxes.length) {
      list.append(agEl("div", { padding: "10px", color: "var(--dim)", fontSize: "12px" },
        "this vendor lists no tools yet - add them under Reference"));
    }
    count.textContent = boxes.filter(b => b.checked).length + " of " + boxes.length + " selected";
    host.append(list);
    host.append(agEl("div", { fontSize: "11px", color: "var(--dim)", marginTop: "7px", lineHeight: "1.5" },
      "Saving writes only the fields you changed. Everything below the frontmatter - the agent's own instructions - is copied through byte for byte."));

    readTools = () => agentToolSelection(
      state.chosen,
      boxes.filter(b => b.checked).map(b => b.value),
      state.tools.map(t => t.name));
  };
  paint();

  const before = { model: state.model, effort: state.effort, description: state.description, tools: state.chosen };
  return {
    node: host,
    name: name,
    vendor: () => state.vendor,
    changes: () => agentChangedKeys(before, {
      model: readModel(), effort: readEffort(),
      description: dta ? dta.value : state.description, tools: readTools(),
    }),
  };
}

async function agOpenAgent(node, root) {
  const u = agUi();
  if (!u) return;
  let reference;
  try { reference = await agGetReference(root); }
  catch (e) { agFail(e); return; }

  const ctx = {};
  const built = agAgentBody(node, reference, ctx);
  const answer = await agModal({
    title: "Edit " + built.name,
    icon: "owner",
    body: [
      node.file ? node.file : "This seat has no file on disk.",
      built.node,
    ],
    actions: [
      { id: "reference", label: "Reference", icon: "doc" },
      { id: "cancel", label: "Cancel", icon: "x", kind: "cancel" },
      { id: "save", label: "Save", icon: "save", kind: "primary", default: true },
    ],
  }, ctx);

  if (!answer) return;
  if (answer.action === "reference") {
    await agOpenReference(root, built.vendor());
    await agOpenAgent(node, root); // come back with the corrected reference
    return;
  }
  const changes = built.changes();
  const keys = Object.keys(changes);
  if (!keys.length) {
    u.toast({ kind: "info", title: "Nothing changed", body: "No frontmatter key was different, so nothing was written." });
    return;
  }
  try {
    const msg = await agPost("agent", Object.assign({ root: root, name: built.name }, changes));
    u.toast({ kind: "success", title: "Saved", body: msg });
    await agRefreshNode(node.id);
  } catch (e) { agFail(e); }
}

// --- the reference manager --------------------------------------------------

const AG_KINDS = {
  model: { bucket: "models", idField: "id", fields: ["label", "note"], icon: "model" },
  tool: { bucket: "tools", idField: "name", fields: ["desc", "category", "permission"], icon: "tools" },
};

function agReferenceBody(reference, vendorId, ctx) {
  const host = agEl("div");
  const vendor = ((reference && reference.vendors) || {})[vendorId] ||
    { models: [], tools: [], efforts: [] };

  const top = agEl("div", { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap", marginBottom: "4px" });
  top.append(agEl("label", { color: "var(--dim)", fontSize: "12px" }, "vendor"));
  const vsel = agEl("select", { font: "inherit", fontSize: "12px", padding: "5px 6px", borderRadius: "6px", border: "1px solid var(--line)", background: "var(--panel)", color: "inherit", flex: "1 1 auto" });
  agentVendorList(reference).forEach(v => {
    const o = agEl("option", null, v.label + " (" + v.id + ")" +
      (v.custom ? "  [added here]" : v.edited ? "  [edited here]" : ""));
    o.value = v.id;
    if (v.id === vendorId) o.selected = true;
    vsel.append(o);
  });
  vsel.onchange = () => agRowIntent(ctx, "switch", { vendor: vsel.value });
  top.append(vsel);
  host.append(top);

  if (vendor.source) {
    host.append(agEl("div", { fontSize: "11px", color: "var(--dim)", lineHeight: "1.45", margin: "4px 0 2px", wordBreak: "break-all" }, vendor.source));
  }
  const eff = agEl("div", { fontSize: "11px", color: "var(--dim)", margin: "2px 0 6px" },
    "efforts: " + ((vendor.efforts || []).join(", ") || "none - the effort field is not offered for this vendor"));
  host.append(eff);

  const section = (kind, entries) => {
    const spec = AG_KINDS[kind];
    const h = agEl("div", { display: "flex", alignItems: "center", gap: "8px", margin: "12px 0 5px" });
    h.append(agEl("strong", { fontSize: "12px" }, spec.bucket + " (" + entries.length + ")"));
    h.append(agEl("span", { flex: "1 1 auto" }));
    h.append(agBtn("edit", "Add " + kind, () => agRowIntent(ctx, "add", { kind: kind })));
    host.append(h);
    const list = agEl("div", { border: "1px solid var(--line)", borderRadius: "8px", maxHeight: "210px", overflowY: "auto" });
    entries.forEach((e, i) => {
      const row = agEl("div", {
        display: "grid", gridTemplateColumns: "1fr auto", gap: "8px", alignItems: "start",
        padding: "7px 9px", borderTop: i ? "1px solid var(--line)" : "none",
      });
      const left = agEl("div");
      const line = agEl("div", { display: "flex", gap: "6px", alignItems: "center", flexWrap: "wrap" });
      line.append(agEl("code", { fontSize: "12px", wordBreak: "break-all" }, e[spec.idField]));
      if (kind === "tool" && e.category) line.append(agChip(e.category));
      if (kind === "tool" && e.permission) line.append(agChip(String(e.permission) === "yes" ? "asks permission" : "no prompt", String(e.permission) === "yes"));
      agMarks(line, e);
      left.append(line);
      const words = (kind === "model" ? [e.label, e.note] : [e.desc]).filter(Boolean).join("  -  ");
      if (words) left.append(agEl("div", { fontSize: "11px", color: "var(--dim)", lineHeight: "1.45", marginTop: "2px" }, words));
      row.append(left);
      const acts = agEl("div", { display: "flex", gap: "4px" });
      acts.append(agIconBtn("edit", "Edit " + kind + " " + e[spec.idField],
        () => agRowIntent(ctx, "edit", { kind: kind, entry: e })));
      acts.append(agIconBtn("trash", "Delete " + kind + " " + e[spec.idField],
        () => agRowIntent(ctx, "delete", { kind: kind, entry: e })));
      row.append(acts);
      list.append(row);
    });
    if (!entries.length) {
      list.append(agEl("div", { padding: "10px", color: "var(--dim)", fontSize: "12px" }, "none yet"));
    }
    host.append(list);
  };
  section("model", vendor.models || []);
  section("tool", vendor.tools || []);
  return host;
}

// One add / edit form, expressed the way ui.js's dialog wants it: labelled text
// inputs and footer actions, nothing custom.
async function agEntryForm(u, root, kind, vendorId, entry) {
  const spec = AG_KINDS[kind];
  const fields = [];
  if (!entry) {
    fields.push({
      name: spec.idField, label: spec.idField,
      hint: "letters, digits, dash, underscore, dot, colon",
      value: "",
    });
  }
  spec.fields.forEach(f => fields.push({
    name: f, label: f,
    value: entry ? (entry[f] === undefined ? "" : String(entry[f])) : "",
    hint: f === "permission" ? "yes if the tool prompts before it runs, no if it does not"
      : f === "category" ? "how the tool is grouped - read, edit, execute, search, agent, ..."
      : undefined,
  }));
  const note = entry
    ? (entry.custom === true
      ? "This entry was added in this repository, so everything about it is yours."
      : "This is a shipped entry. Your text replaces the shipped text for this repository only, " +
        "and its `verified` mark stays exactly as shipped - that flag is the reference's word, not an edit.")
    : "A new entry is recorded as `custom` and starts out unverified. It is stored in this " +
      "repository at `.claude/state/references.json`, never in the shipped reference.";
  const answer = await u.modal({
    title: (entry ? "Edit " : "Add a ") + kind + " in " + vendorId,
    icon: spec.icon,
    body: note,
    fields: fields,
    actions: [
      { id: "cancel", label: "Cancel", icon: "x", kind: "cancel" },
      { id: "save", label: "Save", icon: "save", kind: "primary", default: true },
    ],
  });
  if (!answer) return null;
  const e = {};
  e[spec.idField] = entry ? entry[spec.idField] : answer.values[spec.idField];
  spec.fields.forEach(f => { e[f] = answer.values[f]; });
  return agPost("reference", { root: root, op: "upsert", kind: kind, vendor: vendorId, entry: e });
}

async function agVendorForm(u, root, vendor, vendorId) {
  const answer = await u.modal({
    title: vendorId ? "Edit vendor " + vendorId : "Add a vendor",
    icon: "owner",
    body: "`efforts` is a comma-separated list. Leave it empty for a vendor with no effort levels " +
      "and the effort field will not be offered for its agents.",
    fields: [].concat(
      vendorId ? [] : [{ name: "id", label: "id", value: "", hint: "letters, digits, dash, underscore, dot, colon" }],
      [
        { name: "label", label: "label", value: (vendor && vendor.label) || "" },
        { name: "source", label: "source", value: (vendor && vendor.source) || "" },
        { name: "notes", label: "notes", value: (vendor && vendor.notes) || "" },
        { name: "efforts", label: "efforts", value: ((vendor && vendor.efforts) || []).join(", ") },
      ]),
    actions: [
      { id: "cancel", label: "Cancel", icon: "x", kind: "cancel" },
      { id: "save", label: "Save", icon: "save", kind: "primary", default: true },
    ],
  });
  if (!answer) return null;
  const id = vendorId || answer.values.id;
  await agPost("reference", {
    root: root, op: "upsert", kind: "vendor",
    entry: {
      id: id, label: answer.values.label, source: answer.values.source, notes: answer.values.notes,
      efforts: String(answer.values.efforts).split(",").map(x => x.trim()).filter(Boolean),
    },
  });
  return id;
}

async function agConfirmDelete(u, what, name) {
  const answer = await u.modal({
    title: "Remove " + what + " " + name + "?",
    icon: "trash",
    tone: "danger",
    body: "This changes this repository's copy of the reference only. The shipped list is not " +
      "touched, and a shipped entry can be brought back by adding it again.",
    actions: [
      { id: "cancel", label: "Keep it", icon: "x", kind: "cancel", default: true },
      { id: "delete", label: "Remove", icon: "trash", kind: "danger" },
    ],
  });
  return !!answer;
}

// The reference screen loops: every action repaints it from the SERVER, so what
// is on screen after an edit is what is on disk rather than a local guess.
async function agOpenReference(root, vendorId) {
  const u = agUi();
  if (!u) return;
  for (;;) {
    let reference;
    try { reference = await agGetReference(root); }
    catch (e) { agFail(e); return; }
    const vendors = agentVendorList(reference);
    if (!vendors.length) vendorId = "";
    else if (!vendors.some(v => v.id === vendorId)) vendorId = vendors[0].id;
    const vendor = ((reference && reference.vendors) || {})[vendorId];

    const ctx = {};
    const answer = await agModal({
      title: "Models and tools",
      icon: "tools",
      body: [
        "The shipped list is seed data. Your corrections are stored in this repository at " +
        "`.claude/state/references.json` and merged over it, so upgrading the skill will not lose " +
        "them and the shipped file is never written. An entry marked `unverified` could not be " +
        "confirmed against a first-party source - that mark belongs to the reference, and editing " +
        "an entry does not clear it.",
        agReferenceBody(reference, vendorId, ctx),
      ],
      actions: [
        { id: "edit-vendor", label: "Edit vendor", icon: "edit" },
        { id: "add-vendor", label: "Add vendor", icon: "owner" },
        { id: "delete-vendor", label: "Remove vendor", icon: "trash", kind: "danger" },
        { id: "done", label: "Done", icon: "check", kind: "primary", default: true },
      ],
    }, ctx);

    if (!answer || answer.action === "done") return;
    const it = answer.intent || {};
    try {
      if (answer.action === "switch") { vendorId = it.vendor; continue; }
      if (answer.action === "add") { await agEntryForm(u, root, it.kind, vendorId, null); continue; }
      if (answer.action === "edit") { await agEntryForm(u, root, it.kind, vendorId, it.entry); continue; }
      if (answer.action === "delete") {
        const key = AG_KINDS[it.kind].idField;
        if (await agConfirmDelete(u, it.kind, it.entry[key])) {
          const msg = await agPost("reference", { root: root, op: "delete", kind: it.kind, vendor: vendorId, id: it.entry[key] });
          u.toast({ kind: "success", title: "Reference updated", body: msg });
        }
        continue;
      }
      if (answer.action === "edit-vendor") { await agVendorForm(u, root, vendor, vendorId); continue; }
      if (answer.action === "add-vendor") {
        const id = await agVendorForm(u, root, null, "");
        if (id) vendorId = id;
        continue;
      }
      if (answer.action === "delete-vendor" && vendorId) {
        if (await agConfirmDelete(u, "vendor", vendorId)) {
          const msg = await agPost("reference", { root: root, op: "delete", kind: "vendor", vendor: vendorId });
          u.toast({ kind: "success", title: "Reference updated", body: msg });
          vendorId = "";
        }
        continue;
      }
    } catch (e) { agFail(e); }
  }
}

// --- attaching to the panel -------------------------------------------------

// One bar, appended to the panel's `.head` after ui.js has finished painting it.
// Tagged with the node id so a repaint that did not remove it does not get a
// second one, and so a repaint for a DIFFERENT node replaces it.
function agInject(detail) {
  const state = agentPanelState();
  const old = detail.querySelector("[data-agent-editor]");
  if (!state || !agUi()) { if (old) old.remove(); return; }
  if (old && old.getAttribute("data-agent-editor") === state.node.id) return;
  if (old) old.remove();
  const host = detail.querySelector(".head") || detail;
  const bar = agEl("div", { display: "flex", gap: "6px", flexWrap: "wrap", margin: "8px 0 2px" });
  bar.setAttribute("data-agent-editor", state.node.id);
  bar.append(agBtn("edit", "Edit roster", () => agOpenAgent(state.node, state.root)));
  bar.append(agBtn("tools", "Reference", () => agOpenReference(state.root, "")));
  if (state.node.disabled) {
    bar.append(agEl("span", { fontSize: "11px", color: "var(--dim)", alignSelf: "center" },
      "disabled - enable it before editing"));
  }
  host.append(bar);
}

function installAgentEditor() {
  if (typeof document === "undefined" || typeof MutationObserver === "undefined") return;
  const start = () => {
    const detail = document.getElementById("detail");
    if (!detail) return;
    // ui.js clears and rebuilds `#detail` on every selection, so there is no
    // event to listen for and no hook to ask for: watching the repaint is the
    // whole integration. The re-entrancy guard matters because appending the bar
    // is itself a mutation.
    let busy = false;
    const obs = new MutationObserver(() => {
      if (busy) return;
      busy = true;
      try { agInject(detail); } catch (e) { /* never break someone else's paint */ }
      busy = false;
    });
    obs.observe(detail, { childList: true, subtree: true });
    try { agInject(detail); } catch (e) { /* nothing selected yet */ }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
}

// Node requires this file; the browser does not have `module` and skips the
// line. There is no bundler here and there must not be one: the page is served
// as a single response with these sources spliced in.
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    agentToolList, agentVendorList, agentGuessVendor, agentEditorModel,
    agentToolSelection, agentChangedKeys, agentProvenance,
  };
}

installAgentEditor();
