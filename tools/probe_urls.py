"""One-off check of candidate source URLs from the open web (run in GitHub Actions).

Reads tools/probe_list.txt (one URL per line, '#' comments allowed) and prints,
for each URL: HTTP status, final URL, whether it parses as a feed, entry count,
newest entry date and the first titles. Prints only; writes nothing.

Usage: python tools/probe_urls.py tools/probe_list.txt
"""
import datetime as dt
import re
import sys

import feedparser
import requests

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36 ThePlanningDeskBot/1.0")


def probe(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=25)
    except Exception as exc:  # noqa: BLE001
        return f"ERR  {url}  {type(exc).__name__}"
    head = r.text[:400].lstrip().lower()
    ctype = r.headers.get("content-type", "")
    line = f"{r.status_code}  {url}"
    if r.url != url:
        line += f"  -> {r.url}"
    line += f"  [{ctype.split(';')[0]}] {len(r.content)}B"
    if r.ok and ("xml" in ctype or "rss" in ctype or "atom" in ctype or head.startswith(("<?xml", "<rss", "<feed"))):
        f = feedparser.parse(r.content)
        dates = [e.get("published_parsed") or e.get("updated_parsed") for e in f.entries]
        dates = [dt.datetime(*d[:6]) for d in dates if d]
        newest = max(dates).isoformat() if dates else "no dates"
        titles = " | ".join((e.get("title") or "")[:70] for e in f.entries[:3])
        line += f"\n      FEED {len(f.entries)} entries, newest {newest}: {titles}"
    elif r.ok:
        title = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.I | re.S)
        feeds = re.findall(r"""<link\b[^>]*type=["']application/(?:rss|atom)\+xml["'][^>]*>""", r.text, re.I)
        hrefs = [re.search(r"""href=["']([^"']+)""", t).group(1) for t in feeds if re.search(r"""href=["']([^"']+)""", t)]
        times = re.findall(r"""(?:datePublished|article:published_time|datetime)["']?\s*[:=]\s*["']([0-9]{4}-[0-9]{2}-[0-9]{2}[^"']*)""", r.text)
        line += f"\n      PAGE title={(title.group(1).strip()[:80] if title else '-')!r}"
        if hrefs:
            line += f" feeds={hrefs[:3]}"
        if times:
            line += f" dates={sorted(set(times))[-3:]}"
    return line


def main(path):
    for raw in open(path, encoding="utf-8"):
        url = raw.strip()
        if not url or url.startswith("#"):
            if url:
                print(url)
            continue
        if url.startswith("RAW "):
            url = url[4:]
            r = requests.get(url, headers={"User-Agent": UA}, timeout=25)
            text = r.text
            i = text.find("<item")
            print(f"RAW {url} ({len(text)} chars)\n{text[i:i + 6000]}\n", flush=True)
            continue
        print(probe(url), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
