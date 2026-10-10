"""Partite di calcio GRATIS (senza lucchetto) su DAZN Italia, Spagna, Francia, Germania, Portogallo, Belgio.

Fonte: la guida pubblica di DAZN (la stessa dell'app, senza login). Il paese è scelto dal parametro
`country`. Gratis = elenco `EntitlementIds` vuoto (nessun abbonamento richiesto: basta l'account gratuito).
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

URL = "https://epg.discovery.indazn.com/eu/v5/epgWithDatesRange"
CALCIO = "289u5typ3vp4ifwh5thalohmq"  # id dello sport "calcio", uguale in tutti i paesi
ROMA = ZoneInfo("Europe/Rome")
UTC = dt.timezone.utc
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
PAESI = {"it": "Italia", "es": "Spagna", "fr": "Francia", "de": "Germania", "pt": "Portogallo", "be": "Belgio"}

# competizioni DAZN -> (ordine, etichetta italiana), stesse etichette delle altre fonti
COMPETIZIONI = [
    (r"^Serie A\b", 1, "SERIE A"),
    (r"^Serie B\b", 2, "SERIE B"),
    (r"^Coppa Italia", 3, "COPPA ITALIA"),
    (r"Youth League", 25, "UEFA YOUTH LEAGUE"),
    (r"Wom[ae]n'?s Champions League", 26, "UEFA WOMEN'S CHAMPIONS LEAGUE"),
    (r"Champions League", 4, "UEFA CHAMPIONS LEAGUE"),
    (r"Europa League", 5, "UEFA EUROPA LEAGUE"),
    (r"Conference League", 6, "UEFA CONFERENCE LEAGUE"),
    (r"^Premier League$", 10, "PREMIER LEAGUE"),
    (r"^LALIGA HYPERMOTION|^LaLiga 2|^Segunda", 48, "LALIGA HYPERMOTION (Spagna, 2ª divisione)"),
    (r"^LALIGA|^LaLiga", 11, "LALIGA"),
    (r"^2\. Bundesliga", 41, "2. BUNDESLIGA"),
    (r"^Bundesliga", 12, "BUNDESLIGA"),
    (r"^Ligue 1", 13, "LIGUE 1"),
    (r"^Liga Portugal 2|^Segunda Liga", 49, "LIGA PORTUGAL 2 (Portogallo)"),
    (r"^Liga Portugal|^Primeira Liga", 43, "PRIMEIRA LIGA (Portogallo)"),
    (r"^(Jupiler )?Pro League", 50, "PRO LEAGUE (Belgio)"),
    (r"^Eredivisie", 42, "EREDIVISIE (Olanda)"),
]


def competizione(nome):
    for rx, ordine, etichetta in COMPETIZIONI:
        if re.search(rx, nome or "", re.I):
            return ordine, etichetta
    return 80, (nome or "ALTRO").upper()


def parametri(paese, primo, giorni):
    offset = int(dt.datetime.combine(primo, dt.time(12), ROMA).utcoffset().total_seconds() // 60)
    return {"country": paese, "languageCode": "it" if paese == "it" else "en",
            "startDate": primo.isoformat(), "endDate": (primo + dt.timedelta(days=giorni - 1)).isoformat(),
            "timeZoneOffset": offset, "openBrowse": "true", "brand": "dazn", "platform": "web"}


def scarica(paese, primo, giorni, tentativi=3):
    """(tiles, errore)"""
    url = URL + "?" + urllib.parse.urlencode(parametri(paese, primo, giorni))
    err = None
    for i in range(tentativi):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r).get("Tiles") or [], None
        except Exception as e:  # noqa: BLE001
            err = str(e)[:80]
            time.sleep(2 * (i + 1))
    return None, err


def gratis(t):
    return not t.get("EntitlementIds") or bool(t.get("IsFreeToView")) or bool(t.get("IsPlayForFree"))


def analizza(tiles, paese):
    """Partite di calcio gratuite (una per EventId)."""
    viste = {}
    for t in tiles:
        if (t.get("Sport") or {}).get("Id") != CALCIO:
            continue
        squadre = t.get("Contestants") or []
        if len(squadre) != 2 or t.get("Type") not in ("UpComing", "Live"):
            continue  # programmi in studio, repliche, highlights
        k = t.get("EventId") or (t.get("Start"), squadre[0].get("Title"), squadre[1].get("Title"))
        if k in viste:
            viste[k]["gratis"] = viste[k]["gratis"] or gratis(t)
            continue
        quando = dt.datetime.fromisoformat(t["Start"].replace("Z", "+00:00"))
        viste[k] = {"ts": int(quando.timestamp()), "casa": squadre[0]["Title"].strip(), "ospite": squadre[1]["Title"].strip(),
                    "comp": ((t.get("Competition") or {}).get("Title") or "").strip(), "paese": paese,
                    "gratis": gratis(t), "event_id": t.get("EventId")}
    return [p for p in viste.values() if p["gratis"]]


FRESCHEZZA_S = 3 * 3600  # dati/dazn.json vale solo se generato da meno di 3 ore


def leggi_esterni(percorso, ora=None):
    """Dati DAZN forniti da un'altra macchina (dati/dazn.json): {paese: [partite]} se freschi, altrimenti {}."""
    try:
        with open(percorso, encoding="utf-8") as f:
            d = json.load(f)
        generato = dt.datetime.fromisoformat(d["generato"].replace("Z", "+00:00"))
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    ora = ora or dt.datetime.now(UTC)
    if not (0 <= (ora - generato).total_seconds() < FRESCHEZZA_S):
        return {}
    return {k: v for k, v in (d.get("paesi") or {}).items() if k in PAESI and isinstance(v, list)}


def riassumi_falliti(falliti):
    """Una sola riga: tutti i paesi falliti -> "non raggiungibile", altrimenti l'elenco dei paesi."""
    if not falliti:
        return []
    if len(falliti) == len(PAESI):
        return ["DAZN non raggiungibile in questo aggiornamento"]
    return [f"DAZN non raggiungibile per: {', '.join(PAESI[p] for p in falliti)}"]


def raccogli_dazn(inizio, fine, paesi=PAESI, scarica_fn=None, esterni=None, dettagli=None):
    """Partite gratuite nella finestra [inizio, fine); (partite, righe di avviso).
    Se un paese non risponde si usano, se ci sono, i dati freschi di `esterni` ({paese: [partite]})."""
    scarica_fn = scarica_fn or scarica
    esterni = esterni or {}
    primo = inizio.astimezone(ROMA).date()
    giorni = max(1, (fine.astimezone(ROMA).date() - primo).days + 1)
    partite, falliti = [], []
    for paese in paesi:
        tiles, err = scarica_fn(paese, primo, min(giorni, 7))
        if not err and tiles is not None and not any((t.get("Sport") or {}).get("Id") == CALCIO for t in tiles):
            err = "guida vuota o cambiata"
        if err or tiles is None:
            if dettagli is not None:
                dettagli.append(f"DAZN {PAESI[paese]}: {err or 'nessuna risposta'}")
            if paese in esterni:
                trovate = [dict(p, paese=paese) for p in esterni[paese]]
                if dettagli is not None:
                    dettagli.append(f"DAZN {PAESI[paese]}: usati i dati di dati/dazn.json")
            else:
                falliti.append(paese)
                continue
        else:
            trovate = analizza(tiles, paese)
        for p in trovate:
            if inizio <= dt.datetime.fromtimestamp(p["ts"], UTC) < fine:
                partite.append(p)
    return partite, riassumi_falliti(falliti)


def esporta(percorso, ora=None):
    """Scarica le partite gratuite (oggi + 3 giorni) di tutti i paesi e le scrive in `percorso`.
    Ritorna il numero di paesi letti; i paesi falliti non vengono scritti."""
    ora = ora or dt.datetime.now(ROMA)
    primo = ora.astimezone(ROMA).date()
    paesi = {}
    for paese in PAESI:
        tiles, err = scarica(paese, primo, 4)
        if err or not tiles or not any((t.get("Sport") or {}).get("Id") == CALCIO for t in tiles):
            print(f"DAZN {PAESI[paese]}: non letto ({err or 'guida vuota'})", file=sys.stderr)
            continue
        paesi[paese] = [{k: p[k] for k in ("ts", "casa", "ospite", "comp", "event_id")} for p in analizza(tiles, paese)]
        print(f"DAZN {PAESI[paese]}: {len(paesi[paese])} partite gratis")
    d = {"_nota": "Partite DAZN gratis (senza lucchetto), generato da scripts/aggiorna_dazn.sh. "
                  "Il sito lo usa solo se la lettura diretta fallisce e il file ha meno di 3 ore.",
         "generato": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "dal": primo.isoformat(), "paesi": paesi}
    os.makedirs(os.path.dirname(os.path.abspath(percorso)), exist_ok=True)
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return len(paesi)


if __name__ == "__main__":
    # uso: python3 scraper/dazn.py --esporta dati/dazn.json
    if len(sys.argv) == 3 and sys.argv[1] == "--esporta":
        sys.exit(0 if esporta(sys.argv[2]) else 1)
    print(__doc__)
