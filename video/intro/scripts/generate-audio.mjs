// Generate the intro's audio with ElevenLabs, once, into audio/. Costs API credit, so it only runs
// behind an explicit flag (render.sh --generate) and skips any asset already cached.
//
//   node scripts/generate-audio.mjs [voice|questions|music|sfx|all] [en|ja] [--force]
//
// The key is read from ../../.env (ELEVENLABS_API_KEY) or the environment. It is held in memory,
// sent only in the xi-api-key header, and never printed, logged or written anywhere.
import {existsSync, readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import path from 'node:path';
import {HERE, AUDIO, LANGS, LEAD_IN, TAIL, SCENE_GAP, readScript, narrationText, sha, narrationFile, alignmentFile,
  isQuestion, questionFile, questionText} from './script.mjs';

const API = 'https://api.elevenlabs.io/v1';

// The most natural model first. The key has no models_read scope, so availability cannot be asked
// for: each model is tried in turn, and an error (no access, no timestamps) falls through to the
// next. The model that answered is recorded in audio/ASSETS.json.
//   eleven_v3: stability is a mode, not a dial: 0 creative, 0.5 natural, 1 robust.
//   eleven_multilingual_v2: lower stability and a little style read as spoken, not recited.
const MODELS = [
  {model_id: 'eleven_v3', voice_settings: {stability: 0.5, similarity_boost: 0.75, use_speaker_boost: true}},
  {model_id: 'eleven_multilingual_v2',
    voice_settings: {stability: 0.4, similarity_boost: 0.75, style: 0.25, use_speaker_boost: true}},
];

const VOICES = {
  // The narrator has to sound like someone who knows the subject, not a friendly host.
  // "Klara - Tech Executive & Scientist", a voice-library voice: crisp, articulate and authoritative,
  // a West Coast American woman.
  en: {voice_id: 'KLdWtAstZMPBbfqaBs59', name: 'Klara'},
  // "Konoha - Professional JP Explainer", a native Japanese woman from the voice library, Kanto
  // accent, a calm mid-range voice built for explainers.
  ja: {voice_id: 'T7yYq3WpB94yAuOXraRi', name: 'Konoha'},
};

// The viewer asking the questions: a second, contrasting voice, so a question is heard as someone
// asking and the answer as the narrator replying. Both are young men, tagged conversational.
const ASKERS = {
  // "Mark - Natural Conversations": a casual young American speaking in a natural manner.
  en: {voice_id: 'UgBBYS2sOqTuMpoF3BR0', name: 'Mark'},
  // "Asahi - Calm and Natural": a young native Japanese man, standard accent.
  ja: {voice_id: 'GKDaBI8TKSBJVhsCLD6n', name: 'Asahi'},
};

const MUSIC_PROMPT =
  'Modern, warm, light tech ambient bed for a friendly product explainer. Soft analog synth pads, ' +
  'a steady gentle pulse from a muted kick and soft shaker at 100 BPM, a light plucked arpeggio, ' +
  'warm sub bass. Optimistic and calm, never dramatic. No vocals, no lead melody that competes ' +
  'with a narrator. Present and audible throughout, consistent energy, a gentle lift every half ' +
  'minute, resolves warmly at the end.';

const SFX = {
  'sfx-whoosh': {text: 'A soft, airy cinematic whoosh transition, subtle and short', duration_seconds: 1.2},
  'sfx-block': {text: 'A low, muted digital thud, like a door locking shut in a clean UI, subtle', duration_seconds: 0.8},
  'sfx-chime': {text: 'A gentle, warm two-note confirmation chime, clean and minimal', duration_seconds: 1.5},
};


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
  let j = null;
  let used = null;
  for (const m of MODELS) {
    try {
      const res = await post(
        `${API}/text-to-speech/${v.voice_id}/with-timestamps?output_format=mp3_44100_128`,
        {text, model_id: m.model_id, voice_settings: m.voice_settings},
        key,
      );
      const body = await res.json();
      if (!body.alignment?.characters?.length) throw new Error(`${m.model_id}: no character alignment`);
      j = body;
      used = m;
      break;
    } catch (e) {
      console.log(`  ${m.model_id} unavailable for ${lang}: ${String(e.message).slice(0, 160)}`);
    }
  }
  if (!j) throw new Error(`no model produced a ${lang} narration`);
  writeFileSync(out, audioBytes(Buffer.from(String(j.audio_base64 ?? ''), 'base64'), 'narration'));
  writeFileSync(alignmentFile(lang), JSON.stringify({alignment: j.alignment}, null, 0) + '\n');
  const m2 = loadManifest();
  m2.narration = m2.narration && !m2.narration.voice_id ? m2.narration : {};
  m2.narration[lang] = {endpoint: 'POST /v1/text-to-speech/{voice_id}/with-timestamps',
    voice_id: v.voice_id, voice_name: v.name, model_id: used.model_id, voice_settings: used.voice_settings,
    text_sha256: sha(text)};
  saveManifest(m2);
  console.log(`  wrote   ${path.basename(out)} + ${path.basename(alignmentFile(lang))}`);
}

/** One file per question, in the asker's voice. No alignment is needed: a question is one cue. */
async function questions(key, lang, force) {
  const v = ASKERS[lang];
  for (const scene of readScript(lang)) {
    const cue = scene.cues.find(isQuestion);
    if (!cue) continue;
    const out = questionFile(lang, scene.id);
    const text = questionText(cue);
    const m = loadManifest();
    const same = m.questions?.[lang]?.[scene.id]?.text_sha256 === sha(text);
    if (existsSync(out) && !force && same) {
      console.log(`  cached  ${path.basename(out)}`);
      continue;
    }
    let used = null;
    for (const mod of MODELS) {
      try {
        const res = await post(`${API}/text-to-speech/${v.voice_id}?output_format=mp3_44100_128`,
          {text, model_id: mod.model_id, voice_settings: mod.voice_settings}, key);
        writeFileSync(out, audioBytes(await res.arrayBuffer(), `question ${scene.id}`));
        used = mod;
        break;
      } catch (e) {
        console.log(`  ${mod.model_id} unavailable for ${lang}/${scene.id}: ${String(e.message).slice(0, 160)}`);
      }
    }
    if (!used) throw new Error(`no model produced the ${lang} question for ${scene.id}`);
    const m2 = loadManifest();
    m2.questions = m2.questions || {};
    m2.questions[lang] = m2.questions[lang] || {};
    m2.questions[lang][scene.id] = {endpoint: 'POST /v1/text-to-speech/{voice_id}', voice_id: v.voice_id,
      voice_name: v.name, model_id: used.model_id, voice_settings: used.voice_settings, text_sha256: sha(text)};
    saveManifest(m2);
    console.log(`  wrote   ${path.basename(out)}`);
  }
}

async function music(key, force) {
  const out = path.join(AUDIO, 'music.mp3');
  // One bed for both languages, long enough for the longer narration.
  const ends = LANGS.filter((l) => existsSync(alignmentFile(l))).map((l) =>
    JSON.parse(readFileSync(alignmentFile(l), 'utf8')).alignment.character_end_times_seconds.at(-1)
    + SCENE_GAP * readScript(l).length);
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
const what = words.find((w) => ['voice', 'questions', 'music', 'sfx', 'all'].includes(w)) || 'all';
const langs = words.filter((w) => LANGS.includes(w));
const force = args.includes('--force');
mkdirSync(AUDIO, {recursive: true});
const key = apiKey();
try {
  if (what === 'voice' || what === 'all') for (const l of langs.length ? langs : LANGS) await voice(key, l, force);
  if (what === 'questions' || what === 'all') for (const l of langs.length ? langs : LANGS) await questions(key, l, force);
  if (what === 'music' || what === 'all') await music(key, force);
  if (what === 'sfx' || what === 'all') await sfx(key, force);
} finally {
  console.log(`  ElevenLabs calls this run: ${calls}`);
}
