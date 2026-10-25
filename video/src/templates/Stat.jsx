import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {C, FONT, HEAD, fmt} from '../theme.js';
import {useEnter} from '../components/Scene.jsx';
import {Kicker, Source} from './Cards.jsx';
import {useLayout} from '../layout.js';

export const Stat = ({kicker, value, decimals = 0, prefix = '', suffix = '', label, note, source, dur = 300}) => {
  const frame = useCurrentFrame();
  const {v} = useLayout();
  const x = interpolate(frame, [6, 46], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const eased = 1 - Math.pow(1 - x, 4);
  const shown = fmt(value * eased, decimals);
  const p = useEnter(8, 20);
  const q = useEnter(30, 20);
  const ring = false;
  const textW = v ? 900 : ring ? 1080 : 1400;
  return (
    <AbsoluteFill style={{padding: v ? '20px 90px 20px 70px' : '180px 160px 190px 160px', justifyContent: 'center', fontFamily: FONT}}>
      {kicker && <Kicker>{kicker}</Kicker>}
      <div style={{display: 'flex', alignItems: 'baseline', gap: 10, marginTop: 10, color: C.ink, fontFamily: HEAD}}>
        {prefix && <span style={{fontSize: 90, fontWeight: 700, color: C.muted}}>{prefix}</span>}
        <span style={{fontSize: v ? (shown.length > 5 ? 170 : 220) : 260, fontWeight: 700, letterSpacing: -4, lineHeight: 1, fontVariantNumeric: 'tabular-nums'}}>{shown}</span>
        {suffix && <span style={{fontSize: v ? 100 : 120, fontWeight: 700, color: C.orange}}>{suffix}</span>}
      </div>
      <div style={{fontFamily: HEAD, color: C.ink, fontSize: 52, fontWeight: 700, marginTop: 18, maxWidth: textW, opacity: p, transform: `translateY(${(1 - p) * 20}px)`}}>{label}</div>
      {note && <div style={{color: C.text, opacity: q, fontSize: 34, fontWeight: 400, marginTop: 20, maxWidth: textW}}>{note}</div>}
      {suffix.trim() === '%' && value <= 100 && (
        <div style={{position: 'relative', width: v ? 900 : 1200, height: 22, borderRadius: 11, background: C.paper2, marginTop: 34}}>
          <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: `${value * eased}%`, borderRadius: 11, background: C.amber,
            boxShadow: 'none'}} />
        </div>
      )}
      <Source delay={36}>{source}</Source>
      {ring && (
        <svg width={520} height={520} style={{position: 'absolute', right: 120, top: 280, opacity: 0.9 * p}}>
          <g transform={`rotate(${frame * 0.6} 260 260)`}>
            <circle cx={260} cy={260} r={200} fill="none" stroke={C.grid} strokeWidth={3} strokeDasharray="4 14" />
          </g>
          <circle cx={260} cy={260} r={160} fill="none" stroke={C.amber} strokeWidth={10} strokeLinecap="round"
            strokeDasharray={`${2 * Math.PI * 160 * eased * 0.78} ${2 * Math.PI * 160}`} transform={`rotate(${-90 + frame * 0.25} 260 260)`} />
          <circle cx={260} cy={260} r={120} fill="none" stroke={C.teal} strokeOpacity={0.6} strokeWidth={4}
            strokeDasharray={`${2 * Math.PI * 120 * 0.3} ${2 * Math.PI * 120}`} transform={`rotate(${90 - frame * 0.9} 260 260)`} />
        </svg>
      )}
    </AbsoluteFill>
  );
};
