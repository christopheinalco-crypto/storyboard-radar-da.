#!/usr/bin/env python3
"""Create a compact, traceable RESEARCH inbox. Never select or publish stories."""
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

DATA = Path(__file__).resolve().parents[1] / "data"
PRIORITY = (
    "14 Musique Clips", "01 Spectacle Concert", "02 TV Broadcast",
    "15 Danse Performance", "09 France Pro", "08 Immersif CGI Motion",
    "06 Retail Brand Experience",
)
CAP = {"14 Musique Clips": 12, "01 Spectacle Concert": 12,
       "02 TV Broadcast": 10, "15 Danse Performance": 8,
       "09 France Pro": 8, "08 Immersif CGI Motion": 5,
       "06 Retail Brand Experience": 5}
BAN = re.compile(
    r"/ads/redirect/|/products?/|/solutions?/|/careers?/|/jobs?/|"
    r"/subscribe|/privacy|/category/|/categories/|/tag/|/authors?/|"
    r"/myshows/|/login|/registration|/features?/|/shop/",
    re.I,
)
GENERIC = re.compile(
    r"^(live|music videos?|broadcast|news|events?|projects?|services?|"
    r"products?|obituaries|summer study guide|music video directors|"
    r"theatre, film, studio and architectural lighting)$",
    re.I,
)
PROJECT_PATH = re.compile(
    r"/(?:20[12][0-9]/|projects?/[^/]+|works?/[^/]+|"
    r"videos?/[^/]+|articles?/[^/]+|interviews?/[^/]+|"
    r"case-stud[^/]*|stories?/[^/]+|portfolio/[^/]+)",
    re.I,
)
STAGE_TERMS = re.compile(
    r"music video|clip|concert|tour|stage|scenograph|lighting|"
    r"tv |broadcast|show|performance|dance|ceremon|festival|"
    r"live session|projection|installation|making.of|behind.the.scene",
    re.I,
)

def read(name, default):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return default

def canonical(url):
    try:
        p = urlsplit(url or "")
        return p.netloc.lower().removeprefix("www.") + p.path.rstrip("/").lower()
    except ValueError:
        return str(url or "").lower()

def timestamp(value):
    if not value:
        return None
    try:
        when = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not when.tzinfo:
            when = when.replace(tzinfo=dt.timezone.utc)
        return when.astimezone(dt.timezone.utc)
    except ValueError:
        return None

def main():
    coverage = read("source-coverage.json", {})
    inspections = read("project-inspections.json", {})
    if not coverage or not inspections:
        raise SystemExit("Missing coverage/inspection evidence: editorial brief NOT created")
    if coverage.get("wave_id") != inspections.get("wave_id"):
        raise SystemExit("Mismatched collection waves: editorial brief NOT created")
    anchor = timestamp(coverage.get("checked_at")) or dt.datetime.now(dt.timezone.utc)
    feed = read("feed.json", {}).get("items", [])
    analyses = read("analyses.json", {})
    registry = read("published-projects.json", {}).get("projects", [])
    known = {canonical(x.get("url")) for x in feed + registry if isinstance(x, dict)}
    known.update(canonical(url) for url in analyses)
    buckets = {}
    excluded = Counter()
    for item in inspections.get("items", []):
        if item.get("status") != "page_inspected":
            excluded["not_opened"] += 1
            continue
        url = item.get("url", "")
        name = item.get("page_title", "").strip()
        category = item.get("source_category", "")
        if canonical(url) in known:
            excluded["already_published"] += 1
            continue
        if BAN.search(url) or GENERIC.fullmatch(name):
            excluded["navigation_or_product"] += 1
            continue
        claim = timestamp(item.get("published_date_claim"))
        age = (anchor - claim).total_seconds() / 3600 if claim else None
        if age is not None and not (-12 <= age <= 72):
            excluded["metadata_older_than_72h"] += 1
            continue
        if not (PROJECT_PATH.search(url) or STAGE_TERMS.search(name)):
            excluded["not_project_like"] += 1
            continue
        if category not in PRIORITY:
            excluded["non_priority_category"] += 1
            continue
        buckets.setdefault(category, []).append({
            "title": name[:160], "url": url, "category": category,
            "source": item.get("source", ""),
            "published_date_claim": item.get("published_date_claim", ""),
            "age_hours_claim": round(age, 1) if age is not None else None,
            "date_verified": False, "project_identity_verified": False,
            "image_candidate_unverified": item.get("image_candidate", ""),
            "description": item.get("description", "")[:480],
            "page_excerpt": item.get("page_excerpt", "")[:620],
            "editorial_score": None, "status": "research_only_not_approved",
        })
    for category in buckets:
        buckets[category].sort(key=lambda x: (
            0 if x["age_hours_claim"] is not None else 1,
            x["age_hours_claim"] if x["age_hours_claim"] is not None else 9999,
            x["title"]))
    selected = []
    # Round-robin preserves coverage of clips, concerts, TV and performance.
    for pos in range(max([min(len(buckets.get(c, [])), CAP.get(c, 5)) for c in PRIORITY] + [0])):
        for cat in PRIORITY:
            rows = buckets.get(cat, [])
            if pos < min(len(rows), CAP.get(cat, 5)):
                selected.append(rows[pos])
    result = {
        "wave_id": coverage["wave_id"], "prepared_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "coverage_checked_at": coverage.get("checked_at"),
        "coverage": {
            "attempted": coverage.get("attempted"), "opened_successfully": coverage.get("opened_successfully"),
            "failed": coverage.get("failed"), "target_met": coverage.get("target_met"),
        },
        "project_inspections": {
            "attempted": inspections.get("attempted"), "opened": inspections.get("opened"),
            "failed": inspections.get("failed"),
        },
        "research_only": True,
        "warning": "Mechanical triage, NOT editorial selection. Dates, identity, DA value, image rights and public rendering remain unverified. Editor must also research fresh projects externally.",
        "eligible_for_publication_count": 0,
        "inbox_size": len(selected),
        "dated_candidates": sum(x["age_hours_claim"] is not None for x in selected),
        "by_category": dict(Counter(x["category"] for x in selected)),
        "excluded_counts": dict(excluded),
        "items": selected,
    }
    (DATA / "editorial-brief.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("RADAR DA research brief:", result["inbox_size"],
          "unapproved candidates from", result["coverage"]["opened_successfully"],
          "successfully opened sources")

if __name__ == "__main__":
    main()
