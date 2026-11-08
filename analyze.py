
import os
import json
import re
import html
import sys
import datetime
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from collections import Counter
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
feed_path = ROOT / "data/feed.json"
out_path = ROOT / "data/analyses.json"
review_path = ROOT / "data/reviewed.json"

feed = json.loads(feed_path.read_text(encoding="utf-8"))
saved = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
reviewed = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {}

key = os.environ.get("GEMINI_API_KEY", "")
if not key:
    sys.exit("ERROR: GEMINI_API_KEY missing")

PARIS = ZoneInfo("Europe/Paris")
now = datetime.datetime.now(datetime.timezone.utc)
today = now.astimezone(PARIS).date()

MAX_API_CALLS = min(15, max(0, int(os.environ.get("RADAR_MAX_AI_CALLS", "15"))))
MAX_PER_CATEGORY = 3
MAX_GRAPHIC_DAILY = 2
GRAPHIC_CODES = {"03", "11"}

CATEGORY_ORDER = [
    "01", "02", "14", "15", "09",
    "08", "06", "04", "07", "10",
    "13", "03", "05", "11", "12"
]

CATEGORY_PRIORITY = {
    "01": 100, "02": 98, "14": 100,
    "15": 100, "09": 95, "08": 90,
    "06": 75, "04": 78, "07": 78,
    "10": 72, "13": 55, "03": 45,
    "05": 50, "11": 45, "12": 35
}

DISCIPLINES = re.compile(
    r"sc[eé]nograph|spectacle|stage design|set design|"
    r"lighting design|conception lumi[eè]re|production design|"
    r"show design|broadcast|plateau t[eé]l[eé]|tv show|"
    r"television show|music video|vid[eé]oclip|clip musical|"
    r"projection mapping|immersif|immersive|"
    r"chor[eé]graph|danse|dance|mise en sc[eè]ne|"
    r"stage production|concert production|tour production|"
    r"live production|live show|concert|performance|"
    r"performer|performeur|compagnie|th[eé][aâ]tre|theatre|"
    r"arts de la rue|installation|cr[eé]ation sc[eé]nique|"
    r"show t[eé]l[eé]|sc[eè]ne|d[eé]cor|"
    r"advertising campaign|creative campaign|publicit[eé]|"
    r"brand activation|film publicitaire|"
    r"art direction|direction artistique|"
    r"film|directed by|r[eé]alis[eé] par|"
    r"graphic design|typograph|visual identity|"
    r"identit[eé] visuelle|exhibition design",
    re.I
)

EVIDENCE = re.compile(
    r"design|concep|cr[eé]ation|created|built|"
    r"construi|transform|lighting|lumi[eè]re|"
    r"projection|stage|sc[eè]ne|set design|"
    r"d[eé]cor|costume|material|mat[eé]riau|"
    r"texture|color|colour|couleur|camera|cam[eé]ra|"
    r"cadrage|movement|mouvement|chor[eé]graph|"
    r"montage|rythme|dramaturg|sculpt|spatial|"
    r"espace|[eé]chasse|r[eé]verb[eè]re|"
    r"machinerie|dispositif|fabrication|"
    r"sonor|acoust|animation|mapping|interaction|"
    r"visual|immersif|immersive|performance|"
    r"installation|architecture|composition|"
    r"direction artistique|art direction|"
    r"typograph|identit[eé]|graphique",
    re.I
)

EXCLUSIONS = re.compile(
    r"sag.aftra|unioniz|union recognition|"
    r"collective bargain|labor agreement|"
    r"trade union|syndicat|syndical|"
    r"reconnaissance syndicale|convention collective|"
    r"appointment|appointed|acquires|acquisition|"
    r"product launch|distribution partner|"
    r"playlist|podcast|nominees|new album|"
    r"earnings|hiring|job opening|ranking|"
    r"back[ -]?2[ -]?back|back[ -]?to[ -]?back|"
    r"chacun son tour",
    re.I
)

ANNOUNCEMENTS = re.compile(
    r"\b(announces?|annonce|new album|nouvel album|"
    r"new single|nouveau single|tour dates|"
    r"dates de tourn[eé]e|best songs|"
    r"songs of the week|roundup|"
    r"panorama des singles)\b",
    re.I
)

def editorial_precheck(item):
    title = str(item.get("title") or "")
    summary = str(item.get("summary") or item.get("description") or "")
    content = title + " " + summary

    if EXCLUSIONS.search(title):
        return False, "non_project"
    if ANNOUNCEMENTS.search(title):
        return False, "announcement"
    if not DISCIPLINES.search(content):
        return False, "no_visual_project"
    if not EVIDENCE.search(content):
        return False, "no_creative_evidence"
    return True, "candidate"

def score(item):
    ok, _ = editorial_precheck(item)
    if not ok:
        return -100

    content = (
        str(item.get("title") or "") + " " +
        str(item.get("summary") or item.get("description") or "")
    )
    category = str(item.get("category") or "")[:2]

    result = CATEGORY_PRIORITY.get(category, 40)
    if DISCIPLINES.search(content):
        result += 35
    if EVIDENCE.search(content):
        result += 20
    if item.get("image"):
        result += 10
    result += min(len(content) // 120, 10)
    return result

def reviewed_recently(url):
    record = reviewed.get(url)
    if not record:
        return False
    if not isinstance(record, dict):
        return True

    status = record.get("status", "")
    timestamp = record.get("at", "")
    if not timestamp:
        return False

    try:
        date = datetime.datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )
        if date.tzinfo is None:
            date = date.replace(tzinfo=datetime.timezone.utc)
        age = now - date.astimezone(datetime.timezone.utc)
    except ValueError:
        return False

    if status in ("source_unavailable", "no_image"):
        return age < datetime.timedelta(hours=24)
    return age < datetime.timedelta(days=7)

def article_text(url):
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            raw = response.read(750000).decode("utf-8", "ignore")

        raw = re.sub(
            r"<(script|style|nav|footer|header)[^>]*>[\s\S]*?</\1>",
            " ", raw, flags=re.I
        )
        raw = re.sub(r"<[^>]+>", " ", raw)
        return re.sub(r"\s+", " ", html.unescape(raw)).strip()[:16000]
    except Exception as exc:
        print("Source unavailable:", str(exc)[:150])
        return ""

def source_image(url):
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            markup = response.read(400000).decode("utf-8", "ignore")

        for tag in re.findall(r"<meta\s+[^>]*>", markup, re.I):
            attrs = {
                k.lower(): html.unescape(v)
                for k, v in re.findall(
                    r'([\w:-]+)\s*=\s*["\']([^"\']+)', tag
                )
            }
            if (
                attrs.get("property", "").lower()
                in ("og:image", "og:image:secure_url")
                or attrs.get("name", "").lower() == "twitter:image"
            ):
                image = urllib.parse.urljoin(
                    url, attrs.get("content", "")
                )
                if image.startswith(("http://", "https://")):
                    return image
    except Exception:
        pass
    return ""

def available_gemini_model():
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=100",
        headers={"x-goog-api-key": key}
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        catalog = json.load(response)

    models = [
        m["name"].removeprefix("models/")
        for m in catalog.get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]

    preferred = [
        os.environ.get("RADAR_AI_MODEL", "gemini-3.5-flash-lite"),
        "gemini-3.5-flash-lite",
        "gemini-3-flash",
        "gemini-2.5-flash"
    ]
    model = next((m for m in preferred if m in models), None)
    if not model:
        raise RuntimeError("No compatible Gemini model: " + str(models[:15]))
    print("Gemini model selected:", model)
    return model

def graphic_count_today():
    category_by_url = {
        item.get("url"): str(item.get("category") or "")[:2]
        for item in feed.get("items", [])
    }
    count = 0
    for url, analysis in saved.items():
        if category_by_url.get(url) not in GRAPHIC_CODES:
            continue
        try:
            timestamp = datetime.datetime.fromisoformat(
                analysis["reviewed_at"].replace("Z", "+00:00")
            )
            if timestamp.astimezone(PARIS).date() == today:
                count += 1
        except (KeyError, ValueError, TypeError):
            pass
    return count

graphic_today = graphic_count_today()
reasons = Counter()
by_category = {}
minimum_date = (now - datetime.timedelta(days=14)).date().isoformat()

for item in feed.get("items", []):
    url = item.get("url")
    title = item.get("title")
    category = str(item.get("category") or "")[:2]
    published = str(item.get("published") or "")[:10]

    if not url or not title:
        reasons["missing_title_or_url"] += 1
        continue
    if published < minimum_date:
        reasons["too_old_or_undated"] += 1
        continue
    if url in saved:
        reasons["already_published"] += 1
        continue
    if reviewed_recently(url):
        reasons["recently_reviewed"] += 1
        continue

    ok, reason = editorial_precheck(item)
    if not ok:
        reasons[reason] += 1
        continue

    if score(item) < 100:
        reasons["score_too_low"] += 1
        continue

    by_category.setdefault(category, []).append(item)

for category in by_category:
    by_category[category].sort(
        key=lambda item: (score(item), str(item.get("published") or "")),
        reverse=True
    )

candidates = []
graphic_remaining = max(0, MAX_GRAPHIC_DAILY - graphic_today)

for category in CATEGORY_ORDER + sorted(
    set(by_category) - set(CATEGORY_ORDER)
):
    limit = MAX_PER_CATEGORY
    if category in GRAPHIC_CODES:
        limit = min(limit, graphic_remaining)
    chosen = by_category.get(category, [])[:limit]
    candidates.extend(chosen)
    if category in GRAPHIC_CODES:
        graphic_remaining -= len(chosen)

candidates = candidates[:MAX_API_CALLS]

print("Editorial rejection reasons:", dict(reasons))
print("Eligible by category:", {
    code: len(items) for code, items in by_category.items()
})
print("Editorial priority:", ", ".join(CATEGORY_ORDER[:5]))
print("Editorial shortlist by category:", dict(Counter(
    str(x.get("category") or "")[:2] for x in candidates
)))
print("RADAR candidates:", len(candidates), "existing analyses:", len(saved))

PROMPT = """
Tu es directeur artistique senior, critique visuel et pédagogue.
Analyse exclusivement l'article source fourni, en français.
Réponds uniquement en JSON valide :
{"publish":boolean,"intro":string,"points":[[titre,texte],...],
"takeaway":string,"title_fr":string}

SELECTION :
Le sujet doit être une réalisation créative concrète :
scénographie, spectacle, concert, show TV, clip, danse,
installation, publicité, expérience spatiale ou de marque.
Un projet graphique exceptionnel peut être accepté.
Refuse les simples annonces, classements, portraits,
actualités syndicales et articles sans création analysable.

Publie seulement si la source décrit au moins TROIS décisions
artistiques observables ou explicitement documentées.
Sinon publish=false.

INTRO : 130 à 230 mots. Présente le projet, ses auteurs,
son contexte et son enjeu artistique. Ne répète pas le titre.

POINTS : 4 à 6 analyses approfondies, environ 100 à 160 mots
chacune si la source le permet. Chaque point doit explorer :
1. Un choix créatif concret attesté par la source.
2. Sa logique de conception.
3. Son effet visuel, narratif, sensoriel ou émotionnel plausible.
4. Une tension, contrainte ou alternative, si pertinente.

Privilégie la relation intention → forme → effet produit.
Selon le projet, étudie espace, lumière, matière, couleur,
cadrage, mouvement, son, montage, rythme ou dramaturgie.
N'impose pas une grille identique à tous les projets.

TAKEAWAY : 80 à 130 mots. Formule un enseignement pratique
et transférable en direction artistique, avec ses limites.

RIGUEUR :
Ne fabrique aucun fait, intention d'auteur, chiffre ou
réaction du public. Distingue les faits des interprétations.
N'invente aucune citation d'expert.
Si la source est insuffisante, refuse plutôt que de remplir.
Evite les répétitions entre introduction, points et conclusion.
Ecris avec précision, naturel et lisibilité.
Au plus deux expressions en gras par point.
"""

attempted = 0
accepted = 0
source_fail = 0
api_fail = 0
model = None

if candidates:
    try:
        model = available_gemini_model()
    except Exception as exc:
        print("Gemini configuration error:", str(exc)[:650])
        raise SystemExit(3)

for item in candidates:
    category = str(item.get("category") or "")[:2]
    url = item["url"]

    if category in GRAPHIC_CODES and graphic_today >= MAX_GRAPHIC_DAILY:
        continue

    source = article_text(url)
    if len(source) < 850:
        source_fail += 1
        reviewed[url] = {
            "status": "source_unavailable",
            "at": now.isoformat()
        }
        print("Skip: insufficient source:", item["title"])
        continue

    attempted += 1

    payload = {
        "system_instruction": {
            "parts": [{"text": PROMPT}]
        },
        "contents": [{
            "role": "user",
            "parts": [{
                "text": json.dumps({
                    "title": item["title"],
                    "url": url,
                    "source_text": source
                }, ensure_ascii=False)
            }]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    try:
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + urllib.parse.quote(model, safe="")
            + ":generateContent"
        )
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-goog-api-key": key,
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=65) as response:
            answer = json.load(response)

        raw = "".join(
            p.get("text", "")
            for p in answer["candidates"][0]["content"]["parts"]
        )
        analysis = json.loads(raw)
        points = analysis.get("points", [])

        valid = (
            analysis.get("publish") is True
            and isinstance(points, list)
            and 4 <= len(points) <= 6
            and all(
                isinstance(p, list)
                and len(p) == 2
                and isinstance(p[1], str)
                and len(p[1]) >= 300
                for p in points
            )
            and len(analysis.get("intro", "")) >= 400
            and len(analysis.get("takeaway", "")) >= 250
        )

        if not valid:
            reviewed[url] = {
                "status": "editorial_rejected",
                "at": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat()
            }
            print("Editorial rejected:", item["title"])
            continue

        if not item.get("image"):
            item["image"] = source_image(url)

        if not item.get("image"):
            reviewed[url] = {
                "status": "no_image",
                "at": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat()
            }
            print("Editorial withheld: missing image:", item["title"])
            continue

        timestamp = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()

        saved[url] = {
            "intro": analysis["intro"],
            "points": points,
            "takeaway": analysis["takeaway"],
            "title_fr": analysis.get("title_fr", ""),
            "reviewed_at": timestamp,
            "source_url": url
        }

        if len(analysis.get("title_fr", "")) >= 12:
            item["title_fr"] = analysis["title_fr"]

        accepted += 1
        if category in GRAPHIC_CODES:
            graphic_today += 1

        print("Editorial accepted:", item["title"])

    except urllib.error.HTTPError as exc:
        api_fail += 1
        details = exc.read(1500).decode("utf-8", "replace")
        print("Gemini HTTP error:", exc.code, details[:650])
        if exc.code in (400, 401, 403, 404, 429):
            break

    except Exception as exc:
        api_fail += 1
        print("Analysis failed:", url, str(exc)[:250])

review_path.write_text(
    json.dumps(reviewed, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8"
)
out_path.write_text(
    json.dumps(saved, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8"
)
feed_path.write_text(
    json.dumps(feed, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8"
)

print("Total AI editorials:", len(saved))
print(
    "RADAR summary: attempted=%d accepted=%d "
    "source_unavailable=%d api_errors=%d"
    % (attempted, accepted, source_fail, api_fail)
)

if api_fail:
    sys.exit(3)
