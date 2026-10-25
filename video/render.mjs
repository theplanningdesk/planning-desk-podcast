// Render The Planning Desk episode video with Remotion.
//
//   node render.mjs --stem 2026-10-25 [--from 0 --to 90] [--stills 12,70,140] [--concurrency 2]
//   node render.mjs --stem 2026-11-02 --short [--stills 3,20]   (9:16 Short from the -short.mp3/json)
//
// Inputs (relative to the repo root):
//   build/out/planning-desk-<stem>.mp3 and .json (from render.py)
//   episodes/visuals/visuals-<stem>.json      (visual cues from the script writer; optional)
//   assets/outro.mp3                          (to know when the outro music starts)
// Output: build/out/planning-desk-<stem>.mp4 (or stills in build/stills/)
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import {execFileSync, spawnSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const FPS = 30;

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, arr) => (a.startsWith('--') ? [...acc, [a.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : 'true']] : acc), []),
);
const stem = args.stem;
if (!stem) throw new Error('--stem is required');
const isShort = args.short === 'true';

const out = path.join(root, 'build', 'out');
const base = `planning-desk-${stem}${isShort ? '-short' : ''}`;
const mp3 = path.join(out, `${base}.mp3`);
const meta = JSON.parse(fs.readFileSync(path.join(out, `${base}.json`), 'utf8'));
const config = JSON.parse(fs.readFileSync(path.join(root, 'config.json'), 'utf8'));
const visualsPath = path.join(root, 'episodes', 'visuals', `visuals-${stem}.json`);
const visuals = fs.existsSync(visualsPath) ? JSON.parse(fs.readFileSync(visualsPath, 'utf8')) : {};
const cues = (isShort ? visuals.short_cues : visuals.cues) || [];
if (!cues.length) console.warn(`No visual cues found at ${visualsPath}; using segment cards only.`);

const probe = (file) => Number(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', file]).toString().trim());
const totalSec = probe(mp3);
const outroStartSec = meta.outro_start_sec ?? Math.max(0, totalSec - probe(path.join(root, 'assets', 'outro.mp3')));

// Loudness envelope, one value per video frame, for the hosts' voice meters.
const envelope = (() => {
  const rate = 3000;
  const res = spawnSync('ffmpeg', ['-v', 'error', '-i', mp3, '-ac', '1', '-ar', String(rate), '-f', 'f32le', '-'], {maxBuffer: 1 << 30});
  const buf = res.stdout;
  const samples = new Float32Array(buf.buffer, buf.byteOffset, Math.floor(buf.length / 4));
  const per = rate / FPS;
  const values = [];
  for (let f = 0; f * per < samples.length; f++) {
    let sum = 0;
    const start = Math.floor(f * per), end = Math.min(samples.length, Math.floor((f + 1) * per));
    for (let i = start; i < end; i++) sum += samples[i] * samples[i];
    values.push(Math.sqrt(sum / Math.max(1, end - start)));
  }
  const peak = values.slice().sort((a, b) => a - b)[Math.floor(values.length * 0.98)] || 1;
  return values.map((v) => Math.round(Math.min(1, v / peak) * 100) / 100);
})();

// Remotion serves the audio from video/public.
const publicDir = path.join(here, 'public');
fs.mkdirSync(publicDir, {recursive: true});
const audioFile = `${isShort ? 'short' : 'episode'}-${stem}.mp3`;
fs.copyFileSync(mp3, path.join(publicDir, audioFile));

const week = meta.week || '';
const titleParts = (meta.title || '').split(': ');
const dateLabel = (() => {
  if (!meta.run_date) return '';
  const d = new Date(`${meta.run_date}T12:00:00Z`);
  const label = meta.format === 'saturday' ? (config.formats?.saturday?.title_prefix || 'Book of the week') : 'Daily';
  return `${label} · ${d.toLocaleDateString('en-GB', {weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC'})}`;
})();
const shortProps = {
  show: config.show,
  dateLabel,
  totalSec,
  endCardSec: meta.end_card_sec ?? totalSec - 2.5,
  lines: meta.timeline,
  cues,
  audioFile,
  cta: config.formats?.[meta.format]?.short_cta || config.short?.cta || 'Every weekday on Apple Podcasts and Spotify',
};
const longProps = {
  show: config.show,
  week: (() => {
    const d = meta.run_date ? new Date(`${meta.run_date}T12:00:00Z`).toLocaleDateString('en-GB', {weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC'}) : '';
    if (meta.format === 'saturday') return `${config.formats?.saturday?.title_prefix || 'Book of the week'} · ${d}`;
    return week.includes('-W') ? `Week ${Number(week.split('-W')[1])} · ${d}` : d;
  })(),
  episodeTitle: titleParts.length > 1 ? titleParts.slice(1).join(': ') : meta.title,
  totalSec,
  outroStartSec,
  lines: meta.timeline,
  cues,
  envelope,
  audioFile,
  credit: config.podcast?.credit || '',
  disclosure: config.podcast?.ai_disclosure || '',
  daily: Boolean(config.formats?.daily),
  format: meta.format || 'weekly',
  site: (config.podcast?.base_url || '').replace(/^https?:\/\//, '').replace(/\/$/, ''),
};

const browserExecutable = process.env.REMOTION_BROWSER || null;
const inputProps = isShort ? shortProps : longProps;
console.log(`Bundling ${isShort ? 'Short' : 'Episode'} (${meta.timeline.length} lines, ${cues.length} cues, ${totalSec.toFixed(1)} s)...`);
const serveUrl = await bundle({entryPoint: path.join(here, 'src', 'index.jsx'), publicDir});
const composition = await selectComposition({serveUrl, id: isShort ? 'Short' : 'Episode', inputProps, browserExecutable});

if (args.stills) {
  const dir = path.join(root, 'build', 'stills');
  fs.mkdirSync(dir, {recursive: true});
  for (const s of args.stills.split(',').map(Number)) {
    const file = path.join(dir, `${stem}${isShort ? '-short' : ''}-${String(s).padStart(4, '0')}s.png`);
    await renderStill({composition, serveUrl, output: file, frame: Math.round(s * FPS), inputProps, browserExecutable});
    console.log(`Still ${file}`);
  }
} else {
  const from = args.from !== undefined ? Math.round(Number(args.from) * FPS) : 0;
  const to = args.to !== undefined ? Math.min(composition.durationInFrames - 1, Math.round(Number(args.to) * FPS)) : composition.durationInFrames - 1;
  const suffix = args.from !== undefined || args.to !== undefined ? `-preview` : '';
  const file = path.join(out, `${base}${suffix}.mp4`);
  let last = -1;
  await renderMedia({
    composition, serveUrl, codec: 'h264', audioCodec: 'aac', crf: 20, outputLocation: file, inputProps,
    frameRange: [from, to], concurrency: Number(args.concurrency || 2), browserExecutable,
    onProgress: ({progress}) => {
      const pct = Math.floor(progress * 100);
      if (pct >= last + 10) { last = pct; console.log(`  ${pct}%`); }
    },
  });
  console.log(`Video ${file}`);
}
