/// The build version, taken from Cargo.toml, which scripts/validate_release.py
/// keeps equal to the repo release version. Shown by `--version`, in the served
/// page footer, and stamped into the Windows VERSIONINFO resource by build.rs.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

pub mod assess;
pub mod scan;
pub mod serve;
pub mod toggle;
pub mod watch;
