import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {C, FONT, HEAD} from '../theme.js';
import {useEnter} from '../components/Scene.jsx';
import {Mark} from '../components/Chrome.jsx';

// A faded demand-and-capacity chart behind the bookends, like the end cards of the LinkedIn films.
const GhostChart = ({frame}) => {
  const x0 = 1000, x1 = 1840, y0 = 860, y1 = 220;
  const n = 26;
  const demand = Array.from({length: n}, (_, i) => 0.32 + 0.016 * i + 0.06 * Math.sin(i / 2.2));
  const grow = interpolate(frame, [0, 50], [0, 1], {extrapolateRight: 'clamp'});
  const bw = (x1 - x0) / n - 8;
  const pts = demand.map((d, i) => [x0 + i * ((x1 - x0) / n) + bw / 2, y0 - d * (y0 - y1)]);
  const cap = [[x0, y0 - 0.5 * (y0 - y1)], [x0 + 300, y0 - 0.5 * (y0 - y1)], [x0 + 300, y0 - 0.68 * (y0 - y1)], [x0 + 620, y0 - 0.68 * (y0 - y1)], [x0 + 620, y0 - 0.86 * (y0 - y1)], [x1, y0 - 0.86 * (y0 - y1)]];
  return (
    <svg width={1920} height={1080} style={{position: 'absolute', opacity: 0.55}}>
      {[0.25, 0.5, 0.75].map((g) => <line key={g} x1={x0} x2={x1} y1={y0 - g * (y0 - y1)} y2={y0 - g * (y0 - y1)} stroke={C.grid} strokeWidth={1.5} />)}
      {demand.map((d, i) => (
        <rect key={i} x={x0 + i * ((x1 - x0) / n)} width={bw} y={y0 - d * (y0 - y1) * grow} height={d * (y0 - y1) * grow} fill={C.sage} opacity={0.55} />
      ))}
      <polyline points={pts.map((p) => p.join(',')).join(' ')} fill="none" stroke={C.ink} strokeOpacity={0.35} strokeWidth={3} opacity={grow} />
      <polyline points={cap.map((p) => p.join(',')).join(' ')} fill="none" stroke={C.orange} strokeOpacity={0.45} strokeWidth={3} strokeDasharray="10 8" opacity={grow} />
      <line x1={x0} x2={x1} y1={y0} y2={y0} stroke={C.grid} strokeWidth={2} />
    </svg>
  );
};

const Brand = ({p}) => (
  <div style={{display: 'flex', alignItems: 'center', gap: 22, opacity: p, transform: `translateY(${(1 - p) * 14}px)`}}>
    <Mark size={68} />
    <div style={{fontFamily: HEAD, fontWeight: 700, fontSize: 52, color: C.orange, letterSpacing: -0.5}}>The Planning Desk</div>
  </div>
);

const Footer = ({left, right, p}) => (
  <>
    {left && <div style={{position: 'absolute', left: 110, bottom: 44, fontFamily: FONT, fontSize: 20, color: C.muted, opacity: p, maxWidth: 1100}}>{left}</div>}
    {right && <div style={{position: 'absolute', right: 80, bottom: 44, fontFamily: FONT, fontWeight: 700, fontSize: 20, color: C.sub, opacity: p}}>{right}</div>}
  </>
);

export const TitleCard = ({week, episodeTitle, disclosure, credit}) => {
  const frame = useCurrentFrame();
  const a = useEnter(4, 18);
  const b = useEnter(14, 18);
  const c = useEnter(26, 18);
  const title = episodeTitle || '';
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <GhostChart frame={frame} />
      <div style={{position: 'absolute', left: 110, top: 300, width: 860}}>
        <Brand p={a} />
        <div style={{fontFamily: HEAD, fontWeight: 700, color: C.ink, fontSize: title.length > 48 ? 70 : 88, lineHeight: 1.05, marginTop: 56,
          letterSpacing: -1, opacity: b, transform: `translateY(${(1 - b) * 16}px)`}}>{title}</div>
        <div style={{fontSize: 36, color: C.text, marginTop: 30, opacity: c}}>{week}</div>
      </div>
      <Footer left={disclosure} right={credit} p={c} />
    </AbsoluteFill>
  );
};

const OUTRO = {
  daily: ['Supply chain planning, every weekday.', 'Week in review every Sunday.'],
  saturday: ['A book worth your time, every Saturday.', 'News every weekday, the week in review on Sunday.'],
  weekly: ['Supply chain planning, every Sunday.', 'Fifteen minutes on the week.'],
};

export const OutroCard = ({credit, disclosure, site, daily, format}) => {
  const [big, small] = OUTRO[format === 'saturday' ? 'saturday' : daily ? 'daily' : 'weekly'];
  const frame = useCurrentFrame();
  const a = useEnter(4, 18);
  const b = useEnter(16, 18);
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <GhostChart frame={frame + 50} />
      <div style={{position: 'absolute', left: 110, top: 320, width: 860}}>
        <Brand p={a} />
        <div style={{fontFamily: HEAD, fontWeight: 700, color: C.ink, fontSize: 80, lineHeight: 1.05, marginTop: 56, letterSpacing: -1, opacity: b}}>
          {big}
        </div>
        <div style={{fontSize: 36, color: C.text, marginTop: 30, opacity: b, lineHeight: 1.35}}>
          {small}{site ? <><br /><span style={{color: C.blue, fontWeight: 700}}>{site}</span></> : null}
        </div>
      </div>
      <Footer left={disclosure} right={credit} p={b} />
    </AbsoluteFill>
  );
};
