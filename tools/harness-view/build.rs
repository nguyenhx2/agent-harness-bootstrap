//! Stamps the Windows executable with its VERSIONINFO resource and icon.
//!
//! Without this the .exe shows a blank icon in Explorer and its Properties tab
//! reports no version at all, which makes a downloaded binary unidentifiable -
//! exactly the problem the release automation exists to prevent for the skill
//! zips. On every non-Windows target this file does nothing.
//!
//! The version comes from CARGO_PKG_VERSION, so it follows Cargo.toml, which
//! scripts/validate_release.py keeps pinned to the repo release version.

fn main() {
    println!("cargo:rerun-if-changed=assets/icon.ico");
    println!("cargo:rerun-if-changed=build.rs");

    #[cfg(windows)]
    {
        let mut res = winresource::WindowsResource::new();
        res.set_icon("assets/icon.ico");
        res.set("ProductName", "harness-view");
        res.set("FileDescription", "Agent harness analyzer and viewer");
        res.set("CompanyName", "nguyenhx2");
        res.set("LegalCopyright", "MIT licensed");
        res.set("OriginalFilename", "harness-view.exe");
        // FileVersion and ProductVersion default to CARGO_PKG_VERSION.
        if let Err(e) = res.compile() {
            // A missing resource compiler must not block a developer build; the
            // binary is still correct, it just loses its icon and metadata. But a
            // RELEASE build with no metadata is exactly the unidentifiable binary
            // this file exists to prevent, and a swallowed error here would ship
            // it green: the release workflow sets HARNESS_VIEW_REQUIRE_RESOURCE,
            // which turns the swallow back into the failure it really is.
            if std::env::var_os("HARNESS_VIEW_REQUIRE_RESOURCE").is_some() {
                panic!("windows resource embedding failed, refusing to ship an unstamped exe: {e}");
            }
            println!("cargo:warning=windows resource not embedded ({e})");
        }
    }
}
