import {Config} from '@remotion/cli/config';

// The cached ElevenLabs audio is the public directory: staticFile('narration.mp3') reads audio/.
Config.setPublicDir('./audio');
Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(92);
Config.setOverwriteOutput(true);
