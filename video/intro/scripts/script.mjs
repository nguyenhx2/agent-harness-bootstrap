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

// Seconds of picture before the first word, and the end-card hold after the last one.
export const LEAD_IN = 1.0;
export const TAIL = 4.0;

// The narration is one recording per language, played at its natural pace (no tempo change). It is
// cut at every scene boundary, in the middle of the pause the voice already left there, and each
// scene's piece is placed this many seconds later than the one before, so the music has a moment
// to come up between scenes. `lean` continues `safe`'s question, so it gets only a short breath.
export const SCENE_GAP = 1.1;
export const SCENE_GAP_FOR = {lean: 0.3};
export const gapBefore = (id, n) => (n === 0 ? 0 : SCENE_GAP_FOR[id] ?? SCENE_GAP);

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
