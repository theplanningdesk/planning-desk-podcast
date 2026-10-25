import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {C, FONT, HEAD} from '../theme.js';
import {useEnter} from '../components/Scene.jsx';
import {useLayout} from '../layout.js';

const Stage = ({children}) => {
  const {v} = useLayout();
  return <AbsoluteFill style={{padding: v ? '20px 90px 20px 70px' : '180px 160px 190px 160px', justifyContent: 'center', fontFamily: FONT}}>{children}</AbsoluteFill>;
};

export const Kicker = ({children, delay = 0}) => {
  const p = useEnter(delay, 14);
  return (
    <div style={{display: 'flex', alignItems: 'center', gap: 16, opacity: p, transform: `translateX(${(1 - p) * -30}px)`}}>
      <div style={{color: C.sub, fontSize: 28, fontWeight: 700, letterSpacing: 2.5, textTransform: 'uppercase'}}>{children}</div>
    </div>
  );
};

export const Source = ({children, delay = 20}) => {
  const p = useEnter(delay, 14);
  if (!children) return null;
  return <div style={{color: C.muted, fontSize: 24, fontWeight: 500, marginTop: 36, opacity: p}}>Source: {children}</div>;
};

// Words rise in one by one; `perWord` frames apart, starting at `delay`.
export const Words = ({text, delay = 4, perWord = 3, style}) => {
  const frame = useCurrentFrame();
  return (
    <div style={style}>
      {(text || '').split(' ').map((w, i) => {
        const x = interpolate(frame, [delay + i * perWord, delay + i * perWord + 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        const e = 1 - Math.pow(1 - x, 3);
        return <span key={i} style={{display: 'inline-block', opacity: e, transform: `translateY(${(1 - e) * 28}px)`, marginRight: '0.25em'}}>{w}</span>;
      })}
    </div>
  );
};

export const Headline = ({kicker, title, detail, source, dur = 300}) => {
  const frame = useCurrentFrame();
  const {v} = useLayout();
  const lineW = v ? 900 : 1500;
  const nWords = (title || '').split(' ').length;
  const q = useEnter(10 + nWords * 3, 20);
  const line = interpolate(frame, [0, dur], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <Stage>
      {kicker && <Kicker>{kicker}</Kicker>}
      <Words text={title} style={{fontFamily: HEAD, color: C.ink, fontSize: v ? 78 : 84, fontWeight: 700, lineHeight: 1.08, marginTop: 28, maxWidth: lineW}} />
      <div style={{height: 6, width: lineW * line, maxWidth: lineW, background: C.orange, borderRadius: 3, marginTop: 30}} />
      {detail && (
        <div style={{color: C.text, opacity: q, fontSize: v ? 42 : 40, fontWeight: 400, lineHeight: 1.3, marginTop: 26, maxWidth: v ? 900 : 1400, transform: `translateY(${(1 - q) * 16}px)`}}>{detail}</div>
      )}
      <Source delay={24 + nWords * 3}>{source}</Source>
    </Stage>
  );
};

// The "so what": words build up over the first half of the scene, roughly as the host says it.
export const Takeaway = ({kicker, text, dur = 300}) => {
  const frame = useCurrentFrame();
  const {v} = useLayout();
  const p = useEnter(0, 16);
  const words = (text || '').split(' ');
  const perWord = Math.max(3, Math.min(9, Math.floor((dur * 0.5) / Math.max(1, words.length))));
  const glow = 0.35 + 0.25 * Math.sin(frame / 18);
  const barH = interpolate(frame, [0, 24], [0, 100], {extrapolateRight: 'clamp'});
  return (
    <Stage>
      <div style={{position: 'relative', paddingLeft: 66, opacity: p}}>
        <div style={{position: 'absolute', left: 0, top: 0, width: 10, height: `${barH}%`, borderRadius: 5, background: C.amber, boxShadow: 'none'}} />
        {kicker && <div style={{color: C.sub, fontSize: 28, fontWeight: 700, letterSpacing: 2.5, textTransform: 'uppercase'}}>{kicker}</div>}
        <Words text={text} delay={8} perWord={perWord} style={{fontFamily: HEAD, color: C.ink, fontSize: v ? 70 : 76, fontWeight: 700, lineHeight: 1.15, marginTop: 22, maxWidth: v ? 860 : 1450}} />
      </div>
    </Stage>
  );
};

export const QuickHit = ({n, text}) => {
  const {v} = useLayout();
  const p = useEnter(0, 16);
  const q = useEnter(6, 20);
  return (
    <Stage>
      <Kicker>Quick hits</Kicker>
      <div style={{display: 'flex', flexDirection: v ? 'column' : 'row', alignItems: v ? 'flex-start' : 'center', gap: v ? 36 : 48, marginTop: 40}}>
        <div style={{
          width: 170, height: 170, flex: '0 0 170px', color: C.orange, fontFamily: HEAD,
          display: 'flex', alignItems: 'center', justifyContent: 'flex-start', fontSize: 200, fontWeight: 700, lineHeight: 0.8,
          transform: `scale(${0.6 + 0.4 * p}) rotate(${(1 - p) * -12}deg)`, opacity: p,
        }}>{n}</div>
        <div style={{fontFamily: HEAD, color: C.ink, fontSize: v ? 62 : 60, fontWeight: 700, lineHeight: 1.18, maxWidth: v ? 900 : 1300, opacity: q, transform: `translateX(${(1 - q) * 40}px)`}}>
          {text}
        </div>
      </div>
    </Stage>
  );
};
