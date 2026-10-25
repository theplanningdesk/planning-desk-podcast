import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {C, FONT, HEAD} from '../theme.js';
import {Kicker} from './Cards.jsx';
import {useLayout} from '../layout.js';

// Vertical version for the chart panel: steps stacked top to bottom, linked by arrows.
const VFlow = ({steps = [], itemFrames = []}) => {
  const frame = useCurrentFrame();
  const {w = 1000, h = 880} = useLayout();
  const n = Math.max(1, steps.length);
  const gap = 44;
  const boxH = Math.min(150, (h - gap * (n - 1)) / n);
  const top = (h - (boxH * n + gap * (n - 1))) / 2;
  let active = -1;
  itemFrames.forEach((f, i) => { if (frame >= f) active = i; });
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <svg width={w} height={h} style={{position: 'absolute'}}>
        {steps.slice(0, -1).map((_, i) => {
          const y1 = top + (i + 1) * boxH + i * gap + 6, y2 = y1 + gap - 12, x = 80;
          const lit = i < active;
          const appear = interpolate(frame, [14 + i * 6, 26 + i * 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          return (
            <g key={i} opacity={appear} stroke={lit ? C.ink : C.muted} strokeWidth={4} fill="none" strokeLinecap="round" strokeLinejoin="round">
              <line x1={x} x2={x} y1={y1} y2={y2} />
              <path d={`M${x - 9},${y2 - 9} L${x},${y2} L${x + 9},${y2 - 9}`} />
            </g>
          );
        })}
      </svg>
      {steps.map((st, i) => {
        const appear = interpolate(frame, [8 + i * 6, 22 + i * 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        const isOn = i === active;
        const done = i < active;
        return (
          <div key={i} style={{position: 'absolute', left: 20, top: top + i * (boxH + gap), width: w - 40, height: boxH, boxSizing: 'border-box',
            background: isOn ? C.ink : C.paper2, border: `2px solid ${isOn ? C.ink : done ? C.ink : C.grid}`, borderRadius: 4,
            display: 'flex', alignItems: 'center', gap: 28, padding: '0 30px', opacity: appear, transform: `translateY(${(1 - appear) * 20}px)`}}>
            <div style={{fontFamily: HEAD, fontWeight: 700, fontSize: 30, color: isOn ? C.paper : C.orange, width: 46}}>{String(i + 1).padStart(2, '0')}</div>
            <div>
              <div style={{fontFamily: HEAD, fontWeight: 700, fontSize: 36, color: isOn ? C.paper : C.ink}}>{st.label}</div>
              {st.detail && <div style={{fontSize: 26, color: isOn ? C.paper2 : C.sub, marginTop: 4}}>{st.detail}</div>}
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// A process chain: boxes linked by arrows, with units flowing between them.
// Each step lights up as the hosts mention it. props: kicker, title, steps [{label, detail, say}]
export const Flow = (props) => (useLayout().v ? <VFlow {...props} /> : <HFlow {...props} />);

const HFlow = ({kicker, title, steps = [], itemFrames = []}) => {
  const frame = useCurrentFrame();
  const n = Math.max(1, steps.length);
  const gap = 70;
  const boxW = Math.min(330, (1600 - gap * (n - 1)) / n);
  const total = boxW * n + gap * (n - 1);
  const left = (1920 - total) / 2;
  const top = 470, boxH = 220;
  let active = -1;
  itemFrames.forEach((f, i) => { if (frame >= f) active = i; });
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <div style={{position: 'absolute', left: 160, top: 190, maxWidth: 1500}}>
        {kicker && <Kicker>{kicker}</Kicker>}
        {title && <div style={{color: C.white, fontSize: 64, fontWeight: 800, lineHeight: 1.1, marginTop: 18}}>{title}</div>}
      </div>
      <svg width={1920} height={1080} style={{position: 'absolute'}}>
        {steps.slice(0, -1).map((_, i) => {
          const xA = left + boxW * (i + 1) + gap * i + 8, xB = xA + gap - 16, y = top + boxH / 2;
          const appear = interpolate(frame, [14 + i * 6, 26 + i * 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const lit = i < active;
          return (
            <g key={i} opacity={appear}>
              <line x1={xA} y1={y} x2={xB - 8} y2={y} stroke={lit ? C.amber : C.muted} strokeWidth={6} strokeLinecap="round" />
              <path d={`M${xB - 14},${y - 12} L${xB},${y} L${xB - 14},${y + 12}`} fill="none" stroke={lit ? C.amber : C.muted} strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" />
              {[0, 1].map((k) => {
                const f = ((frame / 26 + k / 2 + i * 0.3) % 1);
                return <circle key={k} cx={xA + (xB - xA) * f} cy={y} r={6} fill={lit ? C.white : C.teal} opacity={0.9} />;
              })}
            </g>
          );
        })}
      </svg>
      {steps.map((st, i) => {
        const appear = interpolate(frame, [8 + i * 6, 22 + i * 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        const isOn = i === active;
        const done = i < active;
        return (
          <div key={i} style={{
            position: 'absolute', left: left + i * (boxW + gap), top, width: boxW, height: boxH, borderRadius: 22,
            background: isOn ? 'rgba(232,86,42,0.10)' : C.paper2, border: `3px solid ${isOn ? C.orange : done ? 'rgba(232,86,42,0.45)' : C.grid}`,
            display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '0 26px', boxSizing: 'border-box',
            opacity: appear, transform: `translateY(${(1 - appear) * 30}px) scale(${isOn ? 1.05 : 1})`,
          }}>
            <div style={{color: C.amber, fontSize: 24, fontWeight: 800, letterSpacing: 2}}>{String(i + 1).padStart(2, '0')}</div>
            <div style={{color: C.white, fontSize: boxW < 280 ? 30 : 36, fontWeight: 800, lineHeight: 1.15, marginTop: 8}}>{st.label}</div>
            {st.detail && <div style={{color: C.muted, fontSize: 24, fontWeight: 500, marginTop: 8, lineHeight: 1.25}}>{st.detail}</div>}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
