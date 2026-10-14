// Parse SCRIPT.md (English) or SCRIPT.ja.md (Japanese) into scenes and caption cues. Shared by the
// generator and the timing build, so the text the voice speaks and the text the captions show are
// the same string by construction.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

export const HERE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const AUDIO = path.join(HERE, 'audio');
export const LANGS = ['en', 'ja'];

// Playback tempo of each narration. render.sh applies it with ffmpeg's atempo (pitch preserved)
// before Remotion mixes the clip, and build-timing.mjs divides every aligned time by it, so the
// captions follow the voice actually heard. The Japanese voice reads its script in about 160 s at
// its own pace, which is long for a clip this dense.
export const TEMPO = {en: 1.0, ja: 1.12};

export const scriptFile = (lang) => path.join(HERE, lang === 'en' ? 'SCRIPT.md' : `SCRIPT.${lang}.md`);
export const narrationFile = (lang) => path.join(AUDIO, `narration.${lang}.mp3`);
export const alignmentFile = (lang) => path.join(AUDIO, `narration.${lang}.alignment.json`);

export function readScript(lang = 'en') {
  const md = readFileSync(scriptFile(lang), 'utf8').replace(/\r\n/g, '\n');
  const scenes = [];
  let cur = null;
  for (const line of md.split('\n')) {
    const h = line.match(/^## (\S+)\s*$/);
    if (h) {
      cur = {id: h[1], cues: []};
      scenes.push(cur);
      continue;
    }
    if (line.startsWith('## ')) {
      cur = null; // a heading with spaces ("## On-screen figures") is prose, not a scene
      continue;
    }
    const c = line.match(/^- (.+)$/);
    if (c && cur) cur.cues.push(c[1].trim());
  }
  const spoken = scenes.filter((s) => s.cues.length);
  if (spoken.length < 3) throw new Error(`${path.basename(scriptFile(lang))}: fewer than three scenes parsed`);
  return spoken;
}

// The exact string sent to the voice: every cue, in order, joined by one space.
export function narrationText(scenes) {
  return scenes.flatMap((s) => s.cues).join(' ');
}

export function sha(s) {
  return createHash('sha256').update(s).digest('hex');
}
