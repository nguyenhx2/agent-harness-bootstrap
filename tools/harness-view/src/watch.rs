//! Watch mode: rebuild the harness graph whenever .claude/ or docs/ changes.
//! Events under .claude/state/ are ignored, otherwise the rebuild's own write
//! would re-trigger the watcher forever.

use crate::scan;
use notify::{recommended_watcher, RecursiveMode, Watcher};
use std::path::PathBuf;
use std::sync::mpsc;
use std::time::{Duration, Instant};

pub fn watch(root: PathBuf) -> Result<(), String> {
    let (tx, rx) = mpsc::channel();
    let mut watcher = recommended_watcher(tx).map_err(|e| e.to_string())?;
    watcher
        .watch(&root.join(".claude"), RecursiveMode::Recursive)
        .map_err(|e| e.to_string())?;
    // docs/ holds the task board and specs; .agent-base/ holds the
    // orchestrator-kit board. Either may be absent.
    for sub in ["docs", ".agent-base"] {
        let dir = root.join(sub);
        if dir.is_dir() {
            watcher
                .watch(&dir, RecursiveMode::Recursive)
                .map_err(|e| e.to_string())?;
        }
    }
    println!("harness-view: watching {} (Ctrl+C to stop)", root.display());
    let state_dir = root.join(".claude").join("state");
    let relevant = |res: &Result<notify::Event, notify::Error>| -> bool {
        match res {
            Ok(ev) => ev.paths.iter().any(|p| !p.starts_with(&state_dir)),
            Err(_) => false,
        }
    };
    loop {
        let first = match rx.recv() {
            Ok(ev) => ev,
            Err(_) => break,
        };
        let mut hit = relevant(&first);
        // debounce: swallow the burst for 500ms
        let deadline = Instant::now() + Duration::from_millis(500);
        loop {
            let left = deadline.saturating_duration_since(Instant::now());
            if left.is_zero() {
                break;
            }
            match rx.recv_timeout(left) {
                Ok(ev) => hit = hit || relevant(&ev),
                Err(_) => break,
            }
        }
        if !hit {
            continue;
        }
        match scan::scan_to_file(&root, None) {
            Ok((n, m, _)) => println!("harness-view: rebuilt ({n} nodes, {m} edges)"),
            Err(e) => eprintln!("harness-view: rebuild failed: {e}"),
        }
    }
    Ok(())
}
