import {Composition} from 'remotion';
import {Intro} from './Intro';
import timingEn from './timing.en.json';
import timingJa from './timing.ja.json';

export const FPS = 30;

// One composition per language. Same scenes, same figures; the script, voice, captions and the
// on-screen strings differ.
export const Root = () => (
  <>
    <Composition
      id="Intro"
      component={Intro}
      defaultProps={{lang: 'en' as const}}
      durationInFrames={Math.ceil(timingEn.total * FPS)}
      fps={FPS}
      width={1920}
      height={1080}
    />
    <Composition
      id="IntroJa"
      component={Intro}
      defaultProps={{lang: 'ja' as const}}
      durationInFrames={Math.ceil(timingJa.total * FPS)}
      fps={FPS}
      width={1920}
      height={1080}
    />
  </>
);
