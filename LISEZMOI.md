# Suivi Or & pièces d'investissement

Outil personnel de suivi des cours : 20 Francs Marianne, Souverain, 50 Pesos, Krugerrand, lingot 1 kg, lingotins 50 g et 20 g, et once d'or.

## Utilisation au quotidien

- **Tableau de bord en ligne : https://zecat26.github.io/suivi-or/** (ordinateur, téléphone, tablette).
- La collecte tourne **sur les serveurs GitHub**, PC éteint, du lundi au vendredi vers 18h00 (heure de Paris, 19h00 en été).
  GitHub peut décaler l'exécution de quelques minutes à une heure. Chaque collecte enregistre les données dans le dépôt
  https://github.com/Zecat26/suivi-or et met à jour le tableau de bord en ligne. En cas d'échec, GitHub envoie un e-mail.
- **Collecte manuelle** : onglet *Actions* du dépôt → *Collecte quotidienne* → *Run workflow*.
- **Copie locale** : `git pull` dans ce dossier récupère les dernières données ; `tableau_de_bord.html` s'ouvre alors aussi en local.

### Tâche Windows locale (secours, désactivée)

La tâche planifiée « Suivi Or - collecte quotidienne » (lundi–vendredi 18h00 + ouverture de session) est **désactivée**
depuis le passage à GitHub, pour éviter deux collectes concurrentes. Pour la réactiver en cas de besoin :
`Enable-ScheduledTask -TaskName 'Suivi Or - collecte quotidienne'` (puis penser à `git pull` avant et `git push` après).

## Contenu

| Fichier | Rôle |
|---|---|
| `suivi_or.py` | Collecte (site + cotation CPR + once d'or Yahoo) → `data/cours.db`, puis export `data/donnees.js` |
| `tableau_de_bord.html` | Graphiques, moyennes mobiles, Bollinger, RSI, tendance, primes, base 100 |
| `installer_tache.ps1` | (Ré)installe la tâche planifiée |
| `data/csv/*.csv` | Mêmes données en CSV standard (virgules) : consultables directement sur GitHub sous forme de tableau |
| `data/excel/*.csv` | Mêmes données en CSV pour Excel en français (points-virgules, décimales à virgule) : ouverture par double-clic |
| `data/cours.db` | Base SQLite : tables `prix_site`, `cotation_cpr`, `or_spot` (ouvrable avec DB Browser for SQLite, Excel via ODBC, Python/pandas…) |
| `logs/collecte.log` | Journal des collectes (à consulter en cas de doute) |

## Les données

- **Prix d'achat / de rachat** : prix unitaire du 1er palier de quantité lu sur la fiche de chaque produit (« de 1 à 9 pièces », ou « de 1 à 4 » selon le produit) et prix auquel le site rachète. Historique construit jour après jour à partir du 15/11/2026 (jusqu'au 17/11 inclus, prix lus sur la page liste du site).
- **Cotation CPR** : cotation de marché publiée par le site (graphique « Voir le graphique » des fiches produit). Le site en fournit 1 an glissant ;
  chaque collecte conserve les points, l'historique s'allonge donc au fil du temps.
- **Once d'or (€/oz)** : contrat COMEX (Yahoo Finance, GC=F) converti en euros (EURUSD=X), historique de 10 ans. Écart constaté avec le cours affiché par le site < 0,1 %.
- Les week-ends sont exclus des calculs (cotations non mises à jour).

## Lecture de la tendance

- **Haussière** : cours > MM moyenne > MM longue · **Baissière** : cours < MM moyenne < MM longue · sinon **Neutre**.
- Le dernier croisement MM courte / MM moyenne est indiqué (signal haussier ou baissier).
- RSI ≥ 70 : surachat ; ≤ 30 : survente.

Ces indicateurs sont des outils d'analyse technique, pas des conseils d'investissement.

## En cas de problème

- Le journal `logs/collecte.log` indique « Bloc 'products' introuvable » → le site a changé sa page ; le script doit être adapté.
- Supprimer la tâche : `Unregister-ScheduledTask -TaskName 'Suivi Or - collecte quotidienne' -Confirm:$false`
