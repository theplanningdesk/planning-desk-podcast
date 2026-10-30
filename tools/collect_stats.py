#!/usr/bin/env python3
"""Collect engagement numbers for every episode and channel, for the "Collect stats" workflow.

Run from the repo root with the stats branch checked out in STATS_DIR (default: stats-branch/).

  python tools/collect_stats.py collect    # pull the numbers from every source that has an API
  python tools/collect_stats.py manual     # log hand-typed numbers (Spotify, Apple, LinkedIn) from MANUAL_* env vars

Files it keeps on the stats branch:
  episodes.csv   one row per episode, the latest numbers (rewritten every run)
  history.csv    date, episode, metric, value: every snapshot, so growth curves can be drawn
  channels.csv   date, channel, metric, value: followers, subscribers and totals per channel
  manual.csv     the hand-typed weekly numbers
  status.json    which sources worked on the last run and why the others didn't
  README.md      a readable scorecard

Each source is optional. A missing secret or an API refusal is noted in status.json and the
rest still runs.

Sources and the secrets they use:
  GitHub release downloads   GH_TOKEN (built in): raw MP3 fetches, bots and app crawlers included
  OP3                        OP3_API_TOKEN: real downloads from every podcast app, bots removed
  YouTube                    YOUTUBE_CLIENT_ID / _SECRET / _REFRESH_TOKEN (the upload ones)
  Instagram                  INSTAGRAM_USER_ID / INSTAGRAM_TOKEN (the Reels ones)
  Buttondown                 BUTTONDOWN_API_KEY
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID, uuid5

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from podcast_lib import load_config  # noqa: E402

REPO = os.environ.get("GITHUB_REPOSITORY", "theplanningdesk/podcast")
STATS = Path(os.environ.get("STATS_DIR", ROOT / "stats-branch"))
TODAY = date.today().isoformat()
STATUS: dict[str, str] = {}


# ---------------------------------------------------------------- helpers

def http_json(url: str, headers: dict | None = None, data: bytes | None = None, method: str | None = None) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "planning-desk-stats", **(headers or {})}, data=data, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def http_text(url: str, headers: dict | None = None) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "planning-desk-stats", **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def err_text(e: Exception) -> str:
    if isinstance(e, urllib.error.HTTPError):
        try:
            body = e.read().decode()[:300]
        except Exception:
            body = ""
        return f"HTTP {e.code} {body}".strip()
    return f"{type(e).__name__}: {e}"[:300]


def gh(path: str):
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return http_json(f"https://api.github.com/{path}", headers)


def read_csv(name: str) -> list[dict]:
    p = STATS / name
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(name: str, rows: list[dict], fields: list[str]) -> None:
    STATS.mkdir(parents=True, exist_ok=True)
    with (STATS / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fmt(v) -> str:
    n = num(v)
    if n is None:
        return ""
    return f"{n:.1f}" if n != int(n) else str(int(n))


# ---------------------------------------------------------------- episode list

def load_episodes() -> list[dict]:
    reg = json.loads((ROOT / "docs" / "episodes.json").read_text(encoding="utf-8"))
    eps = []
    for e in reg:
        stem = e.get("stem") or e["guid"].replace("planning-desk-", "")
        row = {
            "stem": stem, "number": e.get("number"), "format": e.get("format", "weekly"),
            "title": e.get("title", ""), "guid": e.get("guid", ""),
            "weekday": datetime.fromisoformat(e["pub_date"]).strftime("%a"),
            "minutes": round(e.get("duration_sec", 0) / 60, 1),
            "top_story": "", "short_title": "", "segments": "",
        }
        sp = ROOT / "episodes" / "scripts" / f"script-{stem}.json"
        if sp.exists():
            s = json.loads(sp.read_text(encoding="utf-8"))
            segs = [g for g in s.get("segments", []) if g.get("type") != "music"]
            row["segments"] = " ".join(g.get("id", "") for g in segs)
            top = next((g for g in segs if g.get("id") in ("top_story", "lead_stories", "book_intro")), None) \
                or next((g for g in segs if g.get("id") == "cold_open"), None) or {}
            first = next((ln.get("text", "") for ln in top.get("lines", []) if ln.get("text")), "")
            row["top_story"] = (top.get("title") or first)[:140]
            row["short_title"] = (s.get("short") or {}).get("title", "")
        eps.append(row)
    return eps


def release_assets() -> dict[str, dict]:
    """tag -> {asset name: asset}, across all releases."""
    out: dict[str, dict] = {}
    page = 1
    while True:
        rels = gh(f"repos/{REPO}/releases?per_page=100&page={page}")
        for r in rels:
            out[r["tag_name"]] = {a["name"]: a for a in r.get("assets", [])}
        if len(rels) < 100:
            return out
        page += 1


def asset_text(asset: dict) -> str:
    return http_text(asset["browser_download_url"]).strip()


# ---------------------------------------------------------------- sources

def github_downloads(eps: list[dict], assets: dict) -> None:
    for e in eps:
        a = assets.get(f"episode-{e['stem']}", {}).get(f"planning-desk-{e['stem']}.mp3")
        if a:
            e["github_mp3_fetches"] = a["download_count"]
    STATUS["github"] = "ok"


def op3(eps: list[dict], pod: dict) -> dict:
    tok = os.environ.get("OP3_API_TOKEN", "").strip()
    if not tok:
        STATUS["op3"] = "skipped: add the OP3_API_TOKEN secret (free key from op3.dev/api/keys)"
        return {}
    auth = {"Authorization": f"Bearer {tok}"}
    feed = (pod["base_url"].rstrip("/") + "/feed.xml").split("://", 1)[-1]
    guid = pod.get("podcast_guid") or str(uuid5(UUID("ead4c236-bf58-58c6-a2c6-a6b28d128cb6"), feed))
    try:
        show = http_json(f"https://op3.dev/api/1/shows/{guid}", auth)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            STATUS["op3"] = "waiting: OP3 hasn't seen downloads for this show yet (normal for the first few days)"
        elif e.code in (401, 403):
            hint = op3_token_hint(tok, guid)
            STATUS["op3"] = f"error: OP3 refused the OP3_API_TOKEN secret (HTTP {e.code}). {hint}"
        else:
            STATUS["op3"] = f"error: {err_text(e)}"
        return {}
    uuid = show["showUuid"]
    try:
        counts = http_json(f"https://op3.dev/api/1/queries/episode-download-counts?showUuid={uuid}", auth)
    except Exception as e:  # noqa: BLE001
        STATUS["op3"] = f"error: {err_text(e)}"
        return {"op3_stats_page": show.get("statsPageUrl", "")}
    by_guid = {x.get("itemGuid"): x for x in counts.get("episodes", [])}
    by_title = {x.get("title"): x for x in counts.get("episodes", [])}
    for e in eps:
        x = by_guid.get(e["guid"]) or by_title.get(e["title"])
        if x:
            for k in ("downloads1", "downloads3", "downloads7", "downloads30", "downloadsAll"):
                if k in x:
                    e["op3_" + k.replace("downloads", "d").replace("dAll", "all")] = x[k]
    STATUS["op3"] = "ok"
    return {"op3_stats_page": show.get("statsPageUrl", "")}


def op3_token_hint(tok: str, guid: str) -> str:
    """Tell a bad token apart from an OP3-side problem with one call using OP3's public preview token."""
    shape = f"The secret is {len(tok)} characters long."
    try:
        http_json(f"https://op3.dev/api/1/shows/{guid}", {"Authorization": "Bearer preview07ce"})
        ok = "OP3 itself answers fine with its public preview token, so the secret is the problem."
    except urllib.error.HTTPError as e:
        ok = ("OP3 itself answers fine with its public preview token (show not listed yet), so the secret is the problem."
              if e.code == 404 else f"OP3's own preview token also failed (HTTP {e.code}), so the problem is on OP3's side.")
    except Exception as e:  # noqa: BLE001
        ok = f"Couldn't test OP3 with the preview token ({err_text(e)[:80]})."
    return (f"{ok} {shape} Paste the Bearer Token (not the API Key) from op3.dev/api/keys, "
            "copied with the 'Copy to clipboard' button.")


def youtube_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else ""


def youtube(eps: list[dict], assets: dict) -> dict:
    cid, sec, ref = (os.environ.get(k, "") for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"))
    if not (cid and sec and ref):
        STATUS["youtube"] = "skipped: YouTube secrets missing"
        return {}
    try:
        tok = http_json("https://oauth2.googleapis.com/token", data=urllib.parse.urlencode({
            "client_id": cid, "client_secret": sec, "refresh_token": ref, "grant_type": "refresh_token"}).encode())["access_token"]
    except Exception as e:  # noqa: BLE001
        STATUS["youtube"] = f"error getting a token: {err_text(e)}"
        return {}
    auth = {"Authorization": f"Bearer {tok}"}
    wanted: dict[str, tuple[dict, str]] = {}
    for e in eps:
        rel = assets.get(f"episode-{e['stem']}", {})
        for name, kind in ((f"planning-desk-{e['stem']}.youtube.txt", "yt"), (f"planning-desk-{e['stem']}-short.youtube.txt", "short")):
            if name in rel:
                try:
                    vid = youtube_id(asset_text(rel[name]))
                except Exception:  # noqa: BLE001
                    vid = ""
                if vid:
                    wanted[vid] = (e, kind)
    out: dict = {}
    try:
        ids = list(wanted)
        for i in range(0, len(ids), 50):
            res = http_json("https://www.googleapis.com/youtube/v3/videos?part=statistics&id=" + ",".join(ids[i:i + 50]), auth)
            for item in res.get("items", []):
                e, kind = wanted[item["id"]]
                st = item.get("statistics", {})
                e[f"{kind}_views"] = st.get("viewCount", "")
                e[f"{kind}_likes"] = st.get("likeCount", "")
                e[f"{kind}_comments"] = st.get("commentCount", "")
        ch = http_json("https://www.googleapis.com/youtube/v3/channels?part=statistics&mine=true", auth).get("items", [])
        if ch:
            st = ch[0]["statistics"]
            out = {"subscribers": st.get("subscriberCount"), "total_views": st.get("viewCount"), "videos": st.get("videoCount")}
        STATUS["youtube"] = "ok"
    except Exception as e:  # noqa: BLE001
        STATUS["youtube"] = f"error: {err_text(e)}"
    return out


def instagram(eps: list[dict], assets: dict) -> dict:
    uid, tok = os.environ.get("INSTAGRAM_USER_ID", "").strip(), os.environ.get("INSTAGRAM_TOKEN", "").strip()
    if not (uid and tok):
        STATUS["instagram"] = "skipped: Instagram secrets missing"
        return {}
    api = "https://graph.instagram.com/v26.0"
    auth = {"Authorization": f"Bearer {tok}"}
    out: dict = {}
    try:
        me = http_json(f"{api}/{uid}?fields=followers_count,media_count", auth)
        out = {"followers": me.get("followers_count"), "posts": me.get("media_count")}
        media = http_json(f"{api}/{uid}/media?fields=id,permalink,like_count,comments_count&limit=100", auth).get("data", [])
    except Exception as e:  # noqa: BLE001
        STATUS["instagram"] = f"error: {err_text(e)}"
        return out
    by_link = {m.get("permalink", "").rstrip("/"): m for m in media}
    insights_note = "ok"
    for e in eps:
        a = assets.get(f"episode-{e['stem']}", {}).get(f"planning-desk-{e['stem']}-short.instagram.txt")
        if not a:
            continue
        try:
            link = asset_text(a).rstrip("/")
        except Exception:  # noqa: BLE001
            continue
        m = by_link.get(link)
        if not m:
            continue
        e["ig_likes"], e["ig_comments"] = m.get("like_count", ""), m.get("comments_count", "")
        try:
            ins = http_json(f"{api}/{m['id']}/insights?metric=views,reach,saved,shares,total_interactions", auth).get("data", [])
            for x in ins:
                vals = x.get("values") or [{}]
                e[f"ig_{x['name']}"] = vals[0].get("value", x.get("total_value", {}).get("value", ""))
        except Exception as err:  # noqa: BLE001
            insights_note = ("likes and comments only: the token can't read Reel insights (views, reach). "
                             f"Reconnect Instagram with the insights permission to get them. ({err_text(err)[:120]})")
    STATUS["instagram"] = insights_note
    return out


def buttondown() -> dict:
    key = os.environ.get("BUTTONDOWN_API_KEY", "").strip()
    if not key:
        STATUS["buttondown"] = "skipped: BUTTONDOWN_API_KEY missing"
        return {}
    auth = {"Authorization": f"Token {key}"}
    out: dict = {}
    try:
        out["subscribers"] = http_json("https://api.buttondown.com/v1/subscribers?page_size=1", auth).get("count")
        emails = http_json("https://api.buttondown.com/v1/emails?status=sent&ordering=-publish_date&page_size=1", auth).get("results", [])
        if emails:
            em = emails[0]
            out["last_email"] = (em.get("subject") or "")[:80]
            a = http_json(f"https://api.buttondown.com/v1/emails/{em['id']}/analytics", auth)
            for k in ("recipients", "deliveries", "opens", "clicks", "unsubscriptions"):
                if k in a:
                    out[f"last_email_{k}"] = a[k]
            if num(a.get("deliveries")):
                out["last_email_open_rate_pct"] = round(100 * (num(a.get("opens")) or 0) / num(a["deliveries"]), 1)
        STATUS["buttondown"] = "ok" if emails else "ok (no newsletter sent yet)"
    except Exception as e:  # noqa: BLE001
        STATUS["buttondown"] = f"error: {err_text(e)}"
    return out


# ---------------------------------------------------------------- report

EP_FIELDS = ["stem", "number", "format", "weekday", "minutes", "title", "top_story", "short_title", "segments",
             "op3_d1", "op3_d3", "op3_d7", "op3_d30", "op3_all", "github_mp3_fetches",
             "yt_views", "yt_likes", "yt_comments", "short_views", "short_likes", "short_comments",
             "ig_views", "ig_reach", "ig_likes", "ig_comments", "ig_saved", "ig_shares", "ig_total_interactions"]


def write_readme(eps: list[dict], channels: dict, extra: dict) -> None:
    def best(e):
        return num(e.get("op3_d7")) or num(e.get("op3_all")) or num(e.get("github_mp3_fetches")) or 0

    lines = [f"# The Planning Desk: engagement scorecard", "",
             f"Updated {TODAY}. Numbers refresh every morning; the full data is in the CSV files on this branch.", ""]
    if extra.get("op3_stats_page"):
        lines += [f"OP3 stats page: {extra['op3_stats_page']}", ""]

    lines += ["## Channels", "", "| Channel | Metric | Now |", "|---|---|---|"]
    for (ch, metric), v in sorted(channels.items()):
        lines.append(f"| {ch} | {metric.replace('_', ' ')} | {v if isinstance(v, str) else fmt(v)} |")
    manual = read_csv("manual.csv")
    if manual:
        last = manual[-1]
        for k, v in last.items():
            if k not in ("date", "week") and v:
                lines.append(f"| {k.split('_')[0]} (typed in {last.get('date')}) | {' '.join(k.split('_')[1:])} | {v} |")
    lines.append("")

    lines += ["## Episodes, newest first", "",
              "Podcast = OP3 downloads in the first 7 days (bots removed); raw = GitHub MP3 fetches incl. bots. "
              "Short = YouTube Short views. IG = Reel views, or likes when views aren't available.", "",
              "| Date | Format | Episode | Podcast 7d | Raw | YouTube | Short | IG |", "|---|---|---|---|---|---|---|---|"]
    for e in sorted(eps, key=lambda x: x["stem"], reverse=True):
        ig = fmt(e.get("ig_views")) or (fmt(e.get("ig_likes")) + " likes" if fmt(e.get("ig_likes")) else "")
        lines.append(f"| {e['stem']} | {e['format']} | {e['title']} | {fmt(e.get('op3_d7'))} | {fmt(e.get('github_mp3_fetches'))} | "
                     f"{fmt(e.get('yt_views'))} | {fmt(e.get('short_views'))} | {ig} |")
    lines.append("")

    ranked = sorted(eps, key=best, reverse=True)[:3]
    if ranked and best(ranked[0]):
        lines += ["## Top podcast episodes so far", ""]
        lines += [f"{i}. {e['title']} ({e['format']}, {e['weekday']}): {fmt(best(e))}" for i, e in enumerate(ranked, 1)]
        lines.append("")

    lines += ["## Source status", ""] + [f"- {k}: {v}" for k, v in sorted(STATUS.items())] + [""]
    (STATS / "README.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- commands

def collect() -> int:
    cfg = load_config()
    pod = cfg["podcast"]
    eps = load_episodes()
    assets: dict = {}
    try:
        assets = release_assets()
        github_downloads(eps, assets)
    except Exception as e:  # noqa: BLE001
        STATUS["github"] = f"error: {err_text(e)}"

    extra = op3(eps, pod)
    channels: dict[tuple[str, str], object] = {}
    for ch, vals in (("youtube", youtube(eps, assets)), ("instagram", instagram(eps, assets)), ("newsletter", buttondown())):
        for k, v in vals.items():
            if v not in (None, ""):
                channels[(ch, k)] = v
    op3_total = sum(num(e.get("op3_all")) or 0 for e in eps)
    if op3_total:
        channels[("podcast", "op3_downloads_all_episodes")] = op3_total
    channels[("podcast", "github_mp3_fetches_all_episodes")] = sum(num(e.get("github_mp3_fetches")) or 0 for e in eps)

    write_csv("episodes.csv", eps, EP_FIELDS)

    hist = [r for r in read_csv("history.csv") if r.get("date") != TODAY]
    for e in eps:
        for k in EP_FIELDS[9:]:
            if num(e.get(k)) is not None:
                hist.append({"date": TODAY, "stem": e["stem"], "metric": k, "value": e[k]})
    write_csv("history.csv", hist, ["date", "stem", "metric", "value"])

    chan = [r for r in read_csv("channels.csv") if r.get("date") != TODAY]
    chan += [{"date": TODAY, "channel": c, "metric": m, "value": v} for (c, m), v in channels.items()]
    write_csv("channels.csv", chan, ["date", "channel", "metric", "value"])

    (STATS / "status.json").write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                   "sources": STATUS, **extra}, indent=2), encoding="utf-8")
    write_readme(eps, channels, extra)
    for k, v in sorted(STATUS.items()):
        print(f"{'::warning::' if not v.startswith('ok') else ''}{k}: {v}")
    return 0


MANUAL_FIELDS = ["date", "spotify_followers", "spotify_plays", "apple_followers", "apple_listeners",
                 "linkedin_followers", "linkedin_impressions", "linkedin_reactions", "linkedin_comments", "note"]


def manual() -> int:
    row = {"date": os.environ.get("MANUAL_DATE", "").strip() or TODAY}
    for f in MANUAL_FIELDS[1:]:
        v = os.environ.get("MANUAL_" + f.upper(), "").strip().replace(" ", "").replace(",", "") if f != "note" \
            else os.environ.get("MANUAL_NOTE", "").strip()
        row[f] = v
    if not any(row[f] for f in MANUAL_FIELDS[1:-1]):
        raise SystemExit("Nothing to log: every number was blank.")
    rows = [r for r in read_csv("manual.csv") if r.get("date") != row["date"]] + [row]
    rows.sort(key=lambda r: r["date"])
    write_csv("manual.csv", rows, MANUAL_FIELDS)
    print(f"Logged manual numbers for {row['date']}: " + ", ".join(f"{k}={v}" for k, v in row.items() if v and k != "date"))
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "collect":
        sys.exit(collect())
    if cmd == "manual":
        sys.exit(manual())
    raise SystemExit(__doc__)
