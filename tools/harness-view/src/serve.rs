//! Local viewer: GET / (embedded page), GET /graph.json (fresh scan every
//! request, so the page is always current), POST /toggle (shared contract
//! with /harness-toggle; HARD-protected items refuse with 403).

use crate::{scan, toggle};
use std::path::PathBuf;
use tiny_http::{Header, Method, Response, Server};

const PAGE: &str = include_str!("ui.html");

fn header(k: &str, v: &str) -> Header {
    Header::from_bytes(k.as_bytes(), v.as_bytes()).expect("static header")
}

pub fn serve(root: PathBuf, port: u16) -> Result<(), String> {
    let server = Server::http(("127.0.0.1", port)).map_err(|e| e.to_string())?;
    println!("harness-view: serving {} on http://127.0.0.1:{port}/", root.display());
    for mut request in server.incoming_requests() {
        let url = request.url().trim_end_matches('/').to_string();
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
                let mut body = String::new();
                let _ = request.as_reader().read_to_string(&mut body);
                match serde_json::from_str::<serde_json::Value>(&body) {
                    Ok(v) => {
                        let kind = v.get("kind").and_then(|x| x.as_str()).unwrap_or("");
                        let name = v.get("name").and_then(|x| x.as_str()).unwrap_or("");
                        let enable = v.get("enable").and_then(|x| x.as_bool()).unwrap_or(false);
                        let reason = v.get("reason").and_then(|x| x.as_str()).unwrap_or("");
                        match toggle::toggle(&root, kind, name, enable, reason) {
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
