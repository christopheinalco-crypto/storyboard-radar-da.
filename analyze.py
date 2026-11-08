
"""RADAR DA — sélection, analyse Gemini et publication."""
import os
import json
import re
import html
import sys
import time
import datetime
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from collections import Counter
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
FEED = ROOT / "data/feed.json"
OUTPUT = ROOT / "data/analyses.json"
REVIEWED = ROOT / "data/reviewed.json"

def load(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

feed = load(FEED)
saved = load(OUTPUT)
reviewed = load(REVIEWED)

if not isinstance(saved, dict) or not isinstance(reviewed, dict):
    sys.exit("Invalid existing analysis/reviewed data")

key = os.environ.get("GEMINI_API_KEY", "")
if not key:
    sys.exit("ERROR: GEMINI_API_KEY missing")

PARIS = ZoneInfo("Europe/Paris")
now = datetime.datetime.now(datetime.timezone.utc)
today = now.astimezone(PARIS).date()

MAX_API_CALLS = min(
    15, max(0, int(os.environ.get("RADAR_MAX_AI_CALLS", "15")))
)
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

# Exclusion permanente des séries de prix et palmarès sans projet analysable.
BLOCKED_STORIES = re.compile(
    r"acetyl[eè]ne|prix.de.la.conception.lumi[eè]re|prix.de.l.imaginaire.lumi[eè]re",
    re.I
)

def editorial_precheck(item):
    title = str(item.get("title") or "")
    summary = str(
        item.get("summary") or item.get("description") or ""
    )
    content = title + " " + summary

    # Expositions historiques sans dispositif scénique ou expérience spatiale analysable.
    if "fondazione prada" in content.lower() and "global antiquity" in content.lower():
        return False, "off_topic_historical_exhibition"
    if BLOCKED_STORIES.search(content + " " + str(item.get("url") or "")):
        return False, "duplicate_awards_story"
    if EXCLUSIONS.search(title):
        return False, "non_project"
    if ANNOUNCEMENTS.search(title):
        return False, "announcement"
    # La catégorie de source est un indice, pas une preuve : Gemini vérifie le projet.
    priority = str(item.get("category") or "")[:2] in {"01", "02", "14", "15", "09"}
    if not DISCIPLINES.search(content) and not (priority and item.get("image")):
        return False, "no_visual_project"
    if not EVIDENCE.search(content) and not (priority and item.get("image")):
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
    except (ValueError, TypeError):
        return False

    if record.get("status") in (
        "source_unavailable", "no_image", "json_invalid", "format_invalid"
    ):
        return age < datetime.timedelta(hours=24)

    return age < datetime.timedelta(days=7)

def mark_reviewed(url, status):
    reviewed[url] = {
        "status": status,
        "at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    }

def article_text(url):
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read(750000).decode(
                "utf-8", "ignore"
            )

        raw = re.sub(
            r"<(script|style|nav|footer|header)[^>]*>"
            r"[\s\S]*?</\1>",
            " ", raw, flags=re.I
        )
        raw = re.sub(r"<[^>]+>", " ", raw)
        return re.sub(
            r"\s+", " ", html.unescape(raw)
        ).strip()[:16000]

    except Exception as exc:
        print("Source unavailable:", str(exc)[:150])
        return ""

def source_image(url):
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            markup = response.read(400000).decode(
                "utf-8", "ignore"
            )

        for tag in re.findall(
            r"<meta\s+[^>]*>", markup, re.I
        ):
            attrs = {
                k.lower(): html.unescape(v)
                for k, v in re.findall(
                    r'([\w:-]+)\s*=\s*["\']([^"\']+)', tag
                )
            }
            if (
                attrs.get("property", "").lower()
                in ("og:image", "og:image:secure_url")
                or attrs.get("name", "").lower()
                == "twitter:image"
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
    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/"
        "v1beta/models?pageSize=100",
        headers={"x-goog-api-key": key}
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        catalog = json.load(response)

    models = [
        m["name"].removeprefix("models/")
        for m in catalog.get("models", [])
        if "generateContent" in m.get(
            "supportedGenerationMethods", []
        )
    ]

    preferred = [
        os.environ.get(
            "RADAR_AI_MODEL", "gemini-3.5-flash-lite"
        ),
        "gemini-3.5-flash-lite",
        "gemini-3-flash",
        "gemini-2.5-flash"
    ]

    model = next(
        (m for m in preferred if m in models), None
    )
    if not model:
        raise RuntimeError(
            "No compatible Gemini model: " + str(models[:15])
        )
    print("Gemini model selected:", model)
    return model

def graphic_count_today():
    category_by_url = {
        item.get("url"):
        str(item.get("category") or "")[:2]
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
minimum_date = (
    now - datetime.timedelta(days=14)
).date().isoformat()

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

    if score(item) < 65:
        reasons["score_too_low"] += 1
        continue

    by_category.setdefault(category, []).append(item)

for category in by_category:
    by_category[category].sort(
        key=lambda item: (
            score(item), str(item.get("published") or "")
        ),
        reverse=True
    )

candidates = []
graphic_remaining = max(
    0, MAX_GRAPHIC_DAILY - graphic_today
)

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
    code: len(items)
    for code, items in by_category.items()
})
print("Editorial priority:", ", ".join(CATEGORY_ORDER[:5]))
print("Editorial shortlist by category:", dict(Counter(
    str(item.get("category") or "")[:2]
    for item in candidates
)))
print(
    "RADAR candidates:", len(candidates),
    "existing analyses:", len(saved)
)

PROMPT = """
Tu es directeur artistique senior, critique visuel et pédagogue.
Analyse exclusivement l'article source fourni, en français.

Réponds UNIQUEMENT en JSON valide, sans Markdown :
{
 "publish": true,
 "intro": "texte",
 "points": [["titre 1", "texte 1"], ["titre 2", "texte 2"], ["titre 3", "texte 3"]],
 "takeaway": "texte",
 "title_fr": "titre français"
}

SELECTION ET PRIORITÉS :
Priorité forte : clips musicaux avec mise en scène ou univers visuel,
concerts, spectacles, scénographies, shows TV, lancements majeurs
de produits et événements de marque avec set design documenté.
Autres disciplines uniquement si elles apportent un enseignement
concret et transposable à la direction artistique.
Ne publie pas une exposition d'objets historiques, un simple événement,
une annonce ou un projet seulement parce qu'il est visuellement joli.
Refuse les classements, portraits, communiqués et sujets sans matière.
Publie seulement si l'article contient des faits de conception
vérifiables : choix de forme, espace, lumière, image, matière,
mouvement, mise en scène, production ou contraintes.

INTRO :
60 à 95 mots. Identifier le projet, les auteurs/prestataires
nommés dans la source, le lieu, le public et l'enjeu concret.
Ne rien inventer. Ne répète pas le titre.

POINTS :
Trois sections précises de 45 à 85 mots chacune,
avec ces titres EXACTS :
1. "Le sujet" : faits vérifiables, intervenants, dispositifs,
dimensions, technologies et contraintes uniquement si documentés.
2. Choisir un titre adapté à la nature du projet :
"L'insight" UNIQUEMENT lorsqu'un besoin, comportement ou tension
réelle du public ou des usagers est documenté par la source.
Sinon, "Le problème créatif", "L'enjeu de conception"
ou "Le parti pris artistique", selon les faits disponibles.
Un problème technique, une intention esthétique ou une hypothèse
personnelle ne sont PAS automatiquement des insights.
Distinguer explicitement le constat attesté et l'interprétation.
3. "L'idée et la DA" : expliquer précisément comment la forme,
le set design, la lumière, le mouvement ou les images répondent
à l'enjeu identifié, avec leurs effets possibles et limites.
Chaque section s'appuie sur des détails précis de la source.
Privilégie la chaîne enjeu → décision créative → effet plausible,
et seulement lorsque c'est justifié, besoin public → insight → DA.
Ne jamais inventer une motivation, une étude du public ou
une intention du créateur pour remplir une rubrique.
N'écris jamais de phrases génériques sur l'immersion, l'émotion
ou la créativité sans démonstration concrète.

TAKEAWAY :
50 à 85 mots, intitulé "Pour un DA" dans le texte.
Extraire 1 ou 2 principes transférables, donner un exemple
d'application dans un autre contexte, un exercice pratique
et une limite technique ou artistique si documentée.

STYLE ET LISIBILITÉ — OBLIGATOIRE :
Écris comme un excellent mentor DA, pas comme un communiqué de presse.
Français simple, précis, vivant et professionnel. Une idée par phrase.
Phrases courtes (idéalement 10 à 20 mots), paragraphes respirants.
Commence par le fait concret, puis explique le choix et l'effet possible.
Évite les formules abstraites et ampoulées ("instabilité contemplative",
"registre d'authentique vulnérabilité", "désamorce toute distance formelle",
"insuffle une matérialité", "immersion émotionnelle").
Préférer "les contours bougent, ce qui évoque une marche hésitante"
à une phrase abstraite sur "la traduction de la flânerie".
Ne pas empiler les adjectifs, les métaphores ou les synonymes.
Ne répète jamais le titre, un fait ou une conclusion d'une section à l'autre.
Évite le remplissage : chaque phrase doit apporter un fait,
un raisonnement ou une application.
Au maximum une expression en **gras** par section, jamais
de gras sur une phrase entière. Ne pas utiliser de puces dans
le texte d'un point : l'interface ajoute déjà ses propres puces.
Ne pas confondre hypothèse sur l'effet et résultat démontré.
La profondeur vient des preuves et de la logique, pas de la longueur.

RIGUEUR :
Ne fabrique aucun fait, intention d'auteur, chiffre ou
réaction du public. Distingue faits et interprétations.
N'invente aucune citation d'expert.
Si la source est insuffisante, refuse plutôt que de remplir.
Evite les répétitions entre introduction, points et conclusion.
STYLE EDITORIAL IMPERATIF :
Ecris comme un décryptage DA captivant destiné à des créatifs, pas comme une fiche de lecture.
Entre directement dans le projet, par une décision visuelle, une tension ou un effet concret.
INTERDIT : « l'article dit », « l'article explique », « selon l'article »,
« la source présente », « le texte évoque », « on peut constater que »,
« il est intéressant de noter que », ou toute formule de commentaire de source.
Titres de points courts, évocateurs et précis. Verbes actifs, phrases naturelles.
Montre ce que le dispositif fait voir, ressentir ou comprendre et pourquoi c'est utile pour notre pratique.
Aucune accroche artificielle, aucun enthousiasme creux, aucun effet inventé.
Les faits doivent toujours être vérifiables dans la source, même sans la citer dans chaque phrase.
Ecris avec précision, naturel et lisibilité.
Au plus deux expressions en gras par point.

TECHNIQUE :
Le JSON doit être syntaxiquement valide.
Echappe correctement les guillemets et caractères spéciaux.
Ne termine jamais une chaîne ou un tableau prématurément.
"""

def call_gemini(model, item, source, retry=False):
    instructions = PROMPT
    if retry:
        instructions += (
            "\nIMPORTANT : la réponse précédente était "
            "un JSON invalide. Génère une réponse complète "
            "et syntaxiquement valide. Réduis légèrement "
            "la longueur si nécessaire, sans inventer de faits."
        )

    payload = {
        "system_instruction": {
            "parts": [{"text": instructions}]
        },
        "contents": [{
            "role": "user",
            "parts": [{
                "text": json.dumps({
                    "title": item["title"],
                    "url": item["url"],
                    "source_text": source
                }, ensure_ascii=False)
            }]
        }],
        "generationConfig": {
            "temperature": 0.15,
            "responseMimeType": "application/json",
            "maxOutputTokens": 8192
        }
    }

    endpoint = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/"
        + urllib.parse.quote(model, safe="")
        + ":generateContent"
    )

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-goog-api-key": key,
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=90) as response:
        answer = json.load(response)

    raw = "".join(
        part.get("text", "")
        for part in answer["candidates"][0]["content"]["parts"]
    )

    return json.loads(raw)

attempted = 0
accepted = 0
source_fail = 0
api_fail = 0
json_fail = 0
rejected = 0
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

    if (
        category in GRAPHIC_CODES
        and graphic_today >= MAX_GRAPHIC_DAILY
    ):
        continue

    source = article_text(url)
    if len(source) < 850:
        source_fail += 1
        mark_reviewed(url, "source_unavailable")
        print("Skip: insufficient source:", item["title"])
        continue

    attempted += 1
    analysis = None

    for attempt in range(2):
        try:
            analysis = call_gemini(
                model, item, source, retry=(attempt == 1)
            )
            break

        except json.JSONDecodeError as exc:
            print(
                "Gemini JSON invalid:",
                item["title"],
                "attempt:", attempt + 1,
                "error:", str(exc)[:180]
            )
            if attempt == 1:
                json_fail += 1
                mark_reviewed(url, "json_invalid")

        except urllib.error.HTTPError as exc:
            details = exc.read(1200).decode(
                "utf-8", "replace"
            )
            print(
                "Gemini HTTP error:",
                exc.code, details[:500]
            )
            if exc.code in (429, 500, 502, 503):
                if attempt == 0:
                    time.sleep(3)
                    continue
            api_fail += 1
            break

        except Exception as exc:
            print(
                "Gemini analysis error:",
                item["title"], str(exc)[:250]
            )
            api_fail += 1
            break

    if analysis is None:
        continue

    if not isinstance(analysis, dict):
        rejected += 1
        mark_reviewed(url, "editorial_rejected")
        continue

    points = analysis.get("points", [])
    intro = analysis.get("intro", "")
    takeaway = analysis.get("takeaway", "")

    valid = (
        analysis.get("publish") is True
        and isinstance(points, list)
        and len(points) == 3
        and all(
            isinstance(point, list)
            and len(point) == 2
            and isinstance(point[0], str)
            and isinstance(point[1], str)
            and len(point[1]) >= 100
            for point in points
        )
        and isinstance(intro, str)
        and len(intro) >= 90
        and isinstance(takeaway, str)
        and len(takeaway) >= 65
    )

    if not valid:
        rejected += 1
        mark_reviewed(url, "format_invalid" if analysis.get("publish") is True else "editorial_rejected")
        print("Editorial rejected:", item["title"])
        continue

    if not item.get("image"):
        item["image"] = source_image(url)

    if not item.get("image"):
        mark_reviewed(url, "no_image")
        print(
            "Editorial withheld: missing image:",
            item["title"]
        )
        continue

    timestamp = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()

    saved[url] = {
        "intro": intro,
        "points": points,
        "takeaway": takeaway,
        "title_fr": analysis.get("title_fr", ""),
        "reviewed_at": timestamp,
        "source_url": url
    }

    title_fr = analysis.get("title_fr", "")
    if isinstance(title_fr, str) and len(title_fr) >= 12:
        item["title_fr"] = title_fr

    accepted += 1

    if category in GRAPHIC_CODES:
        graphic_today += 1

    print("Editorial accepted:", item["title"])

    # Conserver les analyses acceptées même si un
    # article suivant rencontre une erreur.
    save(OUTPUT, saved)

save(REVIEWED, reviewed)
save(OUTPUT, saved)
save(FEED, feed)

print("Total AI editorials:", len(saved))
print(
    "RADAR summary: attempted=%d accepted=%d "
    "source_unavailable=%d api_errors=%d "
    "json_errors=%d editorial_rejected=%d"
    % (
        attempted, accepted, source_fail,
        api_fail, json_fail, rejected
    )
)

# Une erreur sur un article isolé n'interrompt
# plus l'ensemble du workflow.
# Les erreurs restent visibles dans les journaux.
