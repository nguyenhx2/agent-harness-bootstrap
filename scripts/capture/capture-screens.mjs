// Retake the harness-view UI screenshots from the CURRENT binary.
//
// The screenshots on the landing page and the READMEs show the tool's web UI, and the
// UI's footer carries the running binary's version. A screenshot is pixels: every text
// gate in this repo is blind to it, and the shipped assess screenshot read v1.12.0 for
// two releases while the release page said v1.14.0 - the same burned-in drift the video
// clips had before RENDERED.json. This script is the retake half of the fix; the gate
// half lives in scripts/validate_release.py (capture version must equal the release)
// and scripts/check_numbers.py (the caption figures must equal what was captured).
//
// Usage:  node capture-screens.mjs <repo-to-serve> [--binary <path>] [--out <dir>]
// Writes: harness-view-flow.png, harness-view-assess.png, CAPTURED.json (no timestamps).
//
// Uses puppeteer-core with the system Chrome: nothing is downloaded.

import { spawn, execFileSync } from "node:child_process";
import { writeFileSync, existsSync } from "node:fs";
import { resolve, join } from "node:path";
import puppeteer from "puppeteer-core";

const args = process.argv.slice(2);
const target = args[0];
if (!target || !existsSync(target)) {
  console.error("usage: node capture-screens.mjs <repo-to-serve> [--binary <path>] [--out <dir>]");
  process.exit(2);
}
const opt = (name, dflt) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : dflt;
};
const repoRoot = resolve(new URL("../..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const binary = resolve(opt("--binary",
  join(repoRoot, "tools/harness-view/target/release/harness-view.exe")));
const outDir = resolve(opt("--out", join(repoRoot, "docs/assets")));
const chrome = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/usr/bin/google-chrome",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].find(existsSync);
if (!chrome) { console.error("no system Chrome found"); process.exit(2); }

const version = execFileSync(binary, ["--version"]).toString().trim().split(/\s+/).pop();
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

// A LIST of candidate ports, not one hardcoded number. 7461 was fixed here for a year and then
// Windows swallowed a whole band of it: Hyper-V and WSL reserve dynamic port ranges, and a serve
// on a reserved port fails with "os error 10013" (forbidden) - not "in use", so the squatter poll
// below cannot see it. The old single port turned every capture on such a machine into "server
// never came up" with no hint why. Each candidate is tried in turn: skipped if something is
// already serving it (the wrong-repository hazard the poll guards against), skipped if the binary
// cannot bind it, kept the moment one answers for the target we were given.
const PORTS = [7461, 8137, 8532, 9218, 9714, 41983];
let port = null;
let server = null;
const kill = () => { try { server && server.kill(); } catch {} };
process.on("exit", kill);

for (const candidate of PORTS) {
  // Something already here? Do not photograph whatever it is serving.
  try {
    const squatter = await fetch(`http://127.0.0.1:${candidate}/roots`);
    if (squatter.ok) {
      const who = await squatter.json().catch(() => ({}));
      console.error(`port ${candidate} is already serving ${who.current ?? "something"}; trying the next.`);
      continue;
    }
  } catch { /* nothing listening, which is what we want */ }

  const s = spawn(binary, ["serve", resolve(target), "--port", String(candidate)], { stdio: "ignore" });
  let up = false;
  let dead = false;
  s.on("exit", () => { dead = true; });   // a forbidden port makes the binary exit immediately
  for (let i = 0; i < 25 && !up && !dead; i++) {
    try { up = (await fetch(`http://127.0.0.1:${candidate}/roots`)).ok; } catch { await wait(200); }
  }
  if (up) { server = s; port = candidate; break; }
  try { s.kill(); } catch {}
}

if (port === null) {
  throw new Error(`no usable port among ${PORTS.join(", ")} - every one was taken or forbidden ` +
                  "(Windows reserves ranges for Hyper-V/WSL; `netsh interface ipv4 show excludedportrange protocol=tcp` lists them)");
}

try {

  // Confirm the server we are about to photograph is serving the target we were given.
  const serving = await (await fetch(`http://127.0.0.1:${port}/roots`)).json();
  const want = resolve(target).replace(/\\/g, "/").toLowerCase();
  const got = String(serving.current ?? "").replace(/\\/g, "/").toLowerCase();
  if (!got.endsWith(want) && !want.endsWith(got)) {
    throw new Error(`the server on ${port} is serving ${serving.current}, not ${resolve(target)}`);
  }

  const browser = await puppeteer.launch({ executablePath: chrome, headless: true,
    args: ["--force-device-scale-factor=1"] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1456, height: 790 });
  await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "networkidle0" });
  // the flow layout settles after its first paint; the footer version arrives async
  await page.waitForFunction(
    () => document.getElementById("ver")?.textContent?.startsWith("v"), { timeout: 15000 });
  await wait(1200);

  const footerVer = await page.$eval("#ver", (e) => e.textContent);
  if (footerVer !== "v" + version) {
    throw new Error(`the page footer says ${footerVer} but the binary is ${version} - ` +
                    "refusing to capture a screenshot that would lie");
  }
  const stats = await page.$eval("#stats", (e) => e.textContent);
  const m = stats.match(/(\d+)\s*nodes,\s*(\d+)\s*edges/);
  if (!m) throw new Error(`cannot read node/edge counts from the footer: "${stats}"`);

  await page.screenshot({ path: join(outDir, "harness-view-flow.png") });

  await page.click("#btn-assess");
  // the assess run is synchronous on the server; the score element appears when done
  await page.waitForFunction(() => {
    const t = document.body.textContent || "";
    return /\/100/.test(t) && /Findings/i.test(t);
  }, { timeout: 30000 });
  await wait(600);
  // The score comes from the BINARY, not from scraping the page. Matching /(\d+)\/100/
  // against document.body.textContent picks up whichever figure the DOM happens to put
  // first - a per-category bar reading 100/100, say - so the same harness recorded 99 on
  // one run and 79 on the next. `assess` prints one authoritative line; parse that, and
  // let the caption and the picture come from the same answer.
  const assessOut = execFileSync(binary, ["assess", resolve(target)]).toString();
  const sm = assessOut.match(/overall\s+(\d+)\s*\/\s*100/);
  if (!sm) throw new Error(`cannot read the overall score from assess: ${assessOut.slice(0, 200)}`);
  const score = Number(sm[1]);
  await page.screenshot({ path: join(outDir, "harness-view-assess.png") });
  await browser.close();

  // Provenance, so the gates can hold what the pixels claim. No timestamps: this file
  // is committed, and a volatile byte would cold-miss the prompt cache on every run.
  const captured = {
    comment: "What the harness-view UI screenshots were captured from. Written by " +
             "scripts/capture/capture-screens.mjs, held by validate_release.py " +
             "(tool_version == release) and check_numbers.py (caption figures == these).",
    version: 1,
    tool_version: version,
    nodes: Number(m[1]),
    edges: Number(m[2]),
    score: score,
  };
  writeFileSync(join(outDir, "CAPTURED.json"), JSON.stringify(captured, null, 2) + "\n");
  console.log(`captured: v${version}, ${m[1]} nodes, ${m[2]} edges, score ${score}/100`);
} finally {
  kill();
}
