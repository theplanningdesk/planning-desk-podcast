import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {C, FONT, HEAD} from '../theme.js';
import {Kicker} from './Cards.jsx';
import {useLayout} from '../layout.js';

// Items slide in, then each one lights up as the hosts mention it.
export const ListCard = ({title, items = [], footer, itemFrames = []}) => {
  const frame = useCurrentFrame();
  const {v, bare} = useLayout();
  const big = items.length <= 4;
  const rowH = v ? (big ? 156 : 122) : big ? 92 : 70;
  let active = -1;
  itemFrames.forEach((f, i) => { if (frame >= f) active = i; });
  const markerY = interpolate(frame, [itemFrames[active] ?? 0, (itemFrames[active] ?? 0) + 10], [Math.max(0, active - 1) * rowH, Math.max(0, active) * rowH], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{padding: bare ? '0 20px 0 50px' : v ? '20px 90px 20px 80px' : '170px 160px 200px 160px', justifyContent: 'center', fontFamily: FONT}}>
      {!bare && <Kicker>{title}</Kicker>}
      <div style={{marginTop: bare ? 0 : 40, position: 'relative'}}>
        {active >= 0 && (
          <div style={{position: 'absolute', left: v ? -30 : -40, top: markerY + (v ? 22 : big ? 14 : 10), width: 10, height: v ? rowH - 44 : big ? 52 : 40, borderRadius: 5, background: C.amber}} />
        )}
        {items.map((it, i) => {
          const start = 8 + i * 7;
          const x = interpolate(frame, [start, start + 16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const e = 1 - Math.pow(1 - x, 3);
          const isOn = i === active;
          const dim = active >= 0 && !isOn ? 0.42 : 1;
          const pop = isOn ? interpolate(frame, [itemFrames[i], itemFrames[i] + 8], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0;
          return (
            <div key={i} style={{height: rowH, display: 'flex', flexDirection: v ? 'column' : 'row', justifyContent: 'center', alignItems: v ? 'flex-start' : 'center', gap: v ? 4 : 40, opacity: e * dim, transform: `translateX(${(1 - e) * 50 + pop * 16}px)`}}>
              <div style={{minWidth: v ? 0 : big ? 300 : 260, fontFamily: HEAD, color: isOn ? C.orange : C.ink, fontSize: v ? (big ? 34 : 28) : big ? 44 : 34, fontWeight: 700}}>{it.label}</div>
              <div style={{color: C.ink, fontSize: v ? (big ? 42 : 34) : big ? 46 : 36, fontWeight: isOn ? 700 : 400, lineHeight: 1.2}}>{it.detail}</div>
            </div>
          );
        })}
      </div>
      {footer && <div style={{color: C.muted, fontSize: 26, marginTop: 36}}>{footer}</div>}
    </AbsoluteFill>
  );
};
