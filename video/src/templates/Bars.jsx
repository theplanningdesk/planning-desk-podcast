import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {C, FONT, HEAD, fmt} from '../theme.js';
import {Kicker, Source} from './Cards.jsx';
import {useLayout} from '../layout.js';

export const Bars = ({kicker, title, items = [], decimals = 0, baseline, source}) => {
  const frame = useCurrentFrame();
  const {v, w: LW = 1080, bare} = useLayout();
  const max = Math.max(...items.map((i) => i.value)) * 1.08;
  const min = baseline !== undefined ? Math.min(baseline - (max - baseline) * 0.25, ...items.map((i) => i.value)) : 0;
  const trackW = v ? LW - 390 : 900;
  const scale = (v) => ((v - min) / (max - min)) * trackW;
  return (
    <AbsoluteFill style={{padding: bare ? '0 20px' : v ? '20px 90px 20px 70px' : '170px 160px 190px 160px', justifyContent: 'center', fontFamily: FONT}}>
      {!bare && kicker && <Kicker>{kicker}</Kicker>}
      {bare ? (title && <div style={{color: C.sub, fontSize: 28}}>{title}</div>)
        : (title && <div style={{fontFamily: HEAD, color: C.ink, fontSize: v ? 52 : 56, fontWeight: 700, marginTop: 20, lineHeight: 1.1}}>{title}</div>)}
      <div style={{marginTop: 50, display: 'flex', flexDirection: 'column', gap: v ? 30 : 34, position: 'relative'}}>
        {items.map((it, i) => {
          const start = 10 + i * 8;
          const x = interpolate(frame, [start, start + 30], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const e = 1 - Math.pow(1 - x, 3);
          const w = Math.max(8, scale(it.value) * e);
          return (
            <div key={i} style={{display: 'flex', flexWrap: v ? 'wrap' : 'nowrap', alignItems: 'center', columnGap: v ? 24 : 36, rowGap: 10, opacity: Math.min(1, x * 3)}}>
              <div style={{width: v ? '100%' : 400, flexShrink: 0, textAlign: v ? 'left' : 'right', color: it.highlight ? C.ink : C.sub, fontSize: 32, fontWeight: it.highlight ? 700 : 400}}>{it.label}</div>
              <div style={{position: 'relative', width: trackW, flexShrink: 0, height: 64}}>
                <div style={{position: 'absolute', inset: 0, background: C.paper2, borderRadius: 4}} />
                <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: w, borderRadius: 4, overflow: 'hidden', background: it.highlight ? C.orange : C.ink}}>
                </div>
                {baseline !== undefined && (
                  <div style={{position: 'absolute', left: scale(baseline), top: -10, bottom: -10, width: 3, background: C.white, opacity: 0.6}} />
                )}
              </div>
              <div style={{width: v ? 180 : 200, flexShrink: 0, color: C.white, fontFamily: HEAD, fontSize: 44, fontWeight: 700, fontVariantNumeric: 'tabular-nums'}}>{fmt(it.value * e, decimals)}</div>
            </div>
          );
        })}
      </div>
      {!bare && <Source delay={40}>{source}</Source>}
    </AbsoluteFill>
  );
};
