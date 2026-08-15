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
