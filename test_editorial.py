
"""Tests du filtre éditorial RADAR, sans appel à Gemini."""

import ast
import pathlib
import re

source = pathlib.Path(__file__).with_name("analyze.py").read_text(
    encoding="utf-8"
)
tree = ast.parse(source)

# Charger les constantes et fonctions nécessaires au filtre.
wanted = {
    "DISCIPLINES",
    "EVIDENCE",
    "EXCLUSIONS",
    "ANNOUNCEMENTS",
    "BLOCKED_STORIES",
    "RADAR_ALLOWED_CATEGORIES",
    "RADAR_PROJECT",
    "RADAR_OFFTOPIC",
    "editorial_precheck",
}

nodes = []

for node in tree.body:
    if isinstance(node, ast.Assign):
        names = [
            target.id
            for target in node.targets
            if isinstance(target, ast.Name)
        ]
        if any(name in wanted for name in names):
            nodes.append(node)

    elif isinstance(node, ast.FunctionDef):
        if node.name in {"editorial_precheck", "radar_in_scope"}:
            nodes.append(node)

namespace = {"re": re}

exec(
    compile(
        ast.Module(body=nodes, type_ignores=[]),
        "analyze.py",
        "exec",
    ),
    namespace,
)

check = namespace["editorial_precheck"]

cases = [
    (
        "DJ magazine",
        {
            "title": "Magazine : Back2Back, chacun son tour",
            "category": "14 Musique Clips",
            "summary": "DJ festivals and music performance",
        },
        False,
    ),
    (
        "Palmares lumiere exclu",
        {"title": "Prix de la conception lumière Acétylène", "category": "01 Spectacle Concert", "summary": "Lighting design"},
        False,
    ),
    (
        "Graphisme creatif",
        {
            "title": "New graphic identity with typographic design",
            "category": "03 DA Graphisme",
            "summary": "A studio creates a visual identity",
        },
        False,
    ),
    (
        "Tour announcement",
        {
            "title": "Singer announces new tour dates",
            "category": "14 Musique Clips",
            "summary": "Tickets go on sale tomorrow",
        },
        False,
    ),
    (
        "Music roundup",
        {
            "title": "Best songs of the week",
            "category": "14 Musique Clips",
            "summary": "A selection of new singles",
        },
        False,
    ),
    (
        "Stage design",
        {
            "title": "Stage design for the Aurora concert",
            "category": "01 Spectacle Concert",
            "summary": "Moving lights, sculptural set and projection mapping",
        },
        True,
    ),
    (
        "Broadcast set",
        {
            "title": "Broadcast set design for a new TV show",
            "category": "02 TV Broadcast",
            "summary": "Modular structures and spatial lighting",
        },
        True,
    ),
    (
        "Music video",
        {
            "title": "Music video directed by Ana Silva",
            "category": "14 Musique Clips",
            "summary": "Choreographed camera movement and colored lighting",
        },
        True,
    ),
    (
        "Scenographie francaise",
        {
            "title": "Une scenographie de spectacle immersif",
            "category": "09 France Pro",
            "summary": "Creation d'un dispositif avec lumiere et espace",
        },
        True,
    ),
]

failed = 0

for name, item, expected in cases:
    accepted, reason = check(item)
    passed = accepted == expected

    print(
        f'{"PASS" if passed else "FAIL"}: '
        f"{name} => {accepted} ({reason})"
    )

    if not passed:
        failed += 1

if failed:
    raise SystemExit(f"{failed} editorial checks failed")

print(
    f"Editorial gate: {len(cases)} checks passed. "
    "Gemini calls: 0."
)
