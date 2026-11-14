#!/usr/bin/env python3
"""Replace RADAR DA explanatory diagrams with verified source-specific project photos.

Never use an unrelated stock image. A failed verification keeps the existing image
and records a warning, rather than inventing an asset.
"""
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

TARGETS = ("Max Swan", "YOGI", "Pink Siifu")
DATA = Path("data/feed.json")
REPORT = Path("data/visual_audit.json")

class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("property", "").lower() in ("og:image", "og:image:url", "twitter:image"):
            self.images.append((a.get("content", ""), "social"))
        if tag == "img":
            for key in ("data-src", "src", "data-original"):
                if a.get(key):
                    self.images.append((a[key], a.get("alt", "")))
                    break

def get(url, limit=2500000):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (RADAR DA visual audit)", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read(limit), resp.headers.get("Content-Type", "")

def find_project_image(article):
    raw, mime = get(article["url"])
    if "html" not in mime.lower():
        raise ValueError("Source is not HTML")
    p = Images()
    p.feed(raw.decode("utf-8", "replace"))
    candidates = []
    for link, alt in p.images:
        u = urljoin(article["url"], link)
        if not u.startswith("https://") or re.search(r"(logo|avatar|icon|favicon|pixel|tracking|banner|advert|placeholder)", u, re.I):
            continue
        candidates.append((u, alt))
    for u, alt in candidates[:15]:
        try:
            blob, mime = get(u)
            if mime.lower().startswith("image/") and "svg" not in mime.lower() and len(blob) >= 12000:
                return u, alt
        except Exception:
            continue
    raise ValueError("No sufficiently large source-linked photo verified")

data = json.loads(DATA.read_text(encoding="utf-8"))
report = []
changed = False
for item in data["items"]:
    if not any((item.get("title_fr") or item.get("title") or "").startswith(t) for t in TARGETS):
        continue
    result = {"title": item.get("title_fr") or item.get("title"), "url": item["url"]}
    try:
        image, alt = find_project_image(item)
        item["image"] = image
        item["image_kind"] = "project"
        item["image_alt"] = alt if alt and alt != "social" else "Photographie publiée avec le projet : " + result["title"]
        item["image_credit"] = "Visuel publié dans la source du projet ; URL externe vérifiée automatiquement, droits de réaffichage non confirmés."
        result.update(status="updated", image=image)
        changed = True
    except Exception as e:
        result.update(status="unverified_keep_previous", error=str(e)[:250])
    report.append(result)
REPORT.write_text(json.dumps({"results": report}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
if changed:
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
