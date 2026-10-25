import React from 'react';
import {Composition} from 'remotion';
import '@fontsource/arimo/400.css';
import '@fontsource/arimo/700.css';
import '@fontsource/lato/400.css';
import '@fontsource/lato/700.css';
import '@fontsource/lato/900.css';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';
import '@fontsource/inter/800.css';
import '@fontsource/inter/900.css';
import {Episode} from './Episode.jsx';
import {Short} from './Short.jsx';
import {FPS, H, W} from './theme.js';

const defaultProps = {
  show: 'The Planning Desk',
  week: '',
  episodeTitle: '',
  totalSec: 30,
  outroStartSec: 20,
  lines: [],
  cues: [],
  envelope: [],
  audioFile: null,
  credit: '',
  disclosure: '',
  site: '',
};

const shortDefaults = {show: 'The Planning Desk', dateLabel: '', totalSec: 30, endCardSec: 27, lines: [], cues: [], audioFile: null, cta: ''};

export const RemotionRoot = () => (
  <>
  <Composition
    id="Episode"
    component={Episode}
    width={W}
    height={H}
    fps={FPS}
    durationInFrames={FPS * 30}
    defaultProps={defaultProps}
    calculateMetadata={({props}) => ({durationInFrames: Math.max(1, Math.ceil(props.totalSec * FPS))})}
  />
  <Composition
    id="Short"
    component={Short}
    width={1080}
    height={1920}
    fps={FPS}
    durationInFrames={FPS * 30}
    defaultProps={shortDefaults}
    calculateMetadata={({props}) => ({durationInFrames: Math.max(1, Math.ceil(props.totalSec * FPS))})}
  />
  </>
);
