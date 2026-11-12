# RADAR DA — Audit opérationnel de la veille sociale (12 novembre 2026)

## État constaté dans le dépôt
- Répertoire : `data/social_watchlist.json`, version 2.
- 100 pistes nommées : 50 LinkedIn, 50 Instagram.
- 15 profils avec URL renseignée ; 85 sans URL.
- Les statuts « verified » ne prouvent pas que les publications récentes sont récupérables.
- `data/feed.json` contient 33 fiches à la date du contrôle. Deux fiches mentionnent LinkedIn dans leurs métadonnées, mais aucune garantie d'une collecte de trois posts sociaux par vague.
- `.github/workflows/veille.yml` est suspendu et ne collecte ni ne publie de contenu.
- Aucun changement du site ou des données de veille n'est autorisé par cet audit.

## Ordre des opérations
1. Compléter les 85 URL de profils par des liens de comptes réels, vérifiés depuis les sites officiels ou les plateformes ; ne pas fabriquer de handle.
2. Pour chaque profil, conserver plateforme, URL, date de contrôle, dernière publication pertinente accessible, lien direct vers le post et statut d'accès.
3. Marquer séparément : profil identifié / activité récente constatée / posts accessibles / post qualifié / publié. Un profil identifié n'est pas une source opérationnelle.
4. Rechercher prioritairement concerts et tournées, clips, spectacles, scénographies, lancements de grande ampleur, shows TV.
5. Croiser chaque post candidat avec une source complémentaire indépendante, une image authentique du projet et un détail de DA vérifiable.
6. Dédupliquer par projet avec `data/feed.json` et `data/analyses.json`. Ne jamais effacer une fiche existante pour remplir un quota.
7. Viser trois publications sociales distinctes par vague, sans inventer ni publier de fiche faible pour atteindre le nombre.
8. Après validation, écrire seulement les données nécessaires, puis vérifier les SHA et le site public. Les automatisations ChatGPT sont distinctes du workflow GitHub suspendu.

## Critères de validation
- 50 profils LinkedIn et 50 profils Instagram avec liens vérifiables.
- Pour chaque compte déclaré « actif », au moins une publication récente datée et accessible.
- Pour chaque fiche publiée, URL du post, source de recoupement, visuel pertinent, décryptage DA, absence de doublon.
- Un test réel de vague documente le nombre de candidats, rejets, publications, erreurs d'accès et déploiement.
- Aucun statut « opérationnel » tant que le test de bout en bout n'est pas passé.
