#!/usr/bin/env python3
"""Publish a rendered episode to the public podcast site in docs/ (served by GitHub Pages).

The MP3 itself stays on the episode's GitHub release (podcast.audio_base_url), so the
site never fills up. This script records the episode in docs/episodes.json, writes an
episode page with the full transcript (docs/e/<stem>.html), and rebuilds docs/feed.xml
(the RSS feed for Apple Podcasts and Spotify), docs/index.html and docs/sitemap.xml.

Usage:
  python publish.py 2026-10-25          # publish build/out/planning-desk-2026-10-25.*
  python publish.py --rebuild           # only regenerate the feed, pages and sitemap
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from podcast_lib import ROOT, duration, load_config
from render import episode_format, episode_title

DOCS = ROOT / "docs"
PAGES = DOCS / "e"
REGISTRY = DOCS / "episodes.json"
TZ = ZoneInfo("Europe/Stockholm")

SEGMENT_NAMES = {
    "cold_open": "Opening", "welcome": "Welcome", "top_story": "Top story", "briefing": "The briefing",
    "lead_stories": "Lead stories", "ai_tech": "AI and tech", "nordics_dach": "Nordics and DACH",
    "market_moves": "Market moves", "use_cases": "Use cases", "macro": "Macro and trade", "numbers": "The numbers",
    "events_ahead": "Events ahead", "quick_hits": "Quick hits", "sign_off": "Sign-off",
    "week_threads": "The week's threads", "voices": "Expert voices", "week_ahead": "The week ahead",
    "book_open": "Opening", "book_intro": "Today's book", "book_context": "The book and its author",
    "big_ideas": "The big ideas", "for_planners": "Why it matters now", "reading_guide": "How to read it",
    "shelf": "Also on the shelf", "book_sign_off": "Sign-off",
}


def load_registry() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else []


def cdata(text: str) -> str:
    return "<![CDATA[" + text.replace("]]>", "]]&gt;") + "]]>"


def base_url(pod: dict) -> str:
    return pod["base_url"].rstrip("/") + "/"


def audio_url(pod: dict, e: dict) -> str:
    """Where the MP3 is served from: the GitHub release, or docs/ for episodes published before the move."""
    if e.get("file", "").startswith("episodes/"):
        return base_url(pod) + e["file"]
    return f"{pod['audio_base_url'].rstrip('/')}/episode-{e['stem']}/planning-desk-{e['stem']}.mp3"


def page_url(pod: dict, e: dict) -> str:
    return f"{base_url(pod)}e/{e['stem']}.html"

KIND_LABELS = {"daily": "Daily briefing", "saturday": "Book of the week", "weekly": "Week in review"}


def episode_notes(script: dict, pod: dict, page: str) -> tuple[str, str]:
    """Return (plain summary, HTML notes) from the script's show_notes, or derive them."""
    notes = script.get("show_notes") or {}
    summary = (notes.get("summary") or "").strip()
    if not summary:
        for seg in script.get("segments", []):
            if seg.get("id") == "welcome" and seg.get("lines"):
                summary = max((l["text"] for l in seg["lines"]), key=len)
                break
    parts = [f"<p>{html.escape(summary)}</p>"] if summary else []
    sources = [s for s in notes.get("sources", []) if s.get("url")]
    if sources:
        items = "".join(f'<li><a href="{html.escape(s["url"], quote=True)}">{html.escape(s.get("title") or s["url"])}</a></li>'
                        for s in sources)
        parts.append(f"<p>Sources:</p><ul>{items}</ul>")
    parts.append(f'<p>Full transcript: <a href="{html.escape(page, quote=True)}">{html.escape(page)}</a></p>')
    parts.append(f"<p><em>{html.escape(pod['ai_disclosure'])}</em></p>")
    return summary, "".join(parts)


def add_episode(stem: str, cfg: dict) -> dict:
    pod = cfg["podcast"]
    out = ROOT / "build" / "out"
    mp3 = out / f"planning-desk-{stem}.mp3"
    meta = json.loads((out / f"planning-desk-{stem}.json").read_text(encoding="utf-8"))
    script = json.loads((ROOT / "episodes" / "scripts" / f"script-{stem}.json").read_text(encoding="utf-8"))
    fmt = episode_format(script)

    registry = load_registry()
    guid = f"planning-desk-{stem}"
    existing = next((e for e in registry if e["guid"] == guid), None)
    number = existing["number"] if existing else max((e["number"] for e in registry), default=0) + 1

    run_date = script.get("run_date") or stem[:10]
    when = cfg.get("formats", {}).get(fmt, {}).get("publish_time", "07:30")
    published = existing["pub_date"] if existing else datetime.fromisoformat(f"{run_date}T{when}:00").replace(tzinfo=TZ).isoformat()
    entry = {"guid": guid, "stem": stem, "number": number, "format": fmt, "title": episode_title(cfg, script)}
    summary, notes_html = episode_notes(script, pod, page_url(pod, entry))
    entry.update({
        "summary": summary,
        "notes_html": notes_html,
        "bytes": mp3.stat().st_size,
        "duration_sec": int(round(duration(mp3))),
        "pub_date": published,
        "transcript_lines": len(meta.get("timeline", [])),
    })
    registry = [e for e in registry if e["guid"] != guid] + [entry]
    registry.sort(key=lambda e: e["pub_date"])
    REGISTRY.write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_episode_page(cfg, entry, script, meta)
    print(f"Registered episode {number}: {entry['title']}")
    return entry


def ts(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


PAGE_CSS = """:root{--bg:#0c1421;--card:#142236;--text:#f4f1ea;--muted:#8a98aa;--accent:#f2a33a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:760px;margin:0 auto;padding:32px 16px 64px}a{color:var(--accent)}
h1{margin:4px 0 12px;font-size:28px;line-height:1.2}h2{margin:28px 0 8px;font-size:20px}
.meta{color:var(--muted);margin:0;font-size:14px}audio{width:100%;margin:12px 0}
.card{background:var(--card);border-radius:12px;padding:20px;margin:16px 0}
.t p{margin:6px 0}.t b{color:var(--accent);font-weight:700}.t .time{color:var(--muted);font-size:13px;margin-right:6px}
ul{padding-left:20px}"""


def write_episode_page(cfg: dict, e: dict, script: dict, meta: dict) -> None:
    pod = cfg["podcast"]
    PAGES.mkdir(parents=True, exist_ok=True)
    when = datetime.fromisoformat(e["pub_date"]).strftime("%A %-d %B %Y")
    kind = KIND_LABELS.get(e["format"], "Week in review")
    rows, last_seg = [], None
    for t in meta.get("timeline", []):
        if t["segment"] != last_seg:
            rows.append(f"<h2>{html.escape(SEGMENT_NAMES.get(t['segment'], t['segment'].replace('_', ' ').title()))}</h2>")
            last_seg = t["segment"]
        rows.append(f'<p><span class="time">{ts(t["start_sec"])}</span><b>{html.escape(t["speaker"])}:</b> {html.escape(t["text"])}</p>')
    desc = html.escape(e["summary"][:300], quote=True)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(e['title'])} | {html.escape(pod['title'])}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{html.escape(e['title'], quote=True)}"><meta property="og:description" content="{desc}">
<meta property="og:image" content="{html.escape(base_url(pod))}cover.png"><meta property="og:type" content="article">
<link rel="alternate" type="application/rss+xml" title="{html.escape(pod['title'])}" href="../feed.xml">
<style>{PAGE_CSS}</style></head><body><main>
<p class="meta"><a href="../index.html">{html.escape(pod['title'])}</a> · {kind} · {when} · {e['duration_sec'] // 60} min</p>
<h1>{html.escape(e['title'])}</h1>
<audio controls preload="none" src="{html.escape(audio_url(pod, e), quote=True)}"></audio>
<div class="card">{e['notes_html']}</div>
<h2>Transcript</h2>
<div class="t">{"".join(rows)}</div>
<p class="meta" style="margin-top:32px">{html.escape(pod['ai_disclosure'])}</p>
</main></body></html>
"""
    (PAGES / f"{e['stem']}.html").write_text(page, encoding="utf-8")


def build_feed(cfg: dict, registry: list[dict]) -> None:
    pod = cfg["podcast"]
    base = base_url(pod)
    now = format_datetime(datetime.now(TZ))
    channel_desc = f"{pod['description']} {pod['ai_disclosure']}"

    cat = pod["category"]
    category_xml = f'    <itunes:category text="{escape(cat["main"], {chr(34): "&quot;"})}">'
    if cat.get("sub"):
        category_xml += f'\n      <itunes:category text="{escape(cat["sub"], {chr(34): "&quot;"})}"/>\n    '
    category_xml += "</itunes:category>"
    if cat.get("secondary"):
        sec = cat["secondary"]
        category_xml += f'\n    <itunes:category text="{escape(sec["main"])}">'
        if sec.get("sub"):
            category_xml += f'<itunes:category text="{escape(sec["sub"])}"/>'
        category_xml += "</itunes:category>"

    owner_email = pod.get("owner_email", "").strip()
    owner_xml = (f"    <itunes:owner>\n      <itunes:name>{escape(pod['owner_name'])}</itunes:name>\n"
                 f"      <itunes:email>{escape(owner_email)}</itunes:email>\n    </itunes:owner>\n") if owner_email else ""

    items = []
    for e in sorted(registry, key=lambda x: x["pub_date"], reverse=True):
        pub = format_datetime(datetime.fromisoformat(e["pub_date"]))
        items.append(f"""    <item>
      <title>{escape(e['title'])}</title>
      <link>{escape(page_url(pod, e))}</link>
      <description>{cdata(e['notes_html'])}</description>
      <content:encoded>{cdata(e['notes_html'])}</content:encoded>
      <enclosure url="{escape(audio_url(pod, e))}" length="{e['bytes']}" type="audio/mpeg"/>
      <guid isPermaLink="false">{escape(e['guid'])}</guid>
      <pubDate>{pub}</pubDate>
      <itunes:duration>{e['duration_sec']}</itunes:duration>
      <itunes:episode>{e['number']}</itunes:episode>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>false</itunes:explicit>
      <itunes:image href="{escape(base + 'cover.png')}"/>
    </item>""")

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(pod['title'])}</title>
    <link>{escape(base)}</link>
    <atom:link href="{escape(base + 'feed.xml')}" rel="self" type="application/rss+xml"/>
    <language>{escape(pod['language'])}</language>
    <copyright>{escape(pod['copyright'])}</copyright>
    <description>{cdata(channel_desc)}</description>
    <itunes:summary>{cdata(channel_desc)}</itunes:summary>
    <itunes:author>{escape(pod['author'])}</itunes:author>
{owner_xml}    <itunes:image href="{escape(base + 'cover.png')}"/>
    <image>
      <url>{escape(base + 'cover.png')}</url>
      <title>{escape(pod['title'])}</title>
      <link>{escape(base)}</link>
    </image>
{category_xml}
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <lastBuildDate>{now}</lastBuildDate>
    <generator>planning-desk-podcast</generator>
{chr(10).join(items)}
  </channel>
</rss>
"""
    (DOCS / "feed.xml").write_text(feed, encoding="utf-8")
    print(f"Wrote docs/feed.xml with {len(registry)} episode(s).")


def build_index(cfg: dict, registry: list[dict]) -> None:
    pod = cfg["podcast"]
    base = base_url(pod)
    links = [f'<a href="{html.escape(base)}feed.xml">RSS feed</a>']
    for name, key in (("Apple Podcasts", "apple_url"), ("Spotify", "spotify_url"), ("YouTube", "youtube_url"),
                      ("Newsletter", "newsletter_url"), ("LinkedIn", "linkedin_url"), ("Instagram", "instagram_url")):
        if pod.get(key):
            links.insert(len(links) - 1, f'<a href="{html.escape(pod[key], quote=True)}">{name}</a>')
    eps = []
    for e in sorted(registry, key=lambda x: x["pub_date"], reverse=True)[:60]:
        when = datetime.fromisoformat(e["pub_date"]).strftime("%-d %B %Y")
        kind = {"daily": "Daily", "saturday": "Book of the week"}.get(e.get("format"), "Week in review")
        eps.append(f"""<article><p class="meta">{kind} · {when} · {e['duration_sec'] // 60} min</p>
<h2><a href="e/{e['stem']}.html">{html.escape(e['title'])}</a></h2>
<audio controls preload="none" src="{html.escape(audio_url(pod, e), quote=True)}"></audio>
<p>{html.escape(e['summary'])}</p></article>""")
    body = "\n".join(eps) if eps else '<p class="meta">The first episode arrives on Sunday.</p>'
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(pod['title'])}</title>
<meta name="description" content="{html.escape(pod['description'], quote=True)}">
<link rel="alternate" type="application/rss+xml" title="{html.escape(pod['title'])}" href="feed.xml">
<style>
:root{{--bg:#0c1421;--card:#142236;--text:#f4f1ea;--muted:#8a98aa;--accent:#f2a33a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:760px;margin:0 auto;padding:32px 16px 64px}}
header{{display:flex;gap:24px;align-items:center;flex-wrap:wrap;margin-bottom:32px}}
header img{{width:180px;height:180px;border-radius:12px}}
h1{{margin:0 0 8px;font-size:28px}}h2{{margin:4px 0 12px;font-size:20px}}h2 a{{color:var(--text);text-decoration:none}}
a{{color:var(--accent)}}.links{{display:flex;gap:16px;flex-wrap:wrap}}
.meta{{color:var(--muted);margin:0;font-size:14px}}
article{{background:var(--card);border-radius:12px;padding:20px;margin-bottom:16px}}
audio{{width:100%;margin-bottom:8px}}
</style></head><body><main>
<header><img src="cover.png" alt="The Planning Desk cover"><div>
<h1>{html.escape(pod['title'])}</h1><p class="meta">{html.escape(pod['description'])}</p>
<p class="meta"><em>{html.escape(pod['ai_disclosure'])}</em></p>
<p class="links">{" ".join(links)}</p></div></header>
{body}
</main></body></html>
"""
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    urls = [base] + [page_url(pod, e) for e in registry]
    (DOCS / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{escape(u)}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n", encoding="utf-8")
    print("Wrote docs/index.html and docs/sitemap.xml.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stem", nargs="?", help="episode stem, e.g. 2026-10-25")
    ap.add_argument("--rebuild", action="store_true", help="only rebuild the feed, pages and sitemap")
    args = ap.parse_args()
    if not args.stem and not args.rebuild:
        ap.error("give an episode stem or --rebuild")
    cfg = load_config()
    DOCS.mkdir(exist_ok=True)
    (DOCS / ".nojekyll").touch()
    if args.stem:
        add_episode(args.stem, cfg)
    registry = load_registry()
    for e in registry:  # older entries may predate these fields
        e.setdefault("stem", e["guid"].replace("planning-desk-", ""))
        e.setdefault("format", "weekly")
    build_feed(cfg, registry)
    build_index(cfg, registry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
