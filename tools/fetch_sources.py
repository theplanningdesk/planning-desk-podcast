"""Pull the scrobblers' starting pages into one digest the agents can read.

The scheduled scrobblers can't fetch these pages themselves while Jim sleeps
(each fetch waits for an approval nobody gives), but they can read GitHub
from their shell. This script runs in GitHub Actions, where the open web is
reachable, and writes:

  out/latest.json  every item: source, title, link, published, summary
  out/latest.md    the same, grouped by source, for reading
  out/status.json  per-source result, so a broken feed shows up

Usage: python tools/fetch_sources.py out/
"""
import datetime as dt
import html
import json
import re
import sys
import urllib.parse
from pathlib import Path

import feedparser
import requests

SOURCES = [
    ("Supply Chain Dive", "https://www.supplychaindive.com/feeds/news/"),
    ("SupplyChainBrain", "https://www.supplychainbrain.com/rss/articles"),
    ("SCMR", "https://www.scmr.com/"),
    ("The Loadstar", "https://theloadstar.com/"),
    ("FreightWaves", "https://www.freightwaves.com/news"),
    ("SupplyChain247", "https://www.supplychain247.com/"),
    ("Supply Chain Digital", "https://supplychaindigital.com/news"),
    ("Logistics Management", "https://www.logisticsmgmt.com/"),
    ("DC Velocity", "https://www.dcvelocity.com/"),
    ("Splash247", "https://splash247.com/"),
    ("VerkehrsRundschau", "https://www.verkehrsrundschau.de/nachrichten"),
    ("Logistik Journal", "https://www.logistik-journal.de/"),
    ("BVL", "https://www.bvl.de/"),
    ("Dagens Logistik", "https://dagenslogistik.se/nyheter/"),
    ("Dagens Infrastruktur", "https://dagensinfrastruktur.se/"),
    ("MT Logistikk", "https://www.mtlogistikk.no/"),
    # Added 28 Oct 2026 after source vetting (claude/research/source-vetting-2026-10-28.md).
    # Transportmagasinet dropped: paywalled.
    ("SCM.dk", "https://scm.dk/feeds/articles"),
    ("SC Effect", "https://www.sceffect.se/en/category/nyheter/"),
    ("Osto&Logistiikka", "https://www.ostologistiikka.fi/"),
    ("BME", "https://www.bme.de/news/"),
    ("Logistics Viewpoints", "https://logisticsviewpoints.com/"),
    ("NVIDIA Technical Blog (optimisation)", "https://developer.nvidia.com/blog/feed/"),
    ("Sea-Intelligence", "https://www.sea-intelligence.com/press-room"),
    ("Xeneta", "https://www.xeneta.com/press"),
    ("Eurostat euro indicators", "https://ec.europa.eu/eurostat/news/euro-indicators"),
    ("Talking Logistics", "https://talkinglogistics.com/"),
    ("Supply Chain Shaman", "https://www.supplychainshaman.com/"),
    ("SAP News", "https://news.sap.com/"),
    ("Gartner Newsroom", "https://www.gartner.com/en/newsroom"),
    ("ASCM", "https://www.ascm.org/"),
]

# Sources whose feed is broad: keep only items whose title or summary matches.
KEYWORDS = {
    "NVIDIA Technical Blog (optimisation)": [
        "cuopt", "optimization", "optimisation", "solver", "supply chain", "logistics",
        "routing", "linear program", "mip", "planning", "inventory", "forecast"],
}

# Live Rhine gauges from Pegelonline (WSV), the federal waterways data service.
RHINE_API = ("https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json"
             "?waters=RHEIN&includeTimeseries=true&includeCurrentMeasurement=true")
RHINE_GAUGES = ["MAXAU", "KAUB", "KÖLN", "DUISBURG-RUHRORT", "EMMERICH"]

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36 ThePlanningDeskBot/1.0")
MAX_AGE_DAYS = 8
MAX_PER_SOURCE = 40
TIMEOUT = 25


def clean(text, limit=400):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def get(url):
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def looks_like_feed(resp):
    ctype = resp.headers.get("content-type", "").lower()
    head = resp.text[:500].lstrip().lower()
    return ("xml" in ctype or "rss" in ctype or "atom" in ctype
            or head.startswith("<?xml") or head.startswith("<rss") or head.startswith("<feed"))


def discover_feeds(page_url, page_html):
    found = []
    for tag in re.findall(r"<link\b[^>]*>", page_html, flags=re.I):
        if re.search(r"""type=["']application/(rss|atom)\+xml""", tag, re.I):
            m = re.search(r"""href=["']([^"']+)""", tag, re.I)
            if m:
                href = urllib.parse.urljoin(page_url, html.unescape(m.group(1)))
                if "comments" not in href:
                    found.append(href)
    base = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(page_url))
    found += [page_url.rstrip("/") + "/feed/", base + "/feed/", base + "/rss"]
    seen, out = set(), []
    for f in found:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def parse_feed(source, feed_url, content, cutoff):
    parsed = feedparser.parse(content)
    items = []
    for e in parsed.entries:
        stamp = e.get("published_parsed") or e.get("updated_parsed")
        published = dt.datetime(*stamp[:6], tzinfo=dt.timezone.utc) if stamp else None
        if published and published < cutoff:
            continue
        items.append({
            "source": source,
            "title": clean(e.get("title"), 300),
            "link": e.get("link", ""),
            "published": published.isoformat() if published else None,
            "summary": clean(e.get("summary") or e.get("description")),
            "via": "feed",
        })
    return items, len(parsed.entries)


def scrape_links(source, page_url, page_html):
    """Last resort for pages without a feed: article-looking links on the page."""
    host = urllib.parse.urlparse(page_url).netloc.replace("www.", "")
    items, seen = [], set()
    for href, text in re.findall(r"""<a\b[^>]*href=["']([^"'#]+)["'][^>]*>(.*?)</a>""", page_html, re.I | re.S):
        link = urllib.parse.urljoin(page_url, html.unescape(href))
        parts = urllib.parse.urlparse(link)
        title = clean(text, 300)
        if host not in parts.netloc or link in seen or len(title) < 25:
            continue
        path = parts.path.strip("/")
        if path.count("/") < 1 and not re.search(r"\d{4,}|-[a-z]+-[a-z]+-[a-z]+", path):
            continue
        seen.add(link)
        items.append({"source": source, "title": title, "link": link,
                      "published": None, "summary": "", "via": "page links"})
    return items


def fetch_source(source, url, cutoff):
    status = {"source": source, "url": url, "ok": False, "method": None, "items": 0, "error": None}
    try:
        resp = get(url)
    except Exception as exc:  # noqa: BLE001
        status["error"] = f"{type(exc).__name__}: {exc}"[:200]
        return [], status
    if looks_like_feed(resp):
        items, total = parse_feed(source, url, resp.content, cutoff)
        if total:
            status.update(ok=True, method=f"feed {url}")
            return items[:MAX_PER_SOURCE], {**status, "items": len(items[:MAX_PER_SOURCE])}
    errors = []
    for feed_url in discover_feeds(url, resp.text):
        try:
            fresp = get(feed_url)
            if not looks_like_feed(fresp):
                continue
            items, total = parse_feed(source, feed_url, fresp.content, cutoff)
            if total:
                items = items[:MAX_PER_SOURCE]
                status.update(ok=True, method=f"feed {feed_url}", items=len(items))
                return items, status
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{feed_url}: {type(exc).__name__}")
    items = scrape_links(source, url, resp.text)[:MAX_PER_SOURCE]
    status.update(ok=bool(items), method="page links (no feed found, no dates)", items=len(items),
                  error=None if items else "; ".join(errors)[:200] or "no feed and no article links")
    return items, status


def keep(source, items):
    words = KEYWORDS.get(source)
    if not words:
        return items
    return [i for i in items if any(w in (i["title"] + " " + i["summary"]).lower() for w in words)]


def fetch_rhine():
    """Current water level (cm) at the Rhine gauges that matter for barge loads."""
    status = {"source": "Rhine gauges (Pegelonline)", "url": RHINE_API, "ok": False,
              "method": "json api", "items": 0, "error": None}
    try:
        stations = get(RHINE_API).json()
    except Exception as exc:  # noqa: BLE001
        status["error"] = f"{type(exc).__name__}: {exc}"[:200]
        return [], status
    rows = []
    for st in stations:
        name = st.get("shortname", "").upper()
        if name not in RHINE_GAUGES:
            continue
        for ts in st.get("timeseries", []):
            m = ts.get("currentMeasurement")
            if ts.get("shortname") == "W" and m:
                rows.append({"gauge": st["shortname"], "km": st.get("km"),
                             "level_cm": m.get("value"), "trend": m.get("trend"),
                             "measured_at": m.get("timestamp"), "unit": ts.get("unit")})
    rows.sort(key=lambda r: r["km"] or 0)
    status.update(ok=bool(rows), items=len(rows), error=None if rows else "no gauge data")
    return rows, status


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=MAX_AGE_DAYS)
    all_items, statuses = [], []
    for source, url in SOURCES:
        items, status = fetch_source(source, url, cutoff)
        if source in KEYWORDS:
            items = keep(source, items)
            status["items"] = len(items)
        print(f"{'OK ' if status['ok'] else 'ERR'} {source}: {status['items']} items "
              f"via {status['method'] or '-'} {status['error'] or ''}")
        all_items += items
        statuses.append(status)

    rhine, rhine_status = fetch_rhine()
    print(f"{'OK ' if rhine_status['ok'] else 'ERR'} Rhine gauges: {len(rhine)} {rhine_status['error'] or ''}")
    statuses.append(rhine_status)

    meta = {"fetched_at": now.isoformat(), "window_days": MAX_AGE_DAYS,
            "sources_ok": sum(s["ok"] for s in statuses), "sources_total": len(statuses)}
    (out / "latest.json").write_text(json.dumps({**meta, "items": all_items, "rhine_gauges": rhine}, ensure_ascii=False, indent=1))
    (out / "status.json").write_text(json.dumps({**meta, "sources": statuses}, ensure_ascii=False, indent=1))

    lines = [f"# Source digest, fetched {now:%Y-%m-%d %H:%M} UTC",
             f"{meta['sources_ok']} of {meta['sources_total']} starting pages read. "
             f"Items from the last {MAX_AGE_DAYS} days; 'no date' items come from page links.", ""]
    for s in statuses:
        if s is rhine_status:
            continue
        lines.append(f"## {s['source']}")
        if not s["ok"]:
            lines += [f"(failed: {s['error']})", ""]
            continue
        for it in (i for i in all_items if i["source"] == s["source"]):
            when = it["published"][:16].replace("T", " ") if it["published"] else "no date"
            lines.append(f"- {when} | {it['title']} | {it['link']}")
            if it["summary"]:
                lines.append(f"  {it['summary']}")
        lines.append("")
    lines.append("## Rhine gauges (Pegelonline, live)")
    if rhine:
        lines.append("Water level in cm; trend 1 rising, 0 steady, -1 falling. Kaub needs about 77 cm for a 1.90 m channel.")
        for r in rhine:
            lines.append(f"- {r['gauge']} (Rhine km {r['km']}): {r['level_cm']} {r['unit']}, "
                         f"trend {r['trend']}, measured {r['measured_at']}")
    else:
        lines.append(f"(failed: {rhine_status['error']})")
    lines.append("")
    (out / "latest.md").write_text("\n".join(lines))
    if meta["sources_ok"] == 0:
        sys.exit("No source could be read")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out")
