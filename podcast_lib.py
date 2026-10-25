"""Shared helpers for The Planning Desk render pipeline: ElevenLabs calls and ffmpeg utilities."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import requests

API = "https://api.elevenlabs.io/v1"
ROOT = Path(__file__).resolve().parent
RETRY_STATUS = {429, 500, 502, 503, 504}


class ElevenLabsError(RuntimeError):
    pass


def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY is not set. Add it as a repository secret (Settings > Secrets and variables > Actions).")
    return key


def post_audio(path: str, body: dict, out: Path, *, params: dict | None = None, attempts: int = 6) -> None:
    """POST to an ElevenLabs endpoint that returns audio bytes, with backoff on rate limits and server errors."""
    headers = {"xi-api-key": api_key(), "accept": "audio/mpeg", "content-type": "application/json"}
    delay = 4.0
    for attempt in range(1, attempts + 1):
        r = requests.post(f"{API}{path}", headers=headers, json=body, params=params, timeout=300)
        if r.status_code == 200 and r.content:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(r.content)
            return
        if r.status_code in RETRY_STATUS and attempt < attempts:
            wait = float(r.headers.get("retry-after", delay))
            print(f"  ElevenLabs {r.status_code} on {path}, retrying in {wait:.0f}s ({attempt}/{attempts})")
            time.sleep(wait)
            delay = min(delay * 2, 60)
            continue
        raise ElevenLabsError(f"{path} failed with HTTP {r.status_code}: {r.text[:600]}")


def cache_key(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]


def run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd[:6])}...\n{res.stderr[-1500:]}")


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def to_wav(src: Path, dst: Path, filters: str | None = None) -> None:
    """Decode to 44.1 kHz stereo PCM so every piece concatenates cleanly."""
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src)]
    if filters:
        cmd += ["-af", filters]
    cmd += ["-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(dst)]
    run(cmd)


def tighten(src: Path, dst: Path, max_pause: float = 0.28, edge: float = 0.04, threshold_db: float = -42.0) -> None:
    """Trim a voiced line's leading and trailing silence to `edge` seconds and shorten any pause
    inside it to at most `max_pause`, so the hosts never seem to wait. Expects 16-bit PCM WAV."""
    import wave
    import numpy as np

    with wave.open(str(src), "rb") as w:
        params = w.getparams()
        data = np.frombuffer(w.readframes(params.nframes), dtype=np.int16).reshape(-1, params.nchannels)
    rate = params.framerate
    hop = max(1, rate // 100)  # 10 ms
    n = len(data) // hop
    if n < 3:
        dst.write_bytes(src.read_bytes())
        return
    mono = data[: n * hop].astype(np.float32).mean(axis=1).reshape(n, hop)
    rms = np.sqrt((mono ** 2).mean(axis=1)) / 32768.0
    loud = 20 * np.log10(np.maximum(rms, 1e-9)) > threshold_db
    if not loud.any():
        dst.write_bytes(src.read_bytes())
        return
    first, last = int(np.argmax(loud)), int(n - 1 - np.argmax(loud[::-1]))
    e, keep = int(round(edge * 100)), int(round(max_pause * 100))
    pieces, i, start = [], first, max(0, first - e)
    while i <= last:
        if loud[i]:
            i += 1
            continue
        j = i
        while j <= last and not loud[j]:
            j += 1
        if j - i > keep:  # a long pause: keep its first and last halves only
            pieces.append((start * hop, (i + keep // 2) * hop))
            start = j - (keep - keep // 2)
        i = j
    pieces.append((start * hop, min(len(data), (last + 1 + e) * hop)))
    fade = max(1, rate // 333)  # 3 ms fades at each cut, so no clicks
    out = []
    for a, b in pieces:
        seg = data[a:b].astype(np.float32)
        k = min(fade, len(seg) // 2)
        if k:
            ramp = np.linspace(0, 1, k, dtype=np.float32)[:, None]
            seg[:k] *= ramp
            seg[-k:] *= ramp[::-1]
        out.append(seg)
    joined = np.clip(np.concatenate(out), -32768, 32767).astype(np.int16)
    with wave.open(str(dst), "wb") as w:
        w.setparams(params)
        w.writeframes(joined.tobytes())


def silence(dst: Path, seconds: float) -> None:
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", f"{seconds:.3f}", "-c:a", "pcm_s16le", str(dst)])


def fit_length(src: Path, dst: Path, seconds: float) -> None:
    """Trim or pad a clip to exactly `seconds`."""
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", f"apad=whole_dur={seconds},atrim=0:{seconds}",
         "-ar", "44100", "-ac", "2", "-b:a", "192k", str(dst)])


def tone(dst: Path, seconds: float, freq: int) -> None:
    """Placeholder audio for dry runs without an API key."""
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=44100",
         "-t", f"{seconds:.3f}", "-af", "volume=0.25", "-b:a", "128k", str(dst)])
