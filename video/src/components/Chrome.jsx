import React from 'react';
import {C, FONT, HEAD, segmentLabel} from '../theme.js';

// The show's mark: three planning bars, staggered like a Gantt chart. Original, no logo borrowed.
export const Mark = ({size = 40, color = C.orange}) => (
  <svg width={size} height={size} viewBox="0 0 40 40">
    <rect x={2} y={5} width={22} height={8} rx={1.5} fill={color} />
    <rect x={10} y={16} width={26} height={8} rx={1.5} fill={color} />
    <rect x={6} y={27} width={16} height={8} rx={1.5} fill={color} />
  </svg>
);

export const Wordmark = ({size = 40, color = C.ink}) => (
  <div style={{display: 'flex', alignItems: 'center', gap: size * 0.4}}>
    <Mark size={size} />
    <div style={{fontFamily: HEAD, fontWeight: 700, fontSize: size * 0.62, color, letterSpacing: 0.2}}>The Planning Desk</div>
  </div>
);

// Quiet frame around the show: wordmark and segment bottom left, AI disclosure top right.
export const Frame = ({segment}) => (
  <>
    <div style={{position: 'absolute', left: 110, bottom: 36, display: 'flex', alignItems: 'center', gap: 18, fontFamily: FONT}}>
      <Wordmark size={34} />
      {segment && <div style={{color: C.muted, fontSize: 21}}>·&nbsp;&nbsp;{segmentLabel(segment)}</div>}
    </div>
    <div style={{position: 'absolute', right: 60, top: 38, fontFamily: FONT, fontSize: 18, color: C.muted}}>
      AI-generated · synthetic voices
    </div>
  </>
);
