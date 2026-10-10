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

URL = "https://epg.discovery.indazn.com/eu/v5/epgWithDatesRange"   # riserva (bloccato dai server GitHub)
RAIL = "https://rail-router.discovery.indazn.com/eu/v10/Rail"        # fonte principale (raggiungibile da GitHub)
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


def scarica_rail(paese, tentativi=3):
    """Riquadri delle file "Live" e "ComingUp" della pagina Calcio di DAZN; (tiles, errore)."""
    tiles = []
    for rail in ("Live", "ComingUp"):
        q = urllib.parse.urlencode({"id": rail, "params": f"PageType:Sport;ContentType:Sport;ContentId:{CALCIO}",
                                    "languageCode": "it" if paese == "it" else "en", "country": paese,
                                    "platform": "web", "brand": "dazn"})
        err = None
        for i in range(tentativi):
            try:
                req = urllib.request.Request(f"{RAIL}?{q}", headers={"User-Agent": UA, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=40) as r:
                    tiles += json.load(r).get("Tiles") or []
                err = None
                break
            except Exception as e:  # noqa: BLE001
                err = str(e)[:80]
                time.sleep(2 * (i + 1))
        if err and rail == "ComingUp":
            return None, err
    return tiles, None


RE_SEP = re.compile(r"\s+(?:-|–|v|vs\.?|x)\s+")


def squadre_da_titolo(titolo):
    """I riquadri delle file non hanno 'Contestants': 'Pre | Casa - Ospite (commento)' -> (casa, ospite)."""
    t = re.sub(r"\s*\([^)]*\)\s*$", "", (titolo or "").split("|")[-1]).strip()
    parti = RE_SEP.split(t)
    return (parti[0].strip(), parti[1].strip()) if len(parti) == 2 and all(x.strip() for x in parti) else None


def gratis(t):
    return not t.get("EntitlementIds") or bool(t.get("IsFreeToView")) or bool(t.get("IsPlayForFree"))


def analizza(tiles, paese):
    """Partite di calcio gratuite (una per EventId)."""
    viste = {}
    for t in tiles:
        if (t.get("Sport") or {}).get("Id") != CALCIO:
            continue
        squadre = t.get("Contestants") or []
        if len(squadre) == 2:
            casa, ospite = squadre[0]["Title"].strip(), squadre[1]["Title"].strip()
        else:
            cs = squadre_da_titolo(t.get("Title"))
            if not cs:
                continue  # programmi in studio
            casa, ospite = cs
        if t.get("Type") not in ("UpComing", "Live"):
            continue  # repliche, highlights
        # Start può includere il pre-partita; EventStartTime è il calcio d'inizio vero
        inizio = t.get("EventStartTime") or t["Start"]
        k = (inizio[:13], casa.lower(), ospite.lower())
        if t.get("EventId") in viste:
            k = t["EventId"]
        if k in viste:
            viste[k]["gratis"] = viste[k]["gratis"] or gratis(t)
            continue
        quando = dt.datetime.fromisoformat(inizio.replace("Z", "+00:00"))
        rec = viste[k] = {"ts": int(quando.timestamp()), "casa": casa, "ospite": ospite,
                    "comp": ((t.get("Competition") or {}).get("Title") or "").strip(), "paese": paese,
                    "gratis": gratis(t), "event_id": t.get("EventId")}
        if t.get("EventId"):
            viste[t["EventId"]] = rec
    unici = {id(p): p for p in viste.values()}.values()
    return [p for p in unici if p["gratis"]]


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


def scarica_tutto(paese, primo, giorni):
    """Prima le file DAZN (rail-router), poi la guida EPG come riserva; (tiles, errore)."""
    tiles, err = scarica_rail(paese)
    if tiles and any((t.get("Sport") or {}).get("Id") == CALCIO for t in tiles):
        return tiles, None
    tiles2, err2 = scarica(paese, primo, giorni)
    if tiles2 is not None:
        return tiles2, None
    return None, f"file DAZN: {err or 'vuote'}; guida: {err2}"


def raccogli_dazn(inizio, fine, paesi=PAESI, scarica_fn=None, esterni=None, dettagli=None):
    """Partite gratuite nella finestra [inizio, fine); (partite, righe di avviso).
    Se un paese non risponde si usano, se ci sono, i dati freschi di `esterni` ({paese: [partite]})."""
    scarica_fn = scarica_fn or scarica_tutto
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
        tiles, err = scarica_tutto(paese, primo, 4)
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


# ---------- altri sport gratis (solo DAZN Italia) ----------
SPORT_ALTRI = {"volley": "Pallavolo", "motori": "Motori", "football americano": "Football americano", "basket": "Basket",
               "tennistavolo": "Tennistavolo", "boxe": "Boxe", "ciclismo": "Ciclismo", "hockey su ghiaccio": "Hockey su ghiaccio",
               "baseball": "Baseball", "golf": "Golf", "triathlon": "Triathlon", "sport estremi": "Sport estremi",
               "equitazione | salto ostacoli": "Equitazione", "tennis": "Tennis", "rugby": "Rugby", "pallamano": "Pallamano",
               "atletica": "Atletica", "freccette": "Freccette", "mma": "MMA", "padel": "Padel", "biliardo": "Biliardo"}
PAGINA_IT = "https://www.dazn.com/it-IT/home"


def _rail(rid, params, paese="it", tentativi=3):
    q = urllib.parse.urlencode({"id": rid, "params": params, "languageCode": "it" if paese == "it" else "en",
                                "country": paese, "platform": "web", "brand": "dazn"})
    err = None
    for i in range(tentativi):
        try:
            req = urllib.request.Request(f"{RAIL}?{q}", headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r).get("Tiles") or [], None
        except Exception as e:  # noqa: BLE001
            err = str(e)[:80]
            time.sleep(2 * (i + 1))
    return None, err


def scarica_altri_it():
    """Riquadri DAZN Italia di tutti gli sport tranne il calcio: file Live/ComingUp della home e di ogni sport
    (la home arriva solo a ~24 ore, le pagine dei singoli sport più avanti). (tiles, errore)"""
    home, err = [], None
    for rid in ("Live", "ComingUp"):
        t, e = _rail(rid, "PageType:Home;ContentType:None")
        home += t or []
        err = err or e
    if not home:
        return None, err
    tiles = list(home)
    for sid in sorted({(t.get("Sport") or {}).get("Id") for t in home} - {None, CALCIO}):
        t, _ = _rail("ComingUp", f"PageType:Sport;ContentType:Sport;ContentId:{sid}")
        tiles += t or []
    return tiles, None


def analizza_altri(tiles):
    """Eventi gratis non di calcio, nel formato di altri_sport (una voce per EventId)."""
    out = {}
    for t in tiles:
        sp = t.get("Sport") or {}
        if not sp.get("Id") or sp["Id"] == CALCIO or t.get("Type") not in ("UpComing", "Live") or not gratis(t):
            continue
        k = t.get("EventId") or t.get("Id")
        if k in out:
            continue
        inizio = t.get("EventStartTime") or t["Start"]
        ts = int(dt.datetime.fromisoformat(inizio.replace("Z", "+00:00")).timestamp())
        fine = None
        if t.get("End"):
            fine = int(dt.datetime.fromisoformat(t["End"].replace("Z", "+00:00")).timestamp())
        elif t.get("DurationInMillis"):
            fine = ts + int(t["DurationInMillis"]) // 1000
        if not fine or fine <= ts or fine - ts > 12 * 3600:
            fine = ts + 3 * 3600
        titolo = re.sub(r"\s*\|\s*", " – ", (t.get("Title") or "").strip())
        comp = ((t.get("Competition") or {}).get("Title") or "").strip()
        sfida = len(t.get("Contestants") or []) >= 2 or re.search(r"\svs?\.?\s|\s@\s", t.get("Title") or "")
        testa = " ".join(comp.lower().split()[:2])
        if comp and comp.lower() not in titolo.lower() and testa not in titolo.lower() and not sfida:
            titolo = f"{comp}, {titolo}"
        nome_sport = SPORT_ALTRI.get(sp.get("Title", "").strip().lower()) or sp.get("Title", "Sport").split("|")[0].strip()
        out[k] = {"id": f"dazn:{k}", "ts": ts, "fine": fine, "sport": nome_sport, "titolo": titolo,
                  "titolo_orig": f'{t.get("Title") or ""} {comp}', "titolo_src": t.get("Title") or "", "evento": True,
                  "lingua": "it", "descrizione": t.get("Description") or "",
                  "emittenti": [{"nome": "DAZN Italia", "pagina": PAGINA_IT, "link": None, "vpn": None, "dazn_gratis": True}]}
    return list(out.values())


def altri_sport_it():
    """(eventi, errore) per altri_sport.raccogli_altri."""
    tiles, err = scarica_altri_it()
    return (analizza_altri(tiles), None) if tiles is not None else ([], err)
