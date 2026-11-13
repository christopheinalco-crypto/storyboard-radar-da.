#!/usr/bin/env python3
"""RADAR DA: shortlist editorial discoveries; NEVER publish unverified stories."""
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
NOW = dt.datetime.now(dt.timezone.utc).isoformat()
PRIMARY = ("clip", "music-video", "music_video", "video", "concert", "tour", "stage", "set-design", "scenograph", "lighting", "broadcast", "television", "performance", "immersive", "theatre", "theater", "show", "spectacle", "live")
SECONDARY = ("production", "creative", "design", "director", "behind-the-scenes", "making-of", "visual", "installation", "launch", "projection", "mapping", "choreograph")
EXCLUDE = ("privacy", "terms", "cookie", "contact", "about-us", "newsletter", "login", "register", "subscribe", "shop", "store", "careers", "jobs", "advertis", "support", "category", "tag", "author", "search", "sitemap", "wp-content", "cdn-cgi", "account")
CATEGORY_BOOST = {"14 Musique Clips": 8, "02 TV Broadcast": 7, "01 Spectacle Concert": 7, "15 Danse Performance": 6, "09 France Pro": 4}
MAX_PER_DOMAIN = 8
MAX_PER_CATEGORY = 55

def load(name, fallback):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return fallback

def normalize(url):
    return re.sub(r"/+$", "", url.split("#", 1)[0].split("?", 1)[0]).lower()

def project_key(url):
    path = unquote(urlparse(url).path).lower()
    slug = re.sub(r"[^a-z0-9]+", " ", path.split("/")[-1])
    return " ".join(w for w in slug.split() if w not in ("the", "and", "with", "video", "music", "official", "2026"))

def score(url, category, priority):
    p = urlparse(url)
    path = unquote(p.path).lower()
    tokens = re.sub(r"[^a-z0-9]+", "-", path)
    depth = len([x for x in path.split("/") if x])
    if depth < 2 or len(path) < 14 or any(x in tokens for x in EXCLUDE):
        return -1
    if re.search(r"\.(?:jpg|png|gif|webp|svg|pdf|css|js|woff|mp4|mov)$", path):
        return -1
    # Avoid category landing pages, vendor product catalogues and shallow navigation.
    if re.search(r"/(?:categories|category|topics|products|solutions|services|events|resources|news|videos)/?$",path) and not re.search(r"/(?:videos|projects)/20[0-9]{2}/",path):
        return -1
    if any(x in tokens for x in ("product-software","solution-live","workflow-tools","case-studies-index","expertises-show-design","video-format-conversion","products-product","products-video")):
        return -1
    pts = 3 if priority == "P1" else 2 if priority == "P2" else 0
    pts += CATEGORY_BOOST.get(category, 0)
    pts += 9 * sum(term in tokens for term in PRIMARY)
    pts += 3 * sum(term in tokens for term in SECONDARY)
    pts += min(depth, 5)
    if re.search(r"2026|2027|november|novembre", tokens):
        pts += 4
    if any(x in tokens for x in ("2024", "2023", "2022", "2021", "2020", "2019")):
        pts -= 15
    return pts

def main():
    discoveries = load("source-discoveries.json", {}).get("items", [])
    feed = load("feed.json", {}).get("items", [])
    registry = load("published-projects.json", {}).get("projects", [])
    queue = load("editorial-queue.json", {}).get("candidates", [])
    known_urls = {normalize(x.get("url", "")) for x in feed + registry + queue}
    known_projects = {project_key(x.get("url", "")) for x in feed + registry if len(project_key(x.get("url", ""))) > 13}
    ranked = []
    for item in discoveries:
        url = item.get("url", "")
        if not url.startswith("https://") or normalize(url) in known_urls:
            continue
        key = project_key(url)
        if len(key) > 13 and key in known_projects:
            continue
        category = item.get("source_category", "")
        priority = item.get("priority", "")
        pts = score(url, category, priority)
        if pts < 7:
            continue
        ranked.append({**item, "score": pts, "status": "a_verifier", "requirements": ["date_creation", "choix_DA_observable", "source_primaire", "image_du_projet_et_droits", "doublon_identite"]})
    ranked.sort(key=lambda x: (-x["score"], x.get("url", "")))
    # Reserve coverage across sectors instead of letting the first source dominate.
    selected, domains, categories, seen = [], {}, {}, set()
    sector_order = ["14 Musique Clips","01 Spectacle Concert","02 TV Broadcast","15 Danse Performance","09 France Pro"]
    buckets = {cat:[i for i in ranked if i.get("source_category")==cat] for cat in sector_order}
    other = [i for i in ranked if i.get("source_category") not in sector_order]
    balanced = []
    for pos in range(max([len(v) for v in buckets.values()] + [0])):
        for cat in sector_order:
            if pos < len(buckets[cat]): balanced.append(buckets[cat][pos])
    balanced.extend(other)
    for item in balanced:
        url = item["url"]
        domain = urlparse(url).netloc
        cat = item.get("source_category", "")
        if normalize(url) in seen or domains.get(domain, 0) >= MAX_PER_DOMAIN or categories.get(cat, 0) >= MAX_PER_CATEGORY:
            continue
        seen.add(normalize(url))
        domains[domain] = domains.get(domain, 0) + 1
        categories[cat] = categories.get(cat, 0) + 1
        selected.append(item)
        if len(selected) >= 160:
            break
    report = {"updated_at": NOW, "status": "selection_non_verifiee", "warning": "Scores = priorisation de liens, jamais validation editoriale, date ou droit image.", "total_discoveries": len(discoveries), "ranked": len(ranked), "shortlisted": len(selected), "by_category": categories, "items": selected}
    (DATA / "editorial-shortlist.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"RADAR DA shortlist: {len(selected)} candidats non verifies / {len(discoveries)} liens; categories={categories}")

if __name__ == "__main__":
    main()
