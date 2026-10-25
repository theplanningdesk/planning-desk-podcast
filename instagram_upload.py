#!/usr/bin/env python3
"""Post a weekday Short to Instagram as a Reel (Instagram API with Instagram Login).

Needs repository secrets INSTAGRAM_USER_ID and INSTAGRAM_TOKEN (a long-lived token).
Meta fetches the video from a public URL, so the Short must already be attached to the
episode's GitHub release. The token is refreshed on every run; if the refresh returns a
new token and GH_ADMIN_TOKEN is set, the INSTAGRAM_TOKEN secret is updated too.

Usage: python instagram_upload.py 2026-11-02
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from podcast_lib import ROOT, load_config

API = "https://graph.instagram.com/v26.0"
REPO = os.environ.get("GITHUB_REPOSITORY", "theplanningdesk/podcast")


def call(method: str, url: str, data: dict | None = None, token: str | None = None) -> dict:
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        raise SystemExit(f"Instagram API {err.code}: {err.read().decode(errors='replace')[:800]}") from err


def refresh(token: str) -> str:
    """Long-lived tokens last 60 days; refreshing resets the clock."""
    try:
        res = call("GET", f"https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token={urllib.parse.quote(token)}")
    except SystemExit as err:
        print(f"Token refresh skipped: {err}")
        return token
    new = res.get("access_token") or token
    days = int(res.get("expires_in", 0)) // 86400
    print(f"Instagram token refreshed, valid for {days} more days.")
    if new != token:
        admin = os.environ.get("GH_ADMIN_TOKEN")
        if admin:
            subprocess.run(["gh", "secret", "set", "INSTAGRAM_TOKEN", "-R", REPO, "--body", new],
                           env={**os.environ, "GH_TOKEN": admin}, check=True, capture_output=True)
            print("Stored the refreshed token in the INSTAGRAM_TOKEN secret.")
        else:
            print("::warning::Instagram returned a new token but GH_ADMIN_TOKEN isn't set, so it wasn't saved.")
    return new


def public_video_url(stem: str) -> str:
    """The release download link redirects to a signed file URL; hand Meta the final URL."""
    url = f"https://github.com/{REPO}/releases/download/episode-{stem}/planning-desk-{stem}-short.mp4"
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.geturl()
    except Exception as err:  # fall back to the redirecting link
        print(f"Couldn't resolve the release redirect ({err}); using the release link.")
        return url


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    stem = sys.argv[1]
    cfg = load_config()
    user, token = os.environ["INSTAGRAM_USER_ID"], os.environ["INSTAGRAM_TOKEN"]
    token = refresh(token)

    script = json.loads((ROOT / "episodes" / "scripts" / f"script-{stem}.json").read_text(encoding="utf-8"))
    short = script.get("short") or {}
    tags = " ".join(f"#{h.lstrip('#')}" for h in short.get("hashtags", [])[:5])
    caption = "\n\n".join(x for x in [(short.get("caption") or "").strip(), tags] if x)[:2100]

    container = call("POST", f"{API}/{user}/media", {
        "media_type": "REELS", "video_url": public_video_url(stem), "caption": caption, "share_to_feed": True,
    }, token)["id"]
    print(f"Container {container} created; waiting for Instagram to process the video.")
    status = ""
    for _ in range(20):  # up to 10 minutes
        time.sleep(30)
        status = call("GET", f"{API}/{container}?fields=status_code", token=token).get("status_code", "")
        print(f"  status {status}")
        if status in ("FINISHED", "ERROR", "EXPIRED"):
            break
    if status != "FINISHED":
        raise SystemExit(f"Instagram didn't finish processing the Reel (status {status or 'unknown'}).")
    media = call("POST", f"{API}/{user}/media_publish", {"creation_id": container}, token)["id"]
    link = call("GET", f"{API}/{media}?fields=permalink", token=token).get("permalink", "")
    print(f"Published Reel {link or media}")
    (ROOT / "build" / "out" / f"planning-desk-{stem}-short.instagram.txt").write_text(f"{link or media}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
