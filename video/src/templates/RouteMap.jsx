import React, {useMemo} from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {geoMercator, geoPath} from 'd3-geo';
import {feature} from 'topojson-client';
import world110 from 'world-atlas/countries-110m.json';
import world50 from 'world-atlas/countries-50m.json';
import {C, FONT, HEAD} from '../theme.js';
import {Kicker} from './Cards.jsx';
import {useLayout} from '../layout.js';

const BOX_H = {x: 90, y: 300, w: 1740, h: 620};
const BOX_V = {x: 40, y: 240, w: 1000, h: 660};
const countries110 = feature(world110, world110.objects.countries);
const countries50 = feature(world50, world50.objects.countries);

// Map with optional routes (drawn as animated lines through waypoints, [lon, lat])
// and pins ({name, lat, lon, alert, muted}). The view fits everything shown.
export const RouteMap = ({kicker, title, routes = [], points = [], pad = 8}) => {
  const frame = useCurrentFrame();
  const {v, w: SW, h: SH, bare} = useLayout();
  const BOX = useMemo(() => (bare ? {x: 0, y: 0, w: SW, h: SH - 70} : v ? BOX_V : BOX_H), [bare, v, SW, SH]);

  const geo = useMemo(() => {
    const coords = [
      ...points.map((p) => [p.lon, p.lat]),
      ...routes.flatMap((r) => r.points),
    ];
    const lons = coords.map((c) => c[0]);
    const lats = coords.map((c) => c[1]);
    const minLon = Math.min(...lons) - pad, maxLon = Math.max(...lons) + pad;
    const minLat = Math.max(-70, Math.min(...lats) - pad), maxLat = Math.min(78, Math.max(...lats) + pad);
    const span = Math.max(maxLon - minLon, maxLat - minLat);
    const bboxFeature = {
      type: 'Feature',
      geometry: {type: 'MultiPoint', coordinates: [[minLon, minLat], [maxLon, maxLat], [minLon, maxLat], [maxLon, minLat]]},
    };
    // In the chart panel, keep room on the right for pin labels.
    const inset = bare ? [40, 40, 200, 40] : [0, 0, 0, 0];
    const projection = geoMercator().fitExtent([[BOX.x + inset[0], BOX.y + inset[1]], [BOX.x + BOX.w - inset[2], BOX.y + BOX.h - inset[3]]], bboxFeature);
    const path = geoPath(projection);
    const land = span < 45 ? countries50 : countries110;
    const countryPaths = land.features.map((f) => path(f)).filter(Boolean);
    const projRoutes = routes.map((r) => {
      const pts = r.points.map((c) => projection(c));
      let len = 0;
      for (let i = 1; i < pts.length; i++) len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
      const cum = [0];
      for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
      const at = (dist) => {
        let i = 1;
        while (i < cum.length - 1 && cum[i] < dist) i++;
        const f = (dist - cum[i - 1]) / Math.max(1e-6, cum[i] - cum[i - 1]);
        return [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f];
      };
      return {...r, d: 'M' + pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' L'), len, at};
    });
    // Place each label right of its pin, or left / below / above when it would hit an earlier label or pin.
    const fs = v ? 34 : 30;
    const placed = points.map((p) => { const [x, y] = projection([p.lon, p.lat]); return {x0: x - 16, y0: y - 16, x1: x + 16, y1: y + 16}; });
    const hit = (r) => placed.some((q) => r.x0 < q.x1 && r.x1 > q.x0 && r.y0 < q.y1 && r.y1 > q.y0);
    const projPoints = points.map((p) => {
      const xy = projection([p.lon, p.lat]);
      const w = p.name.length * fs * 0.58;
      const opts = [
        {x: xy[0] + 24, y: xy[1] + 10, anchor: 'start', r: {x0: xy[0] + 20, y0: xy[1] - fs * 0.75, x1: xy[0] + 28 + w, y1: xy[1] + fs * 0.4}},
        {x: xy[0] - 24, y: xy[1] + 10, anchor: 'end', r: {x0: xy[0] - 28 - w, y0: xy[1] - fs * 0.75, x1: xy[0] - 20, y1: xy[1] + fs * 0.4}},
        {x: xy[0], y: xy[1] + 50, anchor: 'middle', r: {x0: xy[0] - w / 2, y0: xy[1] + 20, x1: xy[0] + w / 2, y1: xy[1] + 58}},
        {x: xy[0], y: xy[1] - 30, anchor: 'middle', r: {x0: xy[0] - w / 2, y0: xy[1] - 62, x1: xy[0] + w / 2, y1: xy[1] - 24}},
      ];
      const pick = opts.find((o) => !hit(o.r)) || opts[0];
      placed.push(pick.r);
      return {...p, xy, label: pick};
    });
    return {countryPaths, projRoutes, projPoints};
  }, [routes, points, pad, BOX, bare, v]);

  const mapIn = interpolate(frame, [0, 14], [0, 1], {extrapolateRight: 'clamp'});

  return (
    <AbsoluteFill style={{fontFamily: FONT}}>
      <svg width={SW} height={SH} style={{position: 'absolute', opacity: mapIn}}>
        <defs>
          <clipPath id="mapclip"><rect x={BOX.x} y={BOX.y} width={BOX.w} height={BOX.h} rx={6} /></clipPath>
        </defs>
        <g clipPath="url(#mapclip)">
          <rect x={BOX.x} y={BOX.y} width={BOX.w} height={BOX.h} fill={C.paper} />
          {geo.countryPaths.map((d, i) => (
            <path key={i} d={d} fill={C.paper2} stroke={C.grid} strokeWidth={1.2} />
          ))}
          {geo.projRoutes.map((r, i) => {
            const start = 12 + i * 22;
            const x = interpolate(frame, [start, start + 45], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
            const e = 1 - Math.pow(1 - x, 2);
            const faded = r.style === 'faded';
            return (
              <path key={i} d={r.d} fill="none" stroke={faded ? C.muted : C.amber} strokeOpacity={faded ? 0.55 : 1}
                strokeWidth={faded ? 5 : 8} strokeLinecap="round" strokeLinejoin="round"
                strokeDasharray={faded ? `14 12` : `${r.len} ${r.len}`}
                strokeDashoffset={faded ? -frame * 0.8 : r.len * (1 - e)} opacity={faded ? e : 1} />
            );
          })}
          {geo.projRoutes.filter((r) => r.style !== 'faded').map((r, i) => {
            const ready = interpolate(frame, [12 + i * 22 + 45, 12 + i * 22 + 60], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
            const ships = 4;
            return Array.from({length: ships}, (_, k) => {
              const f = ((frame / 260) + k / ships) % 1;
              const [sx, sy] = r.at(f * r.len);
              return (
                <g key={`s${i}-${k}`} opacity={ready}>
                  <circle cx={sx} cy={sy} r={14} fill={C.amber} opacity={0.25} />
                  <circle cx={sx} cy={sy} r={7} fill={C.ink} />
                </g>
              );
            });
          })}
        </g>
        <rect x={BOX.x} y={BOX.y} width={BOX.w} height={BOX.h} rx={6} fill="none" stroke={C.line} strokeWidth={2} />
        {geo.projPoints.map((p, i) => {
          const start = 18 + i * 8;
          const x = interpolate(frame, [start, start + 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const color = p.alert ? C.red : p.muted ? C.muted : C.teal;
          const pulse = p.alert ? (frame % 45) / 45 : 0;
          const [cx, cy] = p.xy;
          return (
            <g key={i} opacity={x}>
              {p.alert && <circle cx={cx} cy={cy} r={14 + pulse * 46} fill="none" stroke={C.red} strokeWidth={4} strokeOpacity={1 - pulse} />}
              <circle cx={cx} cy={cy} r={13 * x} fill={color} stroke={C.ink} strokeWidth={4} />
              <text x={p.label.x} y={p.label.y} textAnchor={p.label.anchor} fill={p.muted ? C.muted : C.white} fontSize={v ? 34 : 30} fontWeight={700}
                fontFamily={HEAD} style={{paintOrder: 'stroke', stroke: C.paper, strokeWidth: 8, strokeLinejoin: 'round'}}>{p.name}</text>
            </g>
          );
        })}
      </svg>
      {bare && routes.some((r) => r.label) && (
        <div style={{position: 'absolute', left: 0, top: SH - 44, display: 'flex', gap: 28, opacity: mapIn}}>
          {routes.filter((r) => r.label).map((r, i) => (
            <div key={i} style={{display: 'flex', alignItems: 'center', gap: 10, color: C.sub, fontSize: 24, whiteSpace: 'nowrap'}}>
              <div style={{width: 40, height: 5, borderRadius: 2, background: r.style === 'faded' ? C.muted : C.orange}} />
              {r.label}
            </div>
          ))}
        </div>
      )}
      {!bare && (kicker || title) && (
        <div style={{position: 'absolute', left: BOX.x + 6, top: v ? 10 : 146, right: BOX.x, opacity: mapIn, display: 'flex', flexDirection: v ? 'column' : 'row', alignItems: v ? 'flex-start' : 'flex-end', justifyContent: 'space-between', gap: v ? 14 : 40}}>
          <div>
            {kicker && <Kicker>{kicker}</Kicker>}
            {title && <div style={{fontFamily: HEAD, color: C.ink, fontSize: v ? 48 : 56, fontWeight: 700, lineHeight: 1.1, marginTop: 14, maxWidth: v ? 960 : 1350}}>{title}</div>}
          </div>
          {routes.some((r) => r.label) && (
            <div style={{display: 'flex', gap: 28, paddingBottom: 10}}>
              {routes.filter((r) => r.label).map((r, i) => (
                <div key={i} style={{display: 'flex', alignItems: 'center', gap: 10, color: C.muted, fontSize: 26, fontWeight: 600, whiteSpace: 'nowrap'}}>
                  <div style={{width: 40, height: 6, borderRadius: 3, background: r.style === 'faded' ? C.muted : C.amber}} />
                  {r.label}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </AbsoluteFill>
  );
};
