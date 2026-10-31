#!/usr/bin/env python3
"""Prepare the post for The Planning Desk's LinkedIn Page, and post it there when Page access exists.

The show never posts on a personal profile. For every episode this writes the script's
linkedin.page_post text, with "Links in the first comment." under its "Listen:" line, to
build/out/planning-desk-<stem>-linkedin.txt, and the links for the first comment to
build/out/planning-desk-<stem>-linkedin-comment.txt. LinkedIn shows posts with outside links to fewer
people, so the links go in the comment. The workflow attaches both files to the release and the
dispatcher hands them over for posting by hand:
  Sunday and Saturday: the YouTube video and Spotify
  Weekdays: Spotify and Apple Podcasts (the Short itself is uploaded to LinkedIn as the post's video)

Automatic posting needs LinkedIn's Community Management API, which LinkedIn grants only after
reviewing the app. Once approved, set:
  LINKEDIN_PAGE_TOKEN   secret, a token from a Page admin with the w_organization_social scope
  LINKEDIN_ORG_ID       repository variable, the Page's numeric organization id
  LINKEDIN_TOKEN_SET_ON repository variable, YYYY-MM-DD the token was made (warns after 50 days)
Without them the script only writes the text file.

Usage: python linkedin_post.py 2026-11-08 [--text-only]
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date

from podcast_lib import ROOT, load_config

OUT = ROOT / "build" / "out"


def call(method: str, url: str, token: str, data: dict | None = None) -> tuple[dict, dict]:
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Restli-Protocol-Version", "2.0.0")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
            return (json.loads(body) if body else {}), dict(resp.headers)
    except urllib.error.HTTPError as err:
        msg = err.read().decode(errors="replace")[:600]
        if err.code == 401:
            raise SystemExit("LinkedIn Page token expired or revoked. Make a new one and update the "
                             "LINKEDIN_PAGE_TOKEN secret and the LINKEDIN_TOKEN_SET_ON variable.") from err
        if err.code == 403:
            raise SystemExit("LinkedIn refused the Page post (403). The token needs w_organization_social, "
                             "its owner must be a Page admin, and the app needs Community Management access.") from err
        raise SystemExit(f"LinkedIn API {err.code}: {msg}") from err


def link_lines(stem: str, script: dict, pod: dict) -> list[str]:
    """The links that go under the post's Listen line, by format."""
    page = f"{pod['base_url'].rstrip('/')}/e/{stem}.html"
    yt_file = OUT / f"planning-desk-{stem}.youtube.txt"
    youtube = yt_file.read_text().strip() if yt_file.exists() else ""
    spotify, apple = pod.get("spotify_url", ""), pod.get("apple_url", "")
    if script.get("format") == "daily":
        lines = [f"🎧 Spotify: {spotify}" if spotify else "", f"🎧 Apple Podcasts: {apple}" if apple else ""]
    else:
        lines = [f"▶️ YouTube: {youtube}" if youtube else "", f"🎧 Spotify: {spotify}" if spotify else ""]
    lines = [l for l in lines if l]
    return lines or [f"🎧 {page}"]


def with_links(text: str, links: list[str]) -> str:
    """Put the given lines straight under the "Listen:" (or "Watch or listen:") line, above the hashtags."""
    rows = text.splitlines()
    at = next((i for i, r in enumerate(rows) if r.strip().lower().startswith(("listen:", "watch or listen:", "watch:"))), None)
    if at is None:  # no Listen line: put them above the hashtag line, or at the end
        tags = [i for i, r in enumerate(rows) if r.strip().startswith("#")]
        at = (tags[0] - 1) if tags else len(rows) - 1
        while at >= 0 and not rows[at].strip():
            at -= 1
    rows[at + 1:at + 1] = links
    return "\n".join(rows).strip() + "\n"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit(__doc__)
    stem = args[0]
    cfg = load_config()
    pod = cfg["podcast"]

    script = json.loads((ROOT / "episodes" / "scripts" / f"script-{stem}.json").read_text(encoding="utf-8"))
    text = ((script.get("linkedin") or {}).get("page_post") or (script.get("short") or {}).get("caption") or "").strip()
    if not text:
        print("No linkedin.page_post in the script; nothing to post.")
        return 0
    links = link_lines(stem, script, pod)
    post = with_links(text, ["Links in the first comment."])
    lead = {"daily": "Today's full briefing:", "saturday": "The full book episode:"}.get(script.get("format"), "The full week in review:")
    (OUT / f"planning-desk-{stem}-linkedin.txt").write_text(post, encoding="utf-8")
    (OUT / f"planning-desk-{stem}-linkedin-comment.txt").write_text("\n".join([lead] + links) + "\n", encoding="utf-8")
    print(f"Page post and first-comment text written for {stem}.")
    if "--text-only" in sys.argv:
        return 0
    yt = OUT / f"planning-desk-{stem}.youtube.txt"
    url = yt.read_text().strip() if yt.exists() else f"{pod['base_url'].rstrip('/')}/e/{stem}.html"

    token, org = os.environ.get("LINKEDIN_PAGE_TOKEN", ""), os.environ.get("LINKEDIN_ORG_ID", "").strip()
    if not (token and org):
        print("No Page access configured (LINKEDIN_PAGE_TOKEN and LINKEDIN_ORG_ID); post it by hand.")
        return 0
    set_on = os.environ.get("LINKEDIN_TOKEN_SET_ON", "")
    if set_on:
        age = (date.today() - date.fromisoformat(set_on.strip())).days
        if age > 50:
            print(f"::warning::The LinkedIn Page token is {age} days old and stops working at 60. Renew it soon.")

    meta = json.loads((OUT / f"planning-desk-{stem}.json").read_text(encoding="utf-8"))
    body = {
        "author": f"urn:li:organization:{org}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {"com.linkedin.ugc.ShareContent": {
            "shareCommentary": {"text": post[:2900]},
            "shareMediaCategory": "ARTICLE",
            "media": [{"status": "READY", "originalUrl": url, "title": {"text": meta.get("title", pod["title"])[:200]}}],
        }},
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    _, headers = call("POST", "https://api.linkedin.com/v2/ugcPosts", token, body)
    post_id = headers.get("X-RestLi-Id") or headers.get("x-restli-id", "")
    link = f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else "posted"
    print(f"Posted on the LinkedIn Page: {link}")
    (OUT / f"planning-desk-{stem}.linkedin.txt").write_text(link + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
