// Turn SCRIPT.md (or SCRIPT.ja.md), the voice's character alignment and the cached audio into
// src/timing.<lang>.json: when every caption cue is spoken, when every scene starts, which pieces of
// the narration play where, the intervals the music ducks under, and the gains that set the music
// a fixed number of decibels under the voice. No API call. Refuses to run when the script has
// changed since the narration was generated, because captions timed against a different recording
// are captions that lie.
//
//   node scripts/build-timing.mjs [en|ja]      # default: both
//
// Pacing is edited, never sped up. The voice plays at its own tempo; what changes is silence:
//   - a pause longer than KEEP is shortened to KEEP (the middle of the silence is cut out), and
//   - at every scene boundary the narration is split and the next scene placed SCENE_GAP later,
//     so the music comes up between scenes.
// Both edits fall inside silence that ffmpeg's silencedetect found in the cached file, so no word is
// ever cut, and every caption time goes through the same map as the audio it belongs to.
import {readFileSync, writeFileSync, existsSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import {HERE, AUDIO, LANGS, LEAD_IN, TAIL, gapBefore, readScript, narrationText, sha, alignmentFile, narrationFile} from './script.mjs';

const SCENE_LEAD = 0.35; // a scene's picture arrives just ahead of its first word
const KEEP = 0.55; // the longest pause kept inside a scene, in seconds
const SILENCE_DB = -40; // silencedetect threshold
const SILENCE_MIN = 0.3; // shortest silence silencedetect reports

// Mix targets, in LU relative to the voice. Under speech the music sits UNDER_SPEECH below the
// voice; in the gaps between scenes, at the open and at the close it comes up to IN_GAPS below.
export const UNDER_SPEECH = 9;
export const IN_GAPS = 3;

const r = (x) => Math.round(x * 1000) / 1000;

/** Run one ffmpeg audio filter over a file and return what it printed on stderr. */
function analyse(file, filter) {
  const res = spawnSync('ffmpeg', ['-hide_banner', '-nostats', '-i', file, '-af', filter, '-f', 'null', '-'], {
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
  });
  if (res.status !== 0) throw new Error(`ffmpeg failed on ${file}: ${String(res.stderr).slice(-400)}`);
  return res.stderr;
}

/** Silences in a file: [[start, end], ...] in seconds. */
export function silences(file) {
  const log = analyse(file, `silencedetect=n=${SILENCE_DB}dB:d=${SILENCE_MIN}`);
  const out = [];
  let s = null;
  for (const line of log.split(/\r?\n/)) {
    const a = line.match(/silence_start: (-?[\d.]+)/);
    if (a) s = Math.max(0, Number(a[1]));
    const b = line.match(/silence_end: ([\d.]+)/);
    if (b && s !== null) {
      out.push([s, Number(b[1])]);
      s = null;
    }
  }
  return out;
}

/** Integrated loudness of a file, in LUFS. */
export function lufs(file) {
  const log = analyse(file, 'ebur128=framelog=quiet');
  const m = [...log.matchAll(/I:\s+(-?[\d.]+) LUFS/g)].at(-1);
  if (!m) throw new Error(`no loudness reading for ${file}`);
  return Number(m[1]);
}

/**
 * The bed's own dynamics, flattened. A generated bed builds and falls back, so a fixed gain would
 * sit it 13 LU under the voice in one scene and 7 in another. This reads its short-term loudness
 * (3 s window) once per second, smooths it over five seconds, and returns the correction in dB that
 * brings each second back to the bed's integrated level, limited to +-6 dB. Silence (the tail) gets
 * no correction; the fade-out handles it.
 */
function levelling(file, integrated) {
  const res = spawnSync('ffmpeg', ['-hide_banner', '-nostats', '-v', 'verbose', '-i', file, '-af', 'ebur128=framelog=verbose', '-f', 'null', '-'], {
    encoding: 'utf8',
    maxBuffer: 256 * 1024 * 1024,
  });
  const st = [];
  for (const m of String(res.stderr).matchAll(/t: ([\d.]+)\s+TARGET:\S+ LUFS\s+M:\s*\S+ S:\s*(-?[\d.]+|-inf)/g)) {
    const sec = Math.round(Number(m[1]) - 1.5); // centre the 3 s window
    if (sec >= 0 && Math.abs(Number(m[1]) - 1.5 - sec) < 0.051) st[sec] = m[2] === '-inf' ? -120 : Number(m[2]);
  }
  const trim = [];
  for (let i = 0; i < st.length; i++) {
    const win = st.slice(Math.max(0, i - 2), i + 3).filter((x) => x !== undefined && x > -40);
    if (!win.length) {
      trim.push(0);
      continue;
    }
    const avg = 10 * Math.log10(win.reduce((t, x) => t + Math.pow(10, x / 10), 0) / win.length);
    trim.push(Math.round(Math.max(-6, Math.min(6, integrated - avg)) * 10) / 10);
  }
  return trim;
}

/** Duration of a file, in seconds, as ffmpeg reads it. */
function duration(file) {
  const m = analyse(file, 'anull').match(/Duration: (\d+):(\d+):([\d.]+)/);
  return m ? Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]) : 0;
}

function build(lang, music) {
  const scenes = readScript(lang);
  const text = narrationText(scenes);
  const manifest = JSON.parse(readFileSync(path.join(AUDIO, 'ASSETS.json'), 'utf8'));
  if (manifest.narration?.[lang]?.text_sha256 !== sha(text)) {
    console.error(`  FAIL  ${lang}: the script no longer matches the cached narration. Regenerate the voice:`);
    console.error(`        bash render.sh --generate voice ${lang} --force`);
    process.exit(1);
  }
  const a = JSON.parse(readFileSync(alignmentFile(lang), 'utf8')).alignment;
  if (a.characters.join('') !== text) {
    console.error(`  FAIL  ${lang}: the alignment does not spell the narration text; regenerate the voice.`);
    process.exit(1);
  }
  const st = a.character_start_times_seconds;
  const en = a.character_end_times_seconds;

  // Locate every cue in the narration text (original timeline).
  let pos = 0;
  const raw = [];
  for (const s of scenes) {
    for (const c of s.cues) {
      const i = text.indexOf(c, pos);
      if (i < 0) throw new Error(`cue not found in narration: ${c}`);
      const j = i + c.length - 1;
      // The alignment hands a sentence stop the whole pause that follows it. Spoken, the cue is
      // over when the stop begins, so a trailing stop counts for at most 0.3 s.
      const endT = /[。、.,!?」"]/.test(text[j]) ? Math.min(en[j], st[j] + 0.3) : en[j];
      raw.push({scene: s.id, text: c, s: st[i], e: endT});
      pos = j + 1;
    }
  }

  // ---- the edit: silences from the cached file, shortened; scene gaps inserted.
  const voiceFile = narrationFile(lang);
  const sil = silences(voiceFile);
  const firstWord = raw[0].s;
  const lastWord = raw.at(-1).e;
  const cuts = []; // [from, to] of original time removed
  for (const [s0, e0] of sil) {
    if (e0 <= firstWord + 0.05) {
      // Leading silence: keep only a breath of it.
      if (e0 - s0 > 0.15) cuts.push([s0, e0 - 0.1]);
      continue;
    }
    if (s0 >= lastWord) continue;
    if (e0 - s0 > KEEP) cuts.push([s0 + KEEP / 2, e0 - KEEP / 2]);
  }
  // Scene boundaries: the middle of the longest silence between one scene's last word and the next
  // scene's first. The gap is inserted there.
  const inserts = []; // [at original time, seconds]
  scenes.forEach((s, n) => {
    if (n === 0) return;
    const prevEnd = raw.filter((c) => c.scene === scenes[n - 1].id).at(-1).e;
    const nextStart = raw.find((c) => c.scene === s.id).s;
    const lo = prevEnd - 0.4;
    const hi = nextStart + 0.4;
    const cands = sil.filter(([s0, e0]) => e0 > lo && s0 < hi).sort((x, y) => y[1] - y[0] - (x[1] - x[0]));
    const at = cands.length ? (Math.max(cands[0][0], lo) + Math.min(cands[0][1], hi)) / 2 : (prevEnd + nextStart) / 2;
    inserts.push([at, gapBefore(s.id, n)]);
  });

  // Original time -> edited time (before LEAD_IN).
  const map = (t) => {
    let out = t;
    for (const [c0, c1] of cuts) {
      if (t >= c1) out -= c1 - c0;
      else if (t > c0) out -= t - c0;
    }
    for (const [p, g] of inserts) if (t >= p) out += g;
    return out;
  };

  // The audio pieces: the original timeline minus the cuts, split at every insert point.
  const breaks = [...cuts.flat(), ...inserts.map(([p]) => p)].sort((x, y) => x - y);
  const edges = [0, ...breaks, lastWord + 0.6];
  const segments = [];
  for (let k = 0; k + 1 < edges.length; k++) {
    const [s0, e0] = [edges[k], edges[k + 1]];
    if (e0 - s0 < 0.02) continue;
    const mid = (s0 + e0) / 2;
    if (cuts.some(([c0, c1]) => mid > c0 && mid < c1)) continue;
    segments.push({from: r(s0), to: r(e0), at: r(LEAD_IN + map(s0))});
  }

  // The alignment is character-level, but it hands a pause to the character next to it: the voice
  // (eleven_v3 especially) gives the silence before a cue to the cue's first letter, so the caption
  // would land ~0.3 s before the word. Where the detected audio says otherwise, the audio wins: a cue
  // starts where the silence before it ends, and ends where the silence after it begins.
  for (const c of raw) {
    const before = sil.find(([s0, e0]) => s0 <= c.s + 0.05 && e0 > c.s && e0 < c.s + 0.9);
    if (before) c.s = before[1];
    const after = sil.find(([s0, e0]) => s0 >= c.e - 0.5 && s0 <= c.e + 0.15 && e0 > s0);
    if (after && after[0] > c.s) c.e = after[0];
  }
  const cues = raw.map((c) => ({scene: c.scene, text: c.text, start: r(LEAD_IN + map(c.s)), end: r(LEAD_IN + map(c.e))}));

  // Speech intervals: the complement of the detected silences, mapped, merged across pauses shorter
  // than 0.45 s, so the music ducks under each phrase and breathes back up only in real gaps.
  const speech = [];
  let cursor = firstWord;
  const pushRun = (s0, e0) => {
    if (e0 - s0 < 0.05) return;
    const ms = LEAD_IN + map(s0);
    const me = LEAD_IN + map(e0);
    const last = speech.at(-1);
    if (last && ms - last[1] < 0.45) last[1] = Math.max(last[1], me);
    else speech.push([ms, me]);
  };
  for (const [s0, e0] of sil) {
    if (e0 <= cursor) continue;
    if (s0 > cursor) pushRun(cursor, Math.min(s0, lastWord + 0.3));
    cursor = Math.max(cursor, e0);
    if (cursor >= lastWord) break;
  }
  if (cursor < lastWord) pushRun(cursor, lastWord);

  const voiceEnd = LEAD_IN + map(lastWord);
  const total = r(voiceEnd + TAIL);
  const sceneTimes = scenes.map((s, n) => {
    const first = cues.find((c) => c.scene === s.id);
    if (n === 0) return {id: s.id, start: 0};
    const prevEnd = cues.filter((c) => c.scene === scenes[n - 1].id).at(-1).end;
    return {id: s.id, start: r(Math.max(first.start - SCENE_LEAD, (prevEnd + first.start) / 2))};
  });
  sceneTimes.forEach((s, n) => (s.end = n + 1 < sceneTimes.length ? sceneTimes[n + 1].start : total));

  // A caption stays up until the next one replaces it, but never lingers more than 0.8 s past its
  // last word, and never across a scene cut.
  cues.forEach((c, n) => {
    const next = cues[n + 1];
    const sceneEnd = sceneTimes.find((s) => s.id === c.scene).end;
    c.out = r(Math.min(next ? next.start : total, c.end + 0.8, sceneEnd));
  });

  // ---- the mix: gains from measured loudness, so a new voice or a new bed keeps the same balance.
  const voiceLufs = lufs(voiceFile);
  const db = (x) => Math.pow(10, x / 20);
  let voiceGain = 1;
  let low = db(voiceLufs - UNDER_SPEECH - music);
  let high = db(voiceLufs - IN_GAPS - music);
  const peak = high * db(Math.max(0, ...musicTrim));
  if (peak > 1) {
    // Remotion's volume tops out at 1; turn the voice down instead. The final loudnorm restores level.
    voiceGain = 1 / peak;
    low /= peak;
    high /= peak;
  }

  if (musicLength < total) {
    console.error(`  FAIL  ${lang}: the music bed is ${r(musicLength)}s, the clip ${total}s. Regenerate it:`);
    console.error('        bash render.sh --generate music --force');
    process.exit(1);
  }

  const out = {
    comment: `Generated by scripts/build-timing.mjs from ${lang === 'en' ? 'SCRIPT.md' : `SCRIPT.${lang}.md`}, audio/${path.basename(alignmentFile(lang))} and the cached audio. Do not edit.`,
    lang,
    leadIn: LEAD_IN,
    voiceEnd: r(voiceEnd),
    total,
    mix: {
      voiceLufs: r(voiceLufs),
      musicLufs: r(music),
      underSpeechLU: UNDER_SPEECH,
      inGapsLU: IN_GAPS,
      voiceGain: r(voiceGain),
      musicLow: r(low),
      musicHigh: r(high),
      // dB per second of the bed, added to the music gain: see levelling().
      musicTrim,
    },
    scenes: sceneTimes,
    cues,
    segments,
    speech: speech.map(([s, e]) => [r(s), r(e)]),
  };
  writeFileSync(path.join(HERE, 'src', `timing.${lang}.json`), JSON.stringify(out, null, 2) + '\n');
  const cut = cuts.reduce((t, [c0, c1]) => t + c1 - c0, 0);
  console.log(
    `  timing  ${lang}: ${cues.length} cues, ${sceneTimes.length} scenes, ${segments.length} audio pieces, ` +
      `${r(cut)}s of pause trimmed, ${total}s total; voice ${r(voiceLufs)} LUFS, music ${r(music)} LUFS`,
  );
  return sceneTimes.map((s) => s.id).join(' ');
}

const musicFile = path.join(AUDIO, 'music.mp3');
if (!existsSync(musicFile)) throw new Error('audio/music.mp3 is missing: bash render.sh --generate music');
const music = lufs(musicFile);
const musicLength = duration(musicFile);
const musicTrim = levelling(musicFile, music);
const want = process.argv.slice(2).filter((a) => LANGS.includes(a));
const ids = (want.length ? want : LANGS).map((l) => build(l, music));
if (new Set(ids).size > 1) {
  console.error('  FAIL  the scripts do not have the same scenes in the same order:');
  for (const s of ids) console.error(`        ${s}`);
  process.exit(1);
}
