# RADAR DA — architecture opérationnelle (2026-11-13)

**Référence de décision obligatoire : [PUBLICATION_SCORECARD.md](PUBLICATION_SCORECARD.md).** Toute publication doit franchir le barème /20 et les conditions visuelles, avec une image dans le flux et un repli contextuel ou illustré.

## Finalité
Veille créative publique qui explique les partis pris de direction artistique de projets récents : concerts, clips, shows TV, spectacles, théâtre, performances, installations et lancements scénographiés. Une fiche doit faire voir un choix, son effet, et une leçon de DA. Pas de remplissage.

## Chaîne de production
1. **Collecte technique indépendante** — GitHub Actions `.github/workflows/radar-source-collector.yml`, quatre déclenchements quotidiens + déclenchement sur changement du pipeline. Exécute `scripts/collect_sources.py`. Charge 182 références, ouvre les pages en parallèle et journalise succès, erreurs et URLs dans `data/source-coverage.json`. Ne pas confondre 182 tentatives et 182 réussites.
2. **Découverte** — `data/source-discoveries.json` reçoit des liens extraits, sans présumer leur fraîcheur, leur qualité ni leurs droits. Le collecteur suit les liens relatifs et absolus. Instagram exclu ; LinkedIn non requis.
3. **Priorisation** — `scripts/radar_pipeline.py` classe les liens selon les secteurs DA et la probabilité d'une page-projet, filtre bruit et doublons URL, limite le poids d'un même domaine et conserve `data/editorial-shortlist.json`. Ce classement est un *signal de recherche*, pas une validation.
4. **Édition humaine/assistée** — consulter la shortlist ET prospecter directement les sorties récentes non couvertes, notamment les clips du vendredi. Vérifier date réelle, source primaire, observation visuelle, intérêt DA, recoupement utile, identité de projet et historique. Rédiger en français direct avec **L'essentiel / Intention / Idée & DA / Pour un DA**. Intention hypothétique explicitement signalée.
5. **Images** — Chaque nouvelle fiche doit afficher une image dans le flux. Chercher d’abord un visuel du projet, puis croiser les sources (artiste, studio, production, presse, photographe) pour trouver une image pertinente et réutilisable. Si aucun visuel du projet n’est exploitable, utiliser un visuel contextuel réutilisable qui éclaire le choix DA ou créer une illustration éditoriale cohérente. Légender et créditer ces visuels sur la carte. Le bouton « Visuels du projet » complète l’image de la carte. Si aucun visuel ne peut être produit et vérifié, la fiche reste en attente.
6. **Publication** — seules les fiches validées passent dans `data/feed.json`, `data/analyses.json`, `data/published-projects.json`, avec SHA frais et relecture. `data/editorial-queue.json` reste la mémoire des incomplets. Aucune écriture automatique de liens bruts dans le flux public.
7. **Contrôle** — comparer commits, données relues, rendu GitHub Pages, images et lien source. Déclarer séparément publications et collecte.

## Priorités d'exécution
- Première priorité : un projet récent avec une décision visuelle intéressante et démontrable.
- Deuxième : couverture diversifiée des clips, concerts, TV, théâtre et scénographie.
- Troisième : quantité. Viser 3–7 nouvelles analyses par vague, sans fausses découvertes.
- 100 ouvertures de sites par vague : objectif de couverture **technique** mesuré par audit, pas condition préalable pour publier une fiche validée. Signaler explicitement les échecs.
- Les 182 sources ne constituent pas une frontière : la découverte peut élargir librement à des sources fiables.
- Ne jamais republier un ancien projet reconditionné en actualité.
- Pas de quota ni rubrique Instagram/LinkedIn.
- Ne pas modifier `index.html` ni service worker pendant les veilles.

## Diagnostic et indicateurs
- `data/source-coverage.json` : nombre tenté, nombre ouvert, erreurs et URL par URL.
- `data/source-discoveries.json` : liens bruts non vérifiés.
- `data/editorial-shortlist.json` : liens prioritaires, score de prospection seulement.
- `data/editorial-queue.json` : candidats en cours, obstacles et reprises.
- `data/feed.json` + `data/analyses.json` + `data/published-projects.json` : publications vérifiées.
- Si aucune nouvelle fiche : rapporter 0, la raison et la correction.
- Si une exécution GitHub Actions échoue : lire le journal, corriger la cause, relancer ; ne pas déclarer le système opérationnel sur la seule présence du YAML.

## Limite de cette mise en place
Le workflow technique de collecte et de présélection est créé dans GitHub. Son premier run doit être vérifié dans Actions. L'étape de jugement éditorial et de publication contrôlée reste prise en charge par les vagues d'assistant ; aucun modèle ne doit publier des découvertes non validées.
