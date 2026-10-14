// Measure the mix the way a listener hears it: render the voice alone and the music alone through the
// same composition (the `stem` prop), then read the loudness of each, per scene, under speech and in
// the gaps between scenes. No API call. Run after render.sh, or on its own:
//
//   node scripts/measure-mix.mjs [en|ja]
//
// It prints one row per scene; "under" is music minus voice while the voice speaks (the target is
// about -9 LU), "gap" is the music level in the pause before the scene, against the voice's level.
import {spawnSync} from 'node:child_process';
import {mkdirSync, readFileSync} from 'node:fs';
import path from 'node:path';
import {HERE, LANGS} from './script.mjs';

const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';

function run(cmd, args) {
  const res = spawnSync(cmd, args, {cwd: HERE, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, shell: process.platform === 'win32'});
  if (res.status !== 0) throw new Error(`${cmd} ${args.slice(0, 3).join(' ')} failed: ${String(res.stderr).slice(-600)}`);
  return res.stderr;
}

/** Integrated loudness of the parts of a file inside the given intervals. -> LUFS, or null if silent. */
function lufsOver(file, intervals) {
  if (!intervals.length) return null;
  const sel = intervals.map(([a, b]) => `between(t,${a.toFixed(3)},${b.toFixed(3)})`).join('+');
  const log = run('ffmpeg', ['-hide_banner', '-nostats', '-i', file, '-af', `aselect='${sel}',ebur128=framelog=quiet`, '-f', 'null', '-']);
  const m = [...log.matchAll(/I:\s+(-?[\d.]+|-inf) LUFS/g)].at(-1);
  return m && m[1] !== '-inf' ? Number(m[1]) : null;
}

const fmt = (x) => (x === null ? '   -  ' : x.toFixed(1).padStart(6));

for (const lang of process.argv.slice(2).filter((a) => LANGS.includes(a)).length
  ? process.argv.slice(2).filter((a) => LANGS.includes(a))
  : LANGS) {
  const tm = JSON.parse(readFileSync(path.join(HERE, 'src', `timing.${lang}.json`), 'utf8'));
  const comp = lang === 'en' ? 'Intro' : 'IntroJa';
  const dir = path.join(HERE, 'out', lang);
  mkdirSync(dir, {recursive: true});
  const stems = {};
  for (const stem of ['voice', 'music']) {
    stems[stem] = path.join(dir, `stem-${stem}.wav`);
    run(npx, ['remotion', 'render', 'src/index.ts', comp, stems[stem], '--codec=wav', `--props=${JSON.stringify(JSON.stringify({lang, stem}))}`, '--log=error']);
  }
  console.log(`\n  ${lang}: music vs voice, LUFS (target: under speech about -${tm.mix.underSpeechLU} LU, gaps about -${tm.mix.inGapsLU} LU)`);
  console.log('  scene      voice  music  under |  gap music  vs voice');
  const all = {voice: [], musicSpeech: [], musicGap: []};
  tm.scenes.forEach((s, n) => {
    const speech = tm.speech.filter(([a, b]) => a >= s.start - 0.01 && b <= s.end + 0.01);
    const prev = n ? tm.speech.filter(([, b]) => b <= s.start + 0.01).at(-1) : null;
    const first = speech[0];
    // The gap: from the previous scene's last word (or the start) to this scene's first word, less
    // the duck ramps on either side, so it measures the level the music comes up to.
    const gap = first ? [[(prev ? prev[1] + 0.5 : 0), first[0] - 0.3]].filter(([a, b]) => b - a > 0.2) : [];
    const v = lufsOver(stems.voice, speech);
    const m = lufsOver(stems.music, speech);
    const g = lufsOver(stems.music, gap);
    all.voice.push(...speech);
    all.musicGap.push(...gap);
    console.log(`  ${s.id.padEnd(9)} ${fmt(v)} ${fmt(m)} ${fmt(v !== null && m !== null ? m - v : null)} |    ${fmt(g)}   ${fmt(g !== null && v !== null ? g - v : null)}`);
  });
  const V = lufsOver(stems.voice, all.voice);
  const M = lufsOver(stems.music, all.voice);
  const G = lufsOver(stems.music, all.musicGap);
  console.log(`  ${'ALL'.padEnd(9)} ${fmt(V)} ${fmt(M)} ${fmt(M - V)} |    ${fmt(G)}   ${fmt(G - V)}`);
}
