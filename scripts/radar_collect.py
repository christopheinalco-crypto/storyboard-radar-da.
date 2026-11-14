#!/usr/bin/env python3
"""RADAR DA discovery-only collector. Never publishes editorial cards."""
import concurrent.futures
import datetime as dt
import email.utils
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NOW = dt.datetime.now(dt.timezone.utc)
STAMP = NOW.isoformat()
UA = "RADAR-DA/1.0 (+public editorial discovery; contact via repository)"
LIMIT = int(os.getenv("RADAR_WORKERS", "12"))
MAX_BYTES = 750000
TIMEOUT = 12
RSS_SUFFIXES = ("/feed", "/feed/", "/rss", "/rss.xml", "/feed.xml", "/atom.xml")
KEYWORDS = re.compile(r"concert|tour|stage|scenograph|set.design|music.video|video.clip|live.show|performance|theatre|theater|spectacle|tourn[eé]e|clip|sc[eè]ne|show|festival|broadcast|production.design|visual|creative.direction", re.I)

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.title = ""
        self.in_title = False
        self.feed_links = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title": self.in_title = True
        if tag == "link" and ("rss" in a.get("type", "") or "atom" in a.get("type", "")) and a.get("href"):
            self.feed_links.append(a["href"])
        if tag == "a" and a.get("href"):
            self.links.append((a["href"], a.get("title", "")))
    def handle_endtag(self, tag):
        if tag == "title": self.in_title = False
    def handle_data(self, data):
        if self.in_title: self.title += data

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.5"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        content_type = r.headers.get("Content-Type", "")
        raw = r.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES: raise ValueError("response exceeds size limit")
        return r.geturl(), content_type, raw.decode("utf-8", "replace")

def clean_url(url):
    p = urllib.parse.urlsplit(url)
    q = [(k,v) for k,v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith("utm_") and k.lower() not in ("fbclid","gclid")]
    return urllib.parse.urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/") or "/", urllib.parse.urlencode(q), ""))

def parse_feed(text, base):
    root = ET.fromstring(text)
    items = []
    for el in list(root):
        tag = el.tag.split("}")[-1].lower()
        if tag not in ("item","entry"): continue
        vals = {}
        for child in el:
            key = child.tag.split("}")[-1].lower()
            if key == "link" and child.attrib.get("href"):
                vals["link"] = child.attrib["href"]
            elif key in ("title","link","pubdate","published","updated","description","summary"):
                vals[key] = "".join(child.itertext()).strip()
        link = urllib.parse.urljoin(base, vals.get("link",""))
        if link.startswith("http"):
            items.append({"title": html.unescape(vals.get("title","")).strip()[:240], "url":clean_url(link), "date":vals.get("published") or vals.get("pubdate") or vals.get("updated") or "", "description": re.sub("<[^>]+>"," ",vals.get("description") or vals.get("summary") or "")[:500]})
    return items[:35]

def scan(entry):
    base = entry["url"]
    result = {"name":entry["name"],"url":base,"checked_at":STAMP,"status":"error","method":None,"items":[]}
    try:
        final, ctype, body = fetch(base)
        result["evidence_url"] = final
        if "xml" in ctype or body.lstrip().startswith(("<?xml","<rss","<feed")):
            try:
                result["items"] = parse_feed(body, final)
                result["method"] = "feed"
                result["status"] = "ok"
                return result
            except ET.ParseError: pass
        parser = Page()
        parser.feed(body)
        result["method"] = "html"
        result["status"] = "ok"
        # RSS/Atom autodiscovery on the already-fetched page; no blind guessing.
        for href in parser.feed_links[:2]:
            feedurl = urllib.parse.urljoin(final, href)
            try:
                f_url, _, f_body = fetch(feedurl)
                items = parse_feed(f_body, f_url)
                if items:
                    result["items"] = items
                    result["method"] = "rss"
                    result["feed_url"] = f_url
                    return result
            except Exception: pass
        host = urllib.parse.urlsplit(final).hostname or ""
        seen = set()
        for href, title in parser.links:
            url = urllib.parse.urljoin(final, href)
            p = urllib.parse.urlsplit(url)
            if p.scheme not in ("http","https") or p.hostname != host: continue
            if not p.path or p.path in ("/","/en","/fr"): continue
            if re.search(r"\.(jpg|png|svg|gif|webp|pdf|zip|js|css)$",p.path,re.I): continue
            url = clean_url(url)
            if url in seen: continue
            seen.add(url)
            label = html.unescape(title or urllib.parse.unquote(p.path.rsplit("/",1)[-1]).replace("-"," ")).strip()
            if len(label) < 8: continue
            if KEYWORDS.search(label+" "+p.path):
                result["items"].append({"title":label[:240],"url":url,"date":"","description":""})
            if len(result["items"]) >= 35: break
    except Exception as exc:
        result["error"] = str(exc)[:240]
    return result

def main():
    sources = json.loads((ROOT/"data/sources.json").read_text(encoding="utf-8"))
    output = ROOT/"data/collector"
    output.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=LIMIT) as pool:
        results = list(pool.map(scan, sources))
    existing = output/"seen_urls.json"
    try: seen = set(json.loads(existing.read_text(encoding="utf-8")))
    except (OSError,ValueError): seen = set()
    discovered = []
    current = set()
    for source in results:
        for item in source["items"]:
            url = item["url"]
            current.add(url)
            if url not in seen:
                discovered.append({**item,"source":source["name"],"source_url":source["url"],"detected_at":STAMP,"editorial_status":"unreviewed"})
    # Discovery-only: no AI scoring, image verification or publication here.
    seen.update(current)
    existing.write_text(json.dumps(sorted(seen),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report = {"run_at":STAMP,"sources_total":len(sources),"sources_checked":len(results),"sources_ok":sum(x["status"]=="ok" for x in results),"sources_failed":sum(x["status"]!="ok" for x in results),"new_candidate_links":len(discovered),"editorial_published":0,"note":"Discovery only; candidates are not verified or approved for publication.","checks":results}
    (output/"latest_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (output/"latest_candidates.json").write_text(json.dumps({"generated_at":STAMP,"items":discovered},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Checked {len(results)}/{len(sources)} sources; OK {report['sources_ok']}; failed {report['sources_failed']}; new links {len(discovered)}")

if __name__=="__main__": main()
