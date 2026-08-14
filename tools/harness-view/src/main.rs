//! harness-view: deterministic analyzer for a repo bootstrapped with the
//! harness-bootstrap skill. Subcommands: scan, serve, watch. No AI involved;
//! it only reads files and reports relationships.

use harness_view::{scan, serve, watch};
use std::path::PathBuf;
use std::process::exit;

fn usage() -> ! {
    eprintln!(
        "harness-view 0.1.0\n\
         usage:\n  \
         harness-view scan  [path] [-o out.json]   write .claude/state/harness-graph.json\n  \
         harness-view serve [path] [--port 7420]   local web UI (Flow + Graph views, toggles)\n  \
         harness-view watch [path]                 rebuild the graph on .claude/ or docs/ changes"
    );
    exit(2)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(cmd) = args.first() else { usage() };
    let mut path = PathBuf::from(".");
    let mut out: Option<PathBuf> = None;
    let mut port: u16 = 7420;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "-o" | "--out" => {
                i += 1;
                out = args.get(i).map(PathBuf::from);
            }
            "--port" => {
                i += 1;
                port = args
                    .get(i)
                    .and_then(|p| p.parse().ok())
                    .unwrap_or_else(|| usage());
            }
            a if !a.starts_with('-') => path = PathBuf::from(a),
            _ => usage(),
        }
        i += 1;
    }
    let path = path.canonicalize().unwrap_or(path);
    if !path.join(".claude").is_dir() {
        eprintln!(
            "harness-view: {} has no .claude/ directory - point it at a repo that ran harness-bootstrap",
            path.display()
        );
        exit(1);
    }
    match cmd.as_str() {
        "scan" => match scan::scan_to_file(&path, out.as_deref()) {
            Ok((n, m, dest)) => println!("harness-view: {n} nodes, {m} edges -> {dest}"),
            Err(e) => {
                eprintln!("harness-view: scan failed: {e}");
                exit(1);
            }
        },
        "serve" => {
            if let Err(e) = serve::serve(path, port) {
                eprintln!("harness-view: serve failed: {e}");
                exit(1);
            }
        }
        "watch" => {
            if let Err(e) = watch::watch(path) {
                eprintln!("harness-view: watch failed: {e}");
                exit(1);
            }
        }
        _ => usage(),
    }
}
