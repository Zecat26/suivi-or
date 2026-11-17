"""
Suivi des cours de l'or et des pièces d'or d'investissement.

Collecte quotidienne (bibliothèque standard Python uniquement) :
  1. Prix d'achat / de rachat de tous les produits des pages
     https://www.achat-or-et-argent.fr/or/2/pieces-d-or-d-investissement
     https://www.achat-or-et-argent.fr/or/3/lingots-et-lingotins
     + cours de l'once d'or affiché par le site (€/oz et $/oz)
  2. Cotation CPR (1 an glissant) des pièces et lingots suivis, via le graphique du site
  3. Cours de l'once d'or (Yahoo Finance : GC=F / EURUSD=X), historique 10 ans au 1er lancement

Les données sont stockées dans data/cours.db (SQLite) puis exportées dans
data/donnees.js, lu par tableau_de_bord.html.

Usage :
  python suivi_or.py              collecte du jour + export
  python suivi_or.py --export     ré-export seul (sans accès réseau)
  python suivi_or.py --historique force le rechargement de 10 ans d'or (Yahoo)
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import logging
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent
DOSSIER_DATA = RACINE / "data"
DOSSIER_LOGS = RACINE / "logs"
BASE = DOSSIER_DATA / "cours.db"
EXPORT_JS = DOSSIER_DATA / "donnees.js"
DOSSIER_CSV = DOSSIER_DATA / "csv"      # virgules, décimales à point : affichage GitHub, Python, etc.
DOSSIER_EXCEL = DOSSIER_DATA / "excel"  # points-virgules, décimales à virgule : Excel en français

SITE = "https://www.achat-or-et-argent.fr"
URL_PIECES = SITE + "/or/2/pieces-d-or-d-investissement"
URL_LINGOTS = SITE + "/or/3/lingots-et-lingotins"
URL_LISTES = [URL_PIECES, URL_LINGOTS]
URL_CPR = SITE + "/getCoursChart"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

GRAMMES_PAR_ONCE = 31.1034768

# Produits suivis : identifiant produit du site -> nom court, or fin (g), type
PIECES = {
    17: {"nom": "20 Francs Marianne", "or_fin_g": 5.806, "type": "piece"},
    14: {"nom": "Souverain", "or_fin_g": 7.3224, "type": "piece"},
    11: {"nom": "50 Pesos", "or_fin_g": 37.4991, "type": "piece"},
    12: {"nom": "Krugerrand", "or_fin_g": 31.1035, "type": "piece"},
    38: {"nom": "Lingot 1 kg", "or_fin_g": 999.9, "type": "lingot"},
    3553: {"nom": "Lingotin 50 g", "or_fin_g": 49.995, "type": "lingot"},
    3552: {"nom": "Lingotin 20 g", "or_fin_g": 19.998, "type": "lingot"},
}

log = logging.getLogger("suivi_or")


# --------------------------------------------------------------------------- réseau

def http(url: str, data: dict | None = None, referer: str | None = None, essais: int = 3) -> str:
    entetes = {"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"}
    corps = None
    if data is not None:
        corps = urllib.parse.urlencode(data).encode()
        entetes["Content-Type"] = "application/x-www-form-urlencoded"
        entetes["X-Requested-With"] = "XMLHttpRequest"
    if referer:
        entetes["Referer"] = referer
    derniere = None
    for n in range(essais):
        try:
            req = urllib.request.Request(url, data=corps, headers=entetes)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            derniere = e
            log.warning("Échec %s (essai %d/%d) : %s", url, n + 1, essais, e)
            time.sleep(5 * (n + 1))
    raise RuntimeError(f"Impossible de joindre {url} : {derniere}")


def nombre_fr(txt: str) -> float:
    """'3 518.55' / '3 518,55' -> 3518.55"""
    t = re.sub(r"[\s  ]", "", txt)
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    return float(t.replace(",", ""))


# --------------------------------------------------------------------------- base

def connexion() -> sqlite3.Connection:
    DOSSIER_DATA.mkdir(exist_ok=True)
    cx = sqlite3.connect(BASE)
    cx.executescript("""
        CREATE TABLE IF NOT EXISTS prix_site (
            date TEXT NOT NULL, produit_id INTEGER NOT NULL, nom TEXT,
            prix_achat REAL, prix_rachat REAL, horodatage TEXT,
            PRIMARY KEY (date, produit_id));
        CREATE TABLE IF NOT EXISTS cotation_cpr (
            date TEXT NOT NULL, produit_id INTEGER NOT NULL, valeur REAL,
            PRIMARY KEY (date, produit_id));
        CREATE TABLE IF NOT EXISTS or_spot (
            date TEXT NOT NULL, source TEXT NOT NULL, eur_oz REAL, usd_oz REAL,
            PRIMARY KEY (date, source));
    """)
    return cx


# --------------------------------------------------------------------------- collectes

def _produits_page(html: str, url: str) -> list[dict]:
    m = re.search(r"products\s*:\s*(\[\[.*?\]\])\s*,", html, re.S)
    if not m:
        raise RuntimeError(f"Bloc 'products' introuvable dans {url} : la structure de la page a changé.")
    return json.loads(m.group(1))[0]


def collecte_site(cx: sqlite3.Connection) -> None:
    produits, vus, html = [], set(), ""
    for n, url in enumerate(URL_LISTES):
        if n:
            time.sleep(1.5)  # rester discret
        page = http(url)
        html = html or page  # le cours de l'once est lu sur la première page
        for p in _produits_page(page, url):
            if p["id"] not in vus:
                vus.add(p["id"])
                produits.append(p)

    aujourd_hui = dt.date.today().isoformat()
    maintenant = dt.datetime.now().isoformat(timespec="seconds")
    lignes = [(aujourd_hui, p["id"], p["name"], p.get("price") or None,
               p.get("sellPrice") or None, maintenant) for p in produits]
    cx.executemany("INSERT OR REPLACE INTO prix_site VALUES (?,?,?,?,?,?)", lignes)

    trouves = {p["id"] for p in produits}
    for pid, info in PIECES.items():
        if pid not in trouves:
            log.error("Produit %s (id %d) absent des pages !", info["nom"], pid)
    log.info("Site : %d produits enregistrés pour le %s", len(lignes), aujourd_hui)

    eur = re.search(r"Once d.or ([\d\s  .,]+?)\s*€/oz", html)
    usd = re.search(r"Once d.or \$ ([\d\s  .,]+?)\s*\$/oz", html)
    if eur:
        cx.execute("INSERT OR REPLACE INTO or_spot VALUES (?,?,?,?)",
                   (aujourd_hui, "site", nombre_fr(eur.group(1)),
                    nombre_fr(usd.group(1)) if usd else None))
        log.info("Site : once d'or %s €/oz", eur.group(1).strip())
    else:
        log.warning("Cours de l'once d'or non trouvé dans la page.")


URL_FICHE = SITE + "/or/produit/{}"


def collecte_fiches(cx: sqlite3.Connection) -> None:
    """Prix des produits suivis lus sur leur fiche : 1er palier de quantité (1 à 9 pièces,
    ou 1 à 4 selon le produit) et prix de rachat. Remplace, pour ces produits, le prix de la page liste."""
    aujourd_hui = dt.date.today().isoformat()
    for pid, info in PIECES.items():
        time.sleep(1.5)  # rester discret
        try:
            h = http(URL_FICHE.format(pid), referer=URL_LISTES[0])
            palier = re.search(r'<td class="left">.*?</i>(.*?)</td>\s*<td class="[^"]*right"[^>]*>'
                               r'<span id="pa\w*">([\d\s .,]+)</span>', h, re.S)
            rachat = re.search(r'id="pxVU"[^>]*value="([^"]+)"', h)
            if not palier:
                raise RuntimeError("tableau des prix par quantité introuvable")
            achat = nombre_fr(palier.group(2))
            vente = nombre_fr(rachat.group(1)) if rachat else None
            nom = cx.execute("SELECT nom FROM prix_site WHERE date=? AND produit_id=?",
                             (aujourd_hui, pid)).fetchone()
            cx.execute("INSERT OR REPLACE INTO prix_site VALUES (?,?,?,?,?,?)",
                       (aujourd_hui, pid, nom[0] if nom else info["nom"], achat, vente,
                        dt.datetime.now().isoformat(timespec="seconds")))
            log.info("Fiche %s : achat %s € (%s), rachat %s €", info["nom"], achat,
                     re.sub(r"\s+", " ", palier.group(1)).strip(), vente)
        except Exception as e:  # noqa: BLE001
            log.error("Fiche %s : échec (%s) — prix de la page liste conservé", info["nom"], e)


def collecte_cpr(cx: sqlite3.Connection) -> None:
    for pid, info in PIECES.items():
        try:
            brut = http(URL_CPR, {"idmetal": pid, "duree": 1, "type": "YEAR", "sorte": 1},
                        referer=URL_PIECES)
            points = json.loads(brut) or []
            lignes = [(p["ladate"], pid, float(p["valeur"])) for p in points
                      if p.get("ladate") and p.get("valeur") not in (None, "")]
            cx.executemany("INSERT OR REPLACE INTO cotation_cpr VALUES (?,?,?)", lignes)
            log.info("CPR %s : %d points", info["nom"], len(lignes))
        except Exception as e:  # noqa: BLE001
            log.error("CPR %s : échec (%s)", info["nom"], e)
        time.sleep(1.5)  # rester discret


def _yahoo(symbole: str, periode: str) -> dict[str, float]:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbole)}"
           f"?range={periode}&interval=1d")
    j = json.loads(http(url))["chart"]["result"][0]
    decalage = j["meta"].get("gmtoffset", 0)
    cl = j["indicators"]["quote"][0]["close"]
    res = {}
    for ts, v in zip(j.get("timestamp", []), cl):
        if v is not None:
            jour = dt.datetime.fromtimestamp(ts + decalage, dt.timezone.utc).date().isoformat()
            res[jour] = float(v)
    return res


def collecte_yahoo(cx: sqlite3.Connection, forcer_historique: bool = False) -> None:
    vide = cx.execute("SELECT COUNT(*) FROM or_spot WHERE source='yahoo'").fetchone()[0] == 0
    periode = "10y" if (vide or forcer_historique) else "3mo"
    try:
        usd = _yahoo("GC=F", periode)
        change = _yahoo("EURUSD=X", periode)
    except Exception as e:  # noqa: BLE001
        log.error("Yahoo : échec (%s)", e)
        return
    lignes, dernier_change = [], None
    jours_change = sorted(change)
    i = 0
    for jour in sorted(usd):
        while i < len(jours_change) and jours_change[i] <= jour:
            dernier_change = change[jours_change[i]]
            i += 1
        if dernier_change:
            lignes.append((jour, "yahoo", round(usd[jour] / dernier_change, 2), usd[jour]))
    cx.executemany("INSERT OR REPLACE INTO or_spot VALUES (?,?,?,?)", lignes)
    log.info("Yahoo : %d jours d'once d'or (%s)", len(lignes), periode)


# --------------------------------------------------------------------------- export

def export(cx: sqlite3.Connection) -> None:
    pieces = []
    for pid, info in PIECES.items():
        site = cx.execute("SELECT date, prix_achat, prix_rachat FROM prix_site "
                          "WHERE produit_id=? ORDER BY date", (pid,)).fetchall()
        cpr = cx.execute("SELECT date, valeur FROM cotation_cpr "
                         "WHERE produit_id=? ORDER BY date", (pid,)).fetchall()
        pieces.append({"id": pid, "nom": info["nom"], "or_fin_g": info["or_fin_g"],
                       "type": info["type"], "site": site, "cpr": cpr})
    spot = cx.execute("SELECT date, eur_oz, usd_oz FROM or_spot WHERE source='yahoo' "
                      "ORDER BY date").fetchall()
    spot_site = cx.execute("SELECT date, eur_oz, usd_oz FROM or_spot WHERE source='site' "
                           "ORDER BY date").fetchall()
    donnees = {
        "genere": dt.datetime.now().isoformat(timespec="seconds"),
        "grammes_par_once": GRAMMES_PAR_ONCE,
        "pieces": pieces,
        "or_spot": spot,
        "or_spot_site": spot_site,
    }
    EXPORT_JS.write_text("window.DONNEES = " + json.dumps(donnees, ensure_ascii=False) + ";\n",
                         encoding="utf-8")
    log.info("Export : %s", EXPORT_JS)
    export_csv(cx)


def _ecrire_csv(nom: str, entetes: list[str], lignes: list[tuple]) -> None:
    """Écrit le même tableau en 2 formats : CSV standard (data/csv) et CSV Excel français (data/excel)."""
    DOSSIER_CSV.mkdir(exist_ok=True)
    DOSSIER_EXCEL.mkdir(exist_ok=True)
    with open(DOSSIER_CSV / nom, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(entetes)
        w.writerows(["" if v is None else round(v, 2) if isinstance(v, float) else v for v in l] for l in lignes)

    def fr(v):
        if v is None:
            return ""
        if isinstance(v, float):
            return f"{v:.2f}".replace(".", ",")
        return v
    with open(DOSSIER_EXCEL / nom, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(entetes)
        w.writerows([fr(v) for v in l] for l in lignes)


def export_csv(cx: sqlite3.Connection) -> None:
    familles = {pid: ("pièce" if i["type"] == "piece" else "lingot") for pid, i in PIECES.items()}
    noms = {pid: i["nom"] for pid, i in PIECES.items()}

    # 1. Prix du site : tous les produits relevés (suivis ou non), le plus récent en premier
    lignes = [(d, pid, nom, familles.get(pid, ""), "oui" if pid in PIECES else "non", a, r)
              for d, pid, nom, a, r in cx.execute(
                  "SELECT date, produit_id, nom, prix_achat, prix_rachat FROM prix_site "
                  "ORDER BY date DESC, produit_id IN (%s) DESC, nom" % ",".join(map(str, PIECES)))]
    _ecrire_csv("prix_site.csv",
                ["date", "id_produit", "produit", "famille", "suivi", "prix_achat_eur", "prix_rachat_eur"], lignes)

    # 2. Cotation CPR des produits suivis
    lignes = [(d, pid, noms[pid], familles[pid], v) for d, pid, v in cx.execute(
        "SELECT date, produit_id, valeur FROM cotation_cpr ORDER BY date DESC, produit_id")
        if pid in noms]
    _ecrire_csv("cotation_cpr.csv", ["date", "id_produit", "produit", "famille", "cotation_eur"], lignes)

    # 3. Once d'or
    lignes = list(cx.execute("SELECT date, source, eur_oz, usd_oz FROM or_spot ORDER BY date DESC, source"))
    _ecrire_csv("once_or.csv", ["date", "source", "eur_par_once", "usd_par_once"], lignes)
    log.info("Export CSV : %s et %s", DOSSIER_CSV, DOSSIER_EXCEL)


# --------------------------------------------------------------------------- main

def main() -> int:
    DOSSIER_LOGS.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[logging.FileHandler(DOSSIER_LOGS / "collecte.log", encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = set(sys.argv[1:])
    cx = connexion()
    erreurs = 0
    try:
        if "--export" not in args:
            for etape in (collecte_site, collecte_fiches, collecte_cpr):
                try:
                    etape(cx)
                    cx.commit()
                except Exception as e:  # noqa: BLE001
                    erreurs += 1
                    log.error("%s : %s", etape.__name__, e)
            collecte_yahoo(cx, forcer_historique="--historique" in args)
            cx.commit()
        export(cx)
    finally:
        cx.close()
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
