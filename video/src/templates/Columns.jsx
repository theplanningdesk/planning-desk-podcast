import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {C, FONT, HEAD, fmt} from '../theme.js';
import {useLayout} from '../layout.js';

// Vertical columns with value labels, an optional dashed target line and highlighted columns,
// in the style of the "share of what each DC needs" chart.
// props: title (unit line), items [{label, value, highlight, note}], target, decimals, suffix, source
export const Columns = ({title, items = [], target, decimals = 0, suffix = '', source}) => {
  const frame = useCurrentFrame();
  const {w = 1000, h = 880, bare} = useLayout();
  const n = Math.max(1, items.length);
  const left = 40, right = w - 40, top = 130, bottom = h - 170;
  const gap = Math.min(60, (right - left) / n * 0.28);
  const colW = ((right - left) - gap * (n - 1)) / n;
  const max = Math.max(target || 0, ...items.map((i) => i.value)) * 1.12 || 1;
  const y = (v) => bottom - (v / max) * (bottom - top);
  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      {title && <div style={{position: 'absolute', left, top: 60, color: C.sub, fontSize: 26}}>{title}</div>}
      <svg width={w} height={h} style={{position: 'absolute'}}>
        <line x1={left} x2={right} y1={bottom} y2={bottom} stroke={C.grid} strokeWidth={2} />
        {items.map((it, i) => {
          const start = 8 + i * 6;
          const x = interpolate(frame, [start, start + 28], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const e = 1 - Math.pow(1 - x, 3);
          const cx = left + i * (colW + gap);
          const top_ = y(it.value * e);
          const fill = it.highlight ? C.orange : C.ink;
          return (
            <g key={i}>
              <rect x={cx} y={top} width={colW} height={bottom - top} fill={C.paper2} />
              <rect x={cx} y={top_} width={colW} height={bottom - top_} fill={fill} />
              <text x={cx + colW / 2} y={top_ - 14} textAnchor="middle" fill={it.highlight ? C.orange : C.ink}
                fontFamily={HEAD} fontWeight={700} fontSize={34} opacity={Math.min(1, x * 2)}>
                {fmt(it.value * e, decimals)}{suffix}
              </text>
              <text x={cx + colW / 2} y={bottom + 42} textAnchor="middle" fill={C.text} fontFamily={HEAD} fontWeight={700} fontSize={Math.min(26, Math.floor((colW + gap * 0.6) / Math.max(1, it.label.length) * 1.85))}>{it.label}</text>
              {it.note && <text x={cx + colW / 2} y={bottom + 74} textAnchor="middle" fill={C.muted} fontSize={22}>{it.note}</text>}
            </g>
          );
        })}
        {target !== undefined && (
          <line x1={left - 10} x2={right + 10} y1={y(target)} y2={y(target)} stroke={C.text} strokeWidth={2} strokeDasharray="8 7"
            opacity={interpolate(frame, [30, 45], [0, 0.8], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})} />
        )}
      </svg>
      {source && !bare && <div style={{position: 'absolute', right: 40, bottom: 40, color: C.muted, fontSize: 22}}>Source: {source}</div>}
    </AbsoluteFill>
  );
};
