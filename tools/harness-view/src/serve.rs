//! Local viewer: GET / (embedded page), GET /graph.json (fresh scan every
//! request, so the page is always current), GET /roots (which root the server
//! started on), GET /paths (the repo-relative names under .claude/ and docs/,
//! for the step editor's autocomplete), POST /toggle (shared contract with
//! /harness-toggle).
//!
//! The root is selectable per request: GET /graph.json?root=<path> and the
//! optional "root" field on POST /toggle both scan a caller-named directory,
//! falling back to the one named on the command line. A root that does not
//! exist, is not a directory, or carries no .claude/ is refused with 400 and a
//! JSON {"error": ...} the page displays - never an empty graph, because an
//! empty graph is indistinguishable from a harness with nothing in it.
//!
//! That refusal now covers the CLI fallback as well, because `serve` may be
//! started in a directory with no harness at all - a double-clicked binary
//! should open a usable window wherever it happens to sit, not refuse to run.
//! The refusal for that case carries {"noRoot": true}, which is how the page
//! tells "nothing is loaded yet" (choose a folder) apart from "the path you
//! gave me is wrong" (a red banner).
//!
//! The roster editor adds three more: GET /reference (the model and tool
//! reference the pickers are built from - the shipped seed with this
//! repository's own corrections merged over it), POST /agent (one agent's
//! model, effort, tools and description) and POST /reference (add, edit or
//! delete a model, a tool or a vendor in that reference). See agentedit.rs for
//! what the frontmatter writer guarantees and where a user's corrections are
//! stored.
//!
//! POST /toggle is guarded against cross-origin browser requests: the server
//! only mutates .claude/ for same-origin calls. Any present Origin header must
//! name this server's own host:port, any present Sec-Fetch-Site header must be
//! same-origin or none, and the Content-Type must be application/json;
//! anything else is refused with 403. HARD-protected items refuse with 403,
//! SOFT-protected items with 409 unless the body carries confirm_soft: true.

use crate::{agentedit, assess, scan, toggle};
use std::fs;
use std::path::{Path, PathBuf};
use tiny_http::{Header, Method, Request, Response, Server};

const PAGE_TEMPLATE: &str = include_str!("ui.html");
// The UI script is a real .js file so that GitHub detects JavaScript in this
// repository and CodeQL actually analyses the one page that renders a scanned
// repository's own file contents into the DOM. It was inline until then, which
// made the whole UI invisible to language detection. See the header of ui.js.
const UI_JS: &str = include_str!("ui.js");
// The Command Steps parser, split out of ui.js so it can be required by node and
// tested (tests/steps_test.rs). ui.js touches `document` on its first line and
// cannot be.
const UI_STEPS_JS: &str = include_str!("ui-steps.js");
// The agent-frontmatter editor and the model/tool reference manager. Same
// arrangement as ui-steps.js and for the same reason: it is pure until called,
// so node can require it, and it attaches to the detail panel by observation
// rather than by a hook inside ui.js. It rides the UI_STEPS placeholder rather
// than claiming a new one in ui.html, so the page template needs no edit.
const UI_AGENT_JS: &str = include_str!("ui-agent.js");
// Vendored, committed, and inlined rather than fetched: the page must work with
// no network. See vendor/README.md for versions, licences and provenance.
const MARKED_JS: &str = include_str!("../vendor/marked.min.js");
const PURIFY_JS: &str = include_str!("../vendor/purify.min.js");

/// The page with its vendored libraries and its own UI script spliced in. Built
/// once per process. Both splices are plain placeholder replacement rather than
/// a template engine, because the page must remain a file you can open, read and
/// diff - and because a second <script src=...> would break the one property the
/// viewer guarantees: it works with no network and serves from one response.
fn page() -> String {
    PAGE_TEMPLATE
        .replace("/*__VENDOR__*/", &format!("{MARKED_JS}\n{PURIFY_JS}\n"))
        .replace("/*__UI_STEPS__*/", &format!("{UI_STEPS_JS}\n{UI_AGENT_JS}"))
        .replace("/*__UI_JS__*/", UI_JS)
}

fn header(k: &str, v: &str) -> Header {
    Header::from_bytes(k.as_bytes(), v.as_bytes()).expect("static header")
}

fn header_value(request: &Request, name: &str) -> Option<String> {
    request
        .headers()
        .iter()
        .find(|h| h.field.as_str().as_str().eq_ignore_ascii_case(name))
        .map(|h| h.value.as_str().to_string())
}

/// Minimal percent-decoder for a query-string value ("%20" and "+").
fn percent_decode(s: &str) -> String {
    let b = s.as_bytes();
    let mut out: Vec<u8> = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        match b[i] {
            b'%' if i + 2 < b.len() => {
                let hex = std::str::from_utf8(&b[i + 1..i + 3]).unwrap_or("");
                match u8::from_str_radix(hex, 16) {
                    Ok(v) => {
                        out.push(v);
                        i += 3;
                    }
                    Err(_) => {
                        out.push(b[i]);
                        i += 1;
                    }
                }
            }
            b'+' => {
                out.push(b' ');
                i += 1;
            }
            c => {
                out.push(c);
                i += 1;
            }
        }
    }
    String::from_utf8_lossy(&out).into_owned()
}

/// First value of `key` in a raw query string, percent-decoded.
fn query_param(url: &str, key: &str) -> Option<String> {
    let q = url.split_once('?')?.1;
    for pair in q.split('&') {
        let (k, v) = pair.split_once('=').unwrap_or((pair, ""));
        if k == key {
            let v = percent_decode(v);
            return if v.is_empty() { None } else { Some(v) };
        }
    }
    None
}

/// Why a root could not be resolved. `no_root` separates the one refusal that
/// is not a failure - the server was started somewhere with no harness, which
/// is a legal way to start it since `serve` lost that precondition - from every
/// other bad path. The page paints its "choose a folder" state on the flag and
/// a red banner on everything else. It travels as a flag rather than as wording
/// because matching an error by its text breaks the moment someone improves the
/// sentence.
#[derive(Debug)]
struct RootError {
    msg: String,
    no_root: bool,
}

impl RootError {
    fn bad(msg: String) -> Self {
        Self { msg, no_root: false }
    }
    fn none_loaded() -> Self {
        Self {
            msg: "no folder loaded yet - choose one with Browse to start analysing".into(),
            no_root: true,
        }
    }
}

/// Resolve a caller-supplied root, or fall back to the one from the CLI.
///
/// Windows callers paste either separator, so both are accepted and normalized
/// before the path is touched. The `.claude/` requirement is what makes a wrong
/// path an explicit error instead of a convincing empty graph - and it applies
/// to the CLI fallback too, because `serve` now starts in directories that have
/// no harness and scanning one of those would produce exactly that empty graph.
fn resolve_root(requested: Option<&str>, default_root: &Path) -> Result<PathBuf, RootError> {
    let fallback = || {
        if default_root.join(".claude").is_dir() {
            Ok(default_root.to_path_buf())
        } else {
            Err(RootError::none_loaded())
        }
    };
    let Some(raw) = requested else {
        return fallback();
    };
    let trimmed = raw.trim().trim_matches('"');
    if trimmed.is_empty() {
        return fallback();
    }
    let normalized = if cfg!(windows) {
        trimmed.replace('/', "\\")
    } else {
        trimmed.replace('\\', "/")
    };
    // The folder picker always hands back an absolute path (browse() returns
    // canonicalized directories), so nothing the UI produces depends on where
    // the executable was started. A path TYPED into the box may still be
    // relative, and that one resolves against the server's working directory -
    // the only cwd-relative behaviour left, and the reason the picker is the
    // path the empty state points at.
    let p = PathBuf::from(&normalized);
    if !p.exists() {
        return Err(RootError::bad(format!("path does not exist: {normalized}")));
    }
    if !p.is_dir() {
        return Err(RootError::bad(format!("not a directory: {normalized}")));
    }
    if !p.join(".claude").is_dir() {
        return Err(RootError::bad(format!(
            "no .claude/ directory in {normalized} - point this at a repo that ran harness-bootstrap"
        )));
    }
    Ok(p.canonicalize().unwrap_or(p))
}

/// Windows canonicalize() returns an extended-length path (`\\?\C:\...`). That
/// prefix is correct but unusable: it is what the user sees in the input box
/// and what they would paste back, and some tools reject it.
fn display_path(p: &Path) -> String {
    let s = p.display().to_string();
    s.strip_prefix(r"\\?\").unwrap_or(&s).to_string()
}

/// Largest file body the preview will return. Anything past this is truncated
/// with a visible marker rather than silently cut.
const FILE_CAP: usize = 256 * 1024;

/// Subtrees the preview may read. Everything the graph points at lives in one
/// of these two, and an allow-list is the only containment rule that stays
/// correct when the graph gains new node types.
const READABLE: [&str; 2] = [".claude", "docs"];

/// Resolve a repo-relative path for the preview, refusing anything that leaves
/// the root or the readable subtrees.
///
/// Containment is decided AFTER canonicalizing both sides, so `..` segments, an
/// absolute path, and a symlink pointing outside the repo are all caught by the
/// same prefix check rather than by pattern-matching the string.
fn resolve_file(root: &Path, rel: &str) -> Result<PathBuf, String> {
    let cleaned = rel.trim().replace('\\', "/");
    if cleaned.is_empty() {
        return Err("no path given".into());
    }
    // Reject the obvious shapes early so the error names the real reason.
    if cleaned.starts_with('/') || cleaned.contains("://") || cleaned.split('/').any(|s| s == "..")
    {
        return Err(format!("refused: path must stay inside the repo ({rel})"));
    }
    if cleaned.len() > 2 && cleaned.as_bytes()[1] == b':' {
        return Err(format!("refused: absolute paths are not readable ({rel})"));
    }
    let first = cleaned.split('/').next().unwrap_or("");
    if !READABLE.contains(&first) {
        return Err(format!(
            "refused: only .claude/ and docs/ are readable, not {first}/"
        ));
    }
    let root_c = root.canonicalize().map_err(|e| format!("root: {e}"))?;
    let target = root_c.join(&cleaned);
    let target_c = target
        .canonicalize()
        .map_err(|_| format!("no such file: {cleaned}"))?;
    // The decisive check: a symlink that escaped the repo fails here even
    // though its textual path looked contained.
    if !target_c.starts_with(&root_c) {
        return Err(format!("refused: path escapes the repo ({rel})"));
    }
    if !target_c.is_file() {
        return Err(format!("not a file: {cleaned}"));
    }
    Ok(target_c)
}

/// Most path names `/paths` will return, and how deep it will walk. Both are
/// there so a repository with a vendored tree under docs/ cannot turn a
/// suggestion list into a filesystem crawl: the response is capped and says so.
const PATHS_CAP: usize = 4000;
const PATHS_DEPTH: usize = 12;

/// Directory names never worth suggesting and expensive to walk.
const PATHS_SKIP: [&str; 4] = ["node_modules", "target", "__pycache__", "venv"];

/// Every path the step editor may suggest, repo-relative and slash-separated,
/// directories marked with a trailing `/`.
///
/// This is a NAME service, not a read: it returns no file contents, and it is a
/// GET behind the same cross-origin gate `/file` uses. It exists because the
/// GRAPH does not carry these. The graph has nodes for agents, rules, hooks,
/// commands, scripts, skills and tasks, and those five suggestion classes are
/// derived from it with no server call at all - but the commands themselves
/// quote `docs/specs/05-functional-requirements.md`,
/// `docs/templates/ADR.md.template` and `docs/architecture/decisions/`
/// constantly, and not one of those is a node. A typo in one is a step that
/// sends an agent to a file that is not there, which is precisely what the
/// suggestions are for, so the names have to come from somewhere.
///
/// Containment is the allow-list `resolve_file` enforces and nothing wider. The
/// walk STARTS inside `.claude` and `docs` rather than filtering afterwards, so
/// there is no traversal to refuse; symlinked directories are not descended
/// (`DirEntry::file_type` does not follow the link), and every path emitted is
/// still checked against the canonical root before it goes out.
fn list_paths(root: &Path) -> (Vec<String>, bool) {
    let root_c = match root.canonicalize() {
        Ok(p) => p,
        Err(_) => return (Vec::new(), false),
    };
    let mut out: Vec<String> = Vec::new();
    let mut truncated = false;
    // (absolute dir, repo-relative prefix ending in '/', depth)
    let mut stack: Vec<(PathBuf, String, usize)> = READABLE
        .iter()
        .rev()
        .map(|name| (root_c.join(name), format!("{name}/"), 1usize))
        .filter(|(p, _, _)| p.is_dir())
        .collect();
    for (_, rel, _) in &stack {
        out.push(rel.clone());
    }
    while let Some((dir, prefix, depth)) = stack.pop() {
        if out.len() >= PATHS_CAP {
            truncated = true;
            break;
        }
        let entries = match fs::read_dir(&dir) {
            Ok(e) => e,
            Err(_) => continue,
        };
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().into_owned();
            // A dot-directory under .claude/ or docs/ is machine state, not
            // something a step should cite. `.claude` itself is a seed above.
            if name.starts_with('.') || PATHS_SKIP.contains(&name.as_str()) {
                continue;
            }
            let ft = match entry.file_type() {
                Ok(t) => t,
                Err(_) => continue,
            };
            let path = entry.path();
            // The decisive check, done per entry rather than per subtree: a
            // symlinked FILE resolving outside the repo never reaches the list.
            match path.canonicalize() {
                Ok(c) if c.starts_with(&root_c) => {}
                _ => continue,
            }
            if ft.is_dir() {
                let rel = format!("{prefix}{name}/");
                out.push(rel.clone());
                if depth < PATHS_DEPTH {
                    stack.push((path, rel, depth + 1));
                } else {
                    truncated = true;
                }
            } else if ft.is_file() {
                out.push(format!("{prefix}{name}"));
            }
            if out.len() >= PATHS_CAP {
                truncated = true;
                break;
            }
        }
    }
    out.sort();
    out.dedup();
    (out, truncated)
}

/// The cross-origin gate for the read-only endpoints: `same_origin` minus the
/// Content-Type rule, because a GET carries no body. Repo names are not public
/// just because the port is open.
fn same_origin_get(request: &Request, port: u16) -> Result<(), String> {
    if let Some(origin) = header_value(request, "Origin") {
        let allowed = [
            format!("http://127.0.0.1:{port}"),
            format!("http://localhost:{port}"),
        ];
        if !allowed.iter().any(|a| origin.eq_ignore_ascii_case(a)) {
            return Err(format!("cross-origin request refused (Origin: {origin})"));
        }
    }
    if let Some(site) = header_value(request, "Sec-Fetch-Site") {
        let s = site.to_ascii_lowercase();
        if s != "same-origin" && s != "none" {
            return Err(format!("cross-origin request refused (Sec-Fetch-Site: {site})"));
        }
    }
    Ok(())
}

/// Largest command file the step editor will write back. Two orders of
/// magnitude above the biggest shipped command, and small enough that a runaway
/// page cannot fill a disk.
const COMMAND_CAP: usize = 512 * 1024;

/// Resolve the command file the step editor is allowed to rewrite.
///
/// This takes a NAME, never a path. `resolve_file` has to accept paths because
/// the preview reads the whole graph, but the only thing that writes here is the
/// step editor, and it only ever edits an active command. Building the path from
/// a validated bare name means there is no traversal to contain: `..`, a
/// separator, or a drive letter fail the character check before a path exists.
fn resolve_command(root: &Path, name: &str) -> Result<PathBuf, String> {
    let n = name.trim();
    if n.is_empty() {
        return Err("no command named".into());
    }
    if !n
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_' || c == '.')
        || n.contains("..")
        || n.starts_with('.')
    {
        return Err(format!(
            "refused: `{name}` is not a bare command name (letters, digits, dash, underscore)"
        ));
    }
    let p = root.join(".claude").join("commands").join(format!("{n}.md"));
    if !p.is_file() {
        return Err(format!(
            "no active command named `{n}` - a disabled command is not editable; enable it first"
        ));
    }
    Ok(p)
}

/// Directory listing for the folder picker: subdirectory NAMES, a parent link,
/// and whether each child is itself a harness. No file names, no contents, no
/// sizes. On Windows an empty path lists the drives, because there is no single
/// filesystem root to start from.
fn browse(path: Option<&str>, default_root: &Path) -> Result<serde_json::Value, String> {
    let raw = path.map(|s| s.trim().trim_matches('"').to_string()).unwrap_or_default();

    // "" on Windows means "show me the drives"; elsewhere it means "/".
    if raw.is_empty() && cfg!(windows) {
        let mut drives = Vec::new();
        for letter in b'A'..=b'Z' {
            let d = format!("{}:\\", letter as char);
            if Path::new(&d).is_dir() {
                drives.push(serde_json::json!({
                    "name": d, "path": d, "harness": Path::new(&d).join(".claude").is_dir(),
                }));
            }
        }
        return Ok(serde_json::json!({
            "path": "", "parent": serde_json::Value::Null, "drives": true, "entries": drives,
        }));
    }

    let start = if raw.is_empty() {
        // no path and not Windows: start beside whatever we were pointed at
        default_root.to_path_buf()
    } else if cfg!(windows) {
        PathBuf::from(raw.replace('/', "\\"))
    } else {
        PathBuf::from(raw.replace('\\', "/"))
    };

    if !start.exists() {
        return Err(format!("path does not exist: {}", start.display()));
    }
    if !start.is_dir() {
        return Err(format!("not a directory: {}", start.display()));
    }
    let here = start.canonicalize().unwrap_or(start);

    let mut entries = Vec::new();
    match fs::read_dir(&here) {
        Ok(rd) => {
            for e in rd.flatten() {
                let p = e.path();
                if !p.is_dir() {
                    continue; // directories only: this is navigation, not a file browser
                }
                let Some(name) = p.file_name().and_then(|x| x.to_str()) else { continue };
                // hidden and build directories are noise when hunting for a repo,
                // but .claude itself is the thing being looked for, so it stays
                if name.starts_with('.') && name != ".claude" {
                    continue;
                }
                entries.push(serde_json::json!({
                    "name": name,
                    "path": display_path(&p),
                    "harness": p.join(".claude").is_dir(),
                }));
            }
        }
        Err(e) => return Err(format!("cannot list directory: {e}")),
    }
    entries.sort_by(|a, b| {
        a["name"].as_str().unwrap_or("").to_lowercase().cmp(&b["name"].as_str().unwrap_or("").to_lowercase())
    });

    // On Windows the parent of a drive root is the drive list, not None.
    let parent = match here.parent() {
        Some(p) => serde_json::Value::String(display_path(p)),
        None if cfg!(windows) => serde_json::Value::String(String::new()),
        None => serde_json::Value::Null,
    };

    Ok(serde_json::json!({
        "path": display_path(&here),
        "parent": parent,
        "drives": false,
        "harness": here.join(".claude").is_dir(),
        "entries": entries,
    }))
}

fn json_error(msg: &str, code: u16) -> Response<std::io::Cursor<Vec<u8>>> {
    let body = serde_json::json!({ "error": msg }).to_string();
    Response::from_string(body)
        .with_status_code(code)
        .with_header(header("Content-Type", "application/json"))
}

/// A root refusal, carrying the `noRoot` flag the page needs to tell "nothing
/// loaded yet" apart from "the path you gave me is wrong".
fn root_error(e: &RootError) -> Response<std::io::Cursor<Vec<u8>>> {
    let body = serde_json::json!({ "error": e.msg, "noRoot": e.no_root }).to_string();
    Response::from_string(body)
        .with_status_code(400)
        .with_header(header("Content-Type", "application/json"))
}

/// Same-origin gate for the mutating endpoint. Browsers attach Origin and
/// Sec-Fetch-Site to cross-origin fetches; a request carrying either with a
/// foreign value is refused. Non-browser clients (curl) carry neither.
fn same_origin(request: &Request, port: u16) -> Result<(), String> {
    if let Some(origin) = header_value(request, "Origin") {
        let allowed = [
            format!("http://127.0.0.1:{port}"),
            format!("http://localhost:{port}"),
        ];
        if !allowed.iter().any(|a| origin.eq_ignore_ascii_case(a)) {
            return Err(format!("cross-origin request refused (Origin: {origin})"));
        }
    }
    if let Some(site) = header_value(request, "Sec-Fetch-Site") {
        let s = site.to_ascii_lowercase();
        if s != "same-origin" && s != "none" {
            return Err(format!("cross-origin request refused (Sec-Fetch-Site: {site})"));
        }
    }
    let ct = header_value(request, "Content-Type").unwrap_or_default();
    if !ct.to_ascii_lowercase().contains("application/json") {
        return Err("Content-Type must be application/json".into());
    }
    Ok(())
}

pub fn serve(root: PathBuf, port: u16) -> Result<(), String> {
    let server = Server::http(("127.0.0.1", port)).map_err(|e| e.to_string())?;
    println!("harness-view: serving {} on http://127.0.0.1:{port}/", display_path(&root));
    // Starting here is legal (see main.rs), and the page says so too - but
    // someone who ran this from a terminal is looking at the terminal, and an
    // empty graph with no explanation in either place is how a working viewer
    // gets reported as broken.
    if !root.join(".claude").is_dir() {
        println!("harness-view: no harness here yet - choose a folder in the browser");
    }
    for mut request in server.incoming_requests() {
        let raw_url = request.url().to_string();
        // route on the path only - a cache-busting query string still matches
        let url = raw_url.split('?').next().unwrap_or("/").trim_end_matches('/').to_string();
        let url = if url.is_empty() { "/".to_string() } else { url };
        let method = request.method().clone();
        let response = match (method, url.as_str()) {
            (Method::Get, "/") => Response::from_string(page())
                .with_header(header("Content-Type", "text/html; charset=utf-8")),
            (Method::Get, "/roots") => {
                // The recent list lives in the browser's localStorage: it is a
                // per-person convenience, and keeping it there means the server
                // never writes a file outside the repo it was pointed at.
                let body = serde_json::json!({
                    "current": display_path(&root),
                    "recent": [],
                    // reported by the binary so the page footer cannot claim a
                    // version the running executable does not actually have
                    "version": crate::VERSION,
                })
                .to_string();
                Response::from_string(body)
                    .with_header(header("Content-Type", "application/json"))
            }
            (Method::Get, "/browse") => {
                // Directory NAMES only, never file names and never contents.
                // A browser cannot hand the page a real filesystem path, so
                // navigation has to be served; this returns the minimum needed
                // to walk a tree and nothing that could stand in for a read.
                let mut refused = None;
                if let Some(origin) = header_value(&request, "Origin") {
                    let allowed = [
                        format!("http://127.0.0.1:{port}"),
                        format!("http://localhost:{port}"),
                    ];
                    if !allowed.iter().any(|a| origin.eq_ignore_ascii_case(a)) {
                        refused = Some(format!("cross-origin request refused (Origin: {origin})"));
                    }
                }
                if let Some(site) = header_value(&request, "Sec-Fetch-Site") {
                    let s = site.to_ascii_lowercase();
                    if s != "same-origin" && s != "none" {
                        refused =
                            Some(format!("cross-origin request refused (Sec-Fetch-Site: {site})"));
                    }
                }
                if let Some(msg) = refused {
                    let _ = request.respond(json_error(&msg, 403));
                    continue;
                }
                match browse(query_param(&raw_url, "path").as_deref(), &root) {
                    Ok(v) => Response::from_string(v.to_string())
                        .with_header(header("Content-Type", "application/json")),
                    Err(msg) => json_error(&msg, 400),
                }
            }
            (Method::Get, "/graph.json") => {
                let requested = query_param(&raw_url, "root");
                match resolve_root(requested.as_deref(), &root) {
                    Ok(target) => {
                        let mut graph = scan::scan(&target);
                        // echo the resolved root so the page can show what it
                        // is actually looking at, not what the user typed
                        if let Some(obj) = graph.as_object_mut() {
                            obj.insert(
                                "root".into(),
                                serde_json::Value::String(display_path(&target)),
                            );
                        }
                        Response::from_string(scan::to_canonical_json(&graph))
                            .with_header(header("Content-Type", "application/json"))
                    }
                    Err(e) => root_error(&e),
                }
            }
            (Method::Get, "/assess") => {
                // Read-only and deterministic: the same rules engine the CLI
                // runs, so a browser and CI cannot disagree about a harness.
                let requested = query_param(&raw_url, "root");
                match resolve_root(requested.as_deref(), &root) {
                    Ok(target) => {
                        let graph = scan::scan(&target);
                        let report = assess::assess(&target, &graph);
                        Response::from_string(scan::to_canonical_json(&report))
                            .with_header(header("Content-Type", "application/json"))
                    }
                    Err(e) => root_error(&e),
                }
            }
            (Method::Get, "/paths") => {
                // Read-only, and names only - see list_paths for why the graph
                // cannot answer this and what keeps the walk contained.
                if let Err(msg) = same_origin_get(&request, port) {
                    let _ = request.respond(
                        Response::from_string(msg)
                            .with_status_code(403)
                            .with_header(header("Content-Type", "text/plain; charset=utf-8")),
                    );
                    continue;
                }
                let requested = query_param(&raw_url, "root");
                match resolve_root(requested.as_deref(), &root) {
                    Ok(target) => {
                        let (paths, truncated) = list_paths(&target);
                        let body = serde_json::json!({
                            "root": display_path(&target),
                            "paths": paths,
                            "truncated": truncated,
                        })
                        .to_string();
                        Response::from_string(body)
                            .with_header(header("Content-Type", "application/json"))
                    }
                    Err(e) => root_error(&e),
                }
            }
            (Method::Get, "/file") => {
                // Same cross-origin gate as the mutating endpoint, minus the
                // Content-Type rule (a GET carries no body). Repo contents are
                // not public just because the port is open.
                let mut refused = None;
                if let Some(origin) = header_value(&request, "Origin") {
                    let allowed = [
                        format!("http://127.0.0.1:{port}"),
                        format!("http://localhost:{port}"),
                    ];
                    if !allowed.iter().any(|a| origin.eq_ignore_ascii_case(a)) {
                        refused = Some(format!("cross-origin request refused (Origin: {origin})"));
                    }
                }
                if let Some(site) = header_value(&request, "Sec-Fetch-Site") {
                    let s = site.to_ascii_lowercase();
                    if s != "same-origin" && s != "none" {
                        refused =
                            Some(format!("cross-origin request refused (Sec-Fetch-Site: {site})"));
                    }
                }
                if let Some(msg) = refused {
                    let _ = request.respond(
                        Response::from_string(msg)
                            .with_status_code(403)
                            .with_header(header("Content-Type", "text/plain; charset=utf-8")),
                    );
                    continue;
                }
                let requested = query_param(&raw_url, "root");
                let rel = query_param(&raw_url, "path").unwrap_or_default();
                match resolve_root(requested.as_deref(), &root)
                    .and_then(|target| resolve_file(&target, &rel).map_err(RootError::bad))
                {
                    Ok(path) => match fs::read(&path) {
                        Ok(bytes) => {
                            let truncated = bytes.len() > FILE_CAP;
                            let slice = if truncated { &bytes[..FILE_CAP] } else { &bytes[..] };
                            let mut body = String::from_utf8_lossy(slice).into_owned();
                            if truncated {
                                body.push_str("\n\n... truncated at 256 KB by harness-view ...\n");
                            }
                            // text/plain, never text/html: the browser must not
                            // be talked into rendering repo content as markup.
                            Response::from_string(body)
                                .with_header(header("Content-Type", "text/plain; charset=utf-8"))
                                .with_header(header("X-Content-Type-Options", "nosniff"))
                        }
                        Err(e) => json_error(&format!("could not read: {e}"), 400),
                    },
                    Err(e) => root_error(&e),
                }
            }
            (Method::Post, "/toggle") => {
                if let Err(msg) = same_origin(&request, port) {
                    let _ = request.respond(
                        Response::from_string(msg)
                            .with_status_code(403)
                            .with_header(header("Content-Type", "text/plain; charset=utf-8")),
                    );
                    continue;
                }
                let mut body = String::new();
                let _ = request.as_reader().read_to_string(&mut body);
                match serde_json::from_str::<serde_json::Value>(&body) {
                    Ok(v) => {
                        let requested = v.get("root").and_then(|x| x.as_str());
                        match resolve_root(requested, &root) {
                            // plain text, not JSON: the page shows a toggle
                            // refusal verbatim in a confirm dialog
                            Err(e) => Response::from_string(e.msg)
                                .with_status_code(400)
                                .with_header(header("Content-Type", "text/plain; charset=utf-8")),
                            Ok(target) => {
                                let kind = v.get("kind").and_then(|x| x.as_str()).unwrap_or("");
                                let name = v.get("name").and_then(|x| x.as_str()).unwrap_or("");
                                // Absent `enable` used to default to false, so a body with a
                                // misspelt field - `{"action":"enable"}` - silently became a
                                // DISABLE. A HARD item's phrase gate catches that; a SOFT one
                                // has no such backstop, so the destructive direction must never
                                // be the default. Missing or non-boolean is a 400.
                                let enable = match v.get("enable").and_then(|x| x.as_bool()) {
                                    Some(b) => b,
                                    None => {
                                        let _ = request.respond(
                                            Response::from_string(
                                                "toggle needs an explicit boolean `enable`:                                                  true to restore, false to disable",
                                            )
                                            .with_status_code(400)
                                            .with_header(header(
                                                "Content-Type",
                                                "text/plain; charset=utf-8",
                                            )),
                                        );
                                        continue;
                                    }
                                };
                                let reason =
                                    v.get("reason").and_then(|x| x.as_str()).unwrap_or("");
                                let confirm_soft = v
                                    .get("confirm_soft")
                                    .and_then(|x| x.as_bool())
                                    .unwrap_or(false);
                                // Taken verbatim, never normalized: toggle()
                                // compares it byte-for-byte against
                                // `disable <name>` and a trim here would let a
                                // near-miss through.
                                let confirm_hard = v
                                    .get("confirm_hard")
                                    .and_then(|x| x.as_str())
                                    .unwrap_or("");
                                match toggle::toggle(
                                    &target,
                                    kind,
                                    name,
                                    enable,
                                    reason,
                                    confirm_soft,
                                    confirm_hard,
                                ) {
                                    Ok(msg) => Response::from_string(msg).with_header(header(
                                        "Content-Type",
                                        "text/plain; charset=utf-8",
                                    )),
                                    Err(e) => Response::from_string(e.msg)
                                        .with_status_code(e.code)
                                        .with_header(header(
                                            "Content-Type",
                                            "text/plain; charset=utf-8",
                                        )),
                                }
                            }
                        }
                    }
                    Err(_) => Response::from_string("invalid JSON body").with_status_code(400),
                }
            }
            // The step editor's write path. Same gate as /toggle - same-origin,
            // JSON content type - and the same plain-text refusals, because the
            // page shows what comes back verbatim.
            (Method::Post, "/command") => {
                if let Err(msg) = same_origin(&request, port) {
                    let _ = request.respond(
                        Response::from_string(msg)
                            .with_status_code(403)
                            .with_header(header("Content-Type", "text/plain; charset=utf-8")),
                    );
                    continue;
                }
                let mut body = String::new();
                let _ = request.as_reader().read_to_string(&mut body);
                match serde_json::from_str::<serde_json::Value>(&body) {
                    Ok(v) => {
                        let requested = v.get("root").and_then(|x| x.as_str());
                        match resolve_root(requested, &root) {
                            Err(e) => Response::from_string(e.msg)
                                .with_status_code(400)
                                .with_header(header("Content-Type", "text/plain; charset=utf-8")),
                            Ok(target) => {
                                let name = v.get("name").and_then(|x| x.as_str()).unwrap_or("");
                                let content =
                                    v.get("content").and_then(|x| x.as_str()).unwrap_or("");
                                let res = if content.len() > COMMAND_CAP {
                                    Err(format!(
                                        "refused: {} bytes exceeds the {COMMAND_CAP}-byte cap for \
                                         a command file",
                                        content.len()
                                    ))
                                } else if content.trim().is_empty() {
                                    // A save that empties the file is never an
                                    // edit anyone meant; deleting a command is
                                    // POST /toggle's job.
                                    Err("refused: empty content - disable the command instead of \
                                         emptying it"
                                        .into())
                                } else {
                                    resolve_command(&target, name).and_then(|p| {
                                        crate::toggle::atomic_write(&p, content)
                                            .map(|_| format!("wrote .claude/commands/{name}.md"))
                                            .map_err(|e| format!("write failed: {e}"))
                                    })
                                };
                                match res {
                                    Ok(msg) => Response::from_string(msg).with_header(header(
                                        "Content-Type",
                                        "text/plain; charset=utf-8",
                                    )),
                                    Err(msg) => Response::from_string(msg)
                                        .with_status_code(400)
                                        .with_header(header(
                                            "Content-Type",
                                            "text/plain; charset=utf-8",
                                        )),
                                }
                            }
                        }
                    }
                    Err(_) => Response::from_string("invalid JSON body").with_status_code(400),
                }
            }
            // The model/tool reference the roster pickers are built from: the
            // shipped seed with this repository's own corrections merged over
            // it. Read-only, behind the same cross-origin gate as /paths.
            (Method::Get, "/reference") => {
                if let Err(msg) = same_origin_get(&request, port) {
                    let _ = request.respond(
                        Response::from_string(msg)
                            .with_status_code(403)
                            .with_header(header("Content-Type", "text/plain; charset=utf-8")),
                    );
                    continue;
                }
                let requested = query_param(&raw_url, "root");
                match resolve_root(requested.as_deref(), &root) {
                    Ok(target) => match agentedit::merged(&target) {
                        Ok(v) => Response::from_string(scan::to_canonical_json(&v))
                            .with_header(header("Content-Type", "application/json")),
                        Err(msg) => json_error(&msg, 500),
                    },
                    Err(e) => root_error(&e),
                }
            }
            // The roster editor's write path: model, effort, tools and
            // description on one agent file. Same gate as /toggle and /command -
            // same-origin, JSON content type - and the same plain-text refusals,
            // because the page shows what comes back verbatim. Containment is
            // agentedit::resolve_agent: a NAME, never a path.
            (Method::Post, "/agent") => {
                if let Err(msg) = same_origin(&request, port) {
                    let _ = request.respond(
                        Response::from_string(msg)
                            .with_status_code(403)
                            .with_header(header("Content-Type", "text/plain; charset=utf-8")),
                    );
                    continue;
                }
                let mut body = String::new();
                let _ = request.as_reader().read_to_string(&mut body);
                match serde_json::from_str::<serde_json::Value>(&body) {
                    Ok(v) => {
                        let requested = v.get("root").and_then(|x| x.as_str());
                        match resolve_root(requested, &root) {
                            Err(e) => Response::from_string(e.msg)
                                .with_status_code(400)
                                .with_header(header("Content-Type", "text/plain; charset=utf-8")),
                            Ok(target) => {
                                let name = v.get("name").and_then(|x| x.as_str()).unwrap_or("");
                                match agentedit::write_agent(&target, name, &v) {
                                    Ok(msg) => Response::from_string(msg).with_header(header(
                                        "Content-Type",
                                        "text/plain; charset=utf-8",
                                    )),
                                    Err(msg) => Response::from_string(msg)
                                        .with_status_code(400)
                                        .with_header(header(
                                            "Content-Type",
                                            "text/plain; charset=utf-8",
                                        )),
                                }
                            }
                        }
                    }
                    Err(_) => Response::from_string("invalid JSON body").with_status_code(400),
                }
            }
            // Add / edit / delete a model, a tool or a whole vendor. Writes the
            // OVERLAY under the served repository's .claude/state/, never the
            // reference asset this repository ships - see agentedit's header.
            (Method::Post, "/reference") => {
                if let Err(msg) = same_origin(&request, port) {
                    let _ = request.respond(
                        Response::from_string(msg)
                            .with_status_code(403)
                            .with_header(header("Content-Type", "text/plain; charset=utf-8")),
                    );
                    continue;
                }
                let mut body = String::new();
                let _ = request.as_reader().read_to_string(&mut body);
                match serde_json::from_str::<serde_json::Value>(&body) {
                    Ok(v) => {
                        let requested = v.get("root").and_then(|x| x.as_str());
                        match resolve_root(requested, &root) {
                            Err(e) => Response::from_string(e.msg)
                                .with_status_code(400)
                                .with_header(header("Content-Type", "text/plain; charset=utf-8")),
                            Ok(target) => match agentedit::write_override(&target, &v) {
                                Ok(msg) => Response::from_string(msg).with_header(header(
                                    "Content-Type",
                                    "text/plain; charset=utf-8",
                                )),
                                Err(msg) => Response::from_string(msg)
                                    .with_status_code(400)
                                    .with_header(header(
                                        "Content-Type",
                                        "text/plain; charset=utf-8",
                                    )),
                            },
                        }
                    }
                    Err(_) => Response::from_string("invalid JSON body").with_status_code(400),
                }
            }
            _ => Response::from_string("not found").with_status_code(404),
        };
        let _ = request.respond(response);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The UI arrives in the response body or it does not arrive at all: there
    /// is no second request to fall back on. A renamed placeholder would still
    /// build, still serve 200, and still render the whole chrome - with a dead
    /// page underneath it - so the splice is asserted rather than assumed.
    #[test]
    fn page_inlines_the_ui_script_and_the_vendored_libraries() {
        let html = page();
        assert!(!html.contains("/*__UI_JS__*/"), "the UI script placeholder was never replaced");
        assert!(!html.contains("/*__UI_STEPS__*/"), "the steps-parser placeholder was never replaced");
        assert!(!html.contains("/*__VENDOR__*/"), "the vendor placeholder was never replaced");
        assert!(html.contains("function select("), "the served page carries no UI code");
        assert!(html.contains("function parseCommandSteps("), "the served page carries no steps parser");
        assert!(
            html.contains("function agentEditorModel("),
            "the served page carries no agent editor"
        );
        assert!(html.contains("DOMPurify"), "the served page carries no sanitiser");
        assert!(
            html.len() > PAGE_TEMPLATE.len() + UI_JS.len() + UI_STEPS_JS.len() + UI_AGENT_JS.len(),
            "the splice lost content"
        );
        // Order is not cosmetic: ui.js calls parseCommandSteps, and a `const` in
        // an earlier classic script is what puts it in scope for a later one.
        assert!(
            html.find("function parseCommandSteps(").unwrap() < html.find("function select(").unwrap(),
            "the steps parser must be spliced in before the UI that calls it"
        );
    }

    #[test]
    fn query_param_decodes_windows_paths() {
        let url = "/graph.json?root=D%3A%5CProjects%5Cmsboost&t=1";
        assert_eq!(query_param(url, "root").as_deref(), Some(r"D:\Projects\msboost"));
        assert_eq!(query_param("/graph.json", "root"), None);
        assert_eq!(query_param("/graph.json?root=", "root"), None);
    }

    #[test]
    fn resolve_file_refuses_everything_outside_the_readable_subtrees() {
        let tmp = std::env::temp_dir().join("hv-serve-file-test");
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(tmp.join(".claude/agents")).unwrap();
        std::fs::create_dir_all(tmp.join("docs/tasks")).unwrap();
        std::fs::write(tmp.join(".claude/agents/app-dev.md"), "# hi").unwrap();
        std::fs::write(tmp.join("docs/tasks/TASK-01.md"), "# task").unwrap();
        std::fs::write(tmp.join("SECRET.md"), "do not serve").unwrap();
        // a real file outside the root, the target a traversal would want
        let outside = tmp.parent().unwrap().join("hv-outside-secret.txt");
        std::fs::write(&outside, "outside").unwrap();

        // allowed
        assert!(resolve_file(&tmp, ".claude/agents/app-dev.md").is_ok());
        assert!(resolve_file(&tmp, "docs/tasks/TASK-01.md").is_ok());
        // backslashes are normalized, not a bypass
        assert!(resolve_file(&tmp, r".claude\agents\app-dev.md").is_ok());

        // refused, each for its own stated reason
        for bad in [
            "../hv-outside-secret.txt",
            ".claude/../../hv-outside-secret.txt",
            "/etc/passwd",
            "SECRET.md",
            "docs/../SECRET.md",
            "",
            "http://example.com/x",
        ] {
            let e = resolve_file(&tmp, bad);
            assert!(e.is_err(), "should have refused {bad:?}, got {e:?}");
        }
        // an absolute Windows path is refused by shape, before touching disk
        let abs = tmp.join(".claude/agents/app-dev.md").display().to_string();
        assert!(resolve_file(&tmp, &abs).is_err(), "absolute path must be refused");
        // a directory is not a file
        assert!(resolve_file(&tmp, ".claude/agents").is_err());
        // a path under a readable prefix that does not exist
        assert!(resolve_file(&tmp, ".claude/agents/nope.md").is_err());

        let _ = std::fs::remove_file(&outside);
        let _ = std::fs::remove_dir_all(&tmp);
    }

    /// The suggestion name service obeys the same containment as the reader it
    /// sits beside: only the two readable subtrees, nothing above the root, and
    /// no file contents. A list that leaked `SECRET.md` would be a directory
    /// listing of the whole repository dressed up as an editor convenience.
    #[test]
    fn list_paths_offers_only_the_readable_subtrees() {
        let tmp = std::env::temp_dir().join("hv-serve-paths-test");
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(tmp.join(".claude/rules")).unwrap();
        std::fs::create_dir_all(tmp.join(".claude/state/history")).unwrap();
        std::fs::create_dir_all(tmp.join("docs/templates")).unwrap();
        std::fs::create_dir_all(tmp.join("docs/node_modules/pkg")).unwrap();
        std::fs::create_dir_all(tmp.join("src")).unwrap();
        std::fs::write(tmp.join(".claude/rules/testing.md"), "r").unwrap();
        std::fs::write(tmp.join("docs/templates/ADR.md.template"), "t").unwrap();
        std::fs::write(tmp.join("docs/node_modules/pkg/index.js"), "x").unwrap();
        std::fs::write(tmp.join("SECRET.md"), "no").unwrap();
        std::fs::write(tmp.join("src/main.rs"), "no").unwrap();

        let (paths, truncated) = list_paths(&tmp);
        assert!(!truncated, "a five-file tree must not report truncation");
        // the two subtrees themselves, so a bare `docs/` completes
        assert!(paths.contains(&"docs/".to_string()), "{paths:?}");
        assert!(paths.contains(&".claude/".to_string()), "{paths:?}");
        // directories are marked, because half the citations in a command name one
        assert!(paths.contains(&"docs/templates/".to_string()), "{paths:?}");
        assert!(paths.contains(&"docs/templates/ADR.md.template".to_string()), "{paths:?}");
        assert!(paths.contains(&".claude/rules/testing.md".to_string()), "{paths:?}");
        // and nothing else in the repository
        assert!(!paths.iter().any(|p| p.contains("SECRET")), "a file outside the subtrees leaked");
        assert!(!paths.iter().any(|p| p.starts_with("src")), "a file outside the subtrees leaked");
        assert!(!paths.iter().any(|p| p.contains("node_modules")), "a vendored tree was walked");
        assert!(paths.iter().all(|p| p.starts_with(".claude/") || p.starts_with("docs/")),
                "something outside the allow-list was listed: {paths:?}");
        // sorted and unique, so the client can binary-search or just trust it
        let mut sorted = paths.clone();
        sorted.sort();
        sorted.dedup();
        assert_eq!(sorted, paths, "the list is not sorted-unique");

        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn resolve_root_falls_back_and_validates() {
        let tmp = std::env::temp_dir().join("hv-serve-root-test");
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(tmp.join(".claude")).unwrap();
        let default = tmp.clone();

        // absent -> the CLI root
        assert_eq!(resolve_root(None, &default).unwrap(), default);
        // blank -> the CLI root
        assert_eq!(resolve_root(Some("   "), &default).unwrap(), default);
        // both separators accepted
        let with_slash = tmp.display().to_string().replace('\\', "/");
        assert!(resolve_root(Some(&with_slash), &default).is_ok());
        // missing path is an error, not a fallback
        let missing = tmp.join("nope").display().to_string();
        let e = resolve_root(Some(&missing), &default).unwrap_err();
        assert!(e.msg.contains("does not exist"), "{}", e.msg);
        assert!(!e.no_root, "a wrong path is a wrong path, not an empty viewer");
        // a directory without .claude/ is refused by name
        let bare = tmp.join("bare");
        std::fs::create_dir_all(&bare).unwrap();
        let e = resolve_root(Some(&bare.display().to_string()), &default).unwrap_err();
        assert!(e.msg.contains("no .claude/"), "{}", e.msg);
        assert!(!e.no_root);

        let _ = std::fs::remove_dir_all(&tmp);
    }

    /// `serve` may be started in a directory with no harness. The fallback must
    /// then refuse rather than scan it: scanning a directory with no .claude/
    /// succeeds and returns an empty graph, which looks exactly like a harness
    /// that has nothing in it - the failure the whole root check exists for.
    #[test]
    fn a_cli_root_with_no_harness_is_refused_as_nothing_loaded() {
        let tmp = std::env::temp_dir().join("hv-serve-noroot-test");
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(&tmp).unwrap();

        for requested in [None, Some(""), Some("   ")] {
            let e = resolve_root(requested, &tmp).unwrap_err();
            assert!(e.no_root, "expected the nothing-loaded flag, got {}", e.msg);
            assert!(e.msg.contains("Browse"), "the message must say what to do: {}", e.msg);
        }

        // and it stops being refused the moment a harness is there
        std::fs::create_dir_all(tmp.join(".claude")).unwrap();
        assert_eq!(resolve_root(None, &tmp).unwrap(), tmp);

        let _ = std::fs::remove_dir_all(&tmp);
    }
}
