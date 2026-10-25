#!/usr/bin/env python3
"""Render a Planning Desk episode from a script JSON produced by the script writer agent.

Each spoken line is voiced with ElevenLabs text-to-speech (one take per line, cached so
re-runs don't spend credits twice), then intro music, dialogue and outro music are
stitched with ffmpeg, loudness-normalised and written as an MP3 with a transcript and
a timeline next to it.

Daily scripts ("format": "daily") and the Saturday book episode ("format": "saturday") get shorter
music at each end (formats.<format>.jingle_sec) and, when the script has a "short" block, a separate
vertical-video soundtrack (planning-desk-<stem>-short.mp3/json).

Usage:
  python render.py episodes/scripts/script-2026-10-23.json
  python render.py episodes/scripts/script-2026-10-23.json --fake   # no API key, placeholder tones
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from podcast_lib import (ROOT, ElevenLabsError, cache_key, duration, load_config, post_audio,
                         run, silence, tighten, to_wav, tone)

BUILD = ROOT / "build"
CACHE = BUILD / "cache"


def episode_format(script: dict) -> str:
    fmt = script.get("format")
    return fmt if fmt in ("daily", "saturday") else "weekly"


def episode_title(cfg: dict, script: dict) -> str:
    """Feed title without the show name: 'Week 44: ...', 'Mon 2 Nov: ...' or 'Book of the week: ...'."""
    from datetime import date
    name = (script.get("episode_title") or "").strip()
    if episode_format(script) == "saturday":
        prefix = cfg.get("formats", {}).get("saturday", {}).get("title_prefix", "Book of the week")
        return f"{prefix}: {name}".strip(": ")
    if episode_format(script) == "daily":
        d = date.fromisoformat(script.get("run_date"))
        return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}: {name}".strip(": ")
    week = script.get("week", "")
    week_no = week.split("-W")[-1] if "-W" in week else ""
    return f"Week {week_no}: {name}".strip(": ")


def collect_lines(script: dict) -> list[dict]:
    lines = []
    for seg in script["segments"]:
        if seg.get("type") != "speech":
            continue
        for i, line in enumerate(seg["lines"]):
            text = line["text"].strip()
            if not text:
                continue
            lines.append({"segment": seg["id"], "first_in_segment": i == 0,
                          "speaker": line["speaker"], "text": text})
    if not lines:
        raise SystemExit("The script has no speech lines.")
    return lines


class Voicer:
    def __init__(self, cfg: dict, fake: bool):
        self.cfg = cfg
        self.fake = fake
        self.model = cfg["tts"]["model_id"]
        self.fallback = cfg["tts"].get("fallback_model_id")

    def voice(self, line: dict) -> Path:
        speaker = self.cfg["voices"][line["speaker"]]
        settings = self.cfg["tts"].get("voice_settings") or {}
        key = cache_key("fake" if self.fake else self.model, speaker["voice_id"], line["text"], settings)
        out = CACHE / f"{key}.mp3"
        if out.exists():
            return out
        if self.fake:
            words = len(line["text"].split())
            tone(out, max(words / 2.6, 0.6), {"F": 440, "M": 220}.get(line["speaker"], 165))
            return out
        body = {"text": line["text"], "model_id": self.model}
        if settings:
            body["voice_settings"] = settings
        path = f"/text-to-speech/{speaker['voice_id']}"
        params = {"output_format": self.cfg["tts"]["output_format"]}
        try:
            post_audio(path, body, out, params=params)
        except ElevenLabsError as err:
            msg = str(err).lower()
            if "voice" in msg and ("not found" in msg or "not_found" in msg):
                raise ElevenLabsError(
                    f"{err}\nAdd the voice '{speaker['elevenlabs_voice']}' to My Voices in ElevenLabs, "
                    "or change its voice_id in config.json.") from err
            if self.fallback and "model" in msg and self.model != self.fallback:
                print(f"  Model {self.model} rejected, switching to {self.fallback} for the rest of the run.")
                self.model = self.fallback
                return self.voice(line)
            raise
        return out


def build_episode(script_path: Path, fake: bool) -> Path:
    cfg = load_config()
    mix = cfg["mix"]
    script = json.loads(script_path.read_text(encoding="utf-8"))
    stem = script_path.stem.replace("script-", "")
    work = BUILD / stem
    out_dir = BUILD / "out"
    for d in (CACHE, work, out_dir):
        d.mkdir(parents=True, exist_ok=True)

    intro, outro = ROOT / "assets" / "intro.mp3", ROOT / "assets" / "outro.mp3"
    for asset in (intro, outro):
        if not asset.exists():
            raise SystemExit(f"Missing {asset.relative_to(ROOT)}. Run make_jingles.py first.")

    fmt = episode_format(script)
    jingle_sec = float(cfg.get("formats", {}).get(fmt, {}).get("jingle_sec", 10))
    lines = collect_lines(script)
    chars = sum(len(l["text"]) for l in lines)
    print(f"{fmt} episode: {len(lines)} lines, {chars} characters to voice ({'fake' if fake else cfg['tts']['model_id']}).")

    voicer = Voicer(cfg, fake)
    clips = voice_all(voicer, lines, cfg)

    # Normalise every piece to the same PCM format, then concatenate.
    gap_line, gap_seg = work / "gap_line.wav", work / "gap_seg.wav"
    gap_intro, gap_outro = work / "gap_intro.wav", work / "gap_outro.wav"
    silence(gap_line, mix["gap_between_lines_sec"])
    silence(gap_seg, mix["gap_between_segments_sec"])
    silence(gap_intro, mix["gap_after_intro_sec"])
    silence(gap_outro, mix["gap_before_outro_sec"])

    # Shorter episodes use the first seconds of the intro and the last seconds of the outro,
    # so the outro still ends on its final chord.
    intro_len = min(duration(intro), jingle_sec)
    outro_full = duration(outro)
    outro_start = max(outro_full - jingle_sec, 0)
    outro_len = outro_full - outro_start
    intro_wav, outro_wav = work / "intro.wav", work / "outro.wav"
    to_wav(intro, intro_wav, f"atrim=0:{intro_len:.2f},"
                             f"afade=t=out:st={max(intro_len - mix['intro_fade_out_sec'], 0):.2f}:d={mix['intro_fade_out_sec']}")
    to_wav(outro, outro_wav, f"atrim={outro_start:.2f},asetpts=PTS-STARTPTS,afade=t=in:d={mix['outro_fade_in_sec']},"
                             f"afade=t=out:st={max(outro_len - mix['outro_fade_out_sec'], 0):.2f}:d={mix['outro_fade_out_sec']}")

    sequence: list[Path] = [intro_wav, gap_intro]
    timeline, t = [], duration(intro_wav) + mix["gap_after_intro_sec"]
    for i, (line, clip) in enumerate(zip(lines, clips)):
        if i > 0:
            gap = gap_seg if line["first_in_segment"] else gap_line
            sequence.append(gap)
            t += mix["gap_between_segments_sec"] if line["first_in_segment"] else mix["gap_between_lines_sec"]
        wav = work / f"line_{i:03d}.wav"
        # A voice can set its own tempo (the Saturday narrator reads slower than the news hosts).
        tempo = float(cfg["voices"][line["speaker"]].get("tempo", mix.get("speech_tempo", 1.0)))
        to_wav(clip, wav, f"atempo={tempo}" if abs(tempo - 1.0) > 0.001 else None)
        if mix.get("max_pause_sec"):
            raw = wav.with_suffix(".raw.wav")
            wav.rename(raw)
            tighten(raw, wav, max_pause=float(mix["max_pause_sec"]), edge=float(mix.get("line_edge_sec", 0.04)))
        d = duration(wav)
        timeline.append({"start_sec": round(t, 2), "duration_sec": round(d, 2), "segment": line["segment"],
                         "speaker": cfg["voices"][line["speaker"]]["name"], "text": line["text"]})
        sequence.append(wav)
        t += d
    sequence += [gap_outro, outro_wav]

    concat_list = work / "concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in sequence), encoding="utf-8")
    joined = work / "joined.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(joined)])

    week = script.get("week", "")
    title = f"{cfg['show']}, {episode_title(cfg, script)}"
    mp3 = out_dir / f"planning-desk-{stem}.mp3"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(joined),
         "-af", f"loudnorm=I={mix['loudness_lufs']}:TP={mix['true_peak_db']}:LRA=11",
         "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-b:a", mix["mp3_bitrate"],
         "-id3v2_version", "3",
         "-metadata", f"title={title}", "-metadata", f"artist={cfg['artist']}",
         "-metadata", f"album={cfg['show']}", "-metadata", f"date={script.get('run_date', '')}",
         "-metadata", "genre=Podcast", str(mp3)])

    total = duration(mp3)
    (out_dir / f"planning-desk-{stem}.json").write_text(json.dumps({
        "title": title, "format": fmt, "run_date": script.get("run_date"), "week": week, "duration_sec": round(total, 1),
        "outro_start_sec": round(total - outro_len, 2),
        "lines": len(lines), "characters": chars, "model_id": "fake" if fake else voicer.model,
        "timeline": timeline}, indent=2, ensure_ascii=False), encoding="utf-8")
    transcript = [title, ""] + [f"[{int(e['start_sec'] // 60):02d}:{int(e['start_sec'] % 60):02d}] "
                                 f"{e['speaker'].upper()}: {e['text']}" for e in timeline]
    (out_dir / f"planning-desk-{stem}.txt").write_text("\n".join(transcript) + "\n", encoding="utf-8")

    print(f"Done: {mp3.relative_to(ROOT)}  {int(total // 60)}:{int(total % 60):02d}  ({title})")

    if fmt in ("daily", "saturday") and (script.get("short") or {}).get("lines"):
        build_short(script, stem, cfg, voicer, work, out_dir)
    return mp3


def voice_all(voicer: "Voicer", lines: list[dict], cfg: dict) -> list[Path]:
    clips: list[Path | None] = [None] * len(lines)
    with ThreadPoolExecutor(max_workers=cfg["tts"].get("max_workers", 3)) as pool:
        futures = {pool.submit(voicer.voice, line): i for i, line in enumerate(lines)}
        for n, fut in enumerate(as_completed(futures), 1):
            clips[futures[fut]] = fut.result()
            if n % 10 == 0 or n == len(lines):
                print(f"  voiced {n}/{len(lines)}")
    return clips  # type: ignore[return-value]


def build_short(script: dict, stem: str, cfg: dict, voicer: "Voicer", work: Path, out_dir: Path) -> Path:
    """Soundtrack for the vertical video: the short's own lines, no music, a touch louder for phones."""
    mix, sc = cfg["mix"], cfg.get("short", {})
    short = script["short"]
    lines = [{"segment": "short", "first_in_segment": i == 0, "speaker": l["speaker"], "text": l["text"].strip()}
             for i, l in enumerate(short["lines"]) if l.get("text", "").strip()]
    print(f"Short: {len(lines)} lines, {sum(len(l['text']) for l in lines)} characters.")
    clips = voice_all(voicer, lines, cfg)
    sdir = work / "short"
    sdir.mkdir(exist_ok=True)
    lead, tail, gap = sdir / "lead.wav", sdir / "tail.wav", sdir / "gap.wav"
    silence(lead, sc.get("lead_sec", 0.3))
    silence(tail, sc.get("tail_sec", 2.5))
    silence(gap, mix["gap_between_lines_sec"])
    tempo = float(mix.get("speech_tempo", 1.0))
    seq, timeline, t = [lead], [], sc.get("lead_sec", 0.3)
    for i, (line, clip) in enumerate(zip(lines, clips)):
        if i > 0:
            seq.append(gap)
            t += mix["gap_between_lines_sec"]
        wav = sdir / f"line_{i:02d}.wav"
        t_line = float(cfg["voices"][line["speaker"]].get("tempo", tempo))
        to_wav(clip, wav, f"atempo={t_line}" if abs(t_line - 1.0) > 0.001 else None)
        if mix.get("max_pause_sec"):
            raw = wav.with_suffix(".raw.wav")
            wav.rename(raw)
            tighten(raw, wav, max_pause=float(mix["max_pause_sec"]), edge=float(mix.get("line_edge_sec", 0.04)))
        d = duration(wav)
        timeline.append({"start_sec": round(t, 2), "duration_sec": round(d, 2), "segment": "short",
                         "speaker": cfg["voices"][line["speaker"]]["name"], "text": line["text"]})
        seq.append(wav)
        t += d
    end_card_at = t
    seq.append(tail)
    lst = sdir / "concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in seq), encoding="utf-8")
    joined = sdir / "joined.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
    mp3 = out_dir / f"planning-desk-{stem}-short.mp3"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(joined),
         "-af", f"loudnorm=I={sc.get('loudness_lufs', -14)}:TP={mix['true_peak_db']}:LRA=11",
         "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-b:a", mix["mp3_bitrate"], str(mp3)])
    total = duration(mp3)
    (out_dir / f"planning-desk-{stem}-short.json").write_text(json.dumps({
        "title": short.get("title") or script.get("episode_title"), "format": episode_format(script),
        "run_date": script.get("run_date"),
        "duration_sec": round(total, 1), "end_card_sec": round(end_card_at, 2), "timeline": timeline},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Done: {mp3.relative_to(ROOT)}  {total:.1f}s")
    return mp3


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", type=Path, help="path to a script-YYYY-MM-DD.json file")
    ap.add_argument("--fake", action="store_true", help="placeholder tones instead of ElevenLabs (no credits)")
    args = ap.parse_args()
    build_episode(args.script.resolve(), args.fake)
    return 0


if __name__ == "__main__":
    sys.exit(main())
