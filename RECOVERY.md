# RADAR DA — reprise après incident

## Surveillance
Le workflow `.github/workflows/integrity.yml` contrôle les fichiers après chaque modification des données, à intervalles réguliers et sur lancement manuel. Il conserve un instantané des trois JSON en artefact GitHub Actions pendant 30 jours. En cas d'erreur de structure, le workflow échoue et crée ou actualise une issue « RADAR DA — alerte intégrité des données ». Les notifications GitHub dépendent des réglages du compte.

## Si une veille ne publie rien
1. Lire le résultat de l'automatisation « Veilles RADAR DA » et le dernier journal du workflow « RADAR DA — integrity audit ».
2. Vérifier les trois fichiers `data/feed.json`, `data/analyses.json`, `data/social-posts.json` et le dernier commit.
3. Si la collecte est simplement vide, ne rien restaurer : chercher des sources supplémentaires lors de la prochaine vague ou relancer manuellement une collecte en dédupliquant les URL.
4. Si le JSON est cassé, ne pas relancer de publication avant correction.

## Restauration
1. Ouvrir GitHub > Actions > RADAR DA — integrity audit > dernière exécution saine > Artifacts > `radar-data-...`, ou choisir un commit sain dans l'historique du dépôt.
2. Comparer les données saines aux données actuelles. Préserver tous les articles valides apparus depuis l'instantané.
3. Restaurer uniquement les entrées endommagées, avec les SHA actuels des fichiers ; ne jamais écraser les trois fichiers en bloc sans comparaison.
4. Lancer manuellement le workflow d'intégrité ; vérifier les nombres, les liens entre articles et analyses, puis contrôler l'affichage du site.
5. Consigner la cause et la correction dans l'issue d'alerte ; fermer l'issue seulement après vérification.

## Limites
- Les contrôles de structure ne prouvent pas que chaque image externe s'affiche, que chaque source reste accessible, ou que l'interface fonctionne sur tous les mobiles.
- Un artefact de 30 jours n'est pas une sauvegarde hors GitHub ; l'historique Git conserve les versions commitées tant qu'elles restent accessibles.
- La création d'issues dépend des autorisations GitHub Actions et de l'activation des issues dans le dépôt.
- Le workflow de contrôle ne répare ni ne republie automatiquement : toute restauration est volontaire pour éviter les pertes.
- En cas d'échec d'infrastructure GitHub, les contrôles peuvent eux-mêmes ne pas s'exécuter ; les notifications ne sont pas garanties.
