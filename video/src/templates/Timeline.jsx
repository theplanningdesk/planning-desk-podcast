import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {C, FONT, HEAD} from '../theme.js';
import {Kicker} from './Cards.jsx';
import {useLayout} from '../layout.js';

// Vertical version for the chart panel: dates down a line that fills as the hosts reach them.
const VTimeline = ({items = [], itemFrames = []}) => {
  const frame = useCurrentFrame();
  const {w = 1000, h = 880} = useLayout();
  const n = Math.max(1, items.length);
  const top = 30, bottom = h - 30, x = 40;
  const ys = items.map((_, i) => (n === 1 ? (top + bottom) / 2 : top + ((bottom - top) * i) / (n - 1)));
  let active = -1;
  itemFrames.forEach((f, i) => { if (frame >= f) active = i; });
  const draw = interpolate(frame, [4, 30], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const fillTo = active < 0 ? top : interpolate(frame, [itemFrames[active], itemFrames[active] + 14], [active > 0 ? ys[active - 1] : top, ys[active]], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <svg width={w} height={h} style={{position: 'absolute'}}>
        <line x1={x} x2={x} y1={top} y2={top + (bottom - top) * draw} stroke={C.grid} strokeWidth={6} />
        <line x1={x} x2={x} y1={top} y2={fillTo} stroke={C.ink} strokeWidth={6} />
        {items.map((it, i) => {
          const appear = interpolate(frame, [10 + i * 6, 22 + i * 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const reached = i <= active;
          const color = it.alert ? C.orange : C.ink;
          return <circle key={i} cx={x} cy={ys[i]} r={i === active ? 16 : 11} fill={reached ? color : C.paper} stroke={reached ? color : C.muted} strokeWidth={4} opacity={appear} />;
        })}
      </svg>
      {items.map((it, i) => {
        const appear = interpolate(frame, [12 + i * 6, 26 + i * 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        const dim = active >= 0 && i !== active ? 0.45 : 1;
        return (
          <div key={i} style={{position: 'absolute', left: x + 50, top: ys[i] - 24, width: w - x - 70, opacity: appear * dim, transform: `translateX(${(1 - appear) * 20}px)`}}>
            <div style={{fontFamily: HEAD, fontWeight: 700, fontSize: 30, color: it.alert ? C.orange : C.ink}}>{it.label}</div>
            <div style={{fontSize: 30, color: C.text, marginTop: 4, lineHeight: 1.25}}>{it.detail}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// Dated events on a line. The line fills up to each event as the hosts reach it.
// props: kicker, title, items [{label (date), detail, alert, say}]
export const Timeline = (props) => (useLayout().v ? <VTimeline {...props} /> : <HTimeline {...props} />);

const HTimeline = ({kicker, title, items = [], itemFrames = []}) => {
  const frame = useCurrentFrame();
  const n = items.length;
  const x0 = 220, x1 = 1700, y = 610;
  const xs = items.map((_, i) => (n === 1 ? (x0 + x1) / 2 : x0 + ((x1 - x0) * i) / (n - 1)));
  let active = -1;
  itemFrames.forEach((f, i) => { if (frame >= f) active = i; });
  const draw = interpolate(frame, [4, 30], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const fillTo = active < 0 ? x0 : interpolate(frame, [itemFrames[active], itemFrames[active] + 14], [active > 0 ? xs[active - 1] : x0, xs[active]], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <div style={{position: 'absolute', left: 160, top: 190, maxWidth: 1500}}>
        {kicker && <Kicker>{kicker}</Kicker>}
        {title && <div style={{color: C.white, fontSize: 64, fontWeight: 800, lineHeight: 1.1, marginTop: 18}}>{title}</div>}
      </div>
      <svg width={1920} height={1080} style={{position: 'absolute'}}>
        <line x1={x0} y1={y} x2={x0 + (x1 - x0) * draw} y2={y} stroke={C.grid} strokeWidth={8} strokeLinecap="round" />
        <line x1={x0} y1={y} x2={fillTo} y2={y} stroke={C.amber} strokeWidth={8} strokeLinecap="round" />
        {items.map((it, i) => {
          const appear = interpolate(frame, [10 + i * 6, 22 + i * 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const reached = i <= active;
          const isOn = i === active;
          const pulse = isOn ? (frame % 40) / 40 : 0;
          const color = it.alert ? C.red : reached ? C.amber : C.muted;
          return (
            <g key={i} opacity={appear}>
              {isOn && <circle cx={xs[i]} cy={y} r={20 + pulse * 30} fill="none" stroke={color} strokeWidth={4} strokeOpacity={1 - pulse} />}
              <circle cx={xs[i]} cy={y} r={isOn ? 20 : 14} fill={reached ? color : C.ink} stroke={color} strokeWidth={5} />
            </g>
          );
        })}
      </svg>
      {items.map((it, i) => {
        const appear = interpolate(frame, [12 + i * 6, 26 + i * 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        const isOn = i === active;
        const above = i % 2 === 0;
        return (
          <div key={i} style={{
            position: 'absolute', left: xs[i] - 170, width: 340, textAlign: 'center',
            top: above ? y - 190 : y + 44, opacity: appear * (active >= 0 && !isOn ? 0.55 : 1),
            transform: `translateY(${(1 - appear) * (above ? -16 : 16)}px) scale(${isOn ? 1.06 : 1})`,
          }}>
            <div style={{color: it.alert ? C.red : C.amber, fontSize: 32, fontWeight: 800}}>{it.label}</div>
            <div style={{color: C.white, fontSize: 30, fontWeight: 600, lineHeight: 1.25, marginTop: 8}}>{it.detail}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
