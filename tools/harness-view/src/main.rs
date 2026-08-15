//! harness-view: deterministic analyzer for a repo bootstrapped with the
//! harness-bootstrap skill. Subcommands: scan, serve, watch. No AI involved;
//! it only reads files and reports relationships.

use harness_view::{scan, serve, watch, VERSION};
use std::path::PathBuf;
use std::process::exit;

fn usage() -> ! {
    eprintln!(
        "harness-view {VERSION}\n\
         usage:\n  \
         harness-view scan  [path] [-o out.json]   write .claude/state/harness-graph.json\n  \
         harness-view serve [path] [--port 7420]   local web UI (Flow + Graph views, toggles)\n  \
         harness-view watch [path]                 rebuild the graph on .claude/ or docs/ changes\n  \
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
        if launched_bare {
            pause("Press Enter to close");
        }
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
            if launched_bare {
                open_browser(port);
            }
            if let Err(e) = serve::serve(path, port) {
                eprintln!("harness-view: serve failed: {e}");
                if launched_bare {
                    pause("Press Enter to close");
                }
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
