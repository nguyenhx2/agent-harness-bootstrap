//! Local viewer: GET / (embedded page), GET /graph.json (fresh scan every
//! request, so the page is always current), GET /roots (which root the server
//! started on), POST /toggle (shared contract with /harness-toggle).
//!
//! The root is selectable per request: GET /graph.json?root=<path> and the
//! optional "root" field on POST /toggle both scan a caller-named directory,
//! falling back to the one named on the command line. A root that does not
//! exist, is not a directory, or carries no .claude/ is refused with 400 and a
//! JSON {"error": ...} the page displays - never an empty graph, because an
//! empty graph is indistinguishable from a harness with nothing in it.
//!
//! POST /toggle is guarded against cross-origin browser requests: the server
//! only mutates .claude/ for same-origin calls. Any present Origin header must
//! name this server's own host:port, any present Sec-Fetch-Site header must be
//! same-origin or none, and the Content-Type must be application/json;
//! anything else is refused with 403. HARD-protected items refuse with 403,
//! SOFT-protected items with 409 unless the body carries confirm_soft: true.

use crate::{scan, toggle};
use std::fs;
use std::path::{Path, PathBuf};
use tiny_http::{Header, Method, Request, Response, Server};

const PAGE: &str = include_str!("ui.html");

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

/// Resolve a caller-supplied root, or fall back to the one from the CLI.
///
/// Windows callers paste either separator, so both are accepted and normalized
/// before the path is touched. The `.claude/` requirement is what makes a wrong
/// path an explicit error instead of a convincing empty graph.
fn resolve_root(requested: Option<&str>, default_root: &Path) -> Result<PathBuf, String> {
    let Some(raw) = requested else {
        return Ok(default_root.to_path_buf());
    };
    let trimmed = raw.trim().trim_matches('"');
    if trimmed.is_empty() {
        return Ok(default_root.to_path_buf());
    }
    let normalized = if cfg!(windows) {
        trimmed.replace('/', "\\")
    } else {
        trimmed.replace('\\', "/")
    };
    let p = PathBuf::from(&normalized);
    if !p.exists() {
        return Err(format!("path does not exist: {normalized}"));
    }
    if !p.is_dir() {
        return Err(format!("not a directory: {normalized}"));
    }
    if !p.join(".claude").is_dir() {
        return Err(format!(
            "no .claude/ directory in {normalized} - point this at a repo that ran harness-bootstrap"
        ));
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

fn json_error(msg: &str, code: u16) -> Response<std::io::Cursor<Vec<u8>>> {
    let body = serde_json::json!({ "error": msg }).to_string();
    Response::from_string(body)
        .with_status_code(code)
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
    for mut request in server.incoming_requests() {
        let raw_url = request.url().to_string();
        // route on the path only - a cache-busting query string still matches
        let url = raw_url.split('?').next().unwrap_or("/").trim_end_matches('/').to_string();
        let url = if url.is_empty() { "/".to_string() } else { url };
        let method = request.method().clone();
        let response = match (method, url.as_str()) {
            (Method::Get, "/") => Response::from_string(PAGE)
                .with_header(header("Content-Type", "text/html; charset=utf-8")),
            (Method::Get, "/roots") => {
                // The recent list lives in the browser's localStorage: it is a
                // per-person convenience, and keeping it there means the server
                // never writes a file outside the repo it was pointed at.
                let body = serde_json::json!({
                    "current": display_path(&root),
                    "recent": [],
                })
                .to_string();
                Response::from_string(body)
                    .with_header(header("Content-Type", "application/json"))
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
                    Err(msg) => json_error(&msg, 400),
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
                    .and_then(|target| resolve_file(&target, &rel))
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
                    Err(msg) => json_error(&msg, 400),
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
                            Err(msg) => Response::from_string(msg)
                                .with_status_code(400)
                                .with_header(header("Content-Type", "text/plain; charset=utf-8")),
                            Ok(target) => {
                                let kind = v.get("kind").and_then(|x| x.as_str()).unwrap_or("");
                                let name = v.get("name").and_then(|x| x.as_str()).unwrap_or("");
                                let enable =
                                    v.get("enable").and_then(|x| x.as_bool()).unwrap_or(false);
                                let reason =
                                    v.get("reason").and_then(|x| x.as_str()).unwrap_or("");
                                let confirm_soft = v
                                    .get("confirm_soft")
                                    .and_then(|x| x.as_bool())
                                    .unwrap_or(false);
                                match toggle::toggle(
                                    &target,
                                    kind,
                                    name,
                                    enable,
                                    reason,
                                    confirm_soft,
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
            _ => Response::from_string("not found").with_status_code(404),
        };
        let _ = request.respond(response);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

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
        assert!(resolve_root(Some(&missing), &default).unwrap_err().contains("does not exist"));
        // a directory without .claude/ is refused by name
        let bare = tmp.join("bare");
        std::fs::create_dir_all(&bare).unwrap();
        let e = resolve_root(Some(&bare.display().to_string()), &default).unwrap_err();
        assert!(e.contains("no .claude/"), "{e}");

        let _ = std::fs::remove_dir_all(&tmp);
    }
}
