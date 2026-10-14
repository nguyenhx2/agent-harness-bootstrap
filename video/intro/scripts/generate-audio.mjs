// Generate the intro's audio with ElevenLabs, once, into audio/. Costs API credit, so it only runs
// behind an explicit flag (render.sh --generate) and skips any asset already cached.
//
//   node scripts/generate-audio.mjs [voice|music|sfx|all] [en|ja] [--force]
//
// The key is read from ../../.env (ELEVENLABS_API_KEY) or the environment. It is held in memory,
// sent only in the xi-api-key header, and never printed, logged or written anywhere.
import {existsSync, readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import path from 'node:path';
import {HERE, AUDIO, LANGS, TEMPO, readScript, narrationText, sha, narrationFile, alignmentFile} from './script.mjs';

const API = 'https://api.elevenlabs.io/v1';
const TTS_MODEL = 'eleven_multilingual_v2';
const VOICES = {
  // "Brian", an ElevenLabs premade voice: a calm, deep American narrator.
  en: {voice_id: 'nPczCjzI2devNBz1zQrb', name: 'Brian',
    voice_settings: {stability: 0.55, similarity_boost: 0.75, style: 0.1, use_speaker_boost: true}},
  // "Otani", a native Japanese narrator from the ElevenLabs voice library (standard accent,
  // middle-aged male, tagged for narration), so the Japanese clip is not an English voice reading
  // Japanese. Its natural pace is slow for a clip this dense, so render.sh plays it slightly faster
  // (TEMPO in script.mjs, pitch preserved) and the caption timing is scaled to match.
  ja: {voice_id: '3JDquces8E8bkmvbh6Bc', name: 'Otani',
    voice_settings: {stability: 0.55, similarity_boost: 0.75, style: 0.1, use_speaker_boost: true}},
};

const MUSIC_PROMPT =
  'Calm, confident minimal electronic underscore for a technical product explainer. Soft warm ' +
  'synth pads, a gentle muted pulse, light plucked arpeggio, steady 90 BPM, no drum hits that ' +
  'distract, no vocals, no melody that competes with a narrator. Gentle lift every twenty seconds ' +
  'or so, builds slightly in the middle, resolves calmly at the end.';

const SFX = {
  'sfx-whoosh': {text: 'A soft, airy cinematic whoosh transition, subtle and short', duration_seconds: 1.2},
  'sfx-block': {text: 'A low, muted digital thud, like a door locking shut in a clean UI, subtle', duration_seconds: 0.8},
  'sfx-chime': {text: 'A gentle, warm two-note confirmation chime, clean and minimal', duration_seconds: 1.5},
};

// Seconds of picture before the first word, and the end-card hold after the last one. The timing
// build uses the same two numbers; the music has to cover both.
const LEAD_IN = 1.0;
const TAIL = 4.0;

function apiKey() {
  if (process.env.ELEVENLABS_API_KEY) return process.env.ELEVENLABS_API_KEY.trim();
  const envFile = path.resolve(HERE, '..', '..', '.env');
  if (existsSync(envFile)) {
    for (const line of readFileSync(envFile, 'utf8').split(/\r?\n/)) {
      const m = line.match(/^\s*ELEVENLABS_API_KEY\s*=\s*"?([^"\s]+)"?\s*$/);
      if (m) return m[1];
    }
  }
  throw new Error('ELEVENLABS_API_KEY is not set (looked in the environment and the repo .env)');
}

let calls = 0;
async function post(url, body, key) {
  calls += 1;
  const res = await fetch(url, {
    method: 'POST',
    headers: {'xi-api-key': key, 'content-type': 'application/json'},
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    // The response body never echoes the key, but keep the message short regardless.
    const detail = (await res.text()).slice(0, 400);
    throw new Error(`${url.replace(API, '')} -> HTTP ${res.status}: ${detail}`);
  }
  return res;
}

// Bytes from the API are written only after they prove to be audio: an MP3 starts with an ID3 tag
// or an MPEG frame sync, and nothing here needs more than 20 MB. A proxy error page or a changed
// response shape then fails loudly instead of landing in a committed .mp3.
const MAX_AUDIO = 20 * 1024 * 1024;
function audioBytes(buf, what) {
  const b = Buffer.from(buf);
  const id3 = b.length > 3 && b.toString('latin1', 0, 3) === 'ID3';
  const sync = b.length > 2 && b[0] === 0xff && (b[1] & 0xe0) === 0xe0;
  if (!(id3 || sync)) throw new Error(`${what}: response is not MP3 audio`);
  if (b.length > MAX_AUDIO) throw new Error(`${what}: ${b.length} bytes exceeds the ${MAX_AUDIO}-byte cap`);
  return b;
}

const manifestPath = path.join(AUDIO, 'ASSETS.json');
function loadManifest() {
  return existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, 'utf8')) : {};
}
function saveManifest(m) {
  // No timestamp: this file is committed, and a volatile byte makes every diff noise.
  writeFileSync(manifestPath, JSON.stringify(m, null, 2) + '\n');
}

async function voice(key, lang, force) {
  const out = narrationFile(lang);
  const text = narrationText(readScript(lang));
  const m = loadManifest();
  const same = m.narration?.[lang]?.text_sha256 === sha(text);
  if (existsSync(out) && !force) {
    console.log(`  cached  ${path.basename(out)}${same ? '' : '  (SCRIPT changed: pass --force to regenerate)'}`);
    return;
  }
  const v = VOICES[lang];
  const res = await post(
    `${API}/text-to-speech/${v.voice_id}/with-timestamps?output_format=mp3_44100_128`,
    {text, model_id: TTS_MODEL, voice_settings: v.voice_settings},
    key,
  );
  const j = await res.json();
  writeFileSync(out, audioBytes(Buffer.from(String(j.audio_base64 ?? ''), 'base64'), 'narration'));
  writeFileSync(alignmentFile(lang), JSON.stringify({alignment: j.alignment}, null, 0) + '\n');
  const m2 = loadManifest();
  m2.narration = m2.narration && !m2.narration.voice_id ? m2.narration : {};
  m2.narration[lang] = {endpoint: 'POST /v1/text-to-speech/{voice_id}/with-timestamps',
    voice_id: v.voice_id, voice_name: v.name, model_id: TTS_MODEL, voice_settings: v.voice_settings,
    text_sha256: sha(text)};
  saveManifest(m2);
  console.log(`  wrote   ${path.basename(out)} + ${path.basename(alignmentFile(lang))}`);
}

async function music(key, force) {
  const out = path.join(AUDIO, 'music.mp3');
  // One bed for both languages, long enough for the longer narration.
  const ends = LANGS.filter((l) => existsSync(alignmentFile(l))).map((l) =>
    JSON.parse(readFileSync(alignmentFile(l), 'utf8')).alignment.character_end_times_seconds.at(-1) / TEMPO[l]);
  if (!ends.length) throw new Error('no narration alignment yet: generate the voice first');
  const ms = Math.ceil(LEAD_IN + Math.max(...ends) + TAIL + 1) * 1000;
  const m = loadManifest();
  if (existsSync(out) && !force) {
    const have = m.music?.music_length_ms ?? 0;
    console.log(`  cached  music.mp3${have < ms ? `  (only ${have} ms, ${ms} ms needed: pass --force)` : ''}`);
    return;
  }
  const body = {prompt: MUSIC_PROMPT, music_length_ms: ms, model_id: 'music_v1', force_instrumental: true};
  const res = await post(`${API}/music?output_format=mp3_44100_128`, body, key);
  writeFileSync(out, audioBytes(await res.arrayBuffer(), 'music'));
  m.music = {endpoint: 'POST /v1/music', ...body};
  saveManifest(m);
  console.log(`  wrote   music.mp3 (${ms} ms requested)`);
}

async function sfx(key, force) {
  const m = loadManifest();
  m.sfx = m.sfx || {};
  for (const [name, body] of Object.entries(SFX)) {
    const out = path.join(AUDIO, `${name}.mp3`);
    if (existsSync(out) && !force) {
      console.log(`  cached  ${name}.mp3`);
      continue;
    }
    const res = await post(`${API}/sound-generation`, {...body, prompt_influence: 0.5}, key);
    writeFileSync(out, audioBytes(await res.arrayBuffer(), name));
    m.sfx[name] = {endpoint: 'POST /v1/sound-generation', ...body, prompt_influence: 0.5};
    console.log(`  wrote   ${name}.mp3`);
  }
  saveManifest(m);
}

const args = process.argv.slice(2);
const words = args.filter((a) => !a.startsWith('--'));
const what = words.find((w) => ['voice', 'music', 'sfx', 'all'].includes(w)) || 'all';
const langs = words.filter((w) => LANGS.includes(w));
const force = args.includes('--force');
mkdirSync(AUDIO, {recursive: true});
const key = apiKey();
try {
  if (what === 'voice' || what === 'all') for (const l of langs.length ? langs : LANGS) await voice(key, l, force);
  if (what === 'music' || what === 'all') await music(key, force);
  if (what === 'sfx' || what === 'all') await sfx(key, force);
} finally {
  console.log(`  ElevenLabs calls this run: ${calls}`);
}
