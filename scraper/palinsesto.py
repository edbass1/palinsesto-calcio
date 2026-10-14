#!/usr/bin/env python3
"""Palinsesto calcio in TV da LiveSoccerTV + LiveOnSat (canali in chiaro) -> pagina statica.
Solo libreria standard Python 3.9+."""
import argparse
import concurrent.futures as cf
import datetime as dt
import html
import json
import xml.etree.ElementTree as ET
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import liveonsat  # noqa: E402
import unisci  # noqa: E402
import teleboy as teleboy_mod  # noqa: E402
import extra_partite as extra_mod  # noqa: E402
import dazn  # noqa: E402
import primaplay  # noqa: E402
import altri_sport  # noqa: E402
import epg_teleboy  # noqa: E402
import digisport  # noqa: E402
import scooore  # noqa: E402
import altri_los  # noqa: E402
import euroleague_tv  # noqa: E402

ROMA = ZoneInfo("Europe/Rome")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")
RADICE = Path(__file__).resolve().parent.parent

# Competizioni note: (percorso URL LiveSoccerTV, etichetta italiana, ordine)
COMPETIZIONI = [
    ("/italy/serie-a/", "SERIE A", 1),
    ("/italy/serie-b/", "SERIE B", 2),
    ("/italy/serie-c/", "SERIE C", 7),
    ("/italy/coppa-italia/", "COPPA ITALIA", 3),
    ("/international/uefa-super-cup/", "SUPERCOPPA EUROPEA", 7),
    ("/international/uefa-youth-league/", "UEFA YOUTH LEAGUE", 25),
    ("/international/uefa-womens-champions-league/", "UEFA WOMEN'S CHAMPIONS LEAGUE", 26),
    ("/england/premier-league/", "PREMIER LEAGUE", 10),
    ("/spain/primera-division/", "LALIGA", 11),
    ("/germany/bundesliga/", "BUNDESLIGA", 12),
    ("/france/ligue-1/", "LIGUE 1", 13),
    ("/international/uefa-champions-league/", "UEFA CHAMPIONS LEAGUE", 4),
    ("/international/uefa-europa-league/", "UEFA EUROPA LEAGUE", 5),
    ("/international/uefa-europa-conference-league/", "UEFA CONFERENCE LEAGUE", 6),
    ("/international/uefa-nations-league/", "NAZIONALI – UEFA NATIONS LEAGUE", 30),
    ("/international/fifa-womens-world-cup-qualifying/", "NAZIONALI FEMMINILI – QUALIFICAZIONI MONDIALI 2027", 36),
    ("/international/friendly-women/", "NAZIONALI FEMMINILI – AMICHEVOLI", 37),
    ("/england/championship/", "CHAMPIONSHIP (Inghilterra)", 40),
    ("/germany/2-bundesliga/", "2. BUNDESLIGA", 41),
    ("/netherlands/eredivisie/", "EREDIVISIE (Olanda)", 42),
    ("/portugal/liga-sagres/", "PRIMEIRA LIGA (Portogallo)", 43),
    ("/turkey/super-lig/", "SÜPER LIG (Turchia)", 44),
    ("/greece/super-league/", "SUPER LEAGUE (Grecia)", 45),
    ("/romania/liga-1/", "LIGA I (Romania)", 46),
    ("/romania/liga-ll/", "LIGA II (Romania)", 47),
    ("/saudi-arabia/pro-league/", "SAUDI PRO LEAGUE (Arabia Saudita)", 60),
    ("/brazil/serie-a-brasileirao/", "BRASILEIRÃO SERIE A (Brasile)", 70),
    ("/brazil/serie-b/", "SERIE B BRASILE", 71),
    ("/brazil/serie-c/", "SERIE C BRASILE", 72),
    ("/argentina/primera-division/", "LIGA PROFESIONAL (Argentina)", 73),
    ("/mexico/primera-division/", "LIGA MX (Messico)", 74),
    ("/united-states/usl/", "USL CHAMPIONSHIP (USA)", 75),
    ("/united-states/major-league-soccer/", "MLS (USA)", 76),
]

PAESI = {
    "italy": "Italia", "england": "Inghilterra", "spain": "Spagna", "germany": "Germania", "france": "Francia",
    "netherlands": "Olanda", "portugal": "Portogallo", "turkey": "Turchia", "greece": "Grecia", "romania": "Romania",
    "scotland": "Scozia", "belgium": "Belgio", "austria": "Austria", "switzerland": "Svizzera", "brazil": "Brasile",
    "argentina": "Argentina", "mexico": "Messico", "united-states": "USA", "saudi-arabia": "Arabia Saudita",
    "japan": "Giappone", "poland": "Polonia", "croatia": "Croazia", "serbia": "Serbia", "denmark": "Danimarca",
    "sweden": "Svezia", "norway": "Norvegia", "russia": "Russia", "ukraine": "Ucraina", "wales": "Galles",
    "ireland": "Irlanda",
}

SQUADRE = {
    "Internazionale": "Inter", "Greece": "Grecia", "England": "Inghilterra", "Germany": "Germania",
    "Italy": "Italia", "Spain": "Spagna", "France": "Francia", "Netherlands": "Olanda", "Belgium": "Belgio",
    "Switzerland": "Svizzera", "Scotland": "Scozia", "Wales": "Galles", "Northern Ireland": "Irlanda del Nord",
    "Republic of Ireland": "Irlanda", "Ireland": "Irlanda", "Croatia": "Croazia", "Denmark": "Danimarca",
    "Sweden": "Svezia", "Norway": "Norvegia", "Finland": "Finlandia", "Iceland": "Islanda", "Poland": "Polonia",
    "Czech Republic": "Repubblica Ceca", "Czechia": "Repubblica Ceca", "Slovakia": "Slovacchia",
    "Hungary": "Ungheria", "Serbia": "Serbia", "Slovenia": "Slovenia", "Turkey": "Turchia", "Türkiye": "Turchia",
    "Ukraine": "Ucraina", "Moldova": "Moldavia", "Cyprus": "Cipro", "Lithuania": "Lituania", "Latvia": "Lettonia",
    "Belarus": "Bielorussia", "North Macedonia": "Macedonia del Nord", "Bosnia and Herzegovina": "Bosnia ed Erzegovina",
    "Portugal": "Portogallo", "Brazil": "Brasile", "Mexico": "Messico", "United States": "Stati Uniti",
    "USA": "Stati Uniti", "Japan": "Giappone", "South Korea": "Corea del Sud", "Morocco": "Marocco",
    "Egypt": "Egitto", "Chile": "Cile",
}

GIORNI = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
GIORNI_LUNGHI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
        "settembre", "ottobre", "novembre", "dicembre"]


# ---------- finestra: oggi + 5 giorni ----------
GIORNI_FINESTRA = 6
DURATA_PARTITA_S = 2 * 3600 + 15 * 60  # dopo 2h15m dal calcio d'inizio la partita è considerata finita


def togli_finite(gruppi, ora: dt.datetime, durata: int = DURATA_PARTITA_S):
    """Toglie le partite finite (inizio più di 2h15m fa); restano quelle in corso. Gruppi vuoti eliminati."""
    limite = ora.timestamp() - durata
    out = []
    for g in gruppi:
        restano = [e for e in g["partite"] if e["ts"] > limite]
        if restano:
            out.append({**g, "partite": restano})
    return out


def finestra(ora: dt.datetime, giorni: int = GIORNI_FINESTRA):
    """Da oggi alle 00:00 (Europe/Rome) alla fine del 5° giorno successivo: 6 giorni di calendario."""
    oggi = ora.astimezone(ROMA).date()
    inizio = dt.datetime.combine(oggi, dt.time(0, 0), ROMA)
    fine = dt.datetime.combine(oggi + dt.timedelta(days=giorni), dt.time(0, 0), ROMA)
    return oggi, inizio, fine


# ---------- download ----------
def scarica(url: str, tentativi: int = 3):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
    })
    errore = ""
    for i in range(tentativi):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace"), None
        except urllib.error.HTTPError as e:
            errore = f"HTTP {e.code}"
            if e.code == 404:
                break
        except Exception as e:  # rete, timeout, ...
            errore = f"errore di rete: {type(e).__name__}"
        time.sleep(2 * (i + 1))
    return None, errore


# ---------- analisi HTML ----------
RE_RIGA = re.compile(r'<tr id="\d+" class="matchrow[^"]*".*?</tr>', re.S)  # include "matchrow livematch"
RE_TS = re.compile(r'class=["\']timecell["\']>\s*<span[^>]*\bdv=["\'](\d+)["\']')
RE_PARTITA = re.compile(r'<a href="(/match/[^"#]+)[^"]*" title="([^"]+)"')
RE_COMP = re.compile(r'class="compcell_right".*?<a href="([^"]+)"[^>]*title="([^"]+)"', re.S)


def analizza_pagina(h: str):
    """Lista di partite, oppure None se la pagina non sembra una pagina canale valida."""
    righe = RE_RIGA.findall(h)
    if not righe:
        if re.search(r"no upcoming soccer listings|Live Streaming and TV Schedule", h, re.I):
            return []
        return None
    out = []
    for r in righe:
        t, m, c = RE_TS.search(r), RE_PARTITA.search(r), RE_COMP.search(r)
        if not t or not m:
            continue
        out.append({
            "ts": int(t.group(1)) // 1000,
            "url": m.group(1),
            "titolo": html.unescape(m.group(2)),
            "comp_url": c.group(1) if c else "",
            "comp": html.unescape(c.group(2)) if c else "Altro",
        })
    return out


def competizione(url: str, nome: str):
    for percorso, etichetta, ordine in COMPETIZIONI:
        if percorso in url:
            return ordine, etichetta
    m = re.search(r"/competitions/([^/]+)/", url)
    paese = m.group(1) if m else ""
    if paese == "italy":
        return 8, nome.upper()
    if paese == "international":
        return 35, "NAZIONALI / INTERNAZIONALI – " + nome.upper()
    p = PAESI.get(paese) or paese.replace("-", " ").capitalize()
    return 80, nome.upper() + (f" ({p})" if p else "")


def partita(titolo: str):
    return [SQUADRE.get(s.strip(), s.strip()) for s in titolo.split(" vs ")]


# ---------- raccolta ----------
def raccogli_lstv(canali, inizio, fine):
    """Eventi LiveSoccerTV nella finestra (canali uniti), canali falliti, canali senza partite."""
    canali = [c for c in canali if c.get("url") and "dazn" not in (c.get("nome", "") + c["url"]).lower()]
    ordine_canali = list(dict.fromkeys(c["nome"] for c in canali))
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        pagine = list(ex.map(lambda c: scarica(c["url"]), canali))

    eventi, falliti, con_partite = {}, [], set()
    for c, (h, err) in zip(canali, pagine):
        if err:
            falliti.append(f'{c["nome"]} ({err})')
            continue
        partite = analizza_pagina(h)
        if partite is None:
            falliti.append(f'{c["nome"]} (pagina inattesa, possibile blocco)')
            continue
        # la pagina canale non ha paginazione: se è piena (>= 20 righe) e finisce prima della finestra, avvisa nel log
        if len(partite) >= 20 and max(m["ts"] for m in partite) < fine.timestamp():
            print(f'  NOTA: {c["nome"]}: {len(partite)} partite, l\'elenco potrebbe essere troncato', file=sys.stderr)
        for m in partite:
            quando = dt.datetime.fromtimestamp(m["ts"], ROMA)
            if not (inizio <= quando < fine):
                continue
            e = eventi.get((m["url"], m["ts"]))
            if e is None:
                ordine, etichetta = competizione(m["comp_url"], m["comp"])
                casa, *ospite = partita(m["titolo"])
                e = eventi[(m["url"], m["ts"])] = {
                    "ts": m["ts"], "quando": quando, "titolo": m["titolo"], "ordine": ordine, "competizione": etichetta,
                    "casa": casa, "ospite": " - ".join(ospite), "canali": [], "fonti": ["LiveSoccerTV"],
                    "comp_orig": f'{m["comp_url"]} {m["comp"]}'}
            if c["nome"] not in [k["nome"] for k in e["canali"]]:
                e["canali"].append({"nome": c["nome"], "fta": False})
            con_partite.add(c["nome"])
    nomi_falliti = {f.split(" (")[0] for f in falliti}
    senza = [n for n in ordine_canali if n not in con_partite and n not in nomi_falliti]
    for e in eventi.values():
        e["canali"].sort(key=lambda k: ordine_canali.index(k["nome"]))
    return list(eventi.values()), falliti, senza


def evento_los(p):
    """Partita LiveOnSat -> stesso formato degli eventi LiveSoccerTV."""
    ordine, etichetta = liveonsat.competizione_los(p["comp"])
    casa, _, ospite = p["titolo"].partition(" v ")
    casa, ospite = SQUADRE.get(casa.strip(), casa.strip()), SQUADRE.get(ospite.strip(), ospite.strip())
    return {"ts": p["ts"], "quando": dt.datetime.fromtimestamp(p["ts"], ROMA), "titolo": p["titolo"],
            "ordine": ordine, "competizione": etichetta, "casa": casa, "ospite": ospite,
            "canali": [{"nome": c, "fta": True} for c in p["canali_fta"]]
                      + [{"nome": c, "fta": False} for c in p.get("canali_teleboy", [])], "fonti": ["LiveOnSat"]}


def evento_dazn(p):
    """Partita gratuita DAZN -> stesso formato degli altri eventi."""
    ordine, etichetta = dazn.competizione(p["comp"])
    casa, ospite = SQUADRE.get(p["casa"], p["casa"]), SQUADRE.get(p["ospite"], p["ospite"])
    return {"ts": p["ts"], "quando": dt.datetime.fromtimestamp(p["ts"], ROMA), "titolo": f"{casa} v {ospite}",
            "ordine": ordine, "competizione": etichetta, "casa": casa, "ospite": ospite,
            "canali": [{"nome": f"DAZN {dazn.PAESI[p['paese']]}", "fta": False, "dazn_gratis": True}], "fonti": ["DAZN"]}


def unisci_dazn(eventi, partite_dazn):
    """Aggiunge le partite gratuite DAZN (canale "DAZN <Paese>") a quelle già trovate o come nuove."""
    uniti = []
    for p in sorted(partite_dazn, key=lambda p: (p["ts"], list(dazn.PAESI).index(p["paese"]))):
        nuovo = evento_dazn(p)
        migliore, punteggio = None, 0.0
        for e in eventi:
            sc = unisci.stessa_partita(e["ts"], e["casa"], e["ospite"], nuovo["ts"], nuovo["casa"], nuovo["ospite"])
            if sc > punteggio:
                migliore, punteggio = e, sc
        if migliore is None:
            eventi.append(nuovo)
            continue
        k = nuovo["canali"][0]
        if k["nome"] not in [c["nome"] for c in migliore["canali"]]:
            migliore["canali"].append(k)
        if "DAZN" not in migliore["fonti"]:
            if migliore["fonti"] != ["DAZN"]:
                uniti.append(f'{migliore["casa"]} - {migliore["ospite"]}')
            migliore["fonti"].append("DAZN")
    return eventi, uniti


def evento_stream(p):
    """Partita di calcio da SRF/RTS/RSI/ARD (streaming) -> evento calcio."""
    ordine, etichetta = altri_sport.competizione_calcio(p["comp"] + " " + " ".join(p["testi"]))
    return {"ts": p["ts"], "quando": dt.datetime.fromtimestamp(p["ts"], ROMA), "titolo": f'{p["casa"]} v {p["ospite"]}',
            "ordine": ordine, "competizione": etichetta, "casa": p["casa"], "ospite": p["ospite"],
            "canali": [{"nome": x["nome"], "fta": True} if x.get("da_guida") else  # canale TV da guida extra (es. VTM 2)
                       {"nome": x["nome"] if x.get("teleboy") else f'{x["nome"]} stream', "fta": True, "url": x["pagina"],
                        "diretta": x["link"], "vpn": x["vpn"], **({"teleboy": x["nome"]} if x.get("teleboy") else {})}
                       for x in p["emittenti"]],
            "fonti": ["Streaming"]}


def ordine_di(etichetta):
    """Ordine di una competizione dalla sua etichetta italiana (stesse tabelle di LiveSoccerTV, LiveOnSat e DAZN)."""
    for tab in (COMPETIZIONI, liveonsat.COMPETIZIONI_LOS, dazn.COMPETIZIONI):
        for riga in tab:
            if riga[1 if tab is COMPETIZIONI else 2] == etichetta:
                return riga[2 if tab is COMPETIZIONI else 1]
    return 80


def unisci_stream(eventi, partite, converti=None, fonte="Streaming"):
    """Dirette streaming (SRG/ARD): se la partita c'è già si aggiunge il canale, altrimenti si aggiunge la partita."""
    uniti = []
    for p in partite:
        nuovo = (converti or evento_stream)(p)
        migliore, punteggio = None, 0.0
        for e in eventi:
            # la diretta streaming spesso comincia prima del calcio d'inizio (fino a 45 minuti)
            ts = e["ts"] if 0 <= e["ts"] - nuovo["ts"] <= 45 * 60 else nuovo["ts"]
            sc = unisci.stessa_partita(e["ts"], e["casa"], e["ospite"], ts, nuovo["casa"], nuovo["ospite"])
            if sc > punteggio:
                migliore, punteggio = e, sc
        if migliore is None:
            eventi.append(nuovo)
            continue
        for k in nuovo["canali"]:
            if not any(unisci.chiave_canale(c["nome"]) == unisci.chiave_canale(k["nome"]) for c in migliore["canali"]):
                migliore["canali"].append(k)
        migliore["fonti"].append(fonte)
        uniti.append(f'{migliore["casa"]} - {migliore["ospite"]}')
    return eventi, uniti


FINESTRA_DOPPIONI_S = 3 * 3600
FONTI_STREAM = {"Streaming"}


def nome_completo(e, casa, ospite):
    """Nome più completo per la visualizzazione ("Leipzig" -> "RB Leipzig", "PSV" -> "PSV Eindhoven")."""
    if not casa or not ospite or unisci.somiglianza(e["casa"], casa) < unisci.somiglianza(e["casa"], ospite):
        return
    for campo, nuovo in (("casa", casa), ("ospite", ospite)):
        if unisci.nome_italiano(e[campo]):
            continue  # la forma italiana vince (Stella Rossa, non Red Star Belgrade)
        if unisci.nome_italiano(nuovo) or len(nuovo) > len(e[campo]):
            e[campo] = nuovo
    e["titolo"] = f'{e["casa"]} v {e["ospite"]}'


def togli_repliche(eventi, giorni=3):
    """La stessa partita (stesse squadre, stesso ordine casa/ospite) di nuovo entro pochi giorni non è un'altra partita
    (andata e ritorno hanno casa/ospite invertiti e settimane di distanza):
    - se viene solo dalle guide streaming/EPG (Streaming) è una replica/differita -> tolta (non è una diretta, e
      unirne il canale alla partita vera direbbe il falso);
    - se viene da una fonte TV affidabile (es. orario 00:00 segnaposto o data sbagliata) -> i canali si uniscono
      all'originale, che tiene il suo orario."""
    tolte, tenuti = [], []
    for e in sorted(eventi, key=lambda e: e["ts"]):
        orig = next((t for t in tenuti
                     if 3 * 3600 < e["ts"] - t["ts"] <= giorni * 86400 and t.get("ospite") and e.get("ospite")
                     and unisci.marcatori(t["casa"]) == unisci.marcatori(e["casa"])
                     and unisci.marcatori(t["ospite"]) == unisci.marcatori(e["ospite"])
                     and unisci.somiglianza(t["casa"], e["casa"]) >= 0.9 and unisci.somiglianza(t["ospite"], e["ospite"]) >= 0.9), None)
        if orig is None:
            tenuti.append(e)
            continue
        solo_stream = all(f_ in FONTI_STREAM for f_ in e.get("fonti", []))
        if solo_stream:
            tolte.append(f'{e["casa"]} - {e["ospite"]} {e["quando"]:%d/%m %H:%M} (replica, già alle {orig["quando"]:%d/%m %H:%M})')
            continue
        chiavi = {unisci.chiave_canale(k["nome"]) for k in orig["canali"]}
        for k in e["canali"]:
            if unisci.chiave_canale(k["nome"]) not in chiavi:
                orig["canali"].append(k)
                chiavi.add(unisci.chiave_canale(k["nome"]))
        for f_ in e.get("fonti", []):
            if f_ not in orig["fonti"]:
                orig["fonti"].append(f_)
        tolte.append(f'{e["casa"]} - {e["ospite"]} {e["quando"]:%d/%m %H:%M} (unita a {orig["quando"]:%d/%m %H:%M})')
    return tenuti, tolte


def nomi_italiani(eventi):
    for e in eventi:
        c, o = unisci.in_italiano(e["casa"]), unisci.in_italiano(e.get("ospite") or "")
        if (c, o) != (e["casa"], e.get("ospite") or ""):
            e["casa"], e["ospite"] = c, o
            e["titolo"] = f"{c} v {o}" if o else c
    return eventi


RX_SERIE_A_LOS = re.compile(r"^Italian Serie A$", re.I)


def aggiungi_serie_a(eventi, tutte_los, inizio, fine):
    """Partite di Serie A (calendario LiveOnSat, anche senza canali in chiaro) che non sono già nel palinsesto:
    si mostrano con la nota 'Canali non ancora disponibili'. Nessuna partita inventata: solo quelle elencate."""
    aggiunte = []
    for x in sorted(tutte_los, key=lambda x: x["ts"]):
        base = re.sub(r"\s+-\s+.*$", "", x.get("comp") or "").strip()
        if not RX_SERIE_A_LOS.search(base):
            continue
        quando = dt.datetime.fromtimestamp(x["ts"], ROMA)
        if not (inizio <= quando < fine):
            continue
        casa, _, ospite = x["titolo"].partition(" v ")
        casa, ospite = SQUADRE.get(casa.strip(), casa.strip()), SQUADRE.get(ospite.strip(), ospite.strip())
        if not ospite or unisci.marcatori(casa) or unisci.marcatori(ospite):
            continue
        if any(abs(e["ts"] - x["ts"]) <= 3 * 3600 and unisci.stessa_partita(0, e["casa"], e["ospite"], 0, casa, ospite)
               for e in eventi):
            continue
        ordine, etichetta = liveonsat.competizione_los(x["comp"])
        eventi.append({"ts": x["ts"], "quando": quando, "titolo": f"{casa} v {ospite}", "ordine": ordine,
                       "competizione": etichetta, "casa": casa, "ospite": ospite, "canali": [], "fonti": ["LiveOnSat"],
                       "senza_canali": True})
        aggiunte.append(f"{casa} - {ospite} {quando:%d/%m %H:%M}")
    return eventi, aggiunte


def unisci_doppioni(eventi):
    """Ultimo passaggio: la stessa partita (stesse squadre, stesso giorno, inizio entro 3 ore) compare UNA volta sola
    con tutti i canali di tutte le fonti. L'orario è il calcio d'inizio ufficiale: quello delle fonti TV/guide
    (LiveSoccerTV, LiveOnSat, DAZN, Prima...), non quello delle dirette streaming che spesso iniziano prima."""
    def affidabile(e):
        return any(f not in FONTI_STREAM for f in e.get("fonti", []))

    def chiave(e):  # chi tiene l'orario: prima le fonti non streaming, poi più fonti, poi l'orario più tardo
        return (affidabile(e), len(e.get("fonti", [])), e["ts"])

    uniti, tenuti = [], []
    for e in sorted(eventi, key=lambda e: e["ts"]):
        trovato = None
        for t in tenuti:
            if abs(t["ts"] - e["ts"]) > FINESTRA_DOPPIONI_S or t["quando"].date() != e["quando"].date():
                continue
            if unisci.stessa_partita(0, t["casa"], t["ospite"], 0, e["casa"], e["ospite"]):
                trovato = t
                break
        if trovato is None:
            tenuti.append(e)
            continue
        base, altro = (trovato, e) if chiave(trovato) >= chiave(e) else (e, trovato)
        chiavi = {unisci.chiave_canale(k["nome"]): k for k in base["canali"]}
        for k in altro["canali"]:
            gia = chiavi.get(unisci.chiave_canale(k["nome"]))
            if gia:
                gia["fta"] = gia.get("fta") or k.get("fta")
                for campo in ("url", "diretta", "vpn", "teleboy"):
                    if campo in k and not gia.get(campo):
                        gia[campo] = k[campo]
            else:
                base["canali"].append(k)
                chiavi[unisci.chiave_canale(k["nome"])] = k
        for f_ in altro.get("fonti", []):
            if f_ not in base["fonti"]:
                base["fonti"].append(f_)
        nome_completo(base, altro["casa"], altro["ospite"])
        uniti.append(f'{base["casa"]} - {base["ospite"]}')
        if base is e:
            tenuti[tenuti.index(trovato)] = e
    return tenuti, uniti


def unisci_fonti(eventi, partite_los, regole_fta=()):
    """Aggiunge le partite LiveOnSat: se è la stessa partita unisce i canali, altrimenti la aggiunge.
    Restituisce (eventi, elenco dei doppioni uniti)."""
    for e in eventi:  # canali LiveSoccerTV che sono comunque in chiaro (es. ITV1)
        for k in e["canali"]:
            k["fta"] = k["fta"] or liveonsat.in_chiaro(k["nome"], regole_fta)
    uniti = []
    for p in sorted(partite_los, key=lambda p: p["ts"]):
        nuovo = evento_los(p)
        migliore, punteggio = None, 0.0
        for e in eventi:
            sc = unisci.stessa_partita(e["ts"], e["casa"], e["ospite"], nuovo["ts"], nuovo["casa"], nuovo["ospite"])
            if sc > punteggio:
                migliore, punteggio = e, sc
        if migliore is None:
            eventi.append(nuovo)
            continue
        chiavi = {unisci.chiave_canale(k["nome"]): k for k in migliore["canali"]}
        for k in nuovo["canali"]:
            gia = chiavi.get(unisci.chiave_canale(k["nome"]))
            if gia:
                gia["fta"] = gia["fta"] or k["fta"]
            else:
                migliore["canali"].append(k)
                chiavi[unisci.chiave_canale(k["nome"])] = k
        if "LiveOnSat" not in migliore["fonti"]:
            migliore["fonti"].append("LiveOnSat")
        uniti.append((f'{migliore["casa"]} - {migliore["ospite"]}', p["titolo"], migliore["quando"], nuovo["quando"]))
    return eventi, uniti


def unisci_conferma(eventi, partite, canale, fonte, tolleranza_min=15):
    """Partite da una guida che non dice se è diretta (Scooore): si aggiunge il canale SOLO a partite già presenti
    con le stesse squadre e inizio entro tolleranza_min (conferma da un'altra fonte). Restituisce i nomi uniti."""
    uniti = []
    for p in partite:
        migliore, punteggio = None, 0.0
        for e in eventi:
            if abs(e["ts"] - p["ts"]) > tolleranza_min * 60:
                continue
            sc = unisci.stessa_partita(e["ts"], e["casa"], e["ospite"], p["ts"], p["casa"], p["ospite"])
            if sc > punteggio:
                migliore, punteggio = e, sc
        if migliore is None:
            continue
        if unisci.chiave_canale(canale) not in {unisci.chiave_canale(c["nome"]) for c in migliore["canali"]}:
            migliore["canali"].append({"nome": canale, "fta": True})
            migliore["fonti"].append(fonte)
            uniti.append(f'{migliore["casa"]} - {migliore["ospite"]}')
    return uniti


def unisci_primaplay(eventi, partite, tutte_los=(), escludi=None, fonte="Prima Play", etichetta_altre="ALTRE PARTITE (Prima Sport)"):
    """Partite di calcio dal programma Prima Sport: se la partita c'è già si aggiunge il canale (es. PPV2),
    altrimenti si aggiunge; la competizione viene dal titolo o da LiveOnSat (tutte le partite, anche a pagamento).
    escludi(comp, squadre, nome) -> True per calcio femminile / USA. Restituisce (eventi, uniti, nuove)."""
    uniti, nuove = [], []
    for p in sorted(partite, key=lambda p: p["ts"]):
        if p.get("genere") == "F":
            continue
        migliore, punteggio = None, 0.0
        for e in eventi:
            sc = max(unisci.stessa_partita(e["ts"], e["casa"], e["ospite"], p["ts"], p["casa"], p["ospite"]),
                     unisci.stessa_partita(e["ts"], e["casa"], e["ospite"], p["ts"], p["casa_ro"], p["ospite_ro"]))
            if sc > punteggio:
                migliore, punteggio = e, sc
        k = {"nome": p["canale"], "fta": False}
        if migliore is not None:
            if unisci.chiave_canale(k["nome"]) not in {unisci.chiave_canale(c["nome"]) for c in migliore["canali"]}:
                migliore["canali"].append(k)
            if fonte not in migliore["fonti"]:
                migliore["fonti"].append(fonte)
            nome_completo(migliore, p["casa"], p["ospite"])
            uniti.append(f'{migliore["casa"]} - {migliore["ospite"]} ({p["canale"]})')
            continue
        comp = p.get("comp_los") or ""
        if not comp:
            sc_l, comp = 0.0, ""
            giovanili = re.compile(r"\b(U-?\d\d|Under[ -]?\d\d|Youth|Women|W)\b", re.I)
            for x in tutte_los:
                if giovanili.search(f'{x["titolo"]} {x.get("comp", "")}') and not giovanili.search(f'{p["casa"]} {p["ospite"]}'):
                    continue  # la competizione non si prende da una partita giovanile/femminile con le stesse squadre
                c_, _, o_ = x["titolo"].partition(" v ")
                sc = unisci.stessa_partita(x["ts"], c_.strip(), o_.strip(), p["ts"], p["casa"], p["ospite"])
                if sc > sc_l:
                    sc_l, comp = sc, x["comp"]
        ordine, etichetta = liveonsat.competizione_los(comp) if comp else (90, etichetta_altre)
        if escludi and escludi(f"{comp} | {etichetta}", (p["casa"], p["ospite"]), f'{p["casa"]} - {p["ospite"]} [{comp}] ({fonte})'):
            continue
        nuovo = {"ts": p["ts"], "quando": dt.datetime.fromtimestamp(p["ts"], ROMA), "titolo": f'{p["casa"]} v {p["ospite"]}',
                 "ordine": ordine, "competizione": etichetta, "casa": p["casa"], "ospite": p["ospite"], "comp_orig": comp,
                 "canali": [k], "fonti": [fonte]}
        eventi.append(nuovo)
        nuove.append(f'{p["casa"]} - {p["ospite"]} [{etichetta}] ({p["canale"]})')
    return eventi, uniti, nuove


def raggruppa(eventi):
    gruppi = {}
    for e in eventi:
        gruppi.setdefault((e["ordine"], e["competizione"]), []).append(e)
    return [{"nome": nome, "partite": sorted(gruppi[(o, nome)], key=lambda e: (e["ts"], e["casa"]))}
            for (o, nome) in sorted(gruppi)]


def raccogli(canali, inizio, fine, conf_los=None, statistiche=None, teleboy=None, conf_dazn=None, conf_altri=None, conf_pp=None,
             conf_digi=None, conf_scooore=None):
    """Raccoglie da LiveSoccerTV e (se conf_los) da LiveOnSat, unisce e raggruppa per competizione."""
    eventi, falliti, senza = raccogli_lstv(canali, inizio, fine)
    # calcio femminile e calcio USA (MLS, USL, NWSL...) esclusi da tutte le fonti (liveonsat.json -> escludi_competizioni)
    rx_f = unisci.regex_femminile((conf_los or {}).get("escludi_competizioni", []))
    tolte_f = []

    def fem(comp, squadre, nome):
        if unisci.femminile(rx_f, comp, squadre):
            tolte_f.append(nome)
            return True
        return False

    eventi = [e for e in eventi if not fem(f'{e.get("comp_orig", "")} | {e.get("competizione", "")}', (e["casa"], e["ospite"]),
                                           f'{e["casa"]} - {e["ospite"]} [{e["competizione"]}]')]
    st = {"livesoccertv": len(eventi), "liveonsat": 0, "uniti": [], "solo_liveonsat": 0, "femminili_tolte": tolte_f}
    if conf_los:
        partite_los, falliti_los = liveonsat.raccogli_los(conf_los, inizio, fine, teleboy=teleboy)
        partite_los = [x for x in partite_los
                       if not fem(x["comp"], [s.strip() for s in x["titolo"].split(" v ", 1)], f'{x["titolo"]} [{x["comp"]}]')]
        falliti += falliti_los
        st["liveonsat"] = len(partite_los)
        st["pagine_liveonsat"] = len(conf_los.get("pagine", []))
        st["pagine_liveonsat_fallite"] = len(falliti_los)
        eventi, st["uniti"] = unisci_fonti(eventi, partite_los, conf_los.get("canali_in_chiaro", []))
        st["solo_liveonsat"] = sum(1 for e in eventi if e["fonti"] == ["LiveOnSat"])
    if conf_dazn is not None:
        st["dazn_dettagli"] = []
        esterni = dazn.leggi_esterni(conf_dazn["file_esterno"]) if conf_dazn.get("file_esterno") else {}
        partite_dazn, falliti_dazn = dazn.raccogli_dazn(inizio, fine, conf_dazn.get("paesi") or dazn.PAESI,
                                                       conf_dazn.get("scarica_fn"), esterni, st["dazn_dettagli"])
        partite_dazn = [x for x in partite_dazn
                        if not fem(x["comp"], (x["casa"], x["ospite"]), f'{x["casa"]} - {x["ospite"]} [{x["comp"]}] (DAZN)')]
        falliti += falliti_dazn
        st["dazn"] = {}
        for p in partite_dazn:
            st["dazn"][p["paese"]] = st["dazn"].get(p["paese"], 0) + 1
        eventi, st["uniti_dazn"] = unisci_dazn(eventi, partite_dazn)
        st["solo_dazn"] = sum(1 for e in eventi if e["fonti"] == ["DAZN"])
    altri_pp = []
    if conf_pp is not None:  # programma ufficiale Prima Sport (Prima Play)
        st["primaplay"] = {}
        calcio_pp, altri_pp, err_pp = primaplay.raccogli(conf_pp.get("conf") or primaplay.carica_conf(), inizio, fine,
                                                         conf_pp.get("scarica_fn"), conf_pp.get("oggi"), st["primaplay"])
        if err_pp:
            falliti.append(err_pp)
        eventi, st["uniti_pp"], st["nuove_pp"] = unisci_primaplay(eventi, calcio_pp, liveonsat.TUTTE if conf_los else (), fem)
    if conf_digi is not None:  # programma Digi Sport 1-4 (Romania)
        st["digisport"] = {}
        calcio_dg, altri_dg, err_dg = digisport.raccogli(conf_digi.get("conf") or digisport.carica_conf(), inizio, fine,
                                                         conf_digi.get("scarica_fn"), conf_digi.get("oggi"), st["digisport"])
        if err_dg:
            falliti.append(err_dg)
        eventi, st["uniti_dg"], st["nuove_dg"] = unisci_primaplay(eventi, calcio_dg, liveonsat.TUTTE if conf_los else (), fem,
                                                                  "Digi Sport", "ALTRE PARTITE (Digi Sport)")
        altri_pp = altri_pp + altri_dg
    if conf_scooore is not None:  # Scooore (Zattoo): guida senza 'diretta' -> solo conferma di partite già presenti
        xml_sc, err_sc = (conf_scooore.get("scarica_fn") or scooore.scarica)()
        try:
            part_sc = scooore.partite(xml_sc) if xml_sc else []
        except ET.ParseError as e:
            part_sc, err_sc = [], f"XML non valido: {e}"[:80]
        st["scooore"] = {"partite": len(part_sc), "errore": err_sc,
                         "unite": unisci_conferma(eventi, part_sc, "Scooore", "Scooore")}
    st["altri_sport"] = []
    if conf_altri is not None:
        altri, calcio_stream, avvisi = altri_sport.raccogli_altri(
            inizio, fine, conf_altri.get("ora") or dt.datetime.now(ROMA), rx_f,
            scarica_srg_fn=conf_altri.get("scarica_srg_fn"), scarica_ard_fn=conf_altri.get("scarica_ard_fn"),
            conf=conf_altri.get("conf"), programmi_tolti=st.setdefault("programmi_tolti", []),
            scarica_dazn_fn=conf_altri.get("scarica_dazn_fn", dazn.altri_sport_it if conf_dazn is not None else None),
            scarica_los_fn=conf_altri.get("scarica_los_fn", altri_los.fn_raccogli(
                conf_los, teleboy, inizio, fine, stat=st.setdefault("altri_los", {})) if conf_los else None),
            scarica_pp_fn=(lambda: (altri_pp, None)) if (conf_pp is not None or conf_digi is not None) else None,
            scarica_el_fn=conf_altri.get("scarica_el_fn", euroleague_tv.fn_raccogli(
                altri_sport.regole_conf().get("euroleague_tv", {}), inizio, fine, stat=st.setdefault("euroleague_tv", {}))),
            scarica_tb_fn=conf_altri.get("scarica_tb_fn", epg_teleboy.fn_raccogli(
                teleboy, altri_sport.regole_conf().get("teleboy_epg", {}), inizio, fine) if teleboy is not None else None))
        falliti += avvisi
        st["altri_sport"] = altri
        eventi, st["uniti_stream"] = unisci_stream(eventi, calcio_stream)
        st["calcio_stream"] = len(calcio_stream)
    eventi, st["uniti_doppioni"] = unisci_doppioni(eventi)
    eventi, st["repliche"] = togli_repliche(eventi)
    eventi, st["serie_a_senza_canali"] = aggiungi_serie_a(eventi, liveonsat.TUTTE if conf_los else [], inizio, fine)
    nomi_italiani(eventi)
    # esclusioni permanenti (liveonsat.json -> escludi_canali) applicate a tutte le fonti
    escludi = ["dazn"] + [x.lower() for x in (conf_los or {}).get("escludi_canali", []) if x]
    mai = [x.lower() for x in (conf_los or {}).get("mai_escludere", ["idman"]) if x]
    ru_ir = unisci.regola_canali(conf_los or {})
    st["tolte_esclusi"] = []
    st["canali_ru_ir"] = {}  # nome canale -> motivo
    rimasti = []

    def tieni(k):
        n = k["nome"].lower()
        if any(w in n for w in mai):
            return True  # mai_escludere vince sempre (Idman TV)
        if k.get("dazn_gratis"):
            return True
        if any(x in n for x in escludi):
            return False
        tb = teleboy.trova(k["nome"]) if teleboy is not None else None
        m = ru_ir(k["nome"], teleboy.paese(tb) if tb else None)
        if m:
            st["canali_ru_ir"][k["nome"]] = m
            return False
        return True

    for e in eventi:
        # i canali DAZN delle altre fonti sono esclusi; restano solo le partite gratis prese dalla guida DAZN;
        # esclusi anche i canali russi e iraniani (liveonsat.json -> escludi_russi_iraniani), tranne "mai_escludere"
        e["canali"] = [k for k in e["canali"] if tieni(k)]
        if e["canali"] or e.get("senza_canali"):
            rimasti.append(e)
        else:
            st["tolte_esclusi"].append(f'{e["casa"]} - {e["ospite"]}')
    eventi = rimasti
    # canali visibili su Teleboy (tutte le fonti)
    for e in eventi:
        for k in e["canali"]:
            k["teleboy"] = teleboy.trova(k["nome"]) if teleboy is not None else None
            if k["teleboy"]:
                k["teleboy_link"] = teleboy.link(k["teleboy"])
    st["solo_teleboy"] = sum(1 for e in eventi if e["fonti"] == ["LiveOnSat"] and not any(k["fta"] for k in e["canali"]))
    st["totale"] = len(eventi)
    if statistiche is not None:
        statistiche.update(st)
    return raggruppa(eventi), falliti, senza


# ---------- pagina HTML ----------
def periodo(primo: dt.date, giorni: int = GIORNI_FINESTRA):
    """Es. "Sab 10 – Mar 13 ottobre", "Ven 30 ottobre – Lun 2 novembre"."""
    ultimo = primo + dt.timedelta(days=giorni - 1)
    a = f"{GIORNI[primo.weekday()]} {primo.day}"
    b = f"{GIORNI[ultimo.weekday()]} {ultimo.day} {MESI[ultimo.month - 1]}"
    if primo.month != ultimo.month:
        a += f" {MESI[primo.month - 1]}"
    return f"{a} – {b}"


def unifica_canali(gruppi, altri, dove):
    """Voci di "Dove vederli" con 'unifica_in' (es. VTM -> "VTM GO"): sulle schede tutti i canali della voce
    diventano una sola riga con quel nome (doppioni tolti)."""
    regole = [(v["canali"], v["unifica_in"]) for v in (dove or []) if v.get("unifica_in")]
    if not regole:
        return

    def nome(n):
        for rx, nuovo in regole:
            if any(re.search(r, n or "", re.I) for r in rx):
                return nuovo
        return None

    def pulisci(lista, chiave_link=None):
        out, visti = [], {}
        for c in lista:
            nuovo = nome(c.get("nome"))
            if nuovo:
                c = dict(c, nome=nuovo, teleboy=False)
                if chiave_link:
                    c[chiave_link] = None
            k = c["nome"].lower()
            if nuovo and k in visti:
                visti[k]["fta"] = visti[k].get("fta") or c.get("fta")
                for campo in ("url", "diretta", "vpn"):  # link/VPN del doppione se la riga tenuta non li ha
                    if c.get(campo) and not visti[k].get(campo):
                        visti[k][campo] = c[campo]
                continue
            visti[k] = c
            out.append(c)
        return out

    for g in gruppi or []:
        for e in g["partite"]:
            e["canali"] = pulisci(e["canali"])
    for e in altri or []:
        e["emittenti"] = pulisci(e["emittenti"], "link")


def norm_url(u):
    """Confronto di link: senza schema, www./m., barra finale e #frammento; la query resta (tvLiveId, urn, id... indicano
    il canale), ordinata e senza parametri di tracciamento (utm_*, fbclid, gclid)."""
    u = (u or "").strip()
    u = re.sub(r"^[a-z]+://", "", u, flags=re.I)
    u = re.sub(r"^(www\.|m\.)", "", u, flags=re.I)
    u = u.split("#")[0]
    base, _, q = u.partition("?")
    host, _, path = base.partition("/")
    parti = sorted(x for x in q.split("&") if x and not re.match(r"(utm_[^=]*|fbclid|gclid)(=|$)", x, re.I))
    return host.lower() + ("/" + path).rstrip("/") + ("?" + "&".join(parti) if parti else "")


TLD_DOPPI = {"co.uk", "org.uk", "ac.uk", "com.br", "com.au", "net.au", "co.nz", "com.tr", "com.ar", "com.mx", "co.za",
             "co.jp", "com.cn", "co.in", "com.pl", "com.pt", "com.es"}
# piattaforme con molti canali: righe di canali diversi sullo stesso sito vanno bene (vale solo la regola del link identico)
AGGREGATORI = {"teleboy.ch", "zattoo.com", "youtube.com", "youtu.be", "pluto.tv", "twitch.tv", "orange.ro"}


def dominio(u):
    """Dominio registrabile: play.rts.ch -> rts.ch, www.bbc.co.uk -> bbc.co.uk."""
    host = re.sub(r"^[a-z]+://", "", (u or "").strip().lower()).split("/")[0].split("?")[0].split(":")[0]
    parti = host.split(".")
    n = 3 if ".".join(parti[-2:]) in TLD_DOPPI else 2
    return ".".join(parti[-n:])


def specificita(u):
    """Più alto = link più preciso per l'evento (video/urn della partita prima della pagina diretta generica)."""
    n = norm_url(u)
    return (bool(re.search(r"[?&](urn|id|tvliveid|channel)=|/video/", n, re.I)) * 2 + bool(re.search(r"urn=|/video/", n, re.I)),
            len(n))


def togli_link_doppi(h):
    """Ultima sicurezza sulla scheda di una partita: ogni sito (dominio) compare una volta sola tra i link esterni
    (per le piattaforme con molti canali, es. Teleboy, solo lo stesso link identico). Si tiene il link più preciso.
    Una riga che resta senza link esterni propri viene tolta del tutto, tranne se è l'unica di quel canale
    (canale numerato diverso, es. Prima Sport 2, o DAZN di un altro paese): lì si toglie solo il link ripetuto.
    I link alla guida (#dv-...) non contano."""
    rx = re.compile(r'<a( [^>]*?)?href="([^"]+)"[^>]*>(.*?)</a>', re.S)
    righe = re.findall(r"<li\b.*?</li>", h, re.S) if h.lstrip().startswith("<li") else [h]

    def chiave(href):
        u = html.unescape(href)
        d = dominio(u)
        return norm_url(u) if d in AGGREGATORI else d

    def nome(riga):
        t = re.sub(r"<span class=\"tag[^\"]*\"[^>]*>.*?</span>", "", riga.split("▶")[0], flags=re.S)
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()

    migliore = {}  # chiave -> (indice riga, indice link, specificità)
    for r, riga in enumerate(righe):
        for j, m in enumerate(rx.finditer(riga)):
            if m.group(2).startswith("#"):
                continue
            k, sc = chiave(m.group(2)), specificita(html.unescape(m.group(2)))
            if k not in migliore or sc > migliore[k][2]:
                migliore[k] = (r, j, sc)
    out = []
    for r, riga in enumerate(righe):
        stato = {"tolti": 0, "restano": 0, "vince": None, "j": -1}

        def sost(m):
            stato["j"] += 1
            if m.group(2).startswith("#"):
                return m.group(0)
            w = migliore[chiave(m.group(2))]
            if (w[0], w[1]) == (r, stato["j"]):
                stato["restano"] += 1
                return m.group(0)
            stato["tolti"] += 1
            stato["vince"] = w[0]
            return "" if 'class="diretta"' in (m.group(1) or "") else m.group(3)
        nuova = rx.sub(sost, riga)
        if stato["tolti"] and not stato["restano"] and len(righe) > 1:
            n, nv = nome(riga), nome(righe[stato["vince"]])
            numeri = lambda x: re.findall(r"\d+", x)
            unico = (numeri(n) and numeri(nv) and numeri(n) != numeri(nv)) or (n.upper().startswith("DAZN ") and n != nv)
            if not unico:
                continue  # riga doppione: il sito c'è già in un'altra riga
        out.append(nuova)
    return "".join(out) if len(righe) > 1 or h.lstrip().startswith("<li") else out[0]


def stesso_link(canali, dove):
    """In una partita, canali che portano allo stesso link (e con la stessa indicazione VPN) diventano una riga sola:
    nome della voce 'unifica_in' se c'è, altrimenti il primo; IN CHIARO e link/VPN dei doppioni si conservano."""
    out, visti = [], {}
    for c in canali:
        v = voce_dove(c["nome"], dove)
        link = c.get("diretta") or c.get("url") or c.get("teleboy_link") or (sito_ufficiale(v, c["nome"]) if v else None)
        if not link or link.startswith("#"):
            out.append(c)
            continue
        k = norm_url(link)
        if k not in visti:
            c = dict(c)
            if v and v.get("unifica_in"):
                c["nome"] = v["unifica_in"]
            visti[k] = c
            out.append(c)
            continue
        t = visti[k]
        num = lambda n: re.findall(r"\d+", n)
        if (num(t["nome"]) != num(c["nome"]) and num(t["nome"]) and num(c["nome"])) or c.get("dazn_gratis"):
            out.append(c)  # Prima Sport 1 / Prima Sport 2: canali diversi anche con la stessa pagina di registrazione
            continue
        if v and v.get("unifica_in") and t["nome"] != v["unifica_in"]:
            t["nome"] = v["unifica_in"]
        t["fta"] = t.get("fta") or c.get("fta")
        for campo in ("url", "diretta", "vpn", "teleboy", "teleboy_link"):
            if c.get(campo) and not t.get(campo):
                t[campo] = c[campo]
    return out


NAZIONI_COMP = [(r"^(SERIE A|SERIE B|SERIE BKT|SERIE C|COPPA ITALIA|SUPERCOPPA ITALIANA)\b(?!.*BRASIL)", "Italia"),
                (r"^(PREMIER LEAGUE|EFL|FA CUP|CARABAO)\b(?!.*\()", "Inghilterra"), (r"^LALIGA|^COPA DEL REY", "Spagna"),
                (r"^(2\. )?BUNDESLIGA$|^DFB", "Germania"), (r"^LIGUE [12]$|^COUPE DE FRANCE", "Francia"),
                (r"^SCOTIA PREMIE|^SCOTTISH", "Scozia"), (r"^COPPA SVIZZERA|^SUPER LEAGUE$", "Svizzera"),
                (r"BRASIL", "Brasile")]
RE_COPPE_EUROPEE = re.compile(r"^(UEFA (CHAMPIONS|EUROPA|CONFERENCE|YOUTH|SUPER)|SUPERCOPPA (UEFA|EUROPEA))", re.I)
RE_NAZIONALI = re.compile(r"^NAZIONALI(?! / INTERNAZIONALI)", re.I)


ISO_NAZIONE = {"Inghilterra": "gb-eng", "Scozia": "gb-sct", "Galles": "gb-wls", "Irlanda del Nord": "gb-nir", "Arabia Saudita": "sa",
               "Croazia": "hr", "Serbia": "rs", "Danimarca": "dk", "Svezia": "se", "Norvegia": "no", "Ungheria": "hu", "Bulgaria": "bg",
               "Slovacchia": "sk", "Slovenia": "si", "Ucraina": "ua", "Russia": "ru", "Israele": "il", "Cipro": "cy", "Finlandia": "fi",
               "Islanda": "is", "Cile": "cl", "Colombia": "co", "Uruguay": "uy", "Paraguay": "py", "Perù": "pe", "Ecuador": "ec",
               "Giappone": "jp", "Corea del Sud": "kr", "Cina": "cn", "India": "in", "Marocco": "ma", "Egitto": "eg", "Sudafrica": "za",
               "Qatar": "qa", "Bosnia": "ba", "Bosnia-Erzegovina": "ba"}


def iso_nazione(n):
    """Bandiera (SVG locale in static/flags) di una nazione, o '' se non c'è."""
    iso = ISO_NAZIONE.get(n) or next((v for k, v in BANDIERE.items() if k.lower() == (n or "").lower()), "")
    return iso if iso and (RADICE / "static" / "flags" / f"{iso}.svg").exists() else ""


def nazione_comp(nome):
    """Nazione di una competizione dall'etichetta: '(Spagna, 2ª divisione)' -> Spagna, 'SERIE A' -> Italia; '' se non c'è."""
    m = re.search(r"\(([^()]+)\)\s*$", nome or "")
    if m:
        n = m.group(1).split(",")[0].strip()
        return "" if n.lower().startswith(("prima sport", "w")) else n
    for rx, n in NAZIONI_COMP:
        if re.search(rx, nome or "", re.I):
            return n
    return ""


def tipo_comp(nome):
    return "coppe" if RE_COPPE_EUROPEE.search(nome or "") else "nazionali" if RE_NAZIONALI.search(nome or "") else ""


def etichette_extra(e):
    """Etichette accanto alle squadre: info partita (assenze) e rivalità. Spiegazione al passaggio / tocco."""
    esc = html.escape
    t = []
    a = e.get("_info")
    if a:
        def lato(nome, lista):
            righe = []
            for n, m in (lista or []):
                sq = "squalific" in (m or "").lower()
                det = (m or "").split(",", 1)[1].strip() if "," in (m or "") else ("squalificato" if sq else "infortunato")
                righe.append(f'<span class="ti-r {"ti-sq" if sq else "ti-inf"}"><span class="ti-i">{"🟥" if sq else "🚑"}</span>'
                             f'<span class="ti-p">{esc(n)}</span><span class="ti-m">{esc(det)}</span></span>')
            if not righe:
                righe.append('<span class="ti-ok">✅ nessuna assenza segnalata</span>')
            return f'<span class="ti-s"><span class="ti-n">{esc(nome)}</span>{"".join(righe)}</span>'
        corpo = (f'<span class="ti-h">🩺 Infortunati e squalificati</span>{lato(e["casa"], a.get("casa"))}'
                 f'{lato(e["ospite"], a.get("ospite"))}')
        t.append('<button type="button" class="tg tg-info" aria-label="Info partita: assenze">ℹ️ info partita'
                 f'<span class="tip tip-info" role="tooltip">{corpo}<span class="tip-f">fonte: FotMob</span></span></button>')
    if e.get("_big"):
        t.append(f'<button type="button" class="tg tg-big" aria-label="Big match">🔝 Big match<span class="tip" role="tooltip">{esc(e["_big"])}</span></button>')
    if e.get("_salvezza"):
        t.append(f'<button type="button" class="tg tg-salv" aria-label="Salvezza">🆘 Salvezza<span class="tip" role="tooltip">{esc(e["_salvezza"])}</span></button>')
    if e.get("_riv"):
        t.append(f'<button type="button" class="tg tg-riv" aria-label="Rivalità">🔥 rivalità<span class="tip" role="tooltip">{esc(e["_riv"])}</span></button>')
    return f'<span class="tags">{"".join(t)}</span>' if t else ""


def genera_html(primo, ora, gruppi, falliti, senza, dove=None, altri=None, categorie=None):
    VPN_MANCANTI[:] = []
    esc = html.escape
    unifica_canali(gruppi, altri, dove)
    cat_calcio, cat_altro = classificatore(categorie if categorie is not None else carica_categorie())
    for g in gruppi:
        for e in g["partite"]:
            e["_cat"] = " ".join(sorted(cat_calcio(e, g["nome"])))
            e["_naz"], e["_tipo"] = nazione_comp(g["nome"]), tipo_comp(g["nome"])
    ora_r = ora.astimezone(ROMA)
    aggiornato = f"{GIORNI_LUNGHI[ora_r.weekday()]} {ora_r:%d/%m/%Y} alle {ora_r:%H:%M}"
    giorni = [(primo + dt.timedelta(days=i)) for i in range(GIORNI_FINESTRA)]
    dove = dove or []
    for v in dove:
        v.pop("_canali_pagina", None)
    n_partite = sum(len(g["partite"]) for g in gruppi)

    sezioni, usati, usati_c, usati_s = [], set(), set(), set()

    def scheda(e, comp=None):
        q = e["quando"]
        notte = q.hour < 6
        squadre = f'<span class="sq">{esc(e["casa"])}</span>'
        if e["ospite"]:
            squadre += f' <span class="vs">–</span> <span class="sq">{esc(e["ospite"])}</span>'
        if comp:
            squadre = f'<span class="comp-tag">{esc(comp)}</span>' + squadre
        squadre += etichette_extra(e)
        canali = togli_link_doppi("".join(badge(c, dove, usati_c) for c in stesso_link(e["canali"], dove)))
        if not e["canali"]:
            canali = '<li class="senza-canali">Canali non ancora disponibili: potrebbero comparire nei prossimi aggiornamenti.</li>'
        return (f'<li class="partita" data-ts="{e["ts"]}" data-giorno="{q:%Y-%m-%d}" data-cat="{e.get("_cat", "")}"'
                + (f' data-naz="{esc(e["_naz"])}" data-fl="{iso_nazione(e["_naz"])}"' if e.get("_naz") else '') + (f' data-tipo="{e["_tipo"]}"' if e.get("_tipo") else '') + '>'
                f'<div class="quando"><span class="giorno">{GIORNI[q.weekday()]} {q:%d/%m}</span>'
                f'<span class="ora">{q:%H:%M}</span>'
                + (f'<span class="notte">notte tra {GIORNI[(q.weekday() - 1) % 7].lower()} e {GIORNI[q.weekday()].lower()}</span>' if notte else '') +
                '<span class="stato" aria-live="polite"></span></div>'
                f'<div class="squadre">{squadre}</div>'
                f'<ul class="canali" aria-label="Canali">{canali}</ul></li>')

    # vista "per campionato"
    # in ordine di primo calcio d'inizio (a parità, l'ordine fisso delle competizioni); la pagina lo ricalcola con i filtri
    blocco = blocco_tutto(categorie if categorie is not None else carica_categorie())
    for i, g in sorted(enumerate(gruppi), key=lambda x: (min((e["ts"] for e in x[1]["partite"]), default=0), x[0])):
        sezioni.append(f'<section class="comp" data-ordine="{i}" data-blocco="{blocco(g["nome"])}"><h2>{esc(g["nome"])}</h2>'
                       f'<ol class="partite">{"".join(scheda(e) for e in g["partite"])}</ol></section>')
    # vista "in ordine di orario": tutte le partite per ora d'inizio, con separatori per giorno
    tutte = sorted(((e, g["nome"]) for g in gruppi for e in g["partite"]), key=lambda x: (x[0]["ts"], x[1], x[0]["casa"]))
    orario = []
    for d in giorni:
        del_giorno = [x for x in tutte if x[0]["quando"].date() == d]
        if del_giorno:
            orario.append(f'<section class="giorno-sez" data-giorno="{d:%Y-%m-%d}">'
                          f'<h2 class="giorno-h">{GIORNI_LUNGHI[d.weekday()].upper()} {d.day} {MESI[d.month - 1].upper()}</h2>'
                          f'<ol class="partite">{"".join(scheda(e, c) for e, c in del_giorno)}</ol></section>')

    # vista "altri sport": eventi in ordine di orario, per giorno, con lo sport in evidenza
    altri = sorted(altri or [], key=lambda e: (e["ts"], e["sport"]))

    def scheda_altro(e):
        q = dt.datetime.fromtimestamp(e["ts"], ROMA)
        f = dt.datetime.fromtimestamp(e["fine"], ROMA)
        em = togli_link_doppi("".join(emittente_altro(x, dove, usati_s) for x in e["emittenti"]))
        return (f'<li class="partita evento" data-ts="{e["ts"]}" data-fine="{e["fine"]}" data-giorno="{q:%Y-%m-%d}"'
                f' data-cat="{" ".join(sorted(cat_altro(e)))}">'
                f'<div class="quando"><span class="giorno">{GIORNI[q.weekday()]} {q:%d/%m}</span>'
                f'<span class="ora">{q:%H:%M}</span><span class="fino">fino alle {f:%H:%M}</span>'
                '<span class="stato" aria-live="polite"></span></div>'
                f'<div class="squadre"><span class="comp-tag">{esc(e["sport"].upper())}</span>'
                f'<span class="sq">{esc(e["titolo"])}</span>'
                + (f'<span class="orig" lang="{esc(e.get("lingua") or "de")}">{esc(e["titolo_originale"])}</span>'
                   if e.get("titolo_originale") else '') + '</div>'
                f'<ul class="canali" aria-label="Dove">{em}</ul></li>')
    sez_altri = []
    for d in giorni:
        del_giorno = [e for e in altri if dt.datetime.fromtimestamp(e["ts"], ROMA).date() == d]
        if del_giorno:
            sez_altri.append(f'<section class="giorno-sez" data-giorno="{d:%Y-%m-%d}">'
                             f'<h2 class="giorno-h">{GIORNI_LUNGHI[d.weekday()].upper()} {d.day} {MESI[d.month - 1].upper()}</h2>'
                             f'<ol class="partite">{"".join(scheda_altro(e) for e in del_giorno)}</ol></section>')
    # vista "per sport": una sezione per sport (prima quelli con più eventi), eventi in ordine di orario
    per_sport = {}
    for e in altri:
        per_sport.setdefault(e["sport"], []).append(e)
    fissi = sorted(per_sport.items(), key=lambda x: (-len(x[1]), x[0]))  # a parità di orario: prima gli sport con più eventi
    in_testa = {x.lower() for x in (categorie if categorie is not None else carica_categorie()).get("altri", {}).get("sport_in_testa", [])}
    sez_sport = [f'<section class="comp" data-ordine="{i}"' + (' data-testa="1"' if sp.lower() in in_testa else '') + f'><h2>{esc(sp.upper())}</h2><ol class="partite">{"".join(scheda_altro(e) for e in ev)}</ol></section>'
                 for i, (sp, ev) in sorted(enumerate(fissi), key=lambda x: (min(e["ts"] for e in x[1][1]), x[0]))]
    if not sez_altri:
        sez_altri.append('<p class="vuoto">Nessun altro sport in diretta in questi giorni.</p>')
        sez_sport.append('<p class="vuoto">Nessun altro sport in diretta in questi giorni.</p>')
    usati |= usati_c | usati_s
    sez_dove = {i: " ".join(x for x, u in (("calcio", usati_c), ("sport", usati_s)) if i in u) for i in usati}

    avvisi = ""
    if falliti:
        avvisi += ('<section class="avviso"><h2>⚠ Canali o pagine non scaricati</h2><ul>'
                   + "".join(f"<li>{esc(f)}</li>" for f in falliti) + "</ul></section>")
    note = ""
    if senza:
        note += f'<p>Canali senza partite in questi giorni: {esc(", ".join(senza))}.</p>'

    giorni_c = {e["quando"].date() for g in gruppi for e in g["partite"]}
    giorni_s = {dt.datetime.fromtimestamp(e["ts"], ROMA).date() for e in altri}

    def bottoni_giorni(pieni):
        return '<button type="button" data-filtro="tutti" aria-pressed="true">Tutti</button>' + "".join(
            f'<button type="button" data-filtro="{d:%Y-%m-%d}" aria-pressed="false"'
            + ('' if d in pieni else ' disabled title="Niente in programma (o già finito)"')
            + f'><span>{GIORNI[d.weekday()]}</span> <span>{d.day}</span></button>'
            for d in giorni)
    bottoni, bottoni_s = bottoni_giorni(giorni_c), bottoni_giorni(giorni_s)

    cc = (categorie if categorie is not None else carica_categorie())
    tit = lambda g, k, d: esc(((cc.get(g) or {}).get(k) or {}).get("titolo") or d)
    tasti = lambda g, voci: "".join(
        f'<button type="button" data-gruppo="{g}" data-cat="{k}" aria-pressed="{"true" if k == "tutto" else "false"}">{t}</button>'
        for k, t in voci)
    scelta_c = tasti("calcio", [("tutto", "TUTTO"), ("elite", tit("calcio", "elite", "ELITE CALCIO")),
                                 ("sudamerica", tit("calcio", "sudamerica", "SUDAMERICA")),
                                ("minore", tit("calcio", "minore", "CALCIO MINORE"))])
    scelta_s = tasti("altri", [("tutto", "TUTTO"), ("elite", tit("altri", "elite", "ELITE SPORT"))])
    return TEMPLATE.format(
        scelta_c=scelta_c, scelta_s=scelta_s, bottoni_s=bottoni_s, per_sport="\n".join(sez_sport),
        periodo=esc(periodo(primo)), aggiornato=esc(aggiornato), n=n_partite,
        bottoni=bottoni, sezioni="\n".join(sezioni), orario="\n".join(orario), avvisi=avvisi, note=note,
        altri="\n".join(sez_altri), n_altri=len(altri),
        dove=sezione_dove(dove, usati, sez_dove), durata=DURATA_PARTITA_S,
        vuoto_nascosto=' hidden' if gruppi else '')


# ---------- Filtri "Scegli cosa vuoi vedere" (categorie.json) ----------
def carica_categorie(percorso=None):
    p = Path(percorso) if percorso else RADICE / "categorie.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _intero(lista):
    return [re.compile(rf"(?:{x})", re.I) for x in lista or []]


def blocco_tutto(cat):
    """Nome competizione -> 'a' (coppe europee/nazionali), 'b0' (Serie A), 'b' (altri 4 grandi), 'c' (resto).
    Serve all'ordine delle sezioni PER CAMPIONATO con filtro TUTTO (categorie.json -> calcio.ordine_tutto)."""
    o = (cat or {}).get("calcio", {}).get("ordine_tutto", {})
    a, b0, b = _intero(o.get("blocco_a")), _intero(o.get("blocco_b_primo")), _intero(o.get("blocco_b"))

    def fn(nome):
        n = (nome or "").strip()
        for k, rxs in (("b0", b0), ("b", b), ("a", a)):
            if any(r.fullmatch(n) for r in rxs):
                return k
        return "c"
    return fn


def classificatore(cat):
    """-> (fn_calcio(evento, competizione) -> set, fn_altro(evento) -> set) secondo categorie.json."""
    c = (cat or {}).get("calcio", {})
    el, it = c.get("elite", {}), c.get("italia", {})
    el_comp, el_no = _intero(el.get("competizioni")), _intero(el.get("escludi_squadre"))
    it_comp, coppe = _intero(it.get("competizioni")), _intero(it.get("coppe_europee"))
    sa_comp = _intero(c.get("sudamerica", {}).get("competizioni"))
    naz = {x.lower() for x in it.get("nazionale", [])}
    rx_ita = re.compile(r"\b(?:" + "|".join(re.escape(x) for x in it.get("squadre", [])) + r")\b", re.I) if it.get("squadre") else None
    a = (cat or {}).get("altri", {}).get("elite", {})
    a_sport = {x.lower() for x in a.get("sport", [])}
    a_tit = _intero(a.get("titoli"))
    fa_no = _intero(a.get("football_americano_escludi"))
    generici = {x.lower() for x in a.get("titoli_solo_per_sport", ["Sport", "Programma sportivo", ""])}

    def piena(rxs, testo):
        return any(r.fullmatch(testo.strip()) for r in rxs)

    def calcio(e, comp):
        out = set()
        squadre = [x for x in (e.get("casa"), e.get("ospite")) if x]
        if piena(el_comp, comp) and not any(r.search(x) for r in el_no for x in squadre):
            out.add("elite")
        if (piena(it_comp, comp) or any(x.strip().lower() in naz for x in squadre)
                or (rx_ita and piena(coppe, comp) and any(rx_ita.search(x) for x in squadre))):
            out.add("italia")
        if piena(sa_comp, comp):
            out.add("sudamerica")
        return out or {"minore"}  # CALCIO MINORE: tutto il resto

    def altro(e):
        t = " ".join(x for x in (e.get("titolo"), e.get("titolo_originale"), e.get("titolo_orig"), e.get("competizione")) if x)
        sp = (e.get("sport") or "").lower()
        if sp == "football americano" and any(r.search(t) for r in fa_no):
            return set()
        # i titoli valgono solo per gli eventi senza uno sport preciso (es. 'F3 Motors' in una squadra di pallavolo non è Formula 3)
        if sp in a_sport or (sp in generici and any(r.search(t) for r in a_tit)):
            return {"elite"}
        return set()
    return calcio, altro


# ---------- "Dove vederli" ----------
def voce_dove(nome: str, dove):
    for v in dove:
        if any(re.search(rx, nome, re.I) for rx in v.get("canali", [])):
            return v
    return None


def sito_ufficiale(v, nome=""):
    """Link del canale ('link_canale': regex del nome -> url) o primo link della voce "Dove vederli", o None."""
    for rx, url in (v or {}).get("link_canale", {}).items():
        if nome and re.search(rx, nome, re.I):
            return url
    if (v or {}).get("link_card", {}).get("url"):  # link scelto apposta per le schede (es. registrazione Prima Play)
        return v["link_card"]["url"]
    for l in (v or {}).get("link", []):
        if l.get("url"):
            return l["url"]
    return None


VPN_MANCANTI = []  # ultima generazione: righe con un link ▶ ma senza indicazione VPN (per il log)
SENZA_VPN_NOMI = re.compile(r"^(DAZN\b|Rai\b|Sportitalia|SuperTennis)", re.I)


def vpn_breve(v):
    return ((v or {}).get("vpn_tag") or "").strip() or None


def testo_vpn(nome, vpn_src=None, v=None, teleboy=False):
    """Etichetta VPN della riga di un canale: Teleboy => Svizzera; poi la VPN data dalla fonte; poi dove_vederli.json."""
    if teleboy:
        return "VPN Svizzera"
    if vpn_src:
        t = str(vpn_src).strip()
        if re.match(r"(VPN|SENZA|Solo)\b", t, re.I):
            return t
        if t.isupper():
            t = " ".join(w.lower() if w.lower() in ("o", "e", "di") else (w if w in ("USA", "UK") else w.capitalize()) for w in t.split())
        return "VPN " + t
    if SENZA_VPN_NOMI.search(nome or ""):  # canali italiani / DAZN Italia: dall'Italia senza VPN
        return "SENZA VPN"
    if v and vpn_breve(v):
        return vpn_breve(v)
    return None


BANDIERE = {"Svizzera": "ch", "Irlanda": "ie", "UK": "gb", "Regno Unito": "gb", "Germania": "de", "Francia": "fr",
            "Nigeria": "ng", "Ghana": "gh", "Brasile": "br", "Turchia": "tr", "Azerbaigian": "az", "Albania": "al",
            "USA": "us", "Stati Uniti": "us", "Australia": "au", "Nuova Zelanda": "nz", "Austria": "at", "Belgio": "be",
            "Benin": "bj", "Camerun": "cm", "Costa d'Avorio": "ci", "Emirati Arabi": "ae", "Grecia": "gr", "Mozambico": "mz",
            "Olanda": "nl", "Paesi Bassi": "nl", "Polonia": "pl", "Portogallo": "pt", "Rep. Ceca": "cz", "Senegal": "sn",
            "Spagna": "es", "Zambia": "zm", "Italia": "it", "Romania": "ro", "Canada": "ca", "Argentina": "ar", "Messico": "mx"}
RE_PAESI = re.compile(r"(?:%s)(?:\s*(?:/|,|\bo\b)\s*(?:%s))*" % (("|".join(map(re.escape, sorted(BANDIERE, key=len, reverse=True))),) * 2), re.I)


def bandiera(paese):
    iso = next((v for k, v in BANDIERE.items() if k.lower() == paese.lower()), None)
    return (f'<img class="fl" src="flags/{iso}.svg" alt="{html.escape(paese)}" title="{html.escape(paese)}" width="22" height="16">'
            if iso else html.escape(paese))


def pill_vpn(t, nome="", link=None):
    """Pillola VPN accanto al link: 'VPN' + bandiere (SVG locali, i Windows non mostrano le emoji bandiera), o SENZA VPN."""
    esc = html.escape
    if not t:
        if link:
            VPN_MANCANTI.append(f"{nome} -> {link}")
        return ""
    if re.match(r"(Solo app · )?SENZA VPN", t, re.I) or re.match(r"SENZA", t, re.I):
        return f' <span class="tag vpn no" title="{esc(t)}">{esc(t)}</span>'
    m = RE_PAESI.search(t)
    if not m:
        return f' <span class="tag vpn" title="{esc(t)}">{esc(t)}</span>'
    paesi = [x.strip() for x in re.split(r"\s*(?:/|,|\bo\b)\s*", m.group(0)) if x.strip()]
    prima = re.sub(r"\bVPN\s*$", "", t[:m.start()].strip()).strip()
    dopo = t[m.end():].strip()
    corpo = ((esc(prima) + " ") if prima else "") + "VPN " + '<span class="sep">/</span>'.join(bandiera(x) for x in paesi) + ((" " + esc(dopo)) if dopo else "")
    return f' <span class="tag vpn" title="{esc(t)}" aria-label="{esc(t)}">{corpo}</span>'


_DTT = None


def dtt_di(*nomi):
    """Voce di dtt_italia.json (canale italiano in chiaro sul digitale terrestre) per uno dei nomi, o None."""
    global _DTT
    if _DTT is None:
        f = RADICE / "dtt_italia.json"
        voci = json.loads(f.read_text(encoding="utf-8")).get("canali", []) if f.exists() else []
        _DTT = [(v, [re.compile(x, re.I) for x in v.get("canali", [])]) for v in voci]
    for n in nomi:
        n = (n or "").strip()
        for v, rx in _DTT:
            if n and any(r.search(n) for r in rx):
                return v
    return None


def pill_dtt(dtt):
    """Pillola dei canali italiani: bandiera italiana + 'DTT <n>' (niente Teleboy, niente VPN, niente RaiPlay sulle schede)."""
    return (f' <span class="tag dtt" title="Digitale terrestre italiano, canale {dtt["lcn"]} (senza VPN)">'
            f'<img class="fl" src="flags/it.svg" alt="Italia" width="22" height="16"> DTT {dtt["lcn"]}</span>')


def riga_dtt(dtt):
    """Riga in più (a capo) per i canali italiani in chiaro: pillola '🇮🇹 DTT <n>'."""
    return f'<span class="dtt-riga">{pill_dtt(dtt)}</span>' if dtt else ""


def testo_link(url, predefinito):
    """Testo del link ▶: per YouTube l'icona (SVG locale) + 'YouTube', altrimenti il testo predefinito."""
    if re.search(r"(?:^|//)(?:www\.|m\.)?(?:youtube\.com|youtu\.be)/", url or "", re.I):
        return '<img class="yt" src="youtube.svg" alt="" width="28" height="20"> YouTube'
    return predefinito


def emittente_altro(x, dove, usati):
    """Riga di un'emittente in ALTRI SPORT: nome (link al sito o a "Dove vederli"), etichette, link, VPN accanto al link."""
    esc = html.escape
    dtt = dtt_di(x["nome"])  # canale italiano: riga '🇮🇹 DTT n' + solo il link Teleboy (con VPN 🇨🇭)
    v = None if x.get("pagina") else voce_dove(x["nome"], dove)
    if v:
        usati.add(v["id"])
    if x.get("pagina"):
        nome = f'<a href="{esc(x["pagina"])}" target="_blank" rel="noopener">{esc(x["nome"])}</a>'
    elif v:
        nome = f'<a href="#dv-{esc(v["id"])}" title="Dove vederlo">{esc(x["nome"])}</a>'
    else:
        nome = esc(x["nome"])
    tag = ('<span class="tag" aria-label="in chiaro">IN CHIARO</span> ' if x.get("fta") else '')
    tag2 = (('<span class="tag dz">DAZN GRATIS</span> ' if x.get("dazn_gratis") else '')
            + ('<span class="tag tb">TELEBOY</span> ' if x.get("teleboy") else ''))
    link = x.get("link") or (sito_ufficiale(v, x["nome"]) if v else None) or x.get("pagina")
    etichetta = "▶ diretta" if x.get("link") else ("▶ " + v["link_card"]["testo"] if (v or {}).get("link_card", {}).get("testo") else "▶ sito")
    tb = bool(x.get("teleboy")) or "teleboy.ch" in (link or "")
    if tb and x.get("link"):
        etichetta = "▶ Teleboy"
    if dtt and not tb:  # niente RaiPlay/sito sulle schede dei canali italiani
        link = None
    vt = testo_vpn(x["nome"], x.get("vpn"), v or voce_dove(x["nome"], dove), tb)
    if dtt and not link:
        vt = None
    return (f'<li class="fta">{tag}{nome} {tag2}'.rstrip()
            + (f' <a class="diretta" href="{esc(link)}" target="_blank" rel="noopener">{testo_link(link, etichetta)}</a>' if link else '')
            + pill_vpn(vt, x["nome"], link)
            + riga_dtt(dtt)
            + '</li>')


def badge(c, dove, usati):
    esc = html.escape
    dtt = None if c.get("url") else dtt_di(c["nome"], c.get("teleboy") or "")  # canale italiano: + riga '🇮🇹 DTT n'
    testo = esc(c["nome"])
    if c.get("dazn_gratis"):
        testo = f'{testo} <span class="tag dz" aria-label="gratis su DAZN con account gratuito">DAZN GRATIS</span>'
    if c.get("teleboy"):
        testo = f'{testo} <span class="tag tb" aria-label="su Teleboy">TELEBOY</span>'
    if c["fta"]:
        testo = f'<span class="tag" aria-label="in chiaro">IN CHIARO</span> {testo}'
    # priorità: voci dell'utente, poi Teleboy, poi le altre
    if c.get("url"):  # diretta streaming: link alla pagina dell'evento
        link = c.get("diretta")
        tb = "teleboy.ch" in (link or "") or "teleboy.ch" in (c.get("url") or "")
        vt = testo_vpn(c["nome"], c.get("vpn"), voce_dove(c["nome"], dove), tb) or "SENZA VPN"
        testo = (f'<a href="{esc(c["url"])}" target="_blank" rel="noopener">{testo}</a>'
                 + (f' <a class="diretta" href="{esc(link)}" target="_blank" rel="noopener">{testo_link(link, "▶ Teleboy" if tb else "▶ diretta")}</a>' if link else '')
                 + pill_vpn(vt, c["nome"], link or c["url"]))
        return f'<li class="fta">{testo}</li>' if c["fta"] else f'<li>{testo}</li>'
    v_tb = next((x for x in dove if x["id"] == "teleboy"), None) if c.get("teleboy") else None
    if v_tb is not None:
        v_tb.setdefault("_canali_pagina", set()).add(c["nome"])
        usati.add("teleboy")
    v = voce_dove(c["nome"], [x for x in dove if x.get("fonte") == "utente" and x["id"] != "teleboy"]) or v_tb
    extra = (f' <a class="diretta" href="{esc(c["teleboy_link"])}" target="_blank" rel="noopener" '
             f'title="Canale {esc(c["teleboy"])} su Teleboy">▶ Teleboy</a>') if c.get("teleboy_link") else ""
    tb = bool(extra)
    if not v:
        v = voce_dove(c["nome"], dove)
    link = c.get("teleboy_link")
    if v:
        usati.add(v["id"])
        testo = f'<a href="#dv-{esc(v["id"])}" title="Dove vederlo">{testo}</a>'
        sito = sito_ufficiale(v, c["nome"])
        if sito and not extra and v["id"] != "teleboy" and not dtt:
            extra = (f' <a class="diretta" href="{esc(sito)}" title="Come vederli">▶ {esc(v["link_card"]["testo"])}</a>'
                     if sito.startswith("#") else None) or f' <a class="diretta" href="{esc(sito)}" target="_blank" rel="noopener" title="Sito di streaming">{testo_link(sito, "▶ " + v["link_card"]["testo"] if v.get("link_card", {}).get("testo") else "▶ sito")}</a>'
            link = sito
    vt = testo_vpn(c["nome"], None, v, tb) if (v or tb or link) else testo_vpn(c["nome"])
    if dtt and not link:
        vt = None
    testo += extra + pill_vpn(vt, c["nome"], link) + riga_dtt(dtt)
    return f'<li class="fta">{testo}</li>' if c["fta"] else f'<li>{testo}</li>'


def metodi_html(v):
    """Guida a passi ('metodi': titolo, intro, passi numerati con link, chiusura) + 'in_breve' finale."""
    esc = html.escape
    out = ""
    for m in v.get("metodi", []):
        passi = "".join(
            f'<li>{esc(x["testo"])}' + (f' <a href="{esc(x["url"])}" target="_blank" rel="noopener noreferrer">{esc(x["url"])}</a>' if x.get("url") else "")
            + "</li>" for x in m.get("passi", []))
        out += (f'<div class="metodo"><h4>{esc(m["titolo"])}</h4>'
                + (f'<p>{esc(m["intro"])}</p>' if m.get("intro") else "")
                + (f'<ol class="passi">{passi}</ol>' if passi else "")
                + (f'<p class="fatto">{esc(m["chiusura"])}</p>' if m.get("chiusura") else "") + "</div>")
    if v.get("in_breve"):
        out += f'<p class="in-breve"><strong>In breve:</strong> {esc(v["in_breve"])}</p>'
    return out


def sezione_dove(dove, usati, sez=None):
    """Voci inserite dall'utente sempre; quelle trovate con la ricerca solo se servono a qualche partita."""
    esc = html.escape
    voci = [v for v in dove if v.get("fonte") == "utente" or v.get("sempre") or v["id"] in usati]
    if not voci:
        return ""
    righe = []
    for v in voci:
        link = "".join(
            f'<li><a href="{esc(l["url"])}" target="_blank" rel="noopener noreferrer">{esc(l.get("testo") or l["url"])}</a>'
            + ('' if l.get("verificato", v.get("verificato", True)) else ' <span class="verifica">link da verificare</span>')
            + '</li>' for l in v.get("link", []))
        righe.append(
            f'<li class="dove" id="dv-{esc(v["id"])}" data-sez="{esc((sez or {}).get(v["id"]) or "calcio sport")}"><h3>{esc(v["nome"])}</h3>'
            + (f'<p class="consiglio">{"" if v["consiglio"]["testo"].startswith("⭐") else "⭐ "}{esc(v["consiglio"]["testo"])} <a href="{esc(v["consiglio"]["url"])}" target="_blank" '
               f'rel="noopener noreferrer">{esc(v["consiglio"].get("testo_link") or v["consiglio"]["url"])}</a></p>'
               if v.get("consiglio") else '')
            + metodi_html(v)
            + (f'<p class="vpn">VPN: <strong>{esc(v["vpn"])}</strong></p>' if v.get("vpn") else '')
            + (f'<p class="nota">{esc(v["note"])}</p>' if v.get("note") else '')
            + (f'<p class="nota">Canali di questa pagina disponibili su Teleboy: <strong>{esc(", ".join(sorted(v["_canali_pagina"], key=str.lower)))}</strong></p>'
               if v.get("_canali_pagina") else '')
            + (f'<ul class="link">{link}</ul>' if link else '') + '</li>')
    return ('<section class="dove-vederli" id="dove-vederli"><h2>📺 Dove vederli</h2>'
            '<p class="nota">Tocca il nome di un canale in una partita per arrivare qui. I link si aprono in una nuova scheda.</p>'
            f'<ol class="dove">{"".join(righe)}</ol></section>')


TEMPLATE = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>SPORT GRATIS E LEGALE IN TV · {periodo}</title>
<meta name="description" content="Partite di calcio e altri sport in TV e in streaming gratis, oggi e nei prossimi 5 giorni, orari italiani.">
<meta name="theme-color" content="#000000">
<meta name="color-scheme" content="dark">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="Sport gratis">
<script>(function () {{ try {{ var z = parseFloat(localStorage.getItem("zoom")); if (z >= 0.7 && z <= 1.6) document.documentElement.style.setProperty("--zoom", z); }} catch (e) {{}} }})();</script>
<link rel="manifest" href="manifest.webmanifest">
<link rel="preload" href="fonts/bebas-neue-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<style>
  :root {{ --giallo:#ffd400; --azzurro:#8fe3ff; --grigio:#bdbdbd; --verde:#00e676; --rosso:#ff5252; }}
  * {{ box-sizing:border-box; }}
  [hidden] {{ display:none !important; }}
  html {{ font-size:calc(24px * var(--zoom, 1)); -webkit-text-size-adjust:100%; }}
  body {{ margin:0; background:#000; color:#fff; font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
         line-height:1.35; padding:0 max(16px, env(safe-area-inset-left)) 48px; }}
  main, header, footer {{ max-width:1000px; margin:0 auto; }}
  header {{ padding:24px 0 8px; }}
  h1 {{ font-size:2rem; margin:0 0 8px; line-height:1.15; }}
  .periodo {{ font-size:1.25rem; color:var(--giallo); font-weight:700; margin:0; }}
  .agg {{ color:var(--grigio); margin:8px 0 0; font-size:1rem; }}
  nav.filtri {{ position:sticky; top:0; z-index:5; background:#000; padding:12px 0; margin:0 auto; max-width:1000px;
               display:flex; flex-wrap:wrap; gap:10px; border-bottom:2px solid #333; }}
  nav.filtri button {{ font:inherit; font-size:1rem; font-weight:700; min-height:56px; padding:8px 18px; border-radius:12px;
               background:#111; color:#fff; border:3px solid #666; cursor:pointer; flex:1 1 auto; }}
  nav.filtri button[aria-pressed="true"] {{ background:var(--giallo); color:#000; border-color:var(--giallo); }}
  nav.filtri button:disabled {{ opacity:.35; cursor:default; }}
  [hidden] {{ display:none !important; }}
  nav.sezioni {{ max-width:1000px; margin:8px auto 0; display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
  nav.sezioni button {{ font:inherit; font-size:1.55rem; font-weight:900; letter-spacing:.02em; min-height:104px; padding:10px 8px;
               border-radius:18px; background:#111; color:#fff; border:4px solid #888; cursor:pointer; line-height:1.1; }}
  nav.sezioni button .ico {{ display:block; font-size:2rem; line-height:1.1; }}
  nav.sezioni button .n {{ display:block; font-size:.95rem; font-weight:700; color:#ccc; margin-top:4px; }}
  nav.sezioni button .n::after {{ content:" in programma"; }}
  nav.sezioni button[aria-pressed="true"] {{ background:var(--giallo); color:#000; border-color:var(--giallo); box-shadow:0 0 0 4px #fff; }}
  nav.sezioni button[aria-pressed="true"] .n {{ color:#000; }}
  nav.sezioni button:focus-visible {{ outline:5px solid var(--azzurro); outline-offset:4px; }}
  section.pannello {{ max-width:1000px; margin:16px auto 0; border:3px solid #555; border-top:6px solid var(--giallo); border-radius:14px;
               padding:6px 12px 12px; background:#0b0b0b; }}
  .et {{ margin:10px 0 6px; font-size:1.05rem; font-weight:900; color:var(--giallo); letter-spacing:.02em; }}
  .viste {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
  .viste button {{ font:inherit; font-size:1rem; font-weight:800; min-height:58px; padding:6px 8px; border-radius:12px; line-height:1.15;
               background:#111; color:#fff; border:3px solid #777; cursor:pointer; }}
  .viste button[aria-pressed="true"] {{ background:#fff; color:#000; border-color:#fff; }}
  .viste button[aria-pressed="true"]::before {{ content:"✓ "; }}
  .viste button:focus-visible {{ outline:4px solid var(--azzurro); outline-offset:3px; }}
  .scelta-b {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; }}
  .scelta-b.due {{ grid-template-columns:repeat(2, 1fr); }}
  .scelta-b.cinque {{ grid-template-columns:repeat(6, 1fr); }}
  .scelta-b.cinque button {{ grid-column:span 2; }}
  .scelta-b.cinque button:nth-child(n+4) {{ grid-column:span 3; }}
  .scelta-b.quattro {{ grid-template-columns:1fr 1fr; }}
  .scelta-b[hidden] {{ display:none; }}
  .scelta-b button {{ font:inherit; font-size:1rem; font-weight:800; min-height:58px; padding:6px 8px; border-radius:12px; line-height:1.15;
               background:#111; color:#fff; border:3px solid #888; cursor:pointer; }}
  .scelta-b button[aria-pressed="true"] {{ background:#fff; color:#000; border-color:#fff; }}
  .scelta-b button[aria-pressed="true"]::before {{ content:"✓ "; }}
  .scelta-b button:focus-visible {{ outline:4px solid var(--azzurro); outline-offset:3px; }}
  .tag.vpn {{ background:#ffd400; color:#000; font-size:.8em; font-weight:800; padding:.1em .45em; border-radius:999px; white-space:nowrap; }}
  .tag.vpn.no {{ background:#00e676; color:#000; }}
  .tag.vpn img.fl {{ height:1.1em; width:auto; vertical-align:-0.2em; margin:0 .1em; border:1px solid #000; border-radius:2px; }}
  .tag.vpn .sep {{ margin:0 .05em; }}
  a.diretta img.yt {{ height:1em; width:auto; vertical-align:-0.15em; }}
  .dtt-riga {{ display:block; margin-top:.3em; }}
  .tag.dtt {{ background:#fff; color:#000; font-weight:800; font-size:.8em; padding:.1em .45em; border-radius:999px; white-space:nowrap; }}
  .tag.dtt img.fl {{ height:1.1em; width:auto; vertical-align:-0.2em; border:1px solid #000; border-radius:2px; }}
  .orig {{ display:block; font-size:.95rem; font-weight:400; color:#bbb; margin-top:4px; }}
  .metodo {{ font-size:1.1rem; line-height:1.5; background:#111; border:1px solid #333; border-radius:10px; padding:10px 14px; margin:10px 0; }}
  .metodo h4 {{ font-size:1.2rem; margin:0 0 6px; }}
  .metodo ol.passi {{ list-style:decimal; padding-left:1.6em; margin:6px 0; }}
  .metodo ol.passi li {{ margin:6px 0; }}
  .metodo a, .in-breve a {{ word-break:break-all; }}
  .metodo .fatto {{ font-weight:700; }}
  .in-breve {{ font-size:1.15rem; background:#1d1d00; border:2px solid var(--giallo); border-radius:10px; padding:10px 12px; }}
  .consiglio {{ font-size:1.1rem; font-weight:700; background:#1d1d00; border:2px solid var(--giallo); border-radius:10px; padding:10px 12px; }}
  .fino {{ font-size:.85rem; color:#ccc; }}
  a.diretta {{ font-size:.85rem; color:#fff; }}
  .intro-altri {{ font-size:1.05rem; color:#ddd; }}
  h2.giorno-h {{ background:#fff; color:#000; }}
  section.giorno-sez {{ margin-top:36px; }}
  .comp-tag {{ display:block; width:max-content; max-width:100%; background:var(--giallo); color:#000; font-size:.8rem; font-weight:900;
               padding:2px 10px; border-radius:7px; margin-bottom:6px; letter-spacing:.02em; overflow-wrap:anywhere; }}
  .cerca {{ position:relative; max-width:1000px; margin:8px auto 4px; }}
  .cerca input {{ width:100%; box-sizing:border-box; font:inherit; font-size:1.2rem; min-height:56px; padding:10px 60px 10px 16px;
    border-radius:12px; border:2px solid #555; background:#111; color:#fff; }}
  .cerca input:focus {{ outline:none; border-color:var(--giallo); }}
  .cerca input::-webkit-search-cancel-button {{ display:none; }}
  .cerca button {{ position:absolute; right:6px; top:50%; transform:translateY(-50%); font:inherit; font-size:1.4rem; font-weight:700;
    width:46px; height:46px; border-radius:10px; border:0; background:#333; color:#fff; cursor:pointer; }}
  li.senza-canali {{ color:#b0b0b0; font-size:1.05rem; font-style:italic; list-style:none; }}
  .nessun-risultato {{ max-width:1000px; margin:16px auto; font-size:1.2rem; font-weight:700; text-align:center; }}
  nav.filtri button:focus-visible {{ outline:4px solid var(--azzurro); outline-offset:2px; }}
  section.comp {{ margin-top:36px; }}
  h2 {{ font-size:1.5rem; color:#000; background:var(--giallo); padding:10px 16px; border-radius:10px; margin:0 0 14px;
        letter-spacing:.02em; }}
  ol.partite {{ list-style:none; margin:0; padding:0; display:grid; gap:14px; }}
  li.partita {{ background:#111; border:2px solid #444; border-radius:14px; padding:16px 18px;
               display:grid; grid-template-columns: 9.5rem 1fr; grid-template-rows:auto 1fr; grid-template-areas:"quando squadre" "quando canali";
               gap:8px 20px; align-items:start; }}
  .quando {{ grid-area:quando; display:flex; flex-direction:column; gap:2px; }}
  .giorno {{ font-size:1rem; color:var(--grigio); font-weight:700; text-transform:uppercase; }}
  .ora {{ font-size:2rem; font-weight:800; color:var(--giallo); line-height:1.05; font-variant-numeric:tabular-nums; }}
  .notte {{ font-size:.85rem; color:var(--azzurro); font-weight:600; }}
  .stato:empty {{ display:none; }}
  .stato {{ align-self:flex-start; margin-top:6px; font-size:.8rem; font-weight:800; padding:4px 10px; border-radius:8px; }}
  .squadre {{ grid-area:squadre; font-size:1.3rem; font-weight:800; overflow-wrap:anywhere; }}
  .vs {{ color:var(--grigio); font-weight:400; }}
  ul.canali {{ grid-area:canali; list-style:none; margin:0; padding:0; display:flex; flex-wrap:wrap; gap:8px; align-items:flex-start; align-self:start; }}
  ul.canali li {{ color:var(--azzurro); border:2px solid #2d6f86; border-radius:8px; padding:2px 10px; font-size:1rem; font-weight:600; }}
  ul.canali li.fta {{ color:var(--verde); border-color:var(--verde); }}
  .tag {{ display:inline-block; background:var(--verde); color:#000; font-size:.7rem; font-weight:900; letter-spacing:.04em;
          padding:1px 5px; border-radius:5px; vertical-align:middle; position:relative; top:-2px; }}
  .h1p {{ color:var(--giallo); display:block; font-size:.8em; }}
  #vista-sport-tipo .comp-tag {{ display:none; }}
  ul.canali li a {{ color:inherit; text-decoration:underline; text-decoration-thickness:2px; text-underline-offset:4px; }}
  section.dove-vederli {{ margin-top:48px; }}
  ol.dove {{ list-style:none; margin:0; padding:0; display:grid; gap:14px; }}
  li.dove {{ background:#111; border:2px solid #444; border-radius:14px; padding:14px 18px; scroll-margin-top:110px; }}
  li.dove:target {{ border-color:var(--giallo); box-shadow:0 0 0 3px var(--giallo) inset; }}
  li.dove h3 {{ margin:0 0 6px; font-size:1.3rem; color:var(--giallo); }}
  li.dove p {{ margin:4px 0; }}
  .vpn strong {{ color:var(--azzurro); }}
  .nota {{ color:#e0e0e0; font-size:.95rem; }}
  ul.link {{ list-style:none; margin:8px 0 0; padding:0; display:grid; gap:8px; }}
  ul.link a {{ color:var(--azzurro); font-size:1.05rem; font-weight:700; overflow-wrap:anywhere; text-underline-offset:4px; }}
  .verifica {{ font-size:.8rem; color:#000; background:var(--giallo); padding:1px 6px; border-radius:6px; font-weight:800; }}
  .tag.tb {{ background:var(--azzurro); }}
  .tag.dz {{ background:#fff; color:#000; outline:2px solid #ff3df5; }}
  .legenda {{ margin:10px 0 0; font-size:.9rem; color:var(--grigio); }}
  li.partita.in-corso {{ border-color:var(--verde); box-shadow:0 0 0 2px var(--verde) inset; }}
  li.partita.in-corso .stato {{ background:var(--verde); color:#000; }}
  li.partita.tra-poco {{ border-color:var(--giallo); }}
  li.partita.tra-poco .stato {{ background:var(--giallo); color:#000; }}
  .avviso {{ margin-top:40px; border:3px solid var(--rosso); border-radius:14px; padding:12px 18px; }}
  .avviso h2 {{ background:none; color:var(--rosso); padding:0; }}
  footer {{ margin-top:40px; color:var(--grigio); font-size:.85rem; border-top:2px solid #333; padding-top:16px; }}
  footer a {{ color:var(--azzurro); }}
  .vuoto {{ font-size:1.3rem; margin-top:40px; }}
  @media (max-width: 640px) {{
    html {{ font-size:calc(21px * var(--zoom, 1)); }}
    li.partita {{ grid-template-columns:1fr; grid-template-areas:"quando" "squadre" "canali"; padding:14px; }}
    .quando {{ flex-direction:row; align-items:baseline; flex-wrap:wrap; gap:4px 12px; }}
    .stato {{ margin-top:0; align-self:center; }}
    nav.filtri {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:6px; }}
    nav.filtri button {{ padding:4px 2px; min-height:64px; font-size:.95rem; line-height:1.1; border-radius:10px; }}
    nav.filtri button span {{ display:block; }}
    li.partita {{ grid-template-rows:auto; }}
  }}
  /* ---- intestazione e comandi più piccoli e sobri (le schede delle partite restano come sono) ---- */
  header {{ padding:14px 0 4px; }}
  h1 {{ font-size:.95rem; font-weight:900; letter-spacing:.06em; margin:0 0 6px; line-height:1.25; }}
  .h1p {{ display:inline-block; margin:4px 0 0; font-size:.62rem; font-weight:700; letter-spacing:.02em; color:var(--giallo);
         background:rgba(255,212,0,.08); border:1px solid rgba(255,212,0,.55); border-radius:999px; padding:.2em .8em; vertical-align:middle; }}
  .agg {{ font-size:.58rem; margin:2px 0 0; color:#9a9a9a; }}
  nav.sezioni {{ gap:8px; margin-top:6px; }}
  nav.sezioni button {{ font-size:.78rem; min-height:2.6rem; padding:6px 6px; border-width:2px; border-radius:12px; letter-spacing:.03em; }}
  nav.sezioni button .ico {{ display:inline; font-size:.9rem; }}
  nav.sezioni button .n {{ font-size:.55rem; margin-top:2px; }}
  nav.sezioni button[aria-pressed="true"] {{ box-shadow:0 0 0 2px #fff; }}
  section.pannello {{ margin-top:8px; border-width:1px; border-top-width:3px; border-radius:10px; padding:2px 8px 8px; }}
  .et {{ font-size:.62rem; margin:6px 0 4px; }}
  .viste, .scelta-b {{ gap:6px; }}
  .viste button, .scelta-b button {{ font-size:.62rem; min-height:max(40px, 1.9rem); padding:4px 6px; border-width:2px; border-radius:9px; }}
  nav.filtri {{ padding:6px 0; gap:6px; border-bottom-width:1px; }}
  nav.filtri button {{ font-size:.64rem; min-height:max(40px, 1.9rem); padding:4px 10px; border-width:2px; border-radius:9px; }}
  .cerca {{ margin:6px auto 2px; }}
  .cerca input {{ font-size:.7rem; min-height:max(42px, 2rem); padding:6px 48px 6px 12px; border-width:1px; border-radius:10px; }}
  .cerca button {{ font-size:.8rem; width:34px; height:34px; border-radius:8px; }}
  .nessun-risultato {{ font-size:.75rem; }}
  .legenda {{ font-size:.58rem; }}
  .intro-altri {{ font-size:.62rem; }}
  /* zoom e torna su */
  .zoom {{ position:fixed; top:max(8px, env(safe-area-inset-top)); right:max(8px, env(safe-area-inset-right)); z-index:30; display:flex; flex-direction:column; gap:6px; }}
  .zoom button, .su {{ font:inherit; font-size:16px; font-weight:800; color:#fff; background:rgba(30,30,30,.92); border:1px solid #666;
         cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,.6); }}
  .zoom button {{ width:40px; height:40px; border-radius:10px; line-height:1; padding:0; }}
  .su {{ position:fixed; left:max(10px, env(safe-area-inset-left)); bottom:max(12px, env(safe-area-inset-bottom)); z-index:30;
         font-size:13px; font-weight:700; min-height:40px; padding:6px 12px; border-radius:999px; opacity:.9; }}
  .zoom button:focus-visible, .su:focus-visible {{ outline:3px solid var(--azzurro); outline-offset:2px; }}
  @media (max-width: 1120px) {{ nav.filtri, .cerca {{ padding-right:50px; }} .cerca button {{ right:56px; }} h1, .agg {{ padding-right:50px; }} }}
  @media (max-width: 640px) {{
    nav.filtri button {{ font-size:.66rem; min-height:44px; padding:2px; }}
    nav.sezioni button {{ font-size:.8rem; }}
  }}
  /* ---- titolo in Bebas Neue (font locale, SIL OFL) ---- */
  @font-face {{ font-family:"Bebas Neue"; src:url("fonts/bebas-neue-latin.woff2") format("woff2"); font-weight:400; font-style:normal; font-display:swap; }}
  h1 {{ font-family:"Bebas Neue", "Oswald", system-ui, sans-serif; font-weight:400; font-size:1.8rem; letter-spacing:.045em; line-height:1.05; }}
  h1 .h1p {{ font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif; letter-spacing:.02em; margin-left:.3em; vertical-align:.35em; }}
  /* ---- desktop: barra laterale (solo schermi larghi; su telefono non cambia nulla) ---- */
  #barra, #ordina-top {{ display:none; }}
  html.desk body {{ padding-left:calc(13.5rem + 28px); }}
  /* su desktop lo zoom +/− ingrandisce solo la parte destra (elenco): la barra laterale resta sempre della stessa misura */
  html.desk {{ font-size:24px; }}
  html.desk body > :not(#barra):not(.zoom):not(.su):not(script) {{ zoom:var(--zoom, 1); }}
  html.desk nav.sezioni, html.desk section.pannello {{ display:none !important; }}
  html.desk #barra {{ display:block; position:fixed; top:0; left:0; bottom:0; width:13.5rem; overflow-y:auto; background:#0b0b0b;
         border-right:1px solid #262626; padding:16px 12px 80px; z-index:20; }}
  html.desk #barra .cerca {{ margin:0 0 12px; padding-right:0; max-width:none; }}
  html.desk #barra .cerca::before {{ content:""; position:absolute; left:12px; top:50%; width:14px; height:14px; transform:translateY(-60%);
         border:2px solid #aaa; border-radius:50%; pointer-events:none; }}
  html.desk #barra .cerca::after {{ content:""; position:absolute; left:25px; top:calc(50% + 4px); width:7px; height:2px; background:#aaa;
         transform:rotate(45deg); pointer-events:none; }}
  html.desk #barra .cerca input {{ padding-left:38px; font-size:.6rem; min-height:40px; }}
  html.desk #barra .cerca button {{ right:4px; width:32px; height:32px; font-size:.6rem; }}
  .acc {{ border:1px solid #2a2a2a; border-radius:12px; margin:0 0 12px; background:#111; overflow:hidden; }}
  .acc-h {{ display:flex; align-items:stretch; border-bottom:1px solid #2a2a2a; }}
  .acc.chiuso .acc-h {{ border-bottom:0; }}
  .acc-sez {{ flex:1; font:inherit; font-size:.62rem; font-weight:900; letter-spacing:.05em; text-align:left; color:var(--giallo); background:none;
         border:0; padding:10px 12px; min-height:44px; cursor:pointer; }}
  .acc-sez .n {{ display:block; font-size:.48rem; font-weight:600; color:#999; letter-spacing:0; margin-top:2px; }}
  .acc.attiva .acc-sez {{ color:var(--giallo); }}
  .acc.attiva {{ border-color:#5a4d00; }}
  .acc-t {{ width:44px; font:inherit; font-size:.7rem; color:#ccc; background:none; border:0; border-left:1px solid #2a2a2a; cursor:pointer; }}
  .acc-t span {{ display:inline-block; transition:transform .15s; }}
  .acc.chiuso .acc-t span {{ transform:rotate(-90deg); }}
  .acc-b {{ padding:6px 10px 12px; }}
  .acc.chiuso .acc-b {{ display:none; }}
  .b-et {{ margin:10px 0 6px; font-size:.48rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; color:#8a8a8a; }}
  html.desk #barra .scelta-b {{ grid-template-columns:1fr 1fr; gap:6px; }}
  html.desk #barra .scelta-b button {{ grid-column:auto !important; font-size:.5rem; min-height:36px; border-width:1px; }}
  html.desk #barra nav.filtri {{ position:static; display:grid; grid-template-columns:repeat(4, 1fr); gap:5px; padding:0; border:0; background:none; max-width:none; }}
  html.desk #barra nav.filtri button {{ font-size:.5rem; min-height:36px; padding:2px; border-width:1px; line-height:1.1; }}
  html.desk #barra nav.filtri button span {{ display:block; }}
  .b-extra {{ display:grid; gap:6px; }}
  .b-extra button, .b-naz button {{ font:inherit; font-size:.52rem; font-weight:700; text-align:left; min-height:36px; padding:6px 10px;
         border-radius:9px; background:#161616; color:#fff; border:1px solid #444; cursor:pointer; display:flex; justify-content:space-between; gap:8px; }}
  .b-extra button[aria-pressed="true"], .b-naz button[aria-pressed="true"] {{ background:var(--giallo); color:#000; border-color:var(--giallo); }}
  .b-extra button .c, .b-naz button .c {{ color:#999; font-weight:600; }}
  .b-extra button[aria-pressed="true"] .c, .b-naz button[aria-pressed="true"] .c {{ color:#000; }}
  .b-extra button:disabled {{ opacity:.4; cursor:default; }}
  .b-naz {{ display:grid; gap:4px; margin:6px 0 0 8px; padding-left:8px; border-left:2px solid #333; }}
  .b-naz button {{ min-height:32px; font-weight:600; align-items:center; }}
  .b-naz img.fl {{ width:20px; height:15px; vertical-align:-2px; border-radius:2px; box-shadow:0 0 0 1px #000; }}
  .b-naz .ico {{ display:inline-block; width:20px; text-align:center; }}
  html.desk #ordina-top {{ display:flex; align-items:center; gap:10px; max-width:1000px; margin:6px auto 0; }}
  html.desk #ordina-top .lab {{ font-size:.5rem; font-weight:800; letter-spacing:.08em; color:#8a8a8a; text-transform:uppercase; }}
  html.desk #ordina-top .viste {{ display:flex; gap:6px; }}
  html.desk #ordina-top .viste button {{ font-size:.5rem; min-height:34px; padding:4px 12px; border-width:1px; border-radius:999px; }}
  html.desk .su {{ left:calc(13.5rem + 40px); }}
  html.desk nav.filtri, html.desk .cerca {{ padding-right:0; }}
  .sottotitolo {{ color:#fff; font-size:.62rem; font-weight:600; margin:2px 0 6px; line-height:1.3; opacity:.95; }}
  /* etichette sulle partite: info partita e rivalità */
  .squadre .tags {{ display:inline-flex; flex-wrap:wrap; gap:6px; margin-left:10px; vertical-align:middle; }}
  .tg {{ position:static; font:inherit; font-size:.6rem; font-weight:700; line-height:1.2; padding:5px 11px; min-height:32px; border-radius:999px;
        border:1px solid #444; background:#1a1a1a; color:#ddd; cursor:help; }}
  .squadre {{ position:relative; }}
  li.partita:has(.tg:hover, .tg:focus, .tg.aperto) {{ position:relative; z-index:25; }}
  @media (max-width: 640px) {{ .squadre .tags {{ margin-left:6px; margin-top:4px; }} }}
  .tg-info {{ border-color:#3b82c4; color:#9fd0ff; }}
  .tg-big {{ border-color:#ca8a04; color:var(--giallo); }}
  .tg-salv {{ border-color:#7c3aed; color:#d8b4fe; }}
  .tg-riv {{ border-color:#c2410c; color:#ffb38a; }}
  .tg .tip {{ display:none; position:absolute; z-index:30; left:0; top:calc(100% + 6px); width:max-content; max-width:min(24rem, 86vw, calc(100vw - 560px));
             background:#111; color:#eee; border:1px solid #555; border-radius:8px; padding:9px 12px; font-size:.64rem; font-weight:500;
             text-align:left; line-height:1.4; white-space:normal; box-shadow:0 6px 20px #000c; }}
  .tg .tip-t {{ display:block; font-weight:800; color:#fff; margin-bottom:3px; }}
  .tg .tip-f {{ display:block; color:#888; font-size:.85em; margin-top:4px; }}
  .tg:hover .tip, .tg:focus .tip, .tg.aperto .tip {{ display:block; }}
  @media (max-width: 999px) {{ .tg .tip {{ max-width:86vw; }} }}
  @media (hover: none) {{ .tg:hover .tip {{ display:none; }} .tg.aperto .tip {{ display:block; }} }}
  /* popup info partita */
  .tg .tip-info {{ width:min(24rem, calc(100vw - 16px)); max-width:calc(100vw - 16px); padding:0; overflow:auto; overscroll-behavior:contain; font-size:.8rem;
                  background:linear-gradient(180deg,#16202e,#0f141b); border:1px solid #2f4a6b; border-radius:16px;
                  box-shadow:0 14px 40px #000d, 0 0 0 1px #ffffff0d inset; cursor:default; }}
  .tip-info .ti-h {{ display:block; padding:10px 14px; font-size:.95rem; font-weight:800; color:#fff; letter-spacing:.2px;
                    background:linear-gradient(90deg,#1d4ed8,#0ea5e9); }}
  .tip-info .ti-s {{ display:block; padding:10px 14px 4px; }}
  .tip-info .ti-s + .ti-s {{ border-top:1px solid #ffffff14; }}
  .tip-info .ti-n {{ display:block; font-size:.88rem; font-weight:800; color:var(--giallo, #facc15); margin:2px 2px 8px; text-transform:uppercase; letter-spacing:.4px; }}
  .tip-info .ti-r {{ display:flex; align-items:center; gap:8px; padding:7px 9px; margin-bottom:5px; border-radius:10px; border-left:4px solid; }}
  .tip-info .ti-inf {{ background:#ef44441f; border-color:#ef4444; }}
  .tip-info .ti-sq {{ background:#f59e0b1f; border-color:#f59e0b; }}
  .tip-info .ti-i {{ font-size:1rem; flex:none; }}
  .tip-info .ti-p {{ font-weight:700; color:#fff; flex:1; min-width:0; }}
  .tip-info .ti-m {{ font-size:.72rem; font-weight:700; padding:2px 8px; border-radius:999px; white-space:nowrap; }}
  .tip-info .ti-inf .ti-m {{ background:#ef4444; color:#fff; }}
  .tip-info .ti-sq .ti-m {{ background:#f59e0b; color:#1a1200; }}
  .tip-info .ti-ok {{ display:block; padding:8px 10px; margin-bottom:6px; border-radius:10px; background:#22c55e1f; color:#86efac; font-weight:700; }}
  .tip-info .tip-f {{ padding:6px 16px 10px; color:#7d8ea3; font-size:.68rem; margin:0; }}
  @media (max-width: 640px) {{ .tg .tip-info {{ font-size:.85rem; }}
                              .tip-info .ti-m {{ white-space:normal; text-align:center; }} }}
</style>
</head>
<body>
<div class="zoom" role="group" aria-label="Dimensione del testo"><button type="button" id="zoom-meno" aria-label="Testo più piccolo" title="Testo più piccolo">−</button><button type="button" id="zoom-piu" aria-label="Testo più grande" title="Testo più grande">+</button></div>
<button type="button" class="su" id="torna-su" aria-label="Torna su" hidden>↑ torna su</button>
<aside id="barra" aria-label="Filtri">
  <div id="b-cerca"></div>
  <section class="acc" data-acc="calcio"><div class="acc-h"><button type="button" class="acc-sez" data-sezione="calcio">⚽ CALCIO <span class="n" id="bn-calcio"></span></button><button type="button" class="acc-t" aria-expanded="true" aria-label="Apri o chiudi CALCIO"><span>▾</span></button></div>
    <div class="acc-b"><p class="b-et">Cosa vedere</p><div class="slot" data-slot="scelta-calcio"></div>
      <p class="b-et">Giorno</p><div class="slot" data-slot="giorni-calcio"></div>
      <p class="b-et">Filtra</p><div class="b-extra"><button type="button" id="b-naz-t" aria-expanded="false" aria-pressed="false"><span>🏳️ Per nazione</span> <span class="c">▸</span></button></div>
      <div class="b-naz" id="b-naz" hidden></div></div></section>
  <section class="acc" data-acc="sport"><div class="acc-h"><button type="button" class="acc-sez" data-sezione="sport">🏁 ALTRI SPORT <span class="n" id="bn-sport"></span></button><button type="button" class="acc-t" aria-expanded="true" aria-label="Apri o chiudi ALTRI SPORT"><span>▾</span></button></div>
    <div class="acc-b"><p class="b-et">Cosa vedere</p><div class="slot" data-slot="scelta-altri"></div>
      <p class="b-et">Giorno</p><div class="slot" data-slot="giorni-sport"></div></div></section>
</aside>
<header>
  <h1>SPORT GRATIS E LEGALE IN TV <span class="h1p">{periodo}</span></h1>
  <p class="sottotitolo">Match gentilmente offerti da pay TV e canali pubblici</p>
  <p class="agg">Aggiornato {aggiornato} · orari italiani</p>
</header>
<nav class="sezioni" aria-label="Sezione">
  <button type="button" data-sezione="calcio" aria-pressed="true"><span class="ico" aria-hidden="true">⚽</span> CALCIO <span class="n" id="n-partite">{n}</span></button>
  <button type="button" data-sezione="sport" aria-pressed="false"><span class="ico" aria-hidden="true">🏁</span> ALTRI SPORT <span class="n" id="n-eventi">{n_altri}</span></button>
</nav>
<section class="pannello" data-sez="calcio" aria-label="Opzioni calcio">
  <p class="et">Scegli cosa vuoi vedere:</p>
  <div class="scelta-b quattro" data-gruppo="calcio">{scelta_c}</div>
</section>
<section class="pannello" data-sez="sport" aria-label="Opzioni altri sport" hidden>
  <p class="et">Scegli cosa vuoi vedere:</p>
  <div class="scelta-b due" data-gruppo="altri">{scelta_s}</div>
</section>
<nav class="filtri" data-sez="calcio" aria-label="Calcio: filtra per giorno">{bottoni}</nav>
<nav class="filtri" data-sez="sport" aria-label="Altri sport: filtra per giorno" hidden>{bottoni_s}</nav>
<div class="cerca" role="search"><input id="cerca" type="search" autocomplete="off" spellcheck="false" enterkeyhint="search"
  placeholder="🔍 Cerca squadra, sport, competizione, canale…" aria-label="Cerca squadra, sport, competizione o canale"><button type="button" id="cerca-x" aria-label="Cancella la ricerca" title="Cancella" hidden>✕</button></div>
<p id="nessun-risultato" class="nessun-risultato" role="status" hidden>Nessun risultato per «<span></span>»</p>
<main>
<p class="legenda"><span class="tag">IN CHIARO</span> <span style="color:var(--verde);font-weight:700">canale verde</span> = gratuito (free-to-air) nel suo paese · <span class="tag tb">TELEBOY</span> = si vede su Teleboy (VPN Svizzera) · <span class="tag dz">DAZN GRATIS</span> = senza lucchetto su DAZN (account gratuito)</p>
<div id="vista-campionato" class="vista" data-sez="calcio">
{sezioni}
</div>
<div id="vista-orario" class="vista" data-sez="calcio" hidden>
{orario}
</div>
<div id="vista-sport-tipo" class="vista" data-sez="sport" hidden>
{per_sport}
</div>
<div id="vista-sport-orario" class="vista" data-sez="sport" hidden>
{altri}
</div>
<p class="vuoto" id="vuoto-scelta" hidden>Nessun evento per questa scelta nei giorni selezionati. Tocca <strong>TUTTO</strong> per vedere tutto.</p>
<p class="vuoto" id="vuoto"{vuoto_nascosto}>Nessuna partita in programma in questi giorni.</p>
{avvisi}
{dove}
</main>
<footer>
  {note}
  <p>Fonti: <a href="https://www.livesoccertv.com/">LiveSoccerTV</a> (canali scelti) e
  <a href="https://liveonsat.com/">LiveOnSat</a> (solo canali in chiaro). I palinsesti possono cambiare all'ultimo momento.
  La pagina si aggiorna automaticamente ogni ora.</p>
</footer>
<script>
(function () {{
  var DURATA = {durata};  // secondi dopo il calcio d'inizio oltre i quali la partita sparisce (2h15m)
  function tutti(sel, base) {{ return [].slice.call((base || document).querySelectorAll(sel)); }}
  function leggi(k) {{ try {{ return localStorage.getItem(k); }} catch (e) {{ return null; }} }}
  function salva(k, v) {{ try {{ localStorage.setItem(k, v); }} catch (e) {{}} }}
  // stato: sezione (calcio/sport), vista di ogni sezione, scelta (TUTTO/ELITE/ITALIA), giorno
  var S = {{ sezione: 'calcio', vista: {{ calcio: 'campionato', sport: 'tipo' }}, cat: {{ calcio: 'tutto', altri: 'tutto' }},
            giorno: {{ calcio: 'tutti', sport: 'tutti' }} }};
  var q = location.search;
  var m = /[?&]sezione=(calcio|sport)/.exec(q), mv = /[?&]vista=(orario|campionato|altri)/.exec(q);
  var vecchia = leggi('vista');  // versioni precedenti: vista = campionato / orario / altri
  S.sezione = m ? m[1] : (mv && mv[1] === 'altri') ? 'sport' : (leggi('sezione') || (vecchia === 'altri' ? 'sport' : 'calcio'));
  if (S.sezione !== 'sport') S.sezione = 'calcio';
  // ordinamento: sempre quello predefinito (per campionato / per sport); preferenze vecchie cancellate
  try {{ localStorage.removeItem('vista-calcio'); localStorage.removeItem('vista-sport'); localStorage.removeItem('vista'); }} catch (e) {{}}
  ['calcio', 'altri'].forEach(function (g) {{
    var v = leggi('scelta-' + g);
    if (v && document.querySelector('.scelta-b button[data-gruppo="' + g + '"][data-cat="' + v + '"]')) S.cat[g] = v;
  }});
  try {{ var gs = JSON.parse(sessionStorage.getItem('giorni') || 'null'); if (gs) S.giorno = gs; }} catch (e) {{}}
  // ricerca: minuscole e senza accenti; testo di ogni evento = scheda + titolo della sezione (competizione / sport)
  function piatto(t) {{ return (t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/ı/g, 'i').toLowerCase(); }}
  var campo = document.getElementById('cerca'), cx = document.getElementById('cerca-x');
  try {{ campo.value = sessionStorage.getItem('cerca') || ''; }} catch (e) {{}}
  function cercato() {{ return piatto(campo.value).trim().split(/\\s+/).filter(Boolean); }}
  function trovato(p, parole) {{
    if (!parole.length) return true;
    if (p._t === undefined) {{
      var sz = p.closest('section'), h = sz && sz.querySelector('h2');
      p._t = piatto(p.textContent + ' ' + (h ? h.textContent : ''));
    }}
    return parole.every(function (w) {{ return p._t.indexOf(w) >= 0; }});
  }}
  // filtri extra della barra laterale (solo desktop): coppe europee, nazionali, nazione
  var EXTRA = '';
  function extraOk(p) {{
    if (!EXTRA || !document.documentElement.classList.contains('desk') || sezDi(p) !== 'calcio') return true;
    if (EXTRA === 'coppe' || EXTRA === 'nazionali') return p.dataset.tipo === EXTRA;
    return 'naz:' + (p.dataset.naz || '') === EXTRA;
  }}
  function sezDi(el) {{ return el.closest('[data-sez]').dataset.sez; }}
  function gruppo(sez) {{ return sez === 'sport' ? 'altri' : 'calcio'; }}
  function catOk(p) {{
    var c = S.cat[gruppo(sezDi(p))];
    return c === 'tutto' || (' ' + (p.dataset.cat || '') + ' ').indexOf(' ' + c + ' ') >= 0;
  }}
  function idVista(sez) {{ return sez === 'sport' ? 'vista-sport-' + S.vista.sport : 'vista-' + S.vista.calcio; }}
  function premi(lista, f) {{ lista.forEach(function (b) {{ b.setAttribute('aria-pressed', f(b) ? 'true' : 'false'); }}); }}
  function aggiorna() {{
    var sez = S.sezione, vis = idVista(sez);
    premi(tutti('nav.sezioni button'), function (b) {{ return b.dataset.sezione === sez; }});
    tutti('.pannello, nav.filtri, .intro-altri').forEach(function (el) {{ el.hidden = el.dataset.sez !== sez && !el.closest('#barra'); }});
    tutti('#ordina-top .viste').forEach(function (el) {{ el.hidden = el.dataset.sez !== sez; }});
    tutti('.acc').forEach(function (a) {{ a.classList.toggle('attiva', a.dataset.acc === sez); }});
    tutti('div.vista').forEach(function (d) {{ d.hidden = d.id !== vis; }});
    tutti('.viste').forEach(function (d) {{
      premi(tutti('button', d), function (b) {{ return b.dataset.vista === S.vista[d.dataset.sez]; }});
    }});
    premi(tutti('.scelta-b button'), function (b) {{ return S.cat[b.dataset.gruppo] === b.dataset.cat; }});
    ['calcio', 'sport'].forEach(function (z) {{
      // giorni con ancora qualcosa (con la scelta attiva); se il giorno scelto si è svuotato si torna a "Tutti"
      var restano = {{}};
      tutti('#' + idVista(z) + ' li.partita').forEach(function (p) {{ if (catOk(p)) restano[p.dataset.giorno] = true; }});
      var tasti = tutti('nav.filtri[data-sez="' + z + '"] button');
      tasti.forEach(function (b) {{
        if (b.dataset.filtro === 'tutti') return;
        b.disabled = !restano[b.dataset.filtro];
        if (b.disabled) b.title = 'Niente in programma'; else b.removeAttribute('title');
      }});
      if (S.giorno[z] !== 'tutti' && !restano[S.giorno[z]]) S.giorno[z] = 'tutti';
      premi(tasti, function (b) {{ return b.dataset.filtro === S.giorno[z]; }});
    }});
    var parole = cercato();
    tutti('li.partita').forEach(function (p) {{
      var g = S.giorno[sezDi(p)];
      p.hidden = !((g === 'tutti' || p.dataset.giorno === g) && catOk(p) && trovato(p, parole) && extraOk(p));
    }});
    tutti('section.comp, section.giorno-sez').forEach(function (s) {{ s.hidden = !s.querySelector('li.partita:not([hidden])'); }});
    // PER CAMPIONATO / PER SPORT: sezioni in ordine di primo inizio tra le partite visibili (a parità, ordine fisso)
    ['vista-campionato', 'vista-sport-tipo'].forEach(function (id) {{
      var box = document.getElementById(id);
      var sez = tutti(':scope > section.comp', box);
      var chiave = function (s) {{
        var ts = tutti('li.partita:not([hidden])', s).map(function (p) {{ return +p.dataset.ts; }});
        return [ts.length ? Math.min.apply(null, ts) : Infinity, +s.dataset.ordine];
      }};
      var k = sez.map(function (s) {{ return {{ s: s, k: chiave(s), b: s.dataset.blocco || 'c' }}; }});
      var elite = function (s) {{ return tutti('li.partita:not([hidden])', s).some(function (p) {{ return (' ' + (p.dataset.cat || '') + ' ').indexOf(' elite ') >= 0; }}); }};
      if (id === 'vista-sport-tipo') {{
        // F1 e motomondiale (data-testa) prima degli altri sport elite; con TUTTO poi gli altri elite e infine i non elite;
        // dentro ogni gruppo: primo inizio
        var tt = S.cat.altri === 'tutto';
        var gr = function (s) {{ var el = !tt || elite(s); return el && s.dataset.testa ? 0 : el ? 1 : 2; }};
        k.forEach(function (x) {{ x.k = [gr(x.s)].concat(x.k); }});
        k.sort(function (a, b) {{ return (a.k[0] - b.k[0]) || (a.k[1] - b.k[1]) || (a.k[2] - b.k[2]); }});
      }} else if (id === 'vista-campionato' && S.cat.calcio === 'tutto') {{
        // TUTTO: blocco A (coppe europee + nazionali) e blocco B (Serie A, poi gli altri grandi campionati):
        // prima il blocco con la partita visibile più vicina; il resto (C) sempre in fondo
        var primo = function (bl) {{ return Math.min.apply(null, [Infinity].concat(k.filter(function (x) {{ return bl.indexOf(x.b) >= 0; }}).map(function (x) {{ return x.k[0]; }}))); }};
        var aPrima = primo(['a']) < primo(['b0', 'b']);
        var rango = function (x) {{ return x.b === 'a' ? (aPrima ? 0 : 2) : x.b === 'b0' ? (aPrima ? 1 : 0) : x.b === 'b' ? (aPrima ? 2 : 1) : 3; }};
        k.forEach(function (x) {{ x.k = [rango(x)].concat(x.k); }});
        k.sort(function (a, b) {{ return (a.k[0] - b.k[0]) || (a.k[1] - b.k[1]) || (a.k[2] - b.k[2]); }});
      }} else {{
        k.sort(function (a, b) {{ return (a.k[0] - b.k[0]) || (a.k[1] - b.k[1]); }});
      }}
      if (k.some(function (x, i) {{ return x.s !== sez[i]; }})) {{
        var dopo = sez.length ? sez[sez.length - 1].nextSibling : null;
        k.forEach(function (x) {{ box.insertBefore(x.s, dopo); }});
      }}
    }});
    var conta = function (sel) {{ return tutti(sel).filter(catOk).length; }};
    document.getElementById('n-partite').textContent = conta('#vista-campionato li.partita');
    document.getElementById('n-eventi').textContent = conta('#vista-sport-orario li.partita');
    var qui = tutti('#' + vis + ' li.partita');
    var vuoto = document.getElementById('vuoto');
    if (vuoto) vuoto.hidden = !(sez === 'calcio' && !tutti('#vista-campionato li.partita').length);
    var vs = document.getElementById('vuoto-scelta');
    var visibili = qui.some(function (p) {{ return !p.hidden; }});
    if (vs) vs.hidden = !qui.length || visibili || parole.length > 0;
    var nr = document.getElementById('nessun-risultato');
    nr.hidden = !parole.length || visibili;
    nr.querySelector('span').textContent = campo.value.trim();
    cx.hidden = !campo.value;
    try {{ sessionStorage.setItem('cerca', campo.value); }} catch (e) {{}}
    // "Dove vederli": le voci della sezione attiva
    tutti('li.dove').forEach(function (d) {{ d.hidden = (' ' + d.dataset.sez + ' ').indexOf(' ' + sez + ' ') < 0; }});
    try {{ sessionStorage.setItem('giorni', JSON.stringify(S.giorno)); }} catch (e) {{}}
    tutti('#b-naz button').forEach(function (b) {{ b.setAttribute('aria-pressed', EXTRA === b.dataset.k ? 'true' : 'false'); }});
    var bn = document.getElementById('b-naz-t'); if (bn) bn.setAttribute('aria-pressed', EXTRA ? 'true' : 'false');
    var c1 = document.getElementById('bn-calcio'), c2 = document.getElementById('bn-sport');
    if (c1) c1.textContent = document.getElementById('n-partite').textContent + ' in programma';
    if (c2) c2.textContent = document.getElementById('n-eventi').textContent + ' in programma';
  }}
  tutti('nav.sezioni button').forEach(function (b) {{ b.addEventListener('click', function () {{
    S.sezione = b.dataset.sezione; salva('sezione', S.sezione); aggiorna();
  }}); }});
  tutti('.viste button').forEach(function (b) {{ b.addEventListener('click', function () {{
    var z = sezDi(b); S.vista[z] = b.dataset.vista; salva('vista-' + z, b.dataset.vista); aggiorna();
  }}); }});
  tutti('.scelta-b button').forEach(function (b) {{ b.addEventListener('click', function () {{
    S.cat[b.dataset.gruppo] = b.dataset.cat; salva('scelta-' + b.dataset.gruppo, b.dataset.cat); aggiorna();
  }}); }});
  tutti('nav.filtri button').forEach(function (b) {{ b.addEventListener('click', function () {{
    S.giorno[sezDi(b)] = b.dataset.filtro; aggiorna();
  }}); }});
  campo.addEventListener('input', aggiorna);
  campo.addEventListener('keydown', function (e) {{ if (e.key === 'Escape') {{ campo.value = ''; aggiorna(); }} }});
  cx.addEventListener('click', function () {{ campo.value = ''; aggiorna(); campo.focus(); }});
  // stato: in corso (fino a 2h15m dall'inizio o fino alla fine dell'evento), tra poco (entro 1 ora); finite -> tolte
  function stato() {{
    var ora = Date.now() / 1000;
    tutti('li.partita').forEach(function (p) {{
      var ts = +p.dataset.ts, s = p.querySelector('.stato'), c = '', t = '';
      var fine = p.dataset.fine ? +p.dataset.fine : ts + DURATA;
      if (ora >= fine) {{ p.parentNode.removeChild(p); return; }}
      if (ora >= ts) {{ c = 'in-corso'; t = 'IN CORSO'; }}
      else if (ts - ora <= 3600) {{ c = 'tra-poco'; t = 'TRA ' + Math.max(1, Math.round((ts - ora) / 60)) + ' MIN'; }}
      p.classList.remove('in-corso', 'tra-poco');
      if (c) p.classList.add(c);
      s.textContent = t;
    }});
    aggiorna();
  }}
  stato();
  setInterval(stato, 60000);
  // ---- desktop: barra laterale (gli stessi comandi vengono spostati; su telefono restano dove sono) ----
  var SPOSTA = [['.cerca', 'b-cerca'], ['.scelta-b[data-gruppo="calcio"]', 'scelta-calcio'], ['.scelta-b[data-gruppo="altri"]', 'scelta-altri'],
               ['nav.filtri[data-sez="calcio"]', 'giorni-calcio'], ['nav.filtri[data-sez="sport"]', 'giorni-sport'],
               ];
  var segni = SPOSTA.map(function (x) {{
    var el = document.querySelector(x[0]); var seg = document.createComment('posto');
    if (el) el.parentNode.insertBefore(seg, el);
    return {{ el: el, seg: seg, slot: x[1] === 'b-cerca' ? document.getElementById('b-cerca') : document.querySelector('[data-slot="' + x[1] + '"]') }};
  }});
  var mq = window.matchMedia('(min-width: 1000px)');
  function layout() {{
    var desk = mq.matches;
    document.documentElement.classList.toggle('desk', desk);
    segni.forEach(function (x) {{
      if (!x.el) return;
      if (desk) x.slot.appendChild(x.el); else x.seg.parentNode.insertBefore(x.el, x.seg.nextSibling);
      if (!desk) x.el.hidden = false;
    }});
    campo.placeholder = desk ? 'Cerca squadra, sport, canale…' : '🔍 Cerca squadra, sport, competizione, canale…';
    if (!desk) EXTRA = '';
    aggiorna();
  }}
  if (mq.addEventListener) mq.addEventListener('change', layout); else mq.addListener(layout);
  tutti('.acc').forEach(function (a) {{
    var z = a.dataset.acc, t = a.querySelector('.acc-t');
    function chiudi(c) {{ a.classList.toggle('chiuso', c); t.setAttribute('aria-expanded', c ? 'false' : 'true'); }}
    chiudi(leggi('acc-' + z) === 'chiuso');
    t.addEventListener('click', function () {{ var c = !a.classList.contains('chiuso'); chiudi(c); salva('acc-' + z, c ? 'chiuso' : 'aperto'); }});
    a.querySelector('.acc-b').addEventListener('click', function () {{ if (S.sezione !== z) {{ S.sezione = z; salva('sezione', z); }} }}, true);
    a.querySelector('.acc-sez').addEventListener('click', function () {{ S.sezione = z; salva('sezione', z); aggiorna(); }});
  }});
  // "Per nazione": Coppe europee, Nazionali e le nazioni (ordine fisso, poi le altre per numero di partite);
  // da martedì a giovedì (ora italiana), se oggi ci sono partite di coppa, le Coppe europee vanno in cima; altrimenti dopo le nazioni
  (function () {{
    var box = document.getElementById('b-naz'), tasto = document.getElementById('b-naz-t');
    if (!box) return;
    var conta = {{}}, fl = {{}}, tipi = {{ coppe: 0, nazionali: 0 }};
    tutti('#vista-campionato li.partita').forEach(function (p) {{
      if (p.dataset.naz) {{ conta[p.dataset.naz] = (conta[p.dataset.naz] || 0) + 1; fl[p.dataset.naz] = p.dataset.fl; }}
      if (p.dataset.tipo) tipi[p.dataset.tipo]++;
    }});
    var FISSO = ['Italia', 'Inghilterra', 'Spagna', 'Germania', 'Francia', 'Olanda', 'Portogallo', 'Belgio', 'Svizzera'];
    var nazioni = Object.keys(conta).sort(function (a, b) {{
      var ia = FISSO.indexOf(a), ib = FISSO.indexOf(b);
      if (ia >= 0 || ib >= 0) return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
      return conta[b] - conta[a] || a.localeCompare(b);
    }});
    var gg = new Date().toLocaleDateString('en-GB', {{ timeZone: 'Europe/Rome', weekday: 'short' }});
    var oggi = new Date().toLocaleDateString('en-CA', {{ timeZone: 'Europe/Rome' }});  // AAAA-MM-GG
    var coppeOggi = !!document.querySelector('#vista-campionato li.partita[data-tipo="coppe"][data-giorno="' + oggi + '"]');
    var coppeSu = (gg === 'Tue' || gg === 'Wed' || gg === 'Thu') && coppeOggi;  // in cima solo se oggi ci sono partite di coppa
    var voci = nazioni.map(function (n) {{ return {{ k: 'naz:' + n, t: n, n: conta[n], fl: fl[n] }}; }});
    var speciali = [{{ k: 'coppe', t: 'Coppe europee', n: tipi.coppe, ico: '🏆' }}, {{ k: 'nazionali', t: 'Nazionali', n: tipi.nazionali, ico: '🌍' }}]
      .filter(function (x) {{ return x.n > 0; }});
    voci = coppeSu ? speciali.concat(voci) : voci.concat(speciali);
    voci.forEach(function (v) {{
      var b = document.createElement('button'); b.type = 'button'; b.dataset.k = v.k; b.setAttribute('aria-pressed', 'false');
      var l = document.createElement('span'); l.className = 'nm';
      if (v.fl) {{ var i = document.createElement('img'); i.className = 'fl'; i.src = 'flags/' + v.fl + '.svg'; i.alt = ''; i.width = 20; i.height = 15; l.appendChild(i); }}
      else {{ var e = document.createElement('span'); e.className = 'ico'; e.textContent = v.ico || '🏳️'; l.appendChild(e); }}
      l.appendChild(document.createTextNode(' ' + v.t));
      var c = document.createElement('span'); c.className = 'c'; c.textContent = v.n;
      b.appendChild(l); b.appendChild(c);
      b.addEventListener('click', function () {{ EXTRA = EXTRA === v.k ? '' : v.k; aggiorna(); }});
      box.appendChild(b);
    }});
    tasto.addEventListener('click', function () {{
      box.hidden = !box.hidden; tasto.setAttribute('aria-expanded', box.hidden ? 'false' : 'true');
      tasto.querySelector('.c').textContent = box.hidden ? '▸' : '▾';
      if (box.hidden && EXTRA) {{ EXTRA = ''; aggiorna(); }}
    }});
  }})();
  // tieni sempre il popup dentro lo schermo: sposta a sinistra/destra, apri verso l'alto, scroll interno
  function posizionaTip(t) {{
    var p = t.querySelector('.tip'); if (!p) return;
    p.style.left = ''; p.style.top = ''; p.style.bottom = ''; p.style.maxHeight = '';
    var M = 8, vw = document.documentElement.clientWidth, vh = window.innerHeight;
    var r = p.getBoundingClientRect(); if (!r.width) return;
    var z = r.width / (p.offsetWidth || r.width) || 1;
    var dx = 0;
    if (r.right > vw - M) dx = vw - M - r.right;
    if (r.left + dx < M) dx = M - r.left;
    if (dx) p.style.left = (p.offsetLeft + dx / z) + 'px';
    var b = t.getBoundingClientRect(), sotto = vh - b.bottom - M - 6, sopra = b.top - M - 6;
    if (r.height > sotto && sopra > sotto) {{ p.style.top = 'auto'; p.style.bottom = 'calc(100% + 6px)'; p.style.maxHeight = (sopra / z) + 'px'; }}
    else p.style.maxHeight = (Math.max(sotto, 120) / z) + 'px';
    p.style.overflowY = 'auto';
  }}
  document.addEventListener('mouseover', function (ev) {{
    var t = ev.target.closest && ev.target.closest('.tg');
    if (t && !(ev.relatedTarget && t.contains(ev.relatedTarget))) posizionaTip(t);
  }});
  document.addEventListener('focusin', function (ev) {{ var t = ev.target.closest && ev.target.closest('.tg'); if (t) posizionaTip(t); }});
  // etichette: un tocco apre/chiude la spiegazione, un tocco altrove la chiude
  document.addEventListener('click', function (ev) {{
    var t = ev.target.closest && ev.target.closest('.tg');
    tutti('.tg.aperto').forEach(function (x) {{ if (x !== t) x.classList.remove('aperto'); }});
    if (t) t.classList.toggle('aperto');
    if (t && t.classList.contains('aperto')) posizionaTip(t);
  }});
  layout();
  // ogni clic su un filtro o comando (nazione, coppe, sezione, scelta, giorno, fisarmonica, X della ricerca) riporta la pagina in cima,
  // così l'elenco filtrato si vede dall'inizio; zoom e digitazione nella ricerca no
  document.addEventListener('click', function (ev) {{
    var b = ev.target.closest && ev.target.closest('button');
    if (!b || b.closest('.zoom') || b.id === 'torna-su') return;
    if (!b.closest('#barra, nav.sezioni, section.pannello, nav.filtri, .cerca, .scelta-b')) return;
    setTimeout(function () {{ window.scrollTo(0, 0); }}, 0);
  }});
  // zoom (70%-160%, salvato) e "torna su"
  var PASSI = [0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.35, 1.5, 1.6];
  function zoomOra() {{ var z = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--zoom')); return z > 0 ? z : 1; }}
  function zoom(d) {{
    var z = zoomOra(), i = 0;
    PASSI.forEach(function (x, k) {{ if (Math.abs(x - z) < Math.abs(PASSI[i] - z)) i = k; }});
    z = PASSI[Math.max(0, Math.min(PASSI.length - 1, i + d))];
    document.documentElement.style.setProperty('--zoom', z); salva('zoom', z);
    document.getElementById('zoom-meno').disabled = z <= PASSI[0];
    document.getElementById('zoom-piu').disabled = z >= PASSI[PASSI.length - 1];
  }}
  document.getElementById('zoom-meno').addEventListener('click', function () {{ zoom(-1); }});
  document.getElementById('zoom-piu').addEventListener('click', function () {{ zoom(1); }});
  zoom(0);
  var su = document.getElementById('torna-su');
  function mostraSu() {{ var m = document.querySelector('main'); su.hidden = !m || window.scrollY < m.offsetTop; }}
  window.addEventListener('scroll', mostraSu, {{ passive: true }});
  su.addEventListener('click', function () {{ window.scrollTo({{ top: 0, behavior: 'smooth' }}); }});
  mostraSu();
  // ricarica la pagina ogni 30 minuti per prendere gli aggiornamenti
  setTimeout(function () {{ location.reload(); }}, 30 * 60 * 1000);
}})();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="Genera la pagina del palinsesto calcio in TV.")
    ap.add_argument("--canali", default=str(RADICE / "canali.json"))
    ap.add_argument("--liveonsat", default=str(RADICE / "liveonsat.json"), help="configurazione LiveOnSat")
    ap.add_argument("--senza-liveonsat", action="store_true", help="usa solo LiveSoccerTV")
    ap.add_argument("--dove", default=str(RADICE / "dove_vederli.json"), help="link 'Dove vederli'")
    ap.add_argument("--teleboy", default=str(RADICE / "teleboy_canali.json"), help="elenco canali Teleboy")
    ap.add_argument("--teleboy-offline", action="store_true", help="non rilegge la pagina Teleboy, usa solo la copia")
    ap.add_argument("--senza-dazn", action="store_true", help="non legge la guida DAZN")
    ap.add_argument("--senza-primaplay", action="store_true", help="non legge il programma Prima Sport (Prima Play)")
    ap.add_argument("--senza-digisport", action="store_true", help="non legge il programma Digi Sport (Romania)")
    ap.add_argument("--senza-altri-sport", action="store_true", help="non legge SRF/RTS/RSI/ARD")
    ap.add_argument("--out", default=str(RADICE / "site"))
    ap.add_argument("--ora", help="data/ora di riferimento ISO (per test), es. 2026-10-10T18:00+02:00")
    ap.add_argument("--json", action="store_true", help="scrive anche palinsesto.json")
    ap.add_argument("--senza-extra", action="store_true", help="niente assenze FotMob (le rivalità restano)")
    a = ap.parse_args()

    ora = dt.datetime.fromisoformat(a.ora) if a.ora else dt.datetime.now(ROMA)
    if ora.tzinfo is None:
        ora = ora.replace(tzinfo=ROMA)
    canali = json.loads(Path(a.canali).read_text(encoding="utf-8"))["canali"]
    primo, inizio, fine = finestra(ora)
    file_dove = Path(a.dove)
    dove = json.loads(file_dove.read_text(encoding="utf-8")).get("voci", []) if file_dove.exists() else []
    conf_los = None if a.senza_liveonsat else json.loads(Path(a.liveonsat).read_text(encoding="utf-8"))
    st = {}
    tb = None
    if Path(a.teleboy).exists():
        tb = teleboy_mod.carica(a.teleboy, aggiorna=not a.teleboy_offline)
        print(f"Teleboy: {tb.n} canali gratuiti ({tb.fonte})")
    conf_dazn = None if a.senza_dazn else {"file_esterno": str(RADICE / "dati" / "dazn.json")}
    conf_altri = None if a.senza_altri_sport else {}
    conf_pp = None if a.senza_primaplay else {}
    conf_digi = None if a.senza_digisport else {}
    gruppi, falliti, senza = raccogli(canali, inizio, fine, conf_los, st, tb, conf_dazn, conf_altri, conf_pp, conf_digi, {})
    n_tutte = sum(len(g["partite"]) for g in gruppi)
    gruppi = togli_finite(gruppi, dt.datetime.now(ROMA))
    st["finite_tolte"] = n_tutte - sum(len(g["partite"]) for g in gruppi)

    if not a.senza_extra:
        print("Etichette partite:", extra_mod.arricchisci(gruppi, [primo + dt.timedelta(days=i) for i in range(GIORNI_FINESTRA)]))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in (RADICE / "static").iterdir():
        if f.is_file():
            shutil.copy2(f, out / f.name)
        elif f.is_dir():  # es. static/flags (bandiere SVG locali, flag-icons MIT)
            shutil.copytree(f, out / f.name, dirs_exist_ok=True)
    (out / "index.html").write_text(genera_html(primo, dt.datetime.now(ROMA), gruppi, falliti, senza, dove, st.get("altri_sport")), encoding="utf-8")
    if a.json:
        dati = [{"competizione": g["nome"], "partite": [
            {"quando": e["quando"].isoformat(), "partita": f'{e["casa"]} - {e["ospite"]}'.rstrip(" -"),
             "canali": e["canali"], "fonti": e["fonti"]}
            for e in g["partite"]]} for g in gruppi]
        (out / "palinsesto.json").write_text(json.dumps(
            {"periodo": periodo(primo), "dal": str(primo), "gruppi": dati, "falliti": falliti, "senza_partite": senza},
            ensure_ascii=False, indent=1), encoding="utf-8")

    n = sum(len(g["partite"]) for g in gruppi)
    print(f"{periodo(primo)}: {n} partite in {len(gruppi)} competizioni; falliti: {len(falliti)}")
    print(f"  LiveSoccerTV: {st['livesoccertv']} · LiveOnSat (con canali in chiaro): {st['liveonsat']} · "
          f"doppioni uniti: {len(st['uniti'])} · solo LiveOnSat: {st['solo_liveonsat']} · finite tolte: {st['finite_tolte']} · solo grazie a Teleboy: {st.get('solo_teleboy', 0)}")
    for k, x in epg_teleboy.STAT_GUIDE.items():
        print(f"  guida extra {k}: {x if isinstance(x, str) else str(x) + ' dirette'}")
    for x in sorted(set(VPN_MANCANTI)):
        print("  link senza VPN:", x)
    for x in altri_sport.BASKET_TOLTI:
        print("  basket tolto:", x)
    if "primaplay" in st:
        pp = st["primaplay"]
        print(f"  Prima Play (programma Prima Sport): {pp.get('errore') or str(pp.get('calcio', 0)) + ' partite di calcio, ' + str(pp.get('altri', 0)) + ' altri sport'}"
              f" · unite: {len(st.get('uniti_pp', []))} · nuove: {len(st.get('nuove_pp', []))}")
        for x in st.get("nuove_pp", []):
            print("    nuova:", x)
    if "scooore" in st:
        sc = st["scooore"]
        print(f"  Scooore (guida Samsung TV Plus CH, i.mjh.nz): {sc['errore'] or str(sc['partite']) + ' partite in guida'} · "
              f"aggiunto a partite confermate: {sc['unite']}")
    if "digisport" in st:
        dg = st["digisport"]
        print(f"  Digi Sport: {dg.get('calcio', 0)} partite di calcio, {dg.get('altri', 0)} altri sport · unite: "
              f"{len(st.get('uniti_dg', []))} · nuove: {len(st.get('nuove_dg', []))} · calcio Romania/Est escluso: {len(dg.get('calcio_escluso', []))}")
        for x in dg.get("canali_falliti", []):
            print("    NON RAGGIUNGIBILE:", x)
        for x in st.get("nuove_dg", []):
            print("    nuova:", x)
        for x in st.get("uniti_dg", []):
            print("    unita:", x)
    if "dazn" in st:
        print(f"  DAZN gratis per paese: {st['dazn']} · unite a partite già presenti: {len(st['uniti_dazn'])} "
              f"· solo DAZN: {st['solo_dazn']}")
        for r in st["dazn_dettagli"]:
            print("  ", r)
    if "calcio_stream" in st:
        if st.get("euroleague_tv"):
            el = st["euroleague_tv"]
            print(f"  EuroLeague/EuroCup TV Listings: {el.get('eventi', 0)} partite · fonte {el.get('fonte')}")
            for x in el.get("errori", []):
                print("    (solo log) TV Listings non letta:", x)
        if st.get("altri_los"):
            print(f"  LiveOnSat altri sport: {st['altri_los']}")
        al = st["altri_sport"]
        print(f"  Altri sport per fonte: Teleboy (guida TV) {sum(any(x.get('teleboy') for x in e['emittenti']) for e in al)} · "
              f"DAZN Italia {sum(any(x.get('dazn_gratis') for x in e['emittenti']) for e in al)} · "
              f"SRG/ARD {sum(any(not x.get('teleboy') and not x.get('dazn_gratis') and not x.get('pp') for x in e['emittenti']) for e in al)} · "
              f"Prima Play {sum(any(x.get('pp') for x in e['emittenti']) for e in al)}")
        print(f"  Altri sport: {len(st['altri_sport'])} eventi · calcio in streaming: {st['calcio_stream']} "
              f"(uniti a partite già presenti: {len(st['uniti_stream'])})")
    for n, m in sorted(st.get("canali_ru_ir", {}).items()):
        print(f"  canale russo/iraniano escluso: {n} – {m}")
    for x in st.get("tolte_esclusi", []):
        print("  partita tolta (nessun canale rimasto):", x)
    for x in st.get("programmi_tolti", []):
        print("  programma sportivo tolto:", x)
    for x in st.get("femminili_tolte", []):
        print("  esclusa (calcio femminile o USA):", x)
    for f in falliti:
        print("  FALLITO:", f)
    # se nessun canale è stato scaricato, esce con errore: così il deploy non sostituisce la pagina buona
    nomi = {c["nome"] for c in canali if "dazn" not in (c["nome"] + c["url"]).lower()}
    lstv_ko = nomi and len({f.split(" (")[0] for f in falliti if not f.startswith(("LiveOnSat", "DAZN"))}) >= len(nomi)
    los_ko = not conf_los or st.get("pagine_liveonsat_fallite", 0) >= st.get("pagine_liveonsat", 0)
    if lstv_ko and los_ko:
        print("ERRORE: nessuna fonte scaricata (siti irraggiungibili o bloccati).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
