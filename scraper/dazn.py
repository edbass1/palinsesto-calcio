"""Partite di calcio GRATIS (senza lucchetto) su DAZN Italia, Spagna, Francia, Germania, Portogallo, Belgio.

Fonte: la guida pubblica di DAZN (la stessa dell'app, senza login). Il paese è scelto dal parametro
`country`. Gratis = elenco `EntitlementIds` vuoto (nessun abbonamento richiesto: basta l'account gratuito).
"""
import datetime as dt
import json
import re
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


def raccogli_dazn(inizio, fine, paesi=PAESI, scarica_fn=None):
    """Partite gratuite nella finestra [inizio, fine) per tutti i paesi; (partite, falliti)."""
    scarica_fn = scarica_fn or scarica
    primo = inizio.astimezone(ROMA).date()
    giorni = max(1, (fine.astimezone(ROMA).date() - primo).days + 1)
    partite, falliti = [], []
    for paese in paesi:
        tiles, err = scarica_fn(paese, primo, min(giorni, 7))
        if err or tiles is None:
            falliti.append(f"DAZN {PAESI[paese]} ({err or 'nessuna risposta'})")
            continue
        if not any((t.get("Sport") or {}).get("Id") == CALCIO for t in tiles):
            falliti.append(f"DAZN {PAESI[paese]} (guida vuota o cambiata)")
            continue
        for p in analizza(tiles, paese):
            if inizio <= dt.datetime.fromtimestamp(p["ts"], UTC) < fine:
                partite.append(p)
    return partite, falliti
