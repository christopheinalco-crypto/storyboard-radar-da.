# STORYBOARD / RADAR DA

Site statique responsive, construit à partir du classeur de veille DA 2026 (168 URL distinctes, 13 pôles). L'interface sépare **publications repérées** et **analyses pédagogiques**. Aucune intention d'artiste ni citation d'expert n'est inventée.

## Tester localement

```bash
python -m http.server 8000
```

Ouvrir http://localhost:8000.

## Déployer et automatiser

1. Créer un dépôt GitHub et y déposer **tout** le dossier (y compris `.github/workflows/veille.yml`).
2. Dans Settings > Pages, publier depuis la branche principale, racine `/`.
3. Dans Actions > Actualiser la veille, lancer `Run workflow` pour une première collecte. La tâche se répète ensuite chaque jour à 07:20 UTC (planification GitHub approximative, peut être retardée).
4. L'URL GitHub Pages est partageable. Les nouvelles publications sont visibles par tous après la mise à jour du fichier `data/feed.json` et le déploiement Pages.

**Attention** : seuls les flux RSS/Atom détectables des sources P1 sont récupérés automatiquement. Certains sites ne proposent pas de flux, bloquent les robots ou exigent un accès payant. Les éléments collectés sont des titres, extraits et liens : ils ne sont **pas** des analyses DA validées. L'interface n'invente ni visuels protégés, ni citations, ni résultats de campagne. La couche d'analyse approfondie requiert une étape éditoriale supplémentaire et éventuellement un backend IA avec clé API.

Le fichier `data/sources.json` contient le répertoire importé, avec priorités et intérêt DA. La méthode de lecture par calques figure dans l'onglet « L'œil du DA ».
