//! Local viewer: GET / (embedded page), GET /graph.json (fresh scan every
//! request, so the page is always current), POST /toggle (shared contract
//! with /harness-toggle).
//!
//! POST /toggle is guarded against cross-origin browser requests: the server
//! only mutates .claude/ for same-origin calls. Any present Origin header must
//! name this server's own host:port, any present Sec-Fetch-Site header must be
//! same-origin or none, and the Content-Type must be application/json;
//! anything else is refused with 403. HARD-protected items refuse with 403,
//! SOFT-protected items with 409 unless the body carries confirm_soft: true.

use crate::{scan, toggle};
use std::path::PathBuf;
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
    println!("harness-view: serving {} on http://127.0.0.1:{port}/", root.display());
    for mut request in server.incoming_requests() {
        // route on the path only - a cache-busting query string still matches
        let url = request.url().split('?').next().unwrap_or("/").trim_end_matches('/').to_string();
        let url = if url.is_empty() { "/".to_string() } else { url };
        let method = request.method().clone();
        let response = match (method, url.as_str()) {
            (Method::Get, "/") => Response::from_string(PAGE)
                .with_header(header("Content-Type", "text/html; charset=utf-8")),
            (Method::Get, "/graph.json") => {
                let graph = scan::scan(&root);
                Response::from_string(scan::to_canonical_json(&graph))
                    .with_header(header("Content-Type", "application/json"))
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
                        let kind = v.get("kind").and_then(|x| x.as_str()).unwrap_or("");
                        let name = v.get("name").and_then(|x| x.as_str()).unwrap_or("");
                        let enable = v.get("enable").and_then(|x| x.as_bool()).unwrap_or(false);
                        let reason = v.get("reason").and_then(|x| x.as_str()).unwrap_or("");
                        let confirm_soft =
                            v.get("confirm_soft").and_then(|x| x.as_bool()).unwrap_or(false);
                        match toggle::toggle(&root, kind, name, enable, reason, confirm_soft) {
                            Ok(msg) => Response::from_string(msg)
                                .with_header(header("Content-Type", "text/plain; charset=utf-8")),
                            Err(e) => Response::from_string(e.msg)
                                .with_status_code(e.code)
                                .with_header(header("Content-Type", "text/plain; charset=utf-8")),
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
