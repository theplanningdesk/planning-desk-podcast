import React, {useMemo} from 'react';
import {interpolate} from 'remotion';
import {C, FONT} from '../theme.js';
import {captionChunks} from '../timing.js';

// Live captions: the current phrase, with each word lighting up as it is spoken.
export const Captions = ({line, t}) => {
  const chunks = useMemo(() => (line ? captionChunks(line) : []), [line]);
  if (!line || t > line.start_sec + line.duration_sec + 0.15) return null;
  const chunk = [...chunks].reverse().find((c) => c.start <= t) || chunks[0];
  if (!chunk) return null;
  const appear = interpolate(t - chunk.start, [0, 0.18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 46, display: 'flex', justifyContent: 'center'}}>
      <div style={{
        maxWidth: 1560, padding: '14px 30px', borderRadius: 16, background: 'rgba(238,227,222,0.92)',
        fontFamily: FONT, fontSize: 40, fontWeight: 600, lineHeight: 1.3, textAlign: 'center',
        opacity: appear, transform: `translateY(${(1 - appear) * 10}px)`,
      }}>
        {chunk.words.map((w, i) => {
          const on = t >= w.t;
          return (
            <span key={i} style={{color: on ? C.white : 'rgba(23,67,75,0.38)'}}>
              {w.w}{i < chunk.words.length - 1 ? ' ' : ''}
            </span>
          );
        })}
      </div>
    </div>
  );
};
