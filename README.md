# STORYBOARD / RADAR DA

Site statique responsive, construit à partir du classeur de veille DA 2026 (168 URL distinctes, 13 pôles). L'interface sépare **publications repérées** et **analyses pédagogiques**. Aucune intention d'artiste ni citation d'expert n'est inventée.

## Tester localement

```bash
python -m http.server 8000
```

Ouvrir http://localhost:8000.

## Déployer et automatiser

GitHub Pages publie la racine de la branche `main`. Le workflow `radar-source-collector.yml` exécute la collecte, la présélection et l’inspection à quatre créneaux UTC et peut être lancé manuellement. Les rapports portent le même identifiant de vague et sont disponibles dans les artefacts de l’exécution. La collecte ne publie aucune fiche.

Pour publier, appliquer le barème et la seconde lecture définis dans `AGENTS.md`. Dans chaque clone, activer le contrôle avec `git config core.hooksPath .githooks`. Consigner un `project_id` stable dans le flux et le registre, puis joindre à l’analyse `publication_review` avec `scores` (choice, effect, lesson, evidence, freshness), `choice`, `effect`, `lesson`, `second_reading` et `sources` (url, opened_at, locator). Les repères `editorial_review` restent obligatoires. Valider les fichiers, puis vérifier la version servie par Pages.

```bash
node scripts/validate-radar.cjs
node scripts/validate-radar.mjs
node scripts/validate-publication.cjs origin/main HEAD
python test_editorial.py
```
