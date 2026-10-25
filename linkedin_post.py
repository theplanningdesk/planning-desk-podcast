#!/usr/bin/env python3
"""Prepare the Sunday post for The Planning Desk's LinkedIn Page, and post it there when Page access exists.

The show never posts on a personal profile. Every Sunday this writes the script's
linkedin.page_post text, with the YouTube link (or the episode page) on the last line, to
build/out/planning-desk-<stem>-linkedin.txt, which the workflow attaches to the release so the
script writer can hand it over for posting by hand.

Automatic posting needs LinkedIn's Community Management API, which LinkedIn grants only after
reviewing the app. Once approved, set:
  LINKEDIN_PAGE_TOKEN   secret, a token from a Page admin with the w_organization_social scope
  LINKEDIN_ORG_ID       repository variable, the Page's numeric organization id
  LINKEDIN_TOKEN_SET_ON repository variable, YYYY-MM-DD the token was made (warns after 50 days)
Without them the script only writes the text file.

Usage: python linkedin_post.py 2026-11-08
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


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    stem = sys.argv[1]
    cfg = load_config()
    pod = cfg["podcast"]

    script = json.loads((ROOT / "episodes" / "scripts" / f"script-{stem}.json").read_text(encoding="utf-8"))
    text = ((script.get("linkedin") or {}).get("page_post") or "").strip()
    if not text:
        print("No linkedin.page_post in the script; nothing to post.")
        return 0
    yt = OUT / f"planning-desk-{stem}.youtube.txt"
    url = yt.read_text().strip() if yt.exists() else f"{pod['base_url'].rstrip('/')}/e/{stem}.html"
    (OUT / f"planning-desk-{stem}-linkedin.txt").write_text(f"{text}\n\n{url}\n", encoding="utf-8")
    print(f"Page post text written for {stem}.")

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
            "shareCommentary": {"text": text[:2900]},
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
