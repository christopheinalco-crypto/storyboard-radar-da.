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

# Direct article inspection for EVERY catalogued source, with or without RSS.
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current = None
        self.title = ""
        self.in_title = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.current = [attrs["href"], ""]
        if tag == "title":
            self.in_title = True
    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += data
        if self.in_title:
            self.title += data
    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.links.append(self.current)
            self.current = None
        if tag == "title":
            self.in_title = False

def fetch_html(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (compatible; RADAR-DA/1.0)","Accept":"text/html"})
    with urllib.request.urlopen(req, timeout=9) as response:
        raw = response.read(400_000)
        final = response.geturl()
        mime = response.headers.get("Content-Type", "")
    if "html" not in mime.lower():
        raise ValueError("Non-HTML content")
    return raw.decode("utf-8", "replace"), final

ARTICLE_PATH = re.compile(r"/(?:20[12][0-9]/|news/|article/|articles/|project/|projects/|work/|works/|video/|videos/|features/|stories/|blog/|case-stud)", re.I)
DATE_META = re.compile(r'(?:article:published_time|datePublished|pubdate|publish_date|datePublished)[^>]{0,250}', re.I)
ISO_DATE = re.compile(r"20[0-9]{2}-[01][0-9]-[0-3][0-9](?:T[0-9:.+Z-]*)?")

def inspect_website(source):
    url = source.get("url", "")
    record = {"name":source.get("name"),"url":url,"category":source.get("category"),
              "status":"failed","homepage_fetched":False,"articles_opened":0,
              "recent_articles_verified":0,"candidates":[],"errors":[]}
    if not url.startswith(("https://","http://")):
        record["errors"].append("Invalid URL")
        return record
    try:
        html, final = fetch_html(url)
        record["homepage_fetched"] = True
        record["final_url"] = final
        parser = LinkParser()
        parser.feed(html)
        record["page_title"] = unescape(parser.title.strip())[:180]
        base_domain = urlsplit(final).netloc.lower().removeprefix("www.")
        links = []
        seen = set()
        for href, label in parser.links:
            absolute = urljoin(final, href)
            parsed = urlsplit(absolute)
            if parsed.scheme not in ("http","https"):
                continue
            if not parsed.netloc.lower().removeprefix("www.").endswith(base_domain):
                continue
            normalized = canonical(absolute)
            if normalized in seen or normalized in existing or normalized == canonical(final):
                continue
            seen.add(normalized)
            if ARTICLE_PATH.search(parsed.path) or (TERMS.search(label) and len(parsed.path.strip("/")) > 12):
                links.append((absolute, unescape(label.strip())[:160]))
        record["article_links_discovered"] = len(links)
        record["article_links_pending"] = len(links)
        # Open actual article pages, not just the homepage. Limit concurrency/load per publisher.
        for article_url, label in links:
            try:
                body, resolved = fetch_html(article_url)
                record["articles_opened"] += 1
                record["article_links_pending"] -= 1
                p = LinkParser()
                p.feed(body)
                dates = []
                for meta in re.findall(r"<meta\\b[^>]+>", body[:80000], re.I):
                    if DATE_META.search(meta):
                        dates.extend(ISO_DATE.findall(meta))
                if not dates:
                    dates = ISO_DATE.findall(body[:12000])[:3]
                published = None
                for value in dates:
                    candidate_date = parse_date(value)
                    if candidate_date and 0 <= (NOW-candidate_date).total_seconds() <= 72*3600:
                        published = candidate_date
                        break
                if published:
                    record["recent_articles_verified"] += 1
                    record["candidates"].append({"title":unescape(p.title.strip())[:180] or label,
                        "url":resolved,"source_published_at":published.isoformat(),
                        "status":"article_opened_date_found_editorial_unverified",
                        "visual_verified":False,"editorial_score":None})
            except Exception as exc:
                record["errors"].append(str(exc)[:120])
                record["article_links_pending"] -= 1
        record["status"] = "articles_examined" if record["articles_opened"] else "homepage_only_no_article_opened"
    except Exception as exc:
        record["errors"].append(str(exc)[:180])
    return record

catalogue = json.loads((ROOT/"data/sources.json").read_text(encoding="utf-8"))
with ThreadPoolExecutor(max_workers=12) as executor:
    direct = list(executor.map(inspect_website, catalogue))
out["catalogue_sources"] = len(catalogue)
out["direct_sources_attempted"] = len(direct)
out["direct_sources_fetched"] = sum(x["homepage_fetched"] for x in direct)
out["direct_sources_with_articles_opened"] = sum(x["articles_opened"]>0 for x in direct)
out["direct_articles_opened"] = sum(x["articles_opened"] for x in direct)
out["direct_article_links_pending"] = sum(x.get("article_links_pending",0) for x in direct)
out["direct_sources_with_article_errors"] = sum(bool(x["errors"]) for x in direct)
out["direct_sources_failed"] = sum(not x["homepage_fetched"] for x in direct)
out["direct_candidates"] = [c for x in direct for c in x["candidates"]][:200]
out["direct_checks"] = direct
out["warning"] = ("All catalogued source URLs attempted; article pages opened where discoverable. "
                  "An unavailable source, article error, or site with no discoverable links is explicitly reported. "
                  "Dates are provisional until human editorial review; no automatic publication.")
path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\\n",encoding="utf-8")
print(f"Sources={len(direct)} sites with articles opened={out['direct_sources_with_articles_opened']} article pages opened={out['direct_articles_opened']} candidates={len(out['direct_candidates'])}")
