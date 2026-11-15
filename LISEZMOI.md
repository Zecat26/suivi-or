# Suivi Or & pièces d'investissement

Outil personnel de suivi des cours : 20 Francs Marianne, Souverain, 50 Pesos, Krugerrand et once d'or.

## Utilisation au quotidien

- **Ouvrir `tableau_de_bord.html`** (double-clic). Une connexion Internet est nécessaire pour la bibliothèque de graphiques.
- La collecte tourne **seule du lundi au vendredi à 18h00** et **à chaque ouverture de session Windows** (2 min après)
  — tâche planifiée « Suivi Or - collecte quotidienne ». Si le PC était éteint à 18h00, elle est rattrapée au démarrage suivant.
  Plusieurs collectes le même jour ne créent pas de doublon : le dernier relevé du jour remplace le précédent.
- Collecte manuelle à tout moment : `python suivi_or.py`

## Contenu

| Fichier | Rôle |
|---|---|
| `suivi_or.py` | Collecte (site + cotation CPR + once d'or Yahoo) → `data/cours.db`, puis export `data/donnees.js` |
| `tableau_de_bord.html` | Graphiques, moyennes mobiles, Bollinger, RSI, tendance, primes, base 100 |
| `installer_tache.ps1` | (Ré)installe la tâche planifiée |
| `data/cours.db` | Base SQLite : tables `prix_site`, `cotation_cpr`, `or_spot` (ouvrable avec DB Browser for SQLite, Excel via ODBC, Python/pandas…) |
| `logs/collecte.log` | Journal des collectes (à consulter en cas de doute) |

## Les données

- **Prix d'achat / de rachat** : prix unitaire du site (tranche 1 à 4 pièces) et prix auquel le site rachète. Historique construit jour après jour à partir du 15/11/2026.
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
