# RADAR DA — Point de restauration stable (11 novembre 2026)

## Référence immuable

- Dépôt exact : `christopheinalco-crypto/storyboard-radar-da.` (le point final fait partie du nom).
- Branche de sauvegarde : `backup/radar-da-stable-2026-11-11`.
- Commit de référence : `a80463ff8a6838b51aa92aff6ca5150e050b8cb5`.
- URL : https://github.com/christopheinalco-crypto/storyboard-radar-da./tree/backup/radar-da-stable-2026-11-11
- Site : https://christopheinalco-crypto.github.io/storyboard-radar-da./

## Ce qui est préservé

La branche contient une copie Git complète de tous les fichiers suivis au commit de référence, notamment l'interface `index.html`, les fichiers `data/feed.json`, `data/analyses.json`, `data/published-projects.json`, les règles éditoriales et les autres fichiers du site. Elle est indépendante des futurs commits de la branche principale.

## Garde-fous pour les prochaines interventions

1. **Ne jamais modifier cette branche de sauvegarde.** Créer un nouveau point de restauration daté pour chaque nouvel état stable validé.
2. **Avant une modification :** relever le commit HEAD et lire les versions actuelles des fichiers concernés ; ne jamais remplacer des fichiers à partir d'une version ancienne.
3. **Veille ordinaire :** ne modifier que les données nécessaires à la publication (flux, analyses, index anti-doublons) ; ne pas toucher à `index.html`, aux boutons, au menu, au décryptage, aux styles ou à la navigation.
4. **Éditorial :** 5 à 7 nouveaux projets par vague test (5 minimum), priorité concerts, spectacles, clips, shows TV, scénographie, set design et lancements/expériences de marque ; au plus 1 à 2 projets secondaires. Explorer également LinkedIn et Instagram et recouper les posts.
5. **Qualité :** chaque projet doit avoir une image authentique, pertinente, affichable, une source traçable, une analyse DA singulière et un identifiant unique dans le registre anti-doublons.
6. **Durée de vie :** 72 h depuis `radar_added_at` initial, lu ou non lu ; ne jamais réinitialiser cet horodatage.
7. **Après publication :** relire les trois JSON, vérifier leur cohérence et leur cardinalité, vérifier les images et le rendu public lorsque possible. Un lien image présent dans le JSON n'est pas une preuve qu'il s'affiche.
8. **Régression :** si le site est cassé, identifier les fichiers affectés et restaurer uniquement ceux-ci depuis le commit stable, après sauvegarde de l'état courant. Ne jamais restaurer aveuglément tout le dépôt, car cela supprimerait les veilles publiées depuis.
9. **Cache mobile :** en cas d'affichage périmé, contrôler la version publique, le service worker et les caches avant de toucher à l'interface.
10. **Transparence :** distinguer « enregistré sur GitHub », « publié sur le site » et « visuellement vérifié sur mobile ».

## Procédure de secours

Comparer le HEAD courant au commit `a80463ff8a6838b51aa92aff6ca5150e050b8cb5`. Si une modification de l'interface a cassé le site, récupérer la version stable de `index.html` ou du fichier concerné depuis la branche de sauvegarde, sans toucher aux nouvelles données éditoriales. Effectuer une nouvelle vérification avant de valider.

**Important :** cette branche GitHub est une sauvegarde logique dans le même dépôt, pas une copie hors GitHub. Pour une protection contre la perte du dépôt lui-même, exporter aussi une archive ZIP localement.
