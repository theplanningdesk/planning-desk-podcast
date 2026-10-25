#!/usr/bin/env python3
"""Send the Sunday newsletter through Buttondown.

Uses the script's "newsletter" block (subject and a markdown body) and adds the listen and
watch links. Needs the BUTTONDOWN_API_KEY secret. newsletter.status in config.json decides
whether the email goes out at once ("about_to_send") or waits in Buttondown as a draft
("draft") for a final look.

Usage: python newsletter.py 2026-11-08
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from podcast_lib import ROOT, load_config

OUT = ROOT / "build" / "out"


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    stem = sys.argv[1]
    cfg = load_config()
    pod, nl = cfg["podcast"], cfg.get("newsletter", {})
    script = json.loads((ROOT / "episodes" / "scripts" / f"script-{stem}.json").read_text(encoding="utf-8"))
    letter = script.get("newsletter") or {}
    if not letter.get("body_md"):
        print("No newsletter block in the script; nothing to send.")
        return 0

    links = [f"[Listen to the episode and read the transcript]({pod['base_url'].rstrip('/')}/e/{stem}.html)"]
    yt = OUT / f"planning-desk-{stem}.youtube.txt"
    if yt.exists():
        links.append(f"[Watch on YouTube]({yt.read_text().strip()})")
    for name, key in (("Apple Podcasts", "apple_url"), ("Spotify", "spotify_url")):
        if pod.get(key):
            links.append(f"[{name}]({pod[key]})")
    body = "\n\n".join([letter["body_md"].strip(), " · ".join(links), "---",
                        f"*{pod['ai_disclosure']}*"])

    req = urllib.request.Request(
        "https://api.buttondown.com/v1/emails",
        data=json.dumps({"subject": letter.get("subject") or script.get("episode_title", "The Planning Desk"),
                         "body": body, "status": nl.get("status", "draft")}).encode(),
        method="POST")
    req.add_header("Authorization", f"Token {os.environ['BUTTONDOWN_API_KEY']}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            res = json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        raise SystemExit(f"Buttondown {err.code}: {err.read().decode(errors='replace')[:800]}") from err
    print(f"Newsletter {'sent' if nl.get('status') == 'about_to_send' else 'saved as a draft'}: {res.get('id', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
