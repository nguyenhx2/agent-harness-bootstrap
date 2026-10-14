import React, {createContext, useContext} from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import timingEn from './timing.en.json';
import timingJa from './timing.ja.json';
import figures from './figures.json';
import {ICONS, IconName} from './icons';
import {C, FONT, FONT_JA, MONO, enter, ramp} from './theme';
import {Lang, STRINGS, Strings} from './strings';

type Timing = typeof timingEn;
const TIMING: Record<Lang, Timing> = {en: timingEn, ja: timingJa as Timing};

// ---------------------------------------------------------------- context

type Ctx = {lang: Lang; tm: Timing; S: Strings};
const LangCtx = createContext<Ctx>({lang: 'en', tm: timingEn, S: STRINGS.en});
const useL = () => useContext(LangCtx);

/** Start time (s) of the n-th cue of a scene. Every visual beat hangs off a spoken line. */
const cueOf = (tm: Timing, scene: string, n: number) => tm.cues.filter((c) => c.scene === scene)[n];
const useCue = () => {
  const {tm} = useL();
  return (scene: string, n: number) => cueOf(tm, scene, n).start;
};
/** A moment a fraction of the way through a cue: for a beat on a word inside a long line. */
const useAt = () => {
  const {tm} = useL();
  return (scene: string, n: number, frac: number) => {
    const c = cueOf(tm, scene, n);
    return c.start + (c.end - c.start) * frac;
  };
};
const useScene = () => {
  const {tm} = useL();
  return (id: string) => tm.scenes.find((s) => s.id === id)!;
};

// ---------------------------------------------------------------- audio

const DUCK_LOW = 0.07;
const DUCK_HIGH = 0.26;
const DUCK_RAMP = 0.3;

/** Music gain at time t: low under every speech run, back up in real gaps, faded at both ends. */
const musicGain = (tm: Timing, t: number) => {
  let duck = 0;
  for (const [s, e] of tm.speech) {
    const k = Math.min(
      interpolate(t, [s - DUCK_RAMP, s], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
      interpolate(t, [e, e + DUCK_RAMP * 1.6], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
    );
    duck = Math.max(duck, k);
  }
  const level = DUCK_HIGH + (DUCK_LOW - DUCK_HIGH) * duck;
  const fadeIn = interpolate(t, [0, 1.2], [0, 1], {extrapolateRight: 'clamp'});
  const fadeOut = interpolate(t, [tm.total - 2.5, tm.total], [1, 0], {extrapolateLeft: 'clamp'});
  return level * fadeIn * fadeOut;
};

const Sfx: React.FC<{at: number; src: string; volume: number}> = ({at, src, volume}) => {
  const {fps} = useVideoConfig();
  return (
    <Sequence from={Math.max(0, Math.round(at * fps))} layout="none">
      <Audio src={staticFile(src)} volume={volume} />
    </Sequence>
  );
};

const QUESTIONS = ['team', 'safe', 'keys', 'loop', 'spec', 'control', 'assess'];

const Soundtrack = () => {
  const {fps} = useVideoConfig();
  const {lang, tm} = useL();
  const cue = useCue();
  const scene = useScene();
  // render.sh writes the tempo-adjusted copy; at tempo 1 the cached file plays as it is.
  const voice = tm.tempo === 1 ? `narration.${lang}.mp3` : `narration.${lang}.paced.mp3`;
  return (
    <>
      <Audio src={staticFile('music.mp3')} volume={(f) => musicGain(tm, f / fps)} />
      <Sequence from={Math.round(tm.leadIn * fps)} layout="none">
        <Audio src={staticFile(voice)} volume={1} />
      </Sequence>
      {QUESTIONS.map((q) => (
        <Sfx key={q} at={cue(q, 0) - 0.25} src="sfx-whoosh.mp3" volume={0.22} />
      ))}
      <Sfx at={cue('safe', 2) + 1.2} src="sfx-block.mp3" volume={0.55} />
      <Sfx at={scene('close').start + 0.2} src="sfx-chime.mp3" volume={0.4} />
    </>
  );
};

// ---------------------------------------------------------------- shared pieces

// Deliberately still. A moving background changes every pixel of every frame, which reads as
// texture in the MP4 but more than doubles the README GIF, and carries no meaning either way.
const Background: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: C.bg}}>
    <AbsoluteFill
      style={{
        backgroundImage: `linear-gradient(${C.line}55 1px, transparent 1px), linear-gradient(90deg, ${C.line}55 1px, transparent 1px)`,
        backgroundSize: '64px 64px',
        maskImage: 'radial-gradient(ellipse at center, black 30%, transparent 75%)',
        WebkitMaskImage: 'radial-gradient(ellipse at center, black 30%, transparent 75%)',
      }}
    />
    <AbsoluteFill style={{background: `radial-gradient(900px 600px at 960px 460px, ${C.greenDeep}33, transparent 70%)`}} />
  </AbsoluteFill>
);

/** A Heroicons outline icon (24 x 24 grid, stroke 1.5), vendored in icons.ts. */
const Icon: React.FC<{name: IconName; size?: number; color?: string; style?: React.CSSProperties}> = ({
  name,
  size = 40,
  color = C.text,
  style,
}) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth={1.5}
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{flexShrink: 0, ...style}}
  >
    {ICONS[name].map((d, i) => (
      <path key={i} d={d} />
    ))}
  </svg>
);

const Card: React.FC<{color?: string; style?: React.CSSProperties; children: React.ReactNode}> = ({
  color = C.line,
  style,
  children,
}) => (
  <div
    style={{
      background: C.panel,
      border: `2px solid ${color}`,
      borderRadius: 18,
      padding: '20px 28px',
      color: C.text,
      fontSize: 32,
      ...style,
    }}
  >
    {children}
  </div>
);

const Chip: React.FC<{color: string; children: React.ReactNode; style?: React.CSSProperties}> = ({color, children, style}) => (
  <span
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 10,
      fontFamily: MONO,
      fontSize: 24,
      fontWeight: 600,
      color,
      border: `2px solid ${color}`,
      borderRadius: 10,
      padding: '4px 14px',
      whiteSpace: 'nowrap',
      ...style,
    }}
  >
    {children}
  </span>
);

/** Inline `code` spans inside a label: backticked runs render in the mono face. */
const Rich: React.FC<{text: string; codeColor?: string}> = ({text, codeColor = C.green}) => (
  <>
    {text.split('`').map((part, i) =>
      i % 2 ? (
        <span key={i} style={{fontFamily: MONO, color: codeColor, fontSize: '0.9em'}}>
          {part}
        </span>
      ) : (
        <React.Fragment key={i}>{part}</React.Fragment>
      ),
    )}
  </>
);

/** The solution area: below the docked question, above the captions. */
const Stage: React.FC<{children: React.ReactNode; top?: number}> = ({children, top = 215}) => (
  <div
    style={{
      position: 'absolute',
      left: 110,
      right: 110,
      top,
      bottom: 210,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}
  >
    {children}
  </div>
);

const Kicker: React.FC<{t: number; at: number; id: string}> = ({t, at, id}) => {
  const {S} = useL();
  return (
    <div
      style={{
        position: 'absolute',
        top: 34,
        right: 110,
        fontFamily: MONO,
        fontSize: 22,
        letterSpacing: 3,
        textTransform: 'uppercase',
        color: C.dim,
        ...enter(t, at, 0.5, 8),
      }}
    >
      {S.kicker[id]}
    </div>
  );
};

const stripQuotes = (s: string) => s.replace(/^["「]|["」]$/g, '');

/**
 * The pain point. It pops up centre-stage as a speech bubble from "you" while the question is
 * spoken, then docks to the top left and stays there while the answer plays under it.
 */
const Bubble: React.FC<{t: number; text: string; at: number; dockAt: number; still?: boolean}> = ({t, text, at, dockAt, still}) => {
  const {lang, S} = useL();
  const k = still ? 1 : ramp(t, dockAt, 0.7);
  const pop = still ? 1 : ramp(t, at - 0.2, 0.45);
  const scale = (0.86 + 0.14 * pop) * (1 - 0.44 * k);
  const left = interpolate(k, [0, 1], [960, 96]);
  const top = interpolate(k, [0, 1], [470, 40]);
  const tx = interpolate(k, [0, 1], [-50, 0]);
  return (
    <div
      style={{
        position: 'absolute',
        left,
        top,
        transformOrigin: 'left top',
        transform: `translate(${tx}%, ${tx}%) scale(${scale})`,
        opacity: pop,
        display: 'flex',
        alignItems: 'flex-end',
        gap: 26,
        width: 1500,
      }}
    >
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8}}>
        <div
          style={{
            width: 104,
            height: 104,
            borderRadius: '50%',
            border: `3px solid ${C.blue}`,
            background: `${C.blueDeep}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Icon name="user" size={60} color={C.blue} />
        </div>
        <div style={{fontSize: 24, color: C.blue}}>{S.you}</div>
      </div>
      <div
        style={{
          position: 'relative',
          background: `${C.blueDeep}cc`,
          border: `3px solid ${C.blue}`,
          borderRadius: 34,
          padding: '28px 44px',
          fontSize: lang === 'ja' ? 50 : 56,
          lineHeight: 1.28,
          fontWeight: 600,
          color: C.text,
          maxWidth: 1340,
          marginBottom: 46,
        }}
      >
        {lang === 'ja'
          ? wrapJa(stripQuotes(text), 24, 25).map((l, i) => (
              <div key={i} style={{whiteSpace: 'nowrap'}}>
                {l}
              </div>
            ))
          : stripQuotes(text)}
        <svg width={40} height={36} style={{position: 'absolute', left: -3, bottom: -33}}>
          <path d="M3 0 L3 33 L36 0" fill={C.blueDeep} stroke={C.blue} strokeWidth={3} strokeLinejoin="round" />
          <rect x={4.5} y={-3} width={31} height={4.5} fill={C.blueDeep} />
        </svg>
      </div>
    </div>
  );
};

/** The scene's own question, popping then docking. Scenes that continue a question pass `from`. */
const Question: React.FC<{t: number; id: string; from?: string}> = ({t, id, from}) => {
  const {tm} = useL();
  const cue = useCue();
  const q = from ?? id;
  const text = cueOf(tm, q, 0).text;
  return <Bubble t={t} text={text} at={cue(q, 0)} dockAt={cue(q, 1) - 0.45} still={!!from} />;
};

/** A row with an icon badge, a title and an optional line under it. */
const Row: React.FC<{icon: IconName; color: string; title: React.ReactNode; sub?: React.ReactNode; style?: React.CSSProperties}> = ({
  icon,
  color,
  title,
  sub,
  style,
}) => (
  <div style={{display: 'flex', alignItems: 'center', gap: 24, ...style}}>
    <div
      style={{
        width: 70,
        height: 70,
        borderRadius: 16,
        border: `2px solid ${color}`,
        background: `${color}1f`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      <Icon name={icon} size={40} color={color} />
    </div>
    <div>
      <div style={{fontSize: 33, fontWeight: 600, color: C.text}}>{title}</div>
      {sub ? <div style={{fontSize: 25, color: C.dim, marginTop: 4}}>{sub}</div> : null}
    </div>
  </div>
);

// ---------------------------------------------------------------- scenes

const Open: React.FC<{t: number}> = ({t}) => {
  const {S, lang} = useL();
  const cue = useCue();
  const frame = ramp(t, cue('open', 1), 1.0);
  const perim = 2 * (1060 + 300);
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', paddingBottom: 150}}>
      <div style={{textAlign: 'center'}}>
        <div style={{display: 'flex', justifyContent: 'center', ...enter(t, 0.2, 0.6)}}>
          <div style={{width: 120, height: 120, borderRadius: 26, border: `4px solid ${C.green}`, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <Icon name="cpu-chip" size={74} color={C.purple} />
          </div>
        </div>
        <div style={{fontSize: 92, fontWeight: 800, color: C.text, letterSpacing: -2, marginTop: 30, ...enter(t, 0.4, 0.6)}}>{S.title}</div>
        <div style={{position: 'relative', width: 1140, height: 320, margin: '46px auto 0'}}>
          <svg width={1140} height={320} style={{position: 'absolute', left: 0, top: 0}}>
            <rect x={40} y={10} width={1060} height={300} rx={26} fill="none" stroke={C.green} strokeWidth={5} strokeDasharray={perim} strokeDashoffset={perim * (1 - frame)} />
          </svg>
          <div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 30}}>
            <div style={{fontSize: lang === 'ja' ? 50 : 52, color: C.text, ...enter(t, cue('open', 0) + 0.6, 0.6)}}>{S.soul1}</div>
            <div style={{fontSize: lang === 'ja' ? 50 : 52, color: C.green, fontWeight: 700, ...enter(t, cue('open', 1), 0.6)}}>{S.soul2}</div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const PROFILE_ICON: Record<string, IconName> = {code: 'code-bracket', research: 'beaker', strategy: 'light-bulb', docs: 'book-open'};

const Team: React.FC<{t: number}> = ({t}) => {
  const {S} = useL();
  const cue = useCue();
  const at = useAt();
  const a = cue('team', 1);
  const b = cue('team', 2);
  return (
    <>
      <Kicker t={t} at={cue('team', 1) - 0.4} id="team" />
      <Question t={t} id="team" />
      <Stage>
        <div style={{display: 'flex', gap: 40, alignItems: 'stretch'}}>
          <Card color={C.green} style={{width: 470, ...enter(t, a, 0.5)}}>
            <Icon name="magnifying-glass" size={64} color={C.green} />
            <div style={{fontSize: 36, fontWeight: 700, marginTop: 16}}>{S.readsCode}</div>
            <div style={{fontSize: 27, color: C.dim, marginTop: 10}}>{S.readsCodeSub}</div>
          </Card>
          <Card color={C.green} style={{width: 560, ...enter(t, at('team', 1, 0.45), 0.5)}}>
            <div style={{fontSize: 32, fontWeight: 700, marginBottom: 18}}>{S.purposeQ}</div>
            <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16}}>
              {figures.profiles.map((p, i) => (
                <div
                  key={p}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 14,
                    border: `2px solid ${C.line}`,
                    borderRadius: 12,
                    padding: '12px 14px',
                    fontSize: 27,
                    whiteSpace: 'nowrap',
                    ...enter(t, at('team', 1, 0.62 + i * 0.09), 0.4),
                  }}
                >
                  <Icon name={PROFILE_ICON[p] ?? 'document-text'} size={34} color={C.green} />
                  {S.profile[p] ?? p}
                </div>
              ))}
            </div>
          </Card>
          <Card color={C.purple} style={{width: 520, textAlign: 'center', ...enter(t, b, 0.5)}}>
            <Icon name="user-group" size={64} color={C.purple} />
            <div style={{fontSize: 80, fontWeight: 800, color: C.text, lineHeight: 1.1, marginTop: 6}}>
              {S.rosterBig(figures.roster_min, figures.roster_max)}
            </div>
            <div style={{fontSize: 30, color: C.text}}>{S.rosterOf(figures.seats)}</div>
            <div style={{fontSize: 26, color: C.dim, marginTop: 14, whiteSpace: 'pre-line'}}>{S.rosterSub}</div>
            <div style={{fontSize: 26, color: C.green, marginTop: 6, ...enter(t, at('team', 2, 0.7), 0.4)}}>{S.rosterNever}</div>
          </Card>
        </div>
      </Stage>
    </>
  );
};

const Safe: React.FC<{t: number}> = ({t}) => {
  const {S} = useL();
  const cue = useCue();
  const a = cue('safe', 1);
  const b = cue('safe', 2);
  const cmd = 'git push --force origin main';
  const typed = Math.floor(interpolate(t, [b, b + 1.1], [0, cmd.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const blocked = ramp(t, b + 1.2, 0.25);
  const n = figures.eval_cases;
  return (
    <>
      <Kicker t={t} at={a - 0.4} id="safe" />
      <Question t={t} id="safe" />
      <Stage>
        <div style={{display: 'flex', gap: 44, alignItems: 'stretch'}}>
          <div style={{display: 'flex', flexDirection: 'column', gap: 28, width: 1000}}>
            <Card style={{fontFamily: MONO, fontSize: 36, minHeight: 200, ...enter(t, a + 0.2, 0.5)}}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14}}>
                <span style={{fontSize: 22, color: C.dim}}>agent $</span>
                <Chip color={C.green} style={{fontFamily: FONT_OR(S), ...enter(t, b, 0.4)}}>
                  <Icon name="check-circle" size={24} color={C.green} /> {S.byDefault}
                </Chip>
              </div>
              <span style={{color: C.purple}}>$ </span>
              {cmd.slice(0, typed)}
              <div style={{display: 'flex', alignItems: 'center', gap: 16, marginTop: 20, color: C.red, fontWeight: 600, opacity: blocked}}>
                <Icon name="no-symbol" size={44} color={C.red} />
                {S.blocked}
                <span style={{color: C.dim, fontWeight: 400, fontSize: 28}}>{S.blockedBy}</span>
              </div>
              <div style={{fontFamily: FONT_OR(S), fontSize: 26, color: C.dim, marginTop: 8, opacity: blocked}}>{S.neverLands}</div>
            </Card>
            <Card color={C.green} style={{display: 'flex', alignItems: 'center', gap: 22, ...enter(t, b + 2.2, 0.5)}}>
              <Icon name="check-circle" size={52} color={C.green} />
              <div>
                <div style={{fontFamily: MONO, fontSize: 34, color: C.green, fontWeight: 600}}>{S.evalLine(n)}</div>
                <div style={{fontSize: 24, color: C.dim, marginTop: 4}}>{S.evalSub}</div>
              </div>
            </Card>
          </div>
          <Card color={C.red} style={{width: 560, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 18, ...enter(t, a, 0.5)}}>
            <Icon name="shield-check" size={84} color={C.red} />
            <div style={{fontSize: 36, fontWeight: 700, whiteSpace: 'pre-line'}}>{S.hooksLine(figures.hooks)}</div>
            <div style={{display: 'flex', alignItems: 'center', gap: 14, fontSize: 30, color: C.green, ...enter(t, cue('safe', 1) + 1.2, 0.5)}}>
              <Icon name="cpu-chip" size={40} color={C.dim} />
              {S.noModel}
            </div>
          </Card>
        </div>
      </Stage>
    </>
  );
};

// Mono labels in a Japanese line need the Japanese face for the CJK part.
const FONT_OR = (S: Strings) => (S === STRINGS.ja ? FONT_JA : FONT);

const Lean: React.FC<{t: number}> = ({t}) => {
  const {S} = useL();
  const cue = useCue();
  const at = useAt();
  const beats = [cue('lean', 0), cue('lean', 1), at('lean', 1, 0.62), cue('lean', 2)];
  const rows = S.lean;
  return (
    <>
      <Kicker t={t} at={-1} id="lean" />
      <Question t={t} id="lean" from="safe" />
      <Stage>
        <Card style={{width: 1500, padding: '26px 40px', display: 'flex', flexDirection: 'column', gap: 24}}>
          {rows.map((r, i) => {
            const k = ramp(t, beats[i], 0.45);
            const title =
              i === 2 ? S.rounds(figures.review_rounds) : (
                <>
                  <span style={{fontFamily: MONO, color: C.green, fontSize: 28, marginRight: 16}}>{r.title}</span>
                  {r.text}
                </>
              );
            const sub =
              i === 2 ? S.roundsSub(figures.review_rounds) : i === 3 ? (
                <span style={{display: 'flex', gap: 14, marginTop: 6}}>
                  <Chip color={C.purple}>{S.depth(figures.spawn_depth)}</Chip>
                  <Chip color={C.purple}>{S.concurrent(figures.max_subagents)}</Chip>
                </span>
              ) : (
                r.sub
              );
            return (
              <Row
                key={i}
                icon={r.icon as IconName}
                color={i === 3 ? C.purple : C.green}
                title={title}
                sub={sub}
                style={{opacity: k, transform: `translateX(${(1 - k) * -24}px)`}}
              />
            );
          })}
        </Card>
      </Stage>
    </>
  );
};

const Keys: React.FC<{t: number}> = ({t}) => {
  const {S} = useL();
  const cue = useCue();
  const a = cue('keys', 1);
  const b = cue('keys', 2);
  const files: [string, boolean][] = [
    ['.env', false],
    ['.env.local', false],
    ['secrets/', false],
    ['deploy.pem', false],
    ['.env.example', true],
  ];
  return (
    <>
      <Kicker t={t} at={a - 0.4} id="keys" />
      <Question t={t} id="keys" />
      <Stage>
        <div style={{display: 'flex', flexDirection: 'column', gap: 26}}>
          <div style={{display: 'flex', gap: 40}}>
            <Card color={C.red} style={{width: 640, ...enter(t, a, 0.5)}}>
              <div style={{display: 'flex', alignItems: 'center', gap: 16, marginBottom: 14}}>
                <Icon name="lock-closed" size={46} color={C.red} />
                <span style={{fontFamily: MONO, fontSize: 30, fontWeight: 600}}>{S.protectSecrets}</span>
                <Chip color={C.dim} style={{marginLeft: 'auto', fontSize: 20, fontFamily: FONT_OR(S)}}>{S.always}</Chip>
              </div>
              {files.map(([f, ok], i) => (
                <div key={f} style={{display: 'flex', alignItems: 'center', gap: 16, margin: '8px 0', ...enter(t, a + 0.4 + i * 0.35, 0.35)}}>
                  <Icon name={ok ? 'check-circle' : 'no-symbol'} size={34} color={ok ? C.green : C.red} />
                  <span style={{fontFamily: MONO, fontSize: 28, width: 280}}>{f}</span>
                  <span style={{fontSize: 24, color: ok ? C.green : C.red}}>{ok ? S.allowed : S.blockedWord}</span>
                </div>
              ))}
            </Card>
            <Card color={C.green} style={{width: 820, ...enter(t, b, 0.5)}}>
              <div style={{display: 'flex', alignItems: 'center', gap: 16, marginBottom: 18}}>
                <Icon name="eye-slash" size={46} color={C.green} />
                <span style={{fontFamily: MONO, fontSize: 30, fontWeight: 600}}>{S.envRead}</span>
              </div>
              <div style={{fontFamily: MONO, fontSize: 25, background: C.bg, borderRadius: 12, padding: '16px 20px', lineHeight: 1.6}}>
                <div style={{color: C.dim}}>$ python env-read.py run -- npm test</div>
                <div style={{...enter(t, b + 1.4, 0.4)}}>
                  {S.envOut} <span style={{color: C.green}}>[redacted:DATABASE_URL]</span>
                </div>
              </div>
              <div style={{fontSize: 26, color: C.dim, marginTop: 16, ...enter(t, b + 2.0, 0.4)}}>{S.envNote}</div>
            </Card>
          </div>
          <div style={{display: 'flex', gap: 40}}>
            <Card style={{width: 640, padding: '14px 24px', ...enter(t, b + 2.6, 0.5)}}>
              <Row icon="magnifying-glass" color={C.green} title={<span style={{fontSize: 27}}>{S.secretScan}</span>} sub={<span style={{fontSize: 21}}>{S.secretScanSub}</span>} />
            </Card>
            <Card style={{width: 820, padding: '14px 24px', borderStyle: 'dashed', ...enter(t, b + 3.2, 0.5)}}>
              <Row icon="key" color={C.dim} title={<span style={{fontFamily: MONO, fontSize: 26}}>{S.strict}</span>} sub={<span style={{fontSize: 21}}>{S.strictSub}</span>} />
            </Card>
          </div>
        </div>
      </Stage>
    </>
  );
};

const Loop: React.FC<{t: number}> = ({t}) => {
  const {S} = useL();
  const cue = useCue();
  const at = useAt();
  const a = cue('loop', 1);
  const b = cue('loop', 2);
  const steps = S.loopSteps;
  // The steps light in the order they are named, across the second half of the line.
  const lit = (i: number) => ramp(t, at('loop', 1, 0.42 + i * 0.1), 0.3);
  const inline = at('loop', 2, 0.5);
  const guarded = at('loop', 2, 0.78);
  return (
    <>
      <Kicker t={t} at={a - 0.4} id="loop" />
      <Question t={t} id="loop" />
      <Stage>
        <div style={{display: 'flex', flexDirection: 'column', gap: 30, alignItems: 'center'}}>
          <div style={{...enter(t, a, 0.5)}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 14}}>
              {steps.map((s, i) => (
                <React.Fragment key={s}>
                  <div
                    style={{
                      padding: '14px 24px',
                      borderRadius: 14,
                      border: `2px solid ${lit(i) > 0.5 ? C.green : C.line}`,
                      background: lit(i) > 0.5 ? `${C.greenDeep}66` : C.panel,
                      fontFamily: i === 0 || s === 'verify-plan' ? MONO : undefined,
                      fontSize: 30,
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {s}
                  </div>
                  {i < steps.length - 1 ? <span style={{fontFamily: MONO, color: C.dim, fontSize: 30}}>{'->'}</span> : null}
                </React.Fragment>
              ))}
            </div>
            <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14, marginTop: 14, color: C.blue, fontSize: 25, ...enter(t, at('loop', 1, 0.95), 0.4)}}>
              <Icon name="arrow-uturn-left" size={30} color={C.blue} />
              {S.loopBack}
              <span style={{color: C.dim}}> - {S.oracle}</span>
            </div>
          </div>
          <Card style={{width: 1560, padding: '14px 28px', ...enter(t, b, 0.5)}}>
            {figures.tiers.map((tier, i) => {
              const hot = tier.name === 'Inline' ? ramp(t, inline, 0.3) : tier.who === 'orchestrator' ? ramp(t, guarded, 0.3) : 0;
              const color = tier.who === 'orchestrator' ? C.purple : C.green;
              return (
                <div
                  key={tier.name}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '190px 1fr 330px 150px',
                    alignItems: 'center',
                    gap: 20,
                    padding: '9px 14px',
                    borderRadius: 10,
                    background: hot > 0.5 ? `${color}26` : 'transparent',
                    border: `2px solid ${hot > 0.5 ? color : 'transparent'}`,
                  }}
                >
                  <span style={{fontWeight: 700, fontSize: 31, color: hot > 0.5 ? color : C.text}}>{tier.name}</span>
                  <span style={{fontSize: 27}}>{S.tierWhen[tier.name] ?? ''}</span>
                  <span style={{fontSize: 25, color: C.dim}}>{S.who[tier.who] ?? tier.who}</span>
                  <span style={{display: 'flex', gap: 8}}>
                    {figures.tiers.map((_, d) => (
                      <span key={d} style={{width: 20, height: 20, borderRadius: 5, background: d <= i ? color : C.line}} />
                    ))}
                  </span>
                </div>
              );
            })}
          </Card>
        </div>
      </Stage>
    </>
  );
};

const Spec: React.FC<{t: number}> = ({t}) => {
  const {S} = useL();
  const cue = useCue();
  const at = useAt();
  const a = cue('spec', 1);
  const b = cue('spec', 2);
  const sheetAt = at('spec', 1, 0.35);
  const indexAt = at('spec', 1, 0.72);
  return (
    <>
      <Kicker t={t} at={a - 0.4} id="spec" />
      <Question t={t} id="spec" />
      <Stage>
        <div style={{display: 'flex', flexDirection: 'column', gap: 24, alignItems: 'center'}}>
          <div style={{display: 'flex', gap: 34, alignItems: 'stretch'}}>
            <Card color={C.blue} style={{width: 800, ...enter(t, sheetAt, 0.5)}}>
              <div style={{display: 'flex', alignItems: 'center', gap: 14, marginBottom: 12}}>
                <Icon name="document-check" size={42} color={C.blue} />
                <span style={{fontFamily: MONO, fontSize: 28, fontWeight: 600}}>{S.sheet}</span>
                <span style={{fontSize: 23, color: C.dim, marginLeft: 'auto'}}>{S.sheetFor}</span>
              </div>
              <div style={{display: 'grid', gridTemplateColumns: '90px 1fr 70px 70px 80px', gap: '8px 10px', alignItems: 'center', fontSize: 22}}>
                <span />
                <span />
                <span style={{color: C.dim, textAlign: 'center'}}>{S.yes}</span>
                <span style={{color: C.dim, textAlign: 'center'}}>{S.no}</span>
                <span style={{color: C.dim, textAlign: 'center'}}>{S.change}</span>
                {S.sheetRows.map((row, i) => {
                  const tick = ramp(t, sheetAt + 0.8 + i * 0.5, 0.25);
                  return (
                    <React.Fragment key={row}>
                      <span style={{fontFamily: MONO, color: C.green}}>{`FR-0${i + 1}`}</span>
                      <span style={{fontSize: 23}}>{row}</span>
                      {[0, 1, 2].map((c) => (
                        <span key={c} style={{display: 'flex', justifyContent: 'center'}}>
                          <span style={{width: 26, height: 26, border: `2px solid ${C.line}`, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
                            {c === 0 ? <Icon name="check-circle" size={22} color={C.blue} style={{opacity: tick}} /> : null}
                          </span>
                        </span>
                      ))}
                    </React.Fragment>
                  );
                })}
              </div>
            </Card>
            <Card color={C.green} style={{width: 440, ...enter(t, a, 0.5), display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
              <Icon name="document-text" size={56} color={C.green} />
              <div style={{fontSize: 36, fontWeight: 700, marginTop: 10}}>{S.contract}</div>
              <div style={{fontFamily: MONO, fontSize: 24, color: C.dim, marginTop: 6}}>docs/specs/</div>
              <div style={{fontSize: 25, color: C.text, marginTop: 12, whiteSpace: 'pre-line'}}>{S.sections(figures.spec_core, figures.spec_optional)}</div>
            </Card>
            <Card color={C.purple} style={{width: 460, ...enter(t, indexAt, 0.5)}}>
              <div style={{display: 'flex', alignItems: 'center', gap: 14, marginBottom: 12}}>
                <Icon name="list-bullet" size={42} color={C.purple} />
                <span style={{fontFamily: MONO, fontSize: 28, fontWeight: 600}}>{S.index}</span>
              </div>
              <div style={{fontSize: 23, color: C.dim, marginBottom: 10}}>{S.indexFor}</div>
              <div style={{fontFamily: MONO, fontSize: 22, lineHeight: 1.5, background: C.bg, borderRadius: 10, padding: '10px 16px'}}>
                <div style={{color: C.green}}>FR-02</div>
                {S.indexKeys.map((k) => (
                  <div key={k} style={{paddingLeft: 22, color: C.text}}>{k}</div>
                ))}
              </div>
            </Card>
          </div>
          <div style={{display: 'flex', gap: 22, alignItems: 'center'}}>
            <Chip color={C.green} style={{fontFamily: FONT_OR(S), fontSize: 23, ...enter(t, at('spec', 1, 0.95), 0.4)}}>{S.gwt}</Chip>
            <Chip color={C.blue} style={{...enter(t, b + 0.1, 0.4)}}>
              AS-01 <span style={{fontFamily: FONT_OR(S), fontWeight: 400}}>{S.as}</span>
            </Chip>
            <Chip color={C.blue} style={{...enter(t, b + 0.5, 0.4)}}>
              OI-01 <span style={{fontFamily: FONT_OR(S), fontWeight: 400}}>{S.oi}</span>
            </Chip>
            <span style={{fontSize: 28, fontWeight: 700, color: C.green, ...enter(t, b + 1.2, 0.4)}}>{S.neverInvented}</span>
          </div>
        </div>
      </Stage>
    </>
  );
};

// A small, fixed picture of a harness graph: what harness-view draws, not a figure of this repo.
const NODES: {x: number; y: number; k: 'agent' | 'rule' | 'hook' | 'module'}[] = [
  {x: 300, y: 250, k: 'agent'},
  {x: 140, y: 120, k: 'agent'},
  {x: 470, y: 110, k: 'agent'},
  {x: 120, y: 380, k: 'agent'},
  {x: 480, y: 400, k: 'agent'},
  {x: 300, y: 60, k: 'rule'},
  {x: 40, y: 250, k: 'rule'},
  {x: 580, y: 250, k: 'rule'},
  {x: 230, y: 470, k: 'hook'},
  {x: 380, y: 470, k: 'hook'},
  {x: 600, y: 60, k: 'hook'},
  {x: 30, y: 30, k: 'module'},
  {x: 620, y: 460, k: 'module'},
  {x: 30, y: 470, k: 'module'},
];
const EDGES: [number, number][] = [
  [0, 1], [0, 2], [0, 3], [0, 4], [1, 5], [2, 5], [1, 6], [3, 6], [2, 7], [4, 7],
  [0, 8], [0, 9], [2, 10], [1, 11], [4, 12], [3, 13], [4, 9], [3, 8],
];

const Control: React.FC<{t: number}> = ({t}) => {
  const {S} = useL();
  const cue = useCue();
  const at = useAt();
  const a = cue('control', 1);
  const b = cue('control', 2);
  const color = {agent: C.purple, rule: C.neutral, hook: C.red, module: C.green};
  const off = ramp(t, b + 0.3, 0.4); // the toggled-off hook
  // The first two rows land on the words that name them; the last two, which the voice leaves to
  // the picture, follow while the line is still being spoken.
  const beats = [b, at('control', 2, 0.5), at('control', 1, 0.8), at('control', 2, 0.85)];
  return (
    <>
      <Kicker t={t} at={a - 0.4} id="control" />
      <Question t={t} id="control" />
      <Stage>
        <div style={{display: 'flex', gap: 50, alignItems: 'center'}}>
          <Card style={{width: 720, padding: 22, ...enter(t, a, 0.5)}}>
            <svg width={650} height={480} viewBox="0 0 660 500" style={{display: 'block', margin: '0 auto'}}>
              {EDGES.map(([p, q], i) => {
                const k = ramp(t, a + 0.3 + i * 0.12, 0.3);
                const dead = q === 10 ? off : 0;
                return (
                  <line
                    key={i}
                    x1={NODES[p].x}
                    y1={NODES[p].y}
                    x2={NODES[p].x + (NODES[q].x - NODES[p].x) * k}
                    y2={NODES[p].y + (NODES[q].y - NODES[p].y) * k}
                    stroke={C.line}
                    strokeWidth={2.5}
                    strokeDasharray={dead > 0.5 ? '6 6' : undefined}
                  />
                );
              })}
              {NODES.map((nd, i) => {
                const k = ramp(t, a + 0.1 + i * 0.1, 0.3);
                const dead = i === 10 ? off : 0;
                return (
                  <circle
                    key={i}
                    cx={nd.x}
                    cy={nd.y}
                    r={(i === 0 ? 26 : 18) * k}
                    fill={dead > 0.5 ? C.panel : `${color[nd.k]}55`}
                    stroke={dead > 0.5 ? C.neutral : color[nd.k]}
                    strokeWidth={3}
                    strokeDasharray={dead > 0.5 ? '5 5' : undefined}
                  />
                );
              })}
              <g style={{opacity: off}}>
                <rect x={500} y={8} width={92} height={34} rx={8} fill={C.bg} stroke={C.neutral} strokeWidth={2} />
                <text x={546} y={32} textAnchor="middle" fontSize={20} fill={C.dim} fontFamily={MONO}>
                  {S.off}
                </text>
              </g>
            </svg>
            <div style={{display: 'flex', gap: 22, justifyContent: 'center', alignItems: 'center', fontSize: 22, color: C.dim, marginTop: 6, whiteSpace: 'nowrap'}}>
              {(['agent', 'rule', 'hook', 'module'] as const).map((k) => (
                <span key={k} style={{display: 'flex', alignItems: 'center', gap: 8}}>
                  <span style={{width: 16, height: 16, borderRadius: '50%', border: `3px solid ${color[k]}`}} />
                  {S.legend[k]}
                </span>
              ))}
            </div>
            <div style={{textAlign: 'center', fontSize: 22, color: C.green, marginTop: 6}}>{S.readOff}</div>
          </Card>
          <div style={{display: 'flex', flexDirection: 'column', gap: 26, width: 760}}>
            {S.ctl.map((r, i) => (
              <Row
                key={r.text}
                icon={r.icon as IconName}
                color={i < 3 ? C.green : C.dim}
                title={i === 2 ? <Rich text={r.text.replace('harness-check', '`harness-check`')} /> : r.text}
                sub={r.sub}
                style={enter(t, beats[i], 0.45, 14)}
              />
            ))}
          </div>
        </div>
      </Stage>
    </>
  );
};

const Assess: React.FC<{t: number}> = ({t}) => {
  const {S} = useL();
  const cue = useCue();
  const at = useAt();
  const a = cue('assess', 1);
  const b = cue('assess', 2);
  const r = figures.rubric;
  const clickAt = at('assess', 1, 0.55);
  const sinceAt = at('assess', 1, 0.8);
  return (
    <>
      <Kicker t={t} at={a - 0.4} id="assess" />
      <Question t={t} id="assess" />
      <Stage>
        <div style={{display: 'flex', gap: 36, alignItems: 'stretch'}}>
          <Card color={C.green} style={{width: 800, ...enter(t, a, 0.5)}}>
            <div style={{display: 'flex', alignItems: 'center', gap: 14}}>
              <Icon name="queue-list" size={44} color={C.green} />
              <span style={{fontSize: 34, fontWeight: 700}}>{S.fixFirst}</span>
            </div>
            <div style={{fontFamily: MONO, fontSize: 22, color: C.dim, margin: '8px 0 14px'}}>{S.orderedBy}</div>
            {r.worklist.map((w, i) => (
              <div
                key={w.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '130px 1fr auto',
                  gap: 14,
                  alignItems: 'center',
                  padding: '10px 0',
                  borderTop: `1px solid ${C.line}`,
                  ...enter(t, a + 0.5 + i * 0.4, 0.4),
                }}
              >
                <Chip color={w.severity === 'high' ? C.red : C.dim} style={{fontSize: 22, justifyContent: 'center'}}>{w.id}</Chip>
                <div>
                  <div style={{fontFamily: MONO, fontSize: 24}}>{w.slug}</div>
                  <div style={{fontSize: 21, color: C.dim}}>
                    {w.severity} · {S.effort} {w.effort}
                  </div>
                </div>
                <span
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 21,
                    padding: '6px 12px',
                    borderRadius: 10,
                    color: i === 0 && ramp(t, clickAt + 0.5, 0.2) > 0.5 ? C.bg : C.green,
                    background: i === 0 && ramp(t, clickAt + 0.5, 0.2) > 0.5 ? C.green : 'transparent',
                    border: `2px solid ${C.green}`,
                    opacity: ramp(t, clickAt, 0.3),
                  }}
                >
                  <Icon name="cursor-arrow-rays" size={24} color={i === 0 && ramp(t, clickAt + 0.5, 0.2) > 0.5 ? C.bg : C.green} />
                  {S.oneClick}
                </span>
              </div>
            ))}
            <div style={{display: 'flex', alignItems: 'center', gap: 16, marginTop: 12, paddingTop: 14, borderTop: `1px solid ${C.line}`, ...enter(t, sinceAt, 0.4)}}>
              <Icon name="arrows-right-left" size={40} color={C.blue} />
              <div>
                <div style={{fontSize: 26, fontWeight: 600}}>{S.since}</div>
                <div style={{fontSize: 22, color: C.dim, marginTop: 2}}>{S.sinceRows.join(' · ')}</div>
              </div>
            </div>
          </Card>
          <div style={{display: 'flex', flexDirection: 'column', gap: 22, width: 830}}>
            <Card color={C.red} style={{...enter(t, b, 0.5)}}>
              <div style={{display: 'flex', alignItems: 'center', gap: 12, fontSize: 27}}>
                <Chip color={C.red} style={{fontSize: 21}}>high {r.worklist[0].id}</Chip>
                <span>
                  <Rich text={S.finding} codeColor={C.red} />
                </span>
              </div>
              <div style={{fontFamily: MONO, fontSize: 22, marginTop: 12, ...enter(t, at('assess', 2, 0.35), 0.35)}}>
                <span style={{color: C.dim, fontFamily: FONT_OR(S)}}>{S.at}: </span>
                {S.fileLine}
              </div>
              <div style={{fontSize: 23, marginTop: 8, ...enter(t, at('assess', 2, 0.6), 0.35)}}>
                <span style={{color: C.green, fontWeight: 600}}>{S.fix}: </span>
                <Rich text={S.fixText} />
              </div>
            </Card>
            <Card style={{...enter(t, at('assess', 2, 0.8), 0.5)}}>
              <div style={{fontFamily: MONO, fontSize: 25, color: C.green}}>{S.arithmetic(r.weight_high)}</div>
              <div style={{display: 'flex', alignItems: 'center', gap: 12, fontSize: 24, marginTop: 10}}>
                <Icon name="clipboard-document-list" size={30} color={C.text} />
                {S.rubricLine(r.rules, r.categories)}
              </div>
              <div style={{display: 'flex', alignItems: 'center', gap: 12, fontSize: 22, color: C.dim, marginTop: 8}}>
                <Icon name="chart-bar" size={28} color={C.dim} />
                {S.captured(figures.cap_nodes, figures.cap_edges, figures.cap_score)}
              </div>
              <div style={{display: 'flex', alignItems: 'center', gap: 12, fontSize: 24, color: C.green, marginTop: 8}}>
                <Icon name="cpu-chip" size={28} color={C.green} />
                {S.noModelLoop}
              </div>
            </Card>
          </div>
        </div>
      </Stage>
    </>
  );
};

const Close: React.FC<{t: number}> = ({t}) => {
  const {S} = useL();
  const scene = useScene();
  const cue = useCue();
  const s = scene('close').start;
  const c = cue('close', 0);
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', paddingBottom: 150}}>
      <div style={{textAlign: 'center'}}>
        <div style={{fontSize: 66, color: C.text, ...enter(t, s + 0.1, 0.6)}}>{S.closeA}</div>
        <div style={{fontSize: 66, color: C.green, fontWeight: 700, marginTop: 14, ...enter(t, c + 1.6, 0.6)}}>{S.closeB}</div>
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 22, marginTop: 80, ...enter(t, c + 2.8, 0.6)}}>
          <div style={{width: 76, height: 76, borderRadius: 18, border: `3px solid ${C.green}`, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <Icon name="cpu-chip" size={46} color={C.purple} />
          </div>
          <div style={{fontSize: 50, fontWeight: 800, color: C.text}}>{S.title}</div>
        </div>
        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14, marginTop: 20, fontFamily: MONO, fontSize: 34, color: C.green, ...enter(t, c + 3.2, 0.6)}}>
          <Icon name="link" size={36} color={C.green} />
          {S.url}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const SCENES: Record<string, React.FC<{t: number}>> = {
  open: Open,
  team: Team,
  safe: Safe,
  lean: Lean,
  keys: Keys,
  loop: Loop,
  spec: Spec,
  control: Control,
  assess: Assess,
  close: Close,
};

// ---------------------------------------------------------------- captions

const isWide = (ch: string) => /[　-鿿＀-￯]/.test(ch);
const width = (s: string) => [...s].reduce((w, ch) => w + (isWide(ch) ? 1 : 0.55), 0);

/** English: at most two balanced lines, split at a space. */
const wrapEn = (text: string): string[] => {
  if (text.length <= 46) return [text];
  const words = text.split(' ');
  let best = [text];
  let bestDiff = Infinity;
  for (let i = 1; i < words.length; i++) {
    const a = words.slice(0, i).join(' ');
    const b = words.slice(i).join(' ');
    const diff = Math.abs(a.length - b.length);
    if (diff < bestDiff) {
      best = [a, b];
      bestDiff = diff;
    }
  }
  return best;
};

/**
 * Japanese: no spaces to split at, so break after a comma, a stop or a closing quote (or at a
 * space before a Latin word) where the two halves come out most even; inside a Latin word never.
 */
const wrapJa = (text: string, single = 31, max = 34): string[] => {
  const chars = [...text];
  if (width(text) <= single) return [text];
  let best = -1;
  let bestW = Infinity;
  for (let i = 1; i < chars.length; i++) {
    const prev = chars[i - 1];
    const ok = /[、。」）]/.test(prev) || prev === ' ' || chars[i] === '「';
    if (!ok) continue;
    const w = Math.max(width(chars.slice(0, i).join('')), width(chars.slice(i).join('')));
    if (w < bestW) {
      bestW = w;
      best = i;
    }
  }
  if (best < 0 || bestW > max) {
    // No good stop: split at the middle, but outside any Latin run.
    let i = Math.floor(chars.length / 2);
    while (i < chars.length - 1 && /[A-Za-z0-9\-_.]/.test(chars[i]) && /[A-Za-z0-9\-_.]/.test(chars[i - 1])) i++;
    best = i;
  }
  return [chars.slice(0, best).join('').trim(), chars.slice(best).join('').trim()];
};

const Captions: React.FC<{t: number}> = ({t}) => {
  const {lang, tm} = useL();
  const c = tm.cues.find((x) => t >= x.start && t < x.out);
  if (!c) return null;
  const k = Math.min(ramp(t, c.start, 0.15), interpolate(t, [c.out - 0.12, c.out], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const lines = lang === 'ja' ? wrapJa(c.text) : wrapEn(c.text);
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 56}}>
      <div
        style={{
          opacity: k,
          background: 'rgba(8, 9, 12, 0.85)',
          borderRadius: 14,
          padding: '12px 34px',
          maxWidth: 1640,
          textAlign: 'center',
          fontSize: lang === 'ja' ? 42 : 44,
          lineHeight: 1.32,
          fontWeight: 500,
          color: C.text,
        }}
      >
        {lines.map((l, i) => (
          <div key={i} style={{whiteSpace: 'nowrap'}}>
            {l}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- composition

const FADE = 0.35;

export const Intro: React.FC<{lang: Lang}> = ({lang}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const tm = TIMING[lang];
  return (
    <LangCtx.Provider value={{lang, tm, S: STRINGS[lang]}}>
      <AbsoluteFill style={{fontFamily: lang === 'ja' ? FONT_JA : FONT, color: C.text}}>
        <Background />
        {tm.scenes.map((s, i) => {
          const last = i === tm.scenes.length - 1;
          if (t < s.start - 0.01 || t > s.end + FADE) return null;
          const Scene = SCENES[s.id];
          // `lean` continues `safe`'s question, so the docked bubble must not blink across the cut.
          const opacity = Math.min(
            i === 0 ? 1 : ramp(t, s.start, FADE),
            last ? 1 : interpolate(t, [s.end, s.end + FADE], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
          );
          return (
            <AbsoluteFill key={s.id} style={{opacity}}>
              <Scene t={t} />
            </AbsoluteFill>
          );
        })}
        <Captions t={t} />
        <Soundtrack />
      </AbsoluteFill>
    </LangCtx.Provider>
  );
};
