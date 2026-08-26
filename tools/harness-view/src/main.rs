//! harness-view: deterministic analyzer for a repo bootstrapped with the
//! harness-bootstrap skill. Subcommands: scan, serve, watch. No AI involved;
//! it only reads files and reports relationships.

use harness_view::{assess, scan, serve, watch, VERSION};
use std::path::PathBuf;
use std::process::exit;

fn usage() -> ! {
    eprintln!(
        "harness-view {VERSION}\n\
         usage:\n  \
         harness-view scan  [path] [-o out.json]   write .claude/state/harness-graph.json\n  \
         harness-view serve [path] [--port 7420]   local web UI (Flow + Graph views, toggles)\n  \
         harness-view watch [path]                 rebuild the graph on .claude/ or docs/ changes\n  \
         harness-view assess [path] [--json]       score the harness; exit 1 on a high finding\n  \
         harness-view --version                    print the version\n\
         \n\
         Run with no arguments (or double-click the executable) to serve the\n\
         current directory and open it in a browser."
    );
    exit(2)
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();

    if args.iter().any(|a| a == "--version" || a == "-V") {
        println!("harness-view {VERSION}");
        return;
    }
    if args.iter().any(|a| a == "--help" || a == "-h") {
        usage();
    }

    // Double-click case: a GUI launch passes no arguments and the console window
    // closes the instant the process exits, so a bare usage error would flash and
    // vanish. Serving the current directory is the useful default, and it keeps
    // the window alive with the URL printed in it.
    let launched_bare = args.is_empty();
    let cmd = if launched_bare { String::from("serve") } else { args[0].clone() };
    let cmd = &cmd;
    let mut path = PathBuf::from(".");
    let mut out: Option<PathBuf> = None;
    let mut port: u16 = 7420;
    let mut json_out = false;
    let mut i = if launched_bare { 0 } else { 1 };
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
            "--json" => json_out = true,
            a if !a.starts_with('-') => path = PathBuf::from(a),
            _ => usage(),
        }
        i += 1;
    }
    let path = path.canonicalize().unwrap_or(path);
    // The .claude/ precondition belongs to the commands that ACT on one named
    // path, not to the one that opens a window.
    //
    // scan writes a graph file, assess prints a score, watch rebuilds on change:
    // each answers a question about the path it was given, and the honest answer
    // to "analyse this directory that has no harness" is a refusal. A graph file
    // full of nothing, or a score computed from nothing, is worse than an error
    // because it looks like a result.
    //
    // serve answers nothing on its own. It is a window, and the folder it looks
    // at is chosen in the UI, so where the executable happens to sit must not
    // decide whether it runs at all - a double-clicked binary in Downloads used
    // to print this line and close, which is the same as not starting.
    let needs_harness = matches!(cmd.as_str(), "scan" | "assess" | "watch");
    if needs_harness && !path.join(".claude").is_dir() {
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
        "assess" => match assess::assess_cli(&path, json_out) {
            Ok(code) => std::process::exit(code),
            Err(e) => { eprintln!("harness-view: {e}"); std::process::exit(2); }
        },
        "serve" => {
            // Bind BEFORE opening the browser. The port asked for is not always the port bound -
            // a reserved or busy port falls back to the next candidate - and opening the browser
            // first pointed it at a URL nothing was ever going to answer.
            match serve::bind(port) {
                Ok((server, bound)) => {
                    if launched_bare {
                        open_browser(bound);
                    }
                    if let Err(e) = serve::serve_with(server, bound, path) {
                        eprintln!("harness-view: serve failed: {e}");
                        if launched_bare {
                            pause("Press Enter to close");
                        }
                        exit(1);
                    }
                }
                Err(e) => {
                    eprintln!("harness-view: serve failed: {e}");
                    if launched_bare {
                        pause("Press Enter to close");
                    }
                    exit(1);
                }
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


/// Hand the URL to the desktop's default handler. Best effort by design: if it
/// fails the server is still up and the URL is on screen, so the launch is not
/// worse than not trying.
fn open_browser(port: u16) {
    let url = format!("http://127.0.0.1:{port}/");
    let _ = if cfg!(windows) {
        std::process::Command::new("cmd").args(["/C", "start", "", &url]).spawn()
    } else if cfg!(target_os = "macos") {
        std::process::Command::new("open").arg(&url).spawn()
    } else {
        std::process::Command::new("xdg-open").arg(&url).spawn()
    };
}

/// Keep a double-clicked console window open long enough to read the error.
fn pause(msg: &str) {
    eprintln!("{msg}");
    let mut s = String::new();
    let _ = std::io::stdin().read_line(&mut s);
}
