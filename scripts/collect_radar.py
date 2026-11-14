#!/usr/bin/env python3
"""RADAR DA: collect recent RSS candidates without publishing unreviewed articles."""
import datetime as dt
import email.utils
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
NOW = dt.datetime.now(dt.timezone.utc)
PRIORITY = ("concert", "spectacle", "clip", "music", "tv", "broadcast", "scenograph", "stage", "show", "event", "brand", "retail")
TERMS = re.compile(r"concert|tour|stage|scenograph|set design|music video|video director|lighting design|live show|broadcast|ceremony|product launch|brand experience|clip|spectacle|scène|scenographie|lancement", re.I)
EXCLUDE = re.compile(r"webinar|job opening|appointed|speaker line-up|training course|formation métier|packaging", re.I)

def tagname(tag):
    return tag.rsplit("}", 1)[-1].lower()

def child_text(node, names):
    for child in node:
        if tagname(child.tag) in names:
            if child.text and child.text.strip():
                return child.text.strip()
            if child.attrib.get("href"):
                return child.attrib["href"]
    return ""

def parse_date(value):
    if not value:
        return None
    try:
        return email.utils.parsedate_to_datetime(value).astimezone(dt.timezone.utc)
    except (TypeError, ValueError, OverflowError):
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
        except ValueError:
            return None

def canonical(url):
    try:
        u = urlsplit(url)
        return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path.rstrip("/"), "", ""))
    except ValueError:
        return url

feed = json.loads((ROOT / "data/feed.json").read_text(encoding="utf-8"))
existing = {canonical(item.get("url", "")) for item in feed.get("items", [])}
existing.update(canonical(url) for url in json.loads((ROOT / "data/analyses.json").read_text(encoding="utf-8")).keys())
sources = feed.get("working_feeds", [])
results, failures, checked, parsed = [], [], 0, 0
for source in sources:
    url = source.get("feed")
    if not url:
        continue
    checked += 1
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "RADAR-DA-RSS-Collector/1.0 (+editorial research)"})
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read(2_000_000)
        tree = ET.fromstring(raw)
        entries = [e for e in tree.iter() if tagname(e.tag) in ("item", "entry")]
        parsed += 1
        for entry in entries[:50]:
            title = child_text(entry, ("title",))
            link = child_text(entry, ("link", "guid", "id"))
            date_string = child_text(entry, ("pubdate", "published", "updated", "date"))
            date = parse_date(date_string)
            if not title or not link or not link.startswith("http") or not date:
                continue
            age_hours = (NOW - date).total_seconds() / 3600
            if not 0 <= age_hours <= 72 or canonical(link) in existing:
                continue
            category = source.get("category", "")
            if not any(term in category.lower() for term in PRIORITY):
                continue
            if not TERMS.search(title) or EXCLUDE.search(title):
                continue
            results.append({"title": title, "url": link, "source": source.get("name"), "category": category,
                            "source_published_at": date.isoformat(), "age_hours": round(age_hours, 1),
                            "status": "candidate_unverified", "project_date_verified": False,
                            "visual_verified": False, "editorial_score": None})
    except Exception as exc:
        failures.append({"source": source.get("name"), "url": url, "error": str(exc)[:200]})
unique = {canonical(item["url"]): item for item in results}
candidates = sorted(unique.values(), key=lambda x: x["source_published_at"], reverse=True)
out = {"collected_at": NOW.isoformat(), "configured_sources": feed.get("sources_selected"),
       "rss_sources_attempted": checked, "rss_sources_parsed": parsed,
       "rss_sources_failed": len(failures), "candidates_72h": len(candidates),
       "candidates_24h": sum(x["age_hours"] <= 24 for x in candidates),
       "warning": "RSS discovery only: not 182 sources opened; project dates, evidence, rights and images NOT verified.",
       "failures": failures, "candidates": candidates[:200]}
path = ROOT / "data/collection_report.json"
path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"RSS checked={checked} parsed={parsed} failed={len(failures)} candidates={len(candidates)}")

# Second collection lane: directly attempt ALL 182 catalogued websites, RSS or not.
# This is discovery/availability auditing, not proof that every site's articles were read.
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
import ssl

def inspect_website(source):
    url = source.get("url", "")
    record = {"name": source.get("name"), "url": url, "category": source.get("category"),
              "status": "failed", "http_status": None, "page_title": None,
              "links_discovered": 0, "recent_articles_verified": 0}
    if not url.startswith(("https://", "http://")):
        record["error"] = "Missing valid URL"
        return record
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; RADAR-DA-Research/1.0)", "Accept": "text/html,application/xhtml+xml"})
        with urllib.request.urlopen(req, timeout=9) as response:
            record["http_status"] = response.status
            final_url = response.geturl()
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(450_000)
        record["final_url"] = final_url
        if "html" in content_type.lower():
            html = raw.decode("utf-8", "replace")
            title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            if title:
                record["page_title"] = unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip()[:180]
            record["links_discovered"] = len(re.findall(r"<a\\b[^>]*href\\s*=", html, re.I))
        record["status"] = "fetched"
    except Exception as exc:
        record["error"] = str(exc)[:180]
    return record

catalogue = json.loads((ROOT / "data/sources.json").read_text(encoding="utf-8"))
with ThreadPoolExecutor(max_workers=16) as executor:
    futures = [executor.submit(inspect_website, s) for s in catalogue]
    direct = [future.result() for future in futures]
out["catalogue_sources"] = len(catalogue)
out["direct_sources_attempted"] = len(direct)
out["direct_sources_fetched"] = sum(x["status"] == "fetched" for x in direct)
out["direct_sources_failed"] = sum(x["status"] != "fetched" for x in direct)
out["direct_checks"] = direct
out["warning"] = ("Each of the 182 catalogued website URLs was attempted once. "
                  "A successful homepage fetch is NOT a full article review; "
                  "recent_articles_verified=0 until individual articles are opened and checked. "
                  "RSS candidates require editorial, image and publication verification.")
path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Direct websites attempted={len(direct)} fetched={out['direct_sources_fetched']} failed={out['direct_sources_failed']}")
