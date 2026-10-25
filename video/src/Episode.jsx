import React, {useEffect, useMemo, useState} from 'react';
import {AbsoluteFill, Audio, Sequence, continueRender, delayRender, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {C, FONT, HEAD, FPS, fmt, segmentLabel} from './theme.js';
import {LayoutCtx} from './layout.js';
import {Background} from './components/Background.jsx';
import {Frame} from './components/Chrome.jsx';
import {charTime, mentionTimes} from './timing.js';
import {Scene, useEnter} from './components/Scene.jsx';
import {TitleCard, OutroCard} from './templates/Bookends.jsx';
import {Bars} from './templates/Bars.jsx';
import {Columns} from './templates/Columns.jsx';
import {ListCard} from './templates/ListCard.jsx';
import {RouteMap} from './templates/RouteMap.jsx';
import {Timeline} from './templates/Timeline.jsx';
import {Flow} from './templates/Flow.jsx';
import {Voice} from './templates/Voice.jsx';

// Editorial split layout, after the show's LinkedIn films: the words on the left (headline, a line
// of context, up to two KPIs), one chart on the right that stays put while the story moves on.
//
// Cue schema (new):  {line, at?, kicker?, headline, sub?, kpis?: [{value, prefix, suffix, decimals, label, accent}],
//                     visual?: {template, props}, keep?: true (reuse the previous chart), source?}
// Older cues ({line, template, props}) are converted by normalizeCues, carrying the story's
// headline, KPIs and chart forward the same way.

const VISUALS = {bars: Bars, columns: Columns, list: ListCard, route: RouteMap, timeline: Timeline, flow: Flow};
const ITEM_VISUALS = new Set(['list', 'timeline', 'flow']);
const PANEL = {x: 110, w: 660};
const STAGE = {x: 860, y: 100, w: 1000, h: 880};

const useFonts = () => {
  const [handle] = useState(() => delayRender('fonts'));
  useEffect(() => {
    const loads = [
      ...[400, 700].map((w) => `${w} 40px Arimo`),
      ...[400, 700, 900].map((w) => `${w} 40px Lato`),
    ].map((f) => document.fonts.load(f));
    Promise.all(loads).then(() => continueRender(handle)).catch(() => continueRender(handle));
  }, [handle]);
};

const cueStart = (cue, lines) => {
  const l = lines[cue.line];
  if (!l) return null;
  if (!cue.at) return l.start_sec;
  const idx = l.text.toLowerCase().indexOf(String(cue.at).toLowerCase());
  return idx >= 0 ? charTime(l, idx) : l.start_sec;
};

// An older chart cue starts a new story when its kicker shares no first word with the story's kicker.
const firstWord = (k) => (k || '').toLowerCase().split(/[\s,]+/)[0];
const newStory = (p, s) => !!(p.kicker && s.kicker && firstWord(p.kicker) !== firstWord(s.kicker));

const statKpi = (p) => ({value: p.value, prefix: p.prefix || '', suffix: p.suffix || '', decimals: p.decimals || 0, label: p.label});

// Turn every cue into {kicker, headline, sub, kpis, visual, source, mode}, carrying story state forward.
export const normalizeCues = (cues, lines) => {
  const out = [];
  let s = {seg: null};
  const reset = (seg) => { s = {seg, kicker: '', headline: '', sub: '', kpis: [], visual: null}; };
  for (const c of cues) {
    const seg = lines[c.line] ? lines[c.line].segment : null;
    if (seg !== s.seg) reset(seg);
    const p = c.props || {};
    let n;
    if (!c.template) {
      // New schema.
      const vis = c.keep ? s.visual : c.visual || null;
      const same = vis && s.visual && JSON.stringify(vis) === JSON.stringify(s.visual);
      if (vis && vis.template === 'voice') n = {mode: 'voice', voice: vis.props || {}};
      else n = {mode: 'panel', kicker: c.kicker ?? s.kicker, headline: c.headline ?? s.headline, sub: c.sub ?? (c.headline ? '' : s.sub),
        kpis: c.kpis ?? [], visual: same ? s.visual : vis, source: c.source};
    } else {
      switch (c.template) {
        case 'headline':
          reset(seg);
          n = {mode: 'panel', kicker: p.kicker, headline: p.title, sub: p.detail, kpis: [], visual: null, source: p.source};
          break;
        case 'quickhit':
          reset(seg);
          n = {mode: 'quickhit', n: p.n, headline: p.text, kicker: 'Quick hits', kpis: [], visual: null};
          break;
        case 'takeaway':
          n = {mode: 'panel', kicker: p.kicker, headline: p.text, sub: '', kpis: s.kpis, visual: s.visual, takeaway: true};
          break;
        case 'stat': {
          const kpis = [...(s.kpis || []), statKpi(p)].slice(-2);
          n = s.headline && !s.takeaway
            ? {mode: 'panel', kicker: s.kicker, headline: s.headline, sub: p.note || '', kpis, visual: s.visual, source: p.source}
            : {mode: 'panel', kicker: p.kicker, headline: p.note || p.label, sub: '', kpis, visual: s.visual, source: p.source};
          break;
        }
        case 'voice':
          reset(seg);
          n = {mode: 'voice', voice: p};
          break;
        case 'bars':
        case 'columns':
          if (newStory(p, s)) reset(seg);
          n = s.headline && !s.takeaway
            ? {mode: 'panel', kicker: s.kicker, headline: s.headline, sub: s.sub, kpis: s.kpis, visual: {template: c.template, props: p}, source: p.source}
            : {mode: 'panel', kicker: '', headline: p.kicker || p.title, sub: '', kpis: s.kpis, visual: {template: c.template, props: p}, source: p.source};
          break;
        default:
          if (VISUALS[c.template]) {
            if (newStory(p, s)) reset(seg);
            n = {mode: 'panel', kicker: p.kicker || '', headline: p.title || s.headline, sub: p.title ? '' : s.sub, kpis: s.kpis,
              visual: {template: c.template, props: p}, source: p.source};
          } else {
            n = {mode: 'panel', kicker: p.kicker, headline: p.title || p.text || '', sub: p.detail || '', kpis: [], visual: null};
          }
      }
    }
    n.line = c.line;
    n.at = c.at;
    out.push(n);
    if (n.mode === 'panel') s = {...s, ...n, takeaway: !!n.takeaway};
    else reset(seg);
  }
  return out;
};

// Scenes: title card, one per cue, outro card. Visual runs: consecutive cues that share a chart.
const buildScenes = (props) => {
  const {lines, cues, outroStartSec} = props;
  const firstStart = lines.length ? lines[0].start_sec : outroStartSec;
  let norm = normalizeCues([...cues].filter((c) => lines[c.line]), lines)
    .map((c) => ({...c, from: cueStart(c, lines)}))
    .filter((c) => c.from !== null)
    .sort((a, b) => a.from - b.from);
  if (!norm.length || norm[0].from > firstStart + 0.05) {
    norm.unshift({mode: 'panel', kicker: 'Now', headline: segmentLabel(lines[0] ? lines[0].segment : ''), kpis: [], visual: null, from: firstStart});
  }
  norm = norm.map((c, i) => ({...c, to: i + 1 < norm.length ? norm[i + 1].from : outroStartSec})).filter((c) => c.to > c.from);
  const runs = [];
  norm.forEach((c) => {
    if (c.mode !== 'panel' || !c.visual) return;
    const last = runs[runs.length - 1];
    if (last && last.visual === c.visual && Math.abs(last.to - c.from) < 0.01) last.to = c.to;
    else runs.push({visual: c.visual, from: c.from, to: c.to});
  });
  return {cues: norm, runs, firstStart};
};

// ---- Left text panel ----

const fit = (text, sizes) => {
  const n = (text || '').length;
  return n <= sizes[0][0] ? sizes[0][1] : n <= sizes[1][0] ? sizes[1][1] : sizes[2][1];
};

// Fades/rises in when `changed`, fades out at the end when the next scene replaces it.
const usePart = (changed, leaving, dur, delay) => {
  const frame = useCurrentFrame();
  const inP = useEnter(delay, 14);
  const outP = interpolate(frame, [dur - 7, dur], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const o = (changed ? inP : 1) * (leaving ? outP : 1);
  return {opacity: o, transform: `translateY(${changed ? (1 - inP) * 14 : 0}px)`};
};

const kpiText = (k, v) => {
  const pre = k.prefix ? (/^[^\w\s]+$/.test(k.prefix.trim()) ? k.prefix.trim() : k.prefix.trim() + ' ') : '';
  return `${pre}${fmt(v, k.decimals || 0)}${k.suffix || ''}`;
};

// All KPIs in a row share one size, set by the longest, so their labels line up.
const Kpi = ({k, prev, accent, style, size}) => {
  const frame = useCurrentFrame();
  const from = prev && prev.suffix === k.suffix && prev.prefix === k.prefix ? prev.value : 0;
  const x = interpolate(frame, [4, 34], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const e = 1 - Math.pow(1 - x, 4);
  const val = prev && prev.value === k.value ? k.value : from + (k.value - from) * e;
  const shown = kpiText(k, val);
  return (
    <div style={{minWidth: 270, maxWidth: 420, ...style}}>
      <div style={{fontFamily: HEAD, fontWeight: 700, fontSize: size, lineHeight: 1, letterSpacing: -1.5,
        color: accent ? C.orange : C.ink, whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums'}}>{shown}</div>
      <div style={{fontFamily: FONT, fontSize: 28, color: C.text, marginTop: 12, lineHeight: 1.25, maxWidth: 300}}>{k.label}</div>
    </div>
  );
};

const TextPanel = ({cue, prev, next, dur}) => {
  const full = !cue.visual;
  const width = full ? 1400 : PANEL.w;
  const ch = (k) => !prev || prev[k] !== cue[k] || prev.mode !== cue.mode;
  const lv = (k) => !!next && (next[k] !== cue[k] || next.mode !== cue.mode);
  const kicker = usePart(ch('kicker'), lv('kicker'), dur, 0);
  const head = usePart(ch('headline'), lv('headline'), dur, 2);
  const sub = usePart(ch('sub') || ch('headline'), lv('sub') || lv('headline'), dur, 8);
  const src = usePart(ch('source'), lv('source'), dur, 14);
  const kpis = cue.kpis || [];
  const pk = (prev && prev.kpis) || [];
  const nk = (next && next.kpis) || [];
  const kSame = (a, b) => a && b && a.value === b.value && a.label === b.label && a.suffix === b.suffix;
  const k0 = usePart(!kSame(kpis[0], pk[0]), !kSame(kpis[0], nk[0]), dur, 10);
  const k1 = usePart(!kSame(kpis[1], pk[1]), !kSame(kpis[1], nk[1]), dur, 14);
  const longest = Math.max(0, ...kpis.map((k) => kpiText(k, k.value).length));
  const kpiSize = longest > 9 ? 64 : longest > 6 ? 76 : 96;
  const hSize = full ? fit(cue.headline, [[40, 104], [80, 88], [0, 72]]) : fit(cue.headline, [[34, 76], [64, 64], [0, 54]]);
  return (
    <AbsoluteFill>
      <div style={full
        ? {position: 'absolute', left: PANEL.x, width, top: 92, bottom: kpis.length ? 330 : 140, display: 'flex', flexDirection: 'column', justifyContent: 'center'}
        : {position: 'absolute', left: PANEL.x, top: 92, width}}>
        {cue.kicker && (
          <div style={{fontFamily: FONT, fontWeight: 700, fontSize: 24, letterSpacing: 2.5, textTransform: 'uppercase', color: C.sub, ...kicker}}>{cue.kicker}</div>
        )}
        {cue.mode === 'quickhit' ? (
          <div style={{display: 'flex', alignItems: 'flex-start', gap: 48, marginTop: 30, ...head}}>
            <div style={{fontFamily: HEAD, fontWeight: 700, fontSize: 220, lineHeight: 0.8, color: C.orange}}>{cue.n}</div>
            <div style={{fontFamily: HEAD, fontWeight: 700, fontSize: fit(cue.headline, [[60, 80], [110, 66], [0, 56]]), lineHeight: 1.1, color: C.ink, maxWidth: 1150}}>{cue.headline}</div>
          </div>
        ) : (
          <div style={{fontFamily: HEAD, fontWeight: 700, fontSize: hSize, lineHeight: 1.08, color: C.ink, marginTop: cue.kicker ? 22 : 0, letterSpacing: -0.5, ...head}}>
            {cue.headline}
          </div>
        )}
        {cue.sub && (
          <div style={{fontFamily: FONT, fontSize: full ? 40 : 34, lineHeight: 1.3, color: C.text, marginTop: 28, maxWidth: full ? 1300 : width, ...sub}}>{cue.sub}</div>
        )}
      </div>
      {kpis.length > 0 && (
        <div style={{position: 'absolute', left: PANEL.x, top: 790, display: 'flex', gap: 56}}>
          {kpis.map((k, i) => (
            <Kpi key={i} k={k} prev={pk[i]} size={kpiSize} accent={k.accent ?? (kpis.some((x) => x.accent !== undefined) ? false : kpis.length > 1 ? i === kpis.length - 1 : true)} style={i === 0 ? k0 : k1} />
          ))}
        </div>
      )}
      {cue.source && (
        <div style={{position: 'absolute', right: 60, bottom: 40, fontFamily: FONT, fontSize: 20, color: C.muted, ...src}}>Source: {cue.source}</div>
      )}
    </AbsoluteFill>
  );
};

// ---- Composition ----

export const Episode = (props) => {
  useFonts();
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const {cues, runs, firstStart} = useMemo(() => buildScenes(props), [props]);
  const line = useMemo(() => [...props.lines].reverse().find((l) => l.start_sec <= t) || null, [t, props.lines]);
  const inShow = t >= firstStart && t < props.outroStartSec;

  return (
    <AbsoluteFill style={{backgroundColor: C.paper}}>
      <Background />
      <Sequence from={0} durationInFrames={Math.max(1, Math.round(firstStart * FPS))} layout="none">
        <TitleCard {...props} dur={Math.round(firstStart * FPS)} />
      </Sequence>

      {runs.map((r, i) => {
        const from = Math.round(r.from * FPS);
        const dur = Math.max(1, Math.round(r.to * FPS) - from);
        const V = VISUALS[r.visual.template];
        if (!V) return null;
        const vp = r.visual.props || {};
        let itemFrames;
        if (ITEM_VISUALS.has(r.visual.template)) {
          const items = vp.items || vp.steps || [];
          const sceneLines = props.lines.filter((l) => l.start_sec >= r.from - 0.01 && l.start_sec < r.to);
          itemFrames = mentionTimes(items, sceneLines, r.from, r.to).map((sec) => Math.round((sec - r.from) * FPS));
        }
        return (
          <Sequence key={`v${i}`} from={from} durationInFrames={dur} layout="none">
            <div style={{position: 'absolute', left: STAGE.x, top: STAGE.y, width: STAGE.w, height: STAGE.h}}>
              <LayoutCtx.Provider value={{v: true, w: STAGE.w, h: STAGE.h, bare: true}}>
                <Scene dur={dur}><V {...vp} dur={dur} itemFrames={itemFrames} /></Scene>
              </LayoutCtx.Provider>
            </div>
          </Sequence>
        );
      })}

      {cues.map((c, i) => {
        const from = Math.round(c.from * FPS);
        const dur = Math.max(1, Math.round(c.to * FPS) - from);
        return (
          <Sequence key={`c${i}`} from={from} durationInFrames={dur} layout="none">
            {c.mode === 'voice'
              ? <Scene dur={dur}><Voice {...c.voice} dur={dur} /></Scene>
              : <TextPanel cue={c} prev={cues[i - 1]} next={cues[i + 1]} dur={dur} />}
          </Sequence>
        );
      })}

      {inShow && <Frame segment={line ? line.segment : ''} />}

      <Sequence from={Math.round(props.outroStartSec * FPS)} layout="none">
        <OutroCard {...props} dur={Math.max(1, Math.round((props.totalSec - props.outroStartSec) * FPS))} />
      </Sequence>
      {props.audioFile && <Audio src={staticFile(props.audioFile)} />}
    </AbsoluteFill>
  );
};
