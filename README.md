# STORYBOARD / RADAR DA

Site statique responsive, construit à partir du classeur de veille DA 2026. Le catalogue courant contient 182 sources dans `data/sources.json`. L'interface sépare **publications repérées** et **analyses pédagogiques**. Aucune intention d'artiste ni citation d'expert n'est inventée.

## Tester localement

```bash
python -m http.server 8000
```

Ouvrir http://localhost:8000.

## Déployer et automatiser

GitHub Pages publie la racine de la branche `main`. Les collectes commencent à 6 h, 12 h, 16 h et 20 h dans le fuseau `Europe/Paris`. Les balayages complémentaires démarrent cinq et quinze minutes après chaque créneau. Les travaux de collecte produisent les rapports utilisés par la veille éditoriale ChatGPT.

Pour reprendre la collecte des sources après un échec, relancer la même exécution GitHub Actions. Le workflow récupère le dernier point de reprise disponible et ouvre les sources restantes. Les rapports conservent l’identifiant de l’exécution.

Le workflow `radar-public-render.yml` ouvre le site public après les changements du flux, des analyses ou de l’interface. Il compare les cartes affichées avec le flux versionné, vérifie qu’une idée conservée laisse la fiche visible, et contrôle le chargement des images et l’ouverture du décryptage pour les fiches ajoutées ou dont l’image a changé. Il réessaie pendant le déploiement Pages et conserve des captures dans ses artefacts.

Pour publier, appliquer le barème et la seconde lecture définis dans `AGENTS.md`. Dans chaque clone, activer le contrôle avec `git config core.hooksPath .githooks`. Consigner un `project_id` stable dans le flux et le registre, puis joindre à l’analyse `publication_review` avec `scores` (choice, effect, lesson, evidence, freshness), `choice`, `effect`, `lesson`, `second_reading` et `sources` (url, opened_at, locator). Les repères `editorial_review` restent obligatoires. Valider les fichiers, puis vérifier la version servie par Pages.

```bash
node scripts/validate-radar.cjs
node scripts/validate-radar.mjs
node scripts/validate-publication.cjs origin/main HEAD
python test_editorial.py
```
