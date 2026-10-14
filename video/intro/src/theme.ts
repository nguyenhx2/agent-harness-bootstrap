// The colour grammar of video/README.md: a colour means one thing in every clip, never reassigned.
import {Easing, interpolate} from 'remotion';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {loadFont as loadMono} from '@remotion/google-fonts/JetBrainsMono';
import {loadFont as loadNotoJP} from '@remotion/google-fonts/NotoSansJP';

export const C = {
  bg: '#12141a',
  panel: '#1a1d26',
  line: '#2a2f3c',
  text: '#F8F9FA',
  dim: '#9aa1ad',
  neutral: '#495057',
  green: '#52B788', // deterministic / free / the harness / control
  greenDeep: '#2D6A4F',
  purple: '#9D4EDD', // the AI model / agent / billed tokens
  purpleDeep: '#5A189A',
  red: '#E5383B', // guardrail / a blocked action (#9D0208 is the fill, this is its readable edge)
  redDeep: '#9D0208',
  blue: '#A8DADC', // the human
  blueDeep: '#1D3557',
};

export const FONT = loadInter('normal', {weights: ['400', '500', '600', '700', '800'], subsets: ['latin']}).fontFamily;
export const MONO = loadMono('normal', {weights: ['400', '600'], subsets: ['latin']}).fontFamily;
// Japanese text. Inter stays first so Latin runs (tool names, IDs) keep the English clip's shapes.
export const FONT_JA = `${FONT}, ${loadNotoJP('normal', {weights: ['400', '500', '700']}).fontFamily}`;

// One easing family, one exit curve. Nothing else.
const OUT = Easing.bezier(0.22, 1, 0.36, 1);

/** 0 -> 1 between seconds a and a+dur, eased out and clamped. */
export const ramp = (t: number, a: number, dur = 0.5) =>
  interpolate(t, [a, a + dur], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: OUT});

/** Standard entrance: fade plus a short rise. */
export const enter = (t: number, a: number, dur = 0.5, dist = 18) => {
  const k = ramp(t, a, dur);
  return {opacity: k, transform: `translateY(${(1 - k) * dist}px)`};
};
