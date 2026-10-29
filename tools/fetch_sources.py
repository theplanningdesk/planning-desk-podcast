"""Pull the scrobblers' starting pages into one digest the agents can read.

The scheduled scrobblers can't fetch these pages themselves while Jim sleeps
(each fetch waits for an approval nobody gives), but they can read GitHub
from their shell. This script runs in GitHub Actions, where the open web is
reachable, and writes:

  out/latest.json  every item: lane, source, title, link, published, summary, highlights
  out/latest.md    the same, grouped by lane and source, for reading
  out/status.json  per-source result, so a broken feed shows up

Three lanes:
  logistics   trade press, freight, AI and tech (the original starting pages)
  management  operations research, planning research, working capital, efficiency,
              supply chain management press and recurring surveys (added 29 Oct 2026)
  companies   quarterly reports and releases from a watchlist of Nordic companies,
              with the sentences on inventory, working capital, cash flow and cost
              programmes pulled out as highlights (added 29 Oct 2026)

Items found only as page links (no feed) are opened one by one to read the real
publish date and the opening text, so the agents don't have to search for them.

Usage: python tools/fetch_sources.py out/
"""
import datetime as dt
import html
import json
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import feedparser
import requests

# (name, url) or (name, [url, fallback url, ...]); the first URL that yields entries wins.
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
    ("Xeneta", "https://www.xeneta.com/news"),
    ("Talking Logistics", "https://talkinglogistics.com/"),
    ("Supply Chain Shaman", "https://www.supplychainshaman.com/"),
    ("SAP News", "https://news.sap.com/"),
    ("Gartner Newsroom", "https://www.gartner.com/en/newsroom"),
    ("ASCM", "https://www.ascm.org/"),
]

# Added 29 Oct 2026 (claude/research/source-vetting-2026-10-29-management.md).
MANAGEMENT_SOURCES = [
    ("TechXplore (business)", "https://techxplore.com/rss-feed/business-tech-news/"),
    ("TechXplore (all)", "https://techxplore.com/rss-feed/"),
    ("Phys.org (economics and business)", "https://phys.org/rss-feed/science-news/economics-business/"),
    ("idw-online (DACH research)", "https://idw-online.de/de/pressreleasesrss"),
    ("KLU newsroom", "https://www.klu.org/newsroom"),
    ("The Conversation (business)", "https://theconversation.com/uk/business/articles.atom"),
    ("Consultancy.eu", "https://www.consultancy.eu/rss/consultancy_rssfeed.xml"),
    ("CFO Dive", "https://www.cfodive.com/feeds/news/"),
    ("Industriemagazin", "https://industriemagazin.at/rss.xml"),
    ("Placera (Swedish business news)", "https://www.placera.se/artiklar/rss.xml"),
    ("Teknikföretagen", "https://via.tt.se/rss/releases/latest?publisherId=2732851"),
    ("Swedbank PMI", "https://mfn.se/all/a/swedbank.rss"),
    ("STT Info (Finnish releases)", "https://www.sttinfo.fi/rss/releases/latest"),
    ("DACH ad hoc releases (finanznachrichten)", "https://www.finanznachrichten.de/rss-aktien-adhoc/"),
]


def _mfn(slug):
    return f"https://mfn.se/all/a/{slug}.rss"


def _cision(slug):
    return f"https://news.cision.com/se/ListItems?n={slug}&m=Financial&pageIx=1&format=rss"


# Company watchlist: Nordic manufacturers and distributors. Edit freely.
COMPANIES = [
    ("SKF", [_mfn("skf"), _cision("skf")]),
    ("Sandvik", [_mfn("sandvik"), _cision("sandvik")]),
    ("Atlas Copco", [_mfn("atlas-copco"), _cision("atlas-copco")]),
    ("Epiroc", [_mfn("epiroc"), _cision("epiroc")]),
    ("Volvo Group", [_mfn("volvo"), _mfn("ab-volvo"), _cision("ab-volvo")]),
    ("Electrolux", [_mfn("electrolux")]),
    ("Alfa Laval", [_mfn("alfa-laval"), _cision("alfa-laval")]),
    ("Husqvarna", [_mfn("husqvarna")]),
    ("Essity", [_mfn("essity"), _cision("essity")]),
    ("Getinge", [_mfn("getinge"), _cision("getinge")]),
    ("Boliden", [_mfn("boliden"), _cision("boliden")]),
    ("SSAB", [_mfn("ssab"), _cision("ssab")]),
    ("Assa Abloy", [_mfn("assa-abloy"), _cision("assa-abloy")]),
    ("Trelleborg", [_mfn("trelleborg")]),
    ("SCA", [_mfn("sca"), _cision("sca")]),
    ("Holmen", [_mfn("holmen"), _cision("holmen")]),
    ("Billerud", [_mfn("billerud"), _cision("billerud-ab")]),
    ("Thule", [_mfn("thule-group")]),
    ("Axfood", [_mfn("axfood")]),
    ("ICA Gruppen", [_mfn("ica-gruppen")]),
    ("Kone", [_mfn("kone")]),
    ("Wärtsilä", [_mfn("wartsila")]),
    ("Valmet", [_mfn("valmet")]),
    ("UPM", [_mfn("upm-kymmene")]),
    ("Stora Enso", [_mfn("stora-enso")]),
    ("Orkla", [_mfn("orkla")]),
    ("Norsk Hydro", [_mfn("norsk-hydro")]),
    ("Carlsberg", [_mfn("carlsberg")]),
]

PLANNING_WORDS = [
    "supply chain", "supply-chain", "inventor", "logistics", "manufactur", "scheduling",
    "optimization", "optimisation", "forecast", "procurement", "supplier", "operations research",
    "warehouse", "production planning", "working capital", "lean ", "productivity",
]
GERMAN_WORDS = [
    "lieferkette", "supply chain", "supply-chain", "logistik", "lagerbestand", "bestände",
    "produktionsplanung", "optimierung", "beschaffung", "einkauf", "prognose", "operations research",
    "wertschöpfungskette", "lieferengp", "materialmangel", "fertigung",
]

# Sources whose feed is broad: keep only items whose title, summary or text matches.
KEYWORDS = {
    "NVIDIA Technical Blog (optimisation)": [
        "cuopt", "solver", "supply chain", "logistics", "vehicle routing", "linear program",
        "mixed integer", "mixed-integer", "operations research", "inventory", "demand forecast"],
    "TechXplore (business)": PLANNING_WORDS,
    "TechXplore (all)": PLANNING_WORDS,
    "Phys.org (economics and business)": PLANNING_WORDS,
    "The Conversation (business)": PLANNING_WORDS,
    "idw-online (DACH research)": GERMAN_WORDS + PLANNING_WORDS,
    "Consultancy.eu": PLANNING_WORDS + ["s&op", "cost reduction", "efficiency", "operating model"],
    "CFO Dive": ["inventor", "working capital", "supply chain", "cash conversion", "supplier",
                 "procurement", "cash flow"],
    "Industriemagazin": GERMAN_WORDS + [
        "effizienz", "stellenabbau", "restrukturierung", "sparprogramm", "kostensenkung",
        "werksschließung", "produktion", "lean"],
    "Placera (Swedish business news)": [
        "lager", "rörelsekapital", "besparing", "sparprogram", "effektivis", "varsel",
        "omstrukturer", "kassaflöde", "leverantör", "leveranskedj", "produktion", "fabrik"],
    "Teknikföretagen": ["konjunktur", "barometer", "order", "export", "industri", "kapacitet"],
    "Swedbank PMI": ["pmi", "inköpschef"],
    "STT Info (Finnish releases)": [
        "teknologiateollisuus", "toimitusketju", "tilauskanta", "varasto", "teollisuu"],
    "DACH ad hoc releases (finanznachrichten)": [
        "prognose", "restrukturierung", "effizienz", "stellenabbau", "sparprogramm",
        "kostensenkung", "quartal", "werk", "lieferkette"],
}

# Link filters for sources read from page links: keep only article paths.
LINK_RULES = {
    "Xeneta": {"include": ["/news/", "/press/", "/blog/xeneta-weekly", "ocean-market-update"]},
    "Osto&Logistiikka": {"exclude": ["/mainos/"]},
    "KLU newsroom": {"include": ["/article/"]},
}

# Company releases: skip routine notices; pull these words' sentences out as highlights.
COMPANY_NOISE = [
    "managers' transactions", "managers transactions", "johtohenkilöiden", "buyback", "buy-back",
    "återköp", "repurchase", "shareholder disclosure", "disclosure notification", "notification of",
    "holdings", "flaggning", "invitation", "inbjudan", "kutsu", "påminnelse", "reminder",
    "shares converted", "osakkeet", "status share", "major shareholding", "number of shares",
    "number of votes", "annual general", "årsstämma", "extraordinary", "nomination", "valberedning",
    "reporting schedule", "katsausten aikataulu", "share capital", "incentive", "acquisition of carlsberg a/s sha",
]
HIGHLIGHT_WORDS = [
    "inventor", "working capital", "cash flow", "savings", "cost reduction", "cost-reduction",
    "efficiency", "restructuring", "rightsizing", "capacity", "supply chain", "headcount", "footprint",
    "tariff", "lager", "rörelsekapital", "kassaflöde", "besparing", "effektivis", "omstrukturer",
    "varsel", "kapacitet", "varasto", "käyttöpääoma", "kassavirta", "säästö", "tehostam",
]
ENGLISH_HINTS = [" report", "interim", "quarter", "results", "statement", "inside information",
                 "acquire", "announces", "to ", " the "]

# Live Rhine gauges from Pegelonline (WSV), the federal waterways data service.
RHINE_API = ("https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json"
             "?waters=RHEIN&includeTimeseries=true&includeCurrentMeasurement=true")
RHINE_GAUGES = ["MAXAU", "KAUB", "KÖLN", "DUISBURG-RUHRORT", "EMMERICH"]

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36 ThePlanningDeskBot/1.0")
MAX_AGE_DAYS = 8
MAX_PER_SOURCE = 40
ARTICLES_PER_SOURCE = 15
TIMEOUT = 25


def clean(text, limit=400):
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", text or "", flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def get(url, timeout=TIMEOUT):
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=timeout)
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


def entry_text(e):
    if e.get("content"):
        return " ".join(c.get("value", "") for c in e["content"])
    return e.get("summary") or e.get("description") or ""


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
            "_text": clean(entry_text(e), 60000),
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


def fetch_source(source, urls, cutoff):
    urls = [urls] if isinstance(urls, str) else urls
    status = {"source": source, "url": urls[0], "ok": False, "method": None, "items": 0, "error": None}
    errors = []
    for url in urls:
        try:
            resp = get(url)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {type(exc).__name__}: {exc}"[:200])
            continue
        if looks_like_feed(resp):
            items, total = parse_feed(source, url, resp.content, cutoff)
            if total:
                items = items[:MAX_PER_SOURCE]
                status.update(ok=True, url=url, method=f"feed {url}", items=len(items))
                return items, status
            errors.append(f"{url}: empty feed")
            continue
        for feed_url in discover_feeds(url, resp.text):
            try:
                fresp = get(feed_url)
                if not looks_like_feed(fresp):
                    continue
                items, total = parse_feed(source, feed_url, fresp.content, cutoff)
                if total:
                    items = items[:MAX_PER_SOURCE]
                    status.update(ok=True, url=url, method=f"feed {feed_url}", items=len(items))
                    return items, status
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{feed_url}: {type(exc).__name__}")
        items = scrape_links(source, url, resp.text)[:MAX_PER_SOURCE]
        if items:
            status.update(ok=True, url=url, method="page links (articles opened for dates)", items=len(items))
            return items, status
        errors.append(f"{url}: no feed and no article links")
    status["error"] = "; ".join(errors)[:300] or "nothing read"
    return [], status


def keep(source, items):
    words = KEYWORDS.get(source)
    if words:
        items = [i for i in items
                 if any(w in (i["title"] + " " + i["summary"] + " " + i.get("_text", "")).lower() for w in words)]
    rules = LINK_RULES.get(source, {})
    if rules.get("include"):
        items = [i for i in items if any(k in i["link"] for k in rules["include"])]
    if rules.get("exclude"):
        items = [i for i in items if not any(k in i["link"] for k in rules["exclude"])]
    return items


# --- reading single articles (for page-link items) --------------------------------

DATE_PATTERNS = [
    r"""<meta[^>]+(?:property|name|itemprop)=["'](?:article:published_time|og:published_time|datePublished|date|pubdate|publishdate|dc\.date|DC\.date\.issued)["'][^>]*content=["']([^"']+)""",
    r"""<meta[^>]+content=["']([^"']+)["'][^>]*(?:property|name|itemprop)=["'](?:article:published_time|datePublished|date|pubdate)["']""",
    r'''"datePublished"\s*:\s*"([^"]+)"''',
    r"""<time[^>]+datetime=["']([^"']+)""",
]


def parse_date(text):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?", text or "")
    if m:
        y, mo, d, h, mi = m.groups()
        return dt.datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), tzinfo=dt.timezone.utc)
    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text or "")
    if m:
        d, mo, y = m.groups()
        return dt.datetime(int(y), int(mo), int(d), tzinfo=dt.timezone.utc)
    return None


def read_article(url):
    """Return (published datetime or None, opening text) for one article page."""
    resp = get(url, timeout=15)
    page = resp.text
    published = None
    for pat in DATE_PATTERNS:
        m = re.search(pat, page, re.I)
        if m and parse_date(m.group(1)):
            published = parse_date(m.group(1))
            break
    desc = ""
    for pat in (r"""<meta[^>]+property=["']og:description["'][^>]*content=["']([^"']*)""",
                r"""<meta[^>]+name=["']description["'][^>]*content=["']([^"']*)"""):
        m = re.search(pat, page, re.I)
        if m and len(m.group(1)) > 40:
            desc = clean(m.group(1), 300)
            break
    body = re.sub(r"<(script|style|nav|header|footer|aside)\b.*?</\1>", " ", page, flags=re.I | re.S)
    paras = [clean(p, 600) for p in re.findall(r"<p\b[^>]*>(.*?)</p>", body, re.I | re.S)]
    paras = [p for p in paras if len(p) > 80 and "cookie" not in p.lower()]
    opening = " ".join(paras[:3])
    text = (desc + " " + opening).strip() if desc and desc[:60] not in opening else (opening or desc)
    return published, clean(text, 500)


def enrich(items, cutoff):
    """Open page-link items to read their real date and opening text; drop old ones."""
    todo, counts = [], {}
    for it in items:
        if it["via"] != "page links":
            continue
        counts[it["source"]] = counts.get(it["source"], 0) + 1
        if counts[it["source"]] <= ARTICLES_PER_SOURCE:
            todo.append(it)

    def work(it):
        try:
            published, text = read_article(it["link"])
        except Exception:  # noqa: BLE001
            published, text = None, ""
        if not published:
            published = parse_date(it["title"])
        return it, published, text

    with ThreadPoolExecutor(max_workers=8) as pool:
        for it, published, text in pool.map(work, todo):
            it["via"] = "page links, article read"
            if published:
                it["published"] = published.isoformat()
            if text:
                it["summary"] = text
    kept = []
    for it in items:
        if it["via"] == "page links":
            continue  # beyond the per-source article cap: not read, not kept
        if it["published"] and parse_date(it["published"]) < cutoff:
            continue
        kept.append(it)
    return kept


# --- company releases ---------------------------------------------------------------

def highlights(text, limit=1000):
    sentences = re.split(r"(?<=[.!?])\s+", text or "")
    picked, total = [], 0
    for s in sentences:
        s = s.strip()
        if 40 <= len(s) <= 400 and any(w in s.lower() for w in HIGHLIGHT_WORDS):
            if s in picked:
                continue
            picked.append(s)
            total += len(s)
            if total > limit or len(picked) >= 6:
                break
    return " ".join(picked)


def company_items(name, items):
    items = [i for i in items if not any(n in i["title"].lower() for n in COMPANY_NOISE)]
    # MFN publishes each release in two languages at the same minute: keep one, preferring English.
    by_time = {}
    for it in items:
        key = (it["published"] or "")[:16] or it["link"]
        by_time.setdefault(key, []).append(it)
    kept = []
    for group in by_time.values():
        group.sort(key=lambda i: -sum(h in i["title"].lower() for h in ENGLISH_HINTS))
        it = group[0]
        it["company"] = name
        it["highlights"] = highlights(it.get("_text", ""))
        kept.append(it)
    kept.sort(key=lambda i: i["published"] or "", reverse=True)
    return kept


# --- Rhine ----------------------------------------------------------------------------

def fetch_rhine():
    """Current water level (cm) at the Rhine gauges that matter for barge loads."""
    status = {"source": "Rhine gauges (Pegelonline)", "url": RHINE_API, "ok": False,
              "method": "json api", "items": 0, "error": None, "lane": "logistics"}
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


# --- main -----------------------------------------------------------------------------

LANE_TITLES = {
    "logistics": "Logistics, trade, AI and tech sources",
    "management": "Management, operations research and planning research sources",
    "companies": "Company releases (watchlist: quarterly reports, programmes, restructurings)",
}


def run_lane(lane, sources, cutoff, all_items, statuses):
    for source, urls in sources:
        items, status = fetch_source(source, urls, cutoff)
        status["lane"] = lane
        if lane == "companies":
            items = company_items(source, items)
            status["items"] = len(items)
            if status["ok"] and not items:
                status["error"] = "no releases in the window (normal off-season)"
        elif source in KEYWORDS or source in LINK_RULES:
            items = keep(source, items)
            status["items"] = len(items)
            if not items and source in LINK_RULES and status["ok"]:
                status.update(ok=False, error="no article links after filtering")
            elif not items and status["ok"]:
                status["error"] = "no matching posts in the window (normal for this source)"
        for it in items:
            it["lane"] = lane
        print(f"{'OK ' if status['ok'] else 'ERR'} [{lane}] {source}: {status['items']} items "
              f"via {status['method'] or '-'} {status['error'] or ''}", flush=True)
        all_items += items
        statuses.append(status)


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=MAX_AGE_DAYS)
    all_items, statuses = [], []
    run_lane("logistics", SOURCES, cutoff, all_items, statuses)
    run_lane("management", MANAGEMENT_SOURCES, cutoff, all_items, statuses)
    run_lane("companies", COMPANIES, cutoff, all_items, statuses)

    all_items = enrich(all_items, cutoff)
    for s in statuses:
        if s["lane"] != "companies":
            s["items"] = sum(1 for i in all_items if i["source"] == s["source"])
    for it in all_items:
        it.pop("_text", None)

    rhine, rhine_status = fetch_rhine()
    print(f"{'OK ' if rhine_status['ok'] else 'ERR'} Rhine gauges: {len(rhine)} {rhine_status['error'] or ''}")
    statuses.append(rhine_status)

    meta = {"fetched_at": now.isoformat(), "window_days": MAX_AGE_DAYS,
            "sources_ok": sum(s["ok"] for s in statuses), "sources_total": len(statuses)}
    (out / "latest.json").write_text(json.dumps({**meta, "items": all_items, "rhine_gauges": rhine}, ensure_ascii=False, indent=1))
    (out / "status.json").write_text(json.dumps({**meta, "sources": statuses}, ensure_ascii=False, indent=1))

    lines = [f"# Source digest, fetched {now:%Y-%m-%d %H:%M} UTC",
             f"{meta['sources_ok']} of {meta['sources_total']} sources read. Items from the last "
             f"{MAX_AGE_DAYS} days. Items from page links were opened to read their date and opening "
             "text; 'no date' means the article page didn't show one.", ""]
    for lane in ("logistics", "management", "companies"):
        lines += [f"# {LANE_TITLES[lane]}", ""]
        for s in (s for s in statuses if s["lane"] == lane and s is not rhine_status):
            lines.append(f"## {s['source']}")
            if not s["ok"]:
                lines += [f"(failed: {s['error']})", ""]
                continue
            listed = [i for i in all_items if i["source"] == s["source"]]
            if not listed:
                lines += ["(nothing in the window)", ""]
                continue
            for it in listed:
                when = it["published"][:16].replace("T", " ") if it["published"] else "no date"
                lines.append(f"- {when} | {it['title']} | {it['link']}")
                if it.get("highlights"):
                    lines.append(f"  Highlights: {it['highlights']}")
                elif it["summary"]:
                    lines.append(f"  {it['summary']}")
            lines.append("")
    lines.append("## Rhine gauges (Pegelonline, live)")
    if rhine:
        lines.append("Water level in cm; trend 1 rising, 0 steady, -1 falling. Kaub needs about 77 cm for a 1.90 m channel.")
        for r in rhine:
            lines.append(f"- {r['gauge']} (Rhine km {r['km']}): {r['level_cm']} {r['unit']}, "
                         f"{'trend ' + str(r['trend']) + ', ' if r['trend'] is not None else ''}measured {r['measured_at']}")
    else:
        lines.append(f"(failed: {rhine_status['error']})")
    lines.append("")
    (out / "latest.md").write_text("\n".join(lines))
    if meta["sources_ok"] == 0:
        sys.exit("No source could be read")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out")
