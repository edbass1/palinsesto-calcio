#!/usr/bin/env python3
"""Palinsesto calcio in TV da LiveSoccerTV + LiveOnSat (canali in chiaro) -> pagina statica.
Solo libreria standard Python 3.9+."""
import argparse
import concurrent.futures as cf
import datetime as dt
import html
import json
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
import dazn  # noqa: E402
import altri_sport  # noqa: E402

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


# ---------- finestra: oggi + 3 giorni ----------
GIORNI_FINESTRA = 4
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
    """Da oggi alle 00:00 (Europe/Rome) alla fine del 3° giorno successivo: 4 giorni di calendario."""
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
            "canali": [{"nome": f'{x["nome"]} stream', "fta": True, "url": x["pagina"], "diretta": x["link"], "vpn": x["vpn"]}
                       for x in p["emittenti"]],
            "fonti": ["Streaming"]}


def unisci_stream(eventi, partite):
    uniti = []
    for p in partite:
        nuovo = evento_stream(p)
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
            if k["nome"] not in [c["nome"] for c in migliore["canali"]]:
                migliore["canali"].append(k)
        migliore["fonti"].append("Streaming")
        uniti.append(f'{migliore["casa"]} - {migliore["ospite"]}')
    return eventi, uniti


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


def raggruppa(eventi):
    gruppi = {}
    for e in eventi:
        gruppi.setdefault((e["ordine"], e["competizione"]), []).append(e)
    return [{"nome": nome, "partite": sorted(gruppi[(o, nome)], key=lambda e: (e["ts"], e["casa"]))}
            for (o, nome) in sorted(gruppi)]


def raccogli(canali, inizio, fine, conf_los=None, statistiche=None, teleboy=None, conf_dazn=None, conf_altri=None):
    """Raccoglie da LiveSoccerTV e (se conf_los) da LiveOnSat, unisce e raggruppa per competizione."""
    eventi, falliti, senza = raccogli_lstv(canali, inizio, fine)
    # calcio femminile escluso da tutte le fonti (liveonsat.json -> escludi_competizioni)
    rx_f = unisci.regex_femminile((conf_los or {}).get("escludi_competizioni", []))
    tolte_f = []

    def fem(comp, squadre, nome):
        if unisci.femminile(rx_f, comp, squadre):
            tolte_f.append(nome)
            return True
        return False

    eventi = [e for e in eventi if not fem(e.get("comp_orig", ""), (e["casa"], e["ospite"]),
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
    st["altri_sport"] = []
    if conf_altri is not None:
        altri, calcio_stream, avvisi = altri_sport.raccogli_altri(
            inizio, fine, conf_altri.get("ora") or dt.datetime.now(ROMA), rx_f,
            scarica_srg_fn=conf_altri.get("scarica_srg_fn"), scarica_ard_fn=conf_altri.get("scarica_ard_fn"))
        falliti += avvisi
        st["altri_sport"] = altri
        eventi, st["uniti_stream"] = unisci_stream(eventi, calcio_stream)
        st["calcio_stream"] = len(calcio_stream)
    # esclusioni permanenti (liveonsat.json -> escludi_canali) applicate a tutte le fonti
    escludi = ["dazn"] + [x.lower() for x in (conf_los or {}).get("escludi_canali", []) if x]
    st["tolte_esclusi"] = []
    rimasti = []
    for e in eventi:
        # i canali DAZN delle altre fonti sono esclusi; restano solo le partite gratis prese dalla guida DAZN
        e["canali"] = [k for k in e["canali"]
                       if k.get("dazn_gratis") or not any(x in k["nome"].lower() for x in escludi)]
        if e["canali"]:
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


def genera_html(primo, ora, gruppi, falliti, senza, dove=None, altri=None):
    esc = html.escape
    ora_r = ora.astimezone(ROMA)
    aggiornato = f"{GIORNI_LUNGHI[ora_r.weekday()]} {ora_r:%d/%m/%Y} alle {ora_r:%H:%M}"
    giorni = [(primo + dt.timedelta(days=i)) for i in range(GIORNI_FINESTRA)]
    dove = dove or []
    for v in dove:
        v.pop("_canali_pagina", None)
    n_partite = sum(len(g["partite"]) for g in gruppi)

    sezioni, usati = [], set()

    def scheda(e, comp=None):
        q = e["quando"]
        notte = q.hour < 6
        squadre = f'<span class="sq">{esc(e["casa"])}</span>'
        if e["ospite"]:
            squadre += f' <span class="vs">–</span> <span class="sq">{esc(e["ospite"])}</span>'
        if comp:
            squadre = f'<span class="comp-tag">{esc(comp)}</span>' + squadre
        canali = "".join(badge(c, dove, usati) for c in e["canali"])
        return (f'<li class="partita" data-ts="{e["ts"]}" data-giorno="{q:%Y-%m-%d}">'
                f'<div class="quando"><span class="giorno">{GIORNI[q.weekday()]} {q:%d/%m}</span>'
                f'<span class="ora">{q:%H:%M}</span>'
                + (f'<span class="notte">notte tra {GIORNI[(q.weekday() - 1) % 7].lower()} e {GIORNI[q.weekday()].lower()}</span>' if notte else '') +
                '<span class="stato" aria-live="polite"></span></div>'
                f'<div class="squadre">{squadre}</div>'
                f'<ul class="canali" aria-label="Canali">{canali}</ul></li>')

    # vista "per campionato"
    for g in gruppi:
        sezioni.append(f'<section class="comp"><h2>{esc(g["nome"])}</h2>'
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
        em = "".join(
            f'<li class="fta"><a href="{esc(x["pagina"])}" target="_blank" rel="noopener">{esc(x["nome"])}</a> '
            + (f'<span class="tag vpn">VPN {esc(x["vpn"])}</span>' if x.get("vpn") else '<span class="tag vpn">SENZA VPN</span>')
            + f' <a class="diretta" href="{esc(x["link"])}" target="_blank" rel="noopener">▶ diretta</a></li>'
            for x in e["emittenti"])
        return (f'<li class="partita evento" data-ts="{e["ts"]}" data-fine="{e["fine"]}" data-giorno="{q:%Y-%m-%d}">'
                f'<div class="quando"><span class="giorno">{GIORNI[q.weekday()]} {q:%d/%m}</span>'
                f'<span class="ora">{q:%H:%M}</span><span class="fino">fino alle {f:%H:%M}</span>'
                '<span class="stato" aria-live="polite"></span></div>'
                f'<div class="squadre"><span class="comp-tag">{esc(e["sport"].upper())}</span>'
                f'<span class="sq">{esc(e["titolo"])}</span></div>'
                f'<ul class="canali" aria-label="Dove">{em}</ul></li>')
    sez_altri = []
    for d in giorni:
        del_giorno = [e for e in altri if dt.datetime.fromtimestamp(e["ts"], ROMA).date() == d]
        if del_giorno:
            sez_altri.append(f'<section class="giorno-sez" data-giorno="{d:%Y-%m-%d}">'
                             f'<h2 class="giorno-h">{GIORNI_LUNGHI[d.weekday()].upper()} {d.day} {MESI[d.month - 1].upper()}</h2>'
                             f'<ol class="partite">{"".join(scheda_altro(e) for e in del_giorno)}</ol></section>')
    if not sez_altri:
        sez_altri.append('<p class="vuoto">Nessun altro sport in diretta streaming in questi giorni.</p>')

    avvisi = ""
    if falliti:
        avvisi += ('<section class="avviso"><h2>⚠ Canali o pagine non scaricati</h2><ul>'
                   + "".join(f"<li>{esc(f)}</li>" for f in falliti) + "</ul></section>")
    note = ""
    if senza:
        note += f'<p>Canali senza partite in questi giorni: {esc(", ".join(senza))}.</p>'

    per_giorno = {}
    for g in gruppi:
        for e in g["partite"]:
            per_giorno[e["quando"].date()] = per_giorno.get(e["quando"].date(), 0) + 1
    bottoni = '<button type="button" data-filtro="tutti" aria-pressed="true">Tutti</button>' + "".join(
        f'<button type="button" data-filtro="{d:%Y-%m-%d}" aria-pressed="false"'
        + ('' if per_giorno.get(d) else ' disabled title="Nessuna partita (o già giocate)"')
        + f'><span>{GIORNI[d.weekday()]}</span> <span>{d.day}</span></button>'
        for d in giorni)

    return TEMPLATE.format(
        periodo=esc(periodo(primo)), aggiornato=esc(aggiornato), n=n_partite,
        bottoni=bottoni, sezioni="\n".join(sezioni), orario="\n".join(orario), avvisi=avvisi, note=note,
        altri="\n".join(sez_altri), n_altri=len(altri),
        dove=sezione_dove(dove, usati), durata=DURATA_PARTITA_S,
        vuoto_nascosto=' hidden' if gruppi else '')


# ---------- "Dove vederli" ----------
def voce_dove(nome: str, dove):
    for v in dove:
        if any(re.search(rx, nome, re.I) for rx in v.get("canali", [])):
            return v
    return None


def badge(c, dove, usati):
    esc = html.escape
    testo = esc(c["nome"])
    if c.get("dazn_gratis"):
        testo = f'{testo} <span class="tag dz" aria-label="gratis su DAZN con account gratuito">DAZN GRATIS</span>'
    if c.get("teleboy"):
        testo = f'{testo} <span class="tag tb" aria-label="su Teleboy">TELEBOY</span>'
    if c["fta"]:
        testo = f'<span class="tag" aria-label="in chiaro">IN CHIARO</span> {testo}'
    # priorità: voci dell'utente, poi Teleboy, poi le altre
    if c.get("url"):  # diretta streaming: link alla pagina dell'evento
        testo = (f'<a href="{esc(c["url"])}" target="_blank" rel="noopener">{testo}</a>'
                 + (f' <span class="tag vpn">VPN {esc(c["vpn"])}</span>' if c.get("vpn") else ' <span class="tag vpn">SENZA VPN</span>')
                 + (f' <a class="diretta" href="{esc(c["diretta"])}" target="_blank" rel="noopener">▶ diretta</a>' if c.get("diretta") else ''))
        return f'<li class="fta">{testo}</li>' if c["fta"] else f'<li>{testo}</li>'
    v_tb = next((x for x in dove if x["id"] == "teleboy"), None) if c.get("teleboy") else None
    if v_tb is not None:
        v_tb.setdefault("_canali_pagina", set()).add(c["nome"])
        usati.add("teleboy")
    v = voce_dove(c["nome"], [x for x in dove if x.get("fonte") == "utente" and x["id"] != "teleboy"]) or v_tb
    extra = (f' <a class="diretta" href="{esc(c["teleboy_link"])}" target="_blank" rel="noopener" '
             f'title="Canale {esc(c["teleboy"])} su Teleboy">▶ Teleboy</a>') if c.get("teleboy_link") else ""
    if not v:
        v = voce_dove(c["nome"], dove)
    if v:
        usati.add(v["id"])
        testo = f'<a href="#dv-{esc(v["id"])}" title="Dove vederlo">{testo}</a>'
    testo += extra
    return f'<li class="fta">{testo}</li>' if c["fta"] else f'<li>{testo}</li>'


def sezione_dove(dove, usati):
    """Voci inserite dall'utente sempre; quelle trovate con la ricerca solo se servono a qualche partita."""
    esc = html.escape
    voci = [v for v in dove if v.get("fonte") == "utente" or v["id"] in usati]
    if not voci:
        return ""
    righe = []
    for v in voci:
        link = "".join(
            f'<li><a href="{esc(l["url"])}" target="_blank" rel="noopener noreferrer">{esc(l.get("testo") or l["url"])}</a>'
            + ('' if l.get("verificato", v.get("verificato", True)) else ' <span class="verifica">link da verificare</span>')
            + '</li>' for l in v.get("link", []))
        righe.append(
            f'<li class="dove" id="dv-{esc(v["id"])}"><h3>{esc(v["nome"])}</h3>'
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
<title>Calcio in TV · {periodo}</title>
<meta name="description" content="Partite di calcio in TV oggi e nei prossimi 3 giorni, orari italiani.">
<meta name="theme-color" content="#000000">
<meta name="color-scheme" content="dark">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="apple-mobile-web-app-title" content="Calcio TV">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<style>
  :root {{ --giallo:#ffd400; --azzurro:#8fe3ff; --grigio:#bdbdbd; --verde:#00e676; --rosso:#ff5252; }}
  * {{ box-sizing:border-box; }}
  [hidden] {{ display:none !important; }}
  html {{ font-size:24px; -webkit-text-size-adjust:100%; }}
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
  nav.viste {{ max-width:1000px; margin:4px auto 0; display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
  nav.viste button.altri {{ grid-column:1 / -1; border-color:var(--azzurro); }}
  .tag.vpn {{ background:#ffd400; color:#000; }}
  .fino {{ font-size:.85rem; color:#ccc; }}
  a.diretta {{ font-size:.85rem; color:#fff; }}
  .intro-altri {{ font-size:1.05rem; color:#ddd; }}
  nav.viste button {{ font:inherit; font-size:1.05rem; font-weight:900; letter-spacing:.02em; min-height:72px; padding:8px 10px;
               border-radius:14px; background:#111; color:#fff; border:3px solid #888; cursor:pointer; line-height:1.15; }}
  nav.viste button[aria-pressed="true"] {{ background:#fff; color:#000; border-color:#fff; box-shadow:0 0 0 3px var(--giallo); }}
  nav.viste button[aria-pressed="true"]::before {{ content:"✓ "; }}
  nav.viste button:focus-visible {{ outline:4px solid var(--azzurro); outline-offset:3px; }}
  h2.giorno-h {{ background:#fff; color:#000; }}
  section.giorno-sez {{ margin-top:36px; }}
  .comp-tag {{ display:block; width:max-content; max-width:100%; background:var(--giallo); color:#000; font-size:.8rem; font-weight:900;
               padding:2px 10px; border-radius:7px; margin-bottom:6px; letter-spacing:.02em; overflow-wrap:anywhere; }}
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
  .h1p {{ color:var(--giallo); }}
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
    html {{ font-size:21px; }}
    h1 {{ font-size:1.6rem; }}
    li.partita {{ grid-template-columns:1fr; grid-template-areas:"quando" "squadre" "canali"; padding:14px; }}
    .quando {{ flex-direction:row; align-items:baseline; flex-wrap:wrap; gap:4px 12px; }}
    .stato {{ margin-top:0; align-self:center; }}
    nav.filtri {{ display:grid; grid-template-columns:repeat(5, 1fr); gap:6px; }}
    nav.filtri button {{ padding:4px 2px; min-height:64px; font-size:.95rem; line-height:1.1; border-radius:10px; }}
    nav.filtri button span {{ display:block; }}
    li.partita {{ grid-template-rows:auto; }}
  }}
</style>
</head>
<body>
<header>
  <h1>⚽ Calcio in TV <span class="h1p">· {periodo}</span></h1>
  <p class="agg">Aggiornato {aggiornato} · <span id="n-partite">{n}</span> partite · orari italiani</p>
  <p class="legenda"><span class="tag">IN CHIARO</span> <span style="color:var(--verde);font-weight:700">canale verde</span> = gratuito (free-to-air) nel suo paese · <span class="tag tb">TELEBOY</span> = si vede su Teleboy (VPN Svizzera) · <span class="tag dz">DAZN GRATIS</span> = partita senza lucchetto su DAZN (account gratuito)</p>
</header>
<nav class="viste" aria-label="Come ordinare le partite">
  <button type="button" data-vista="campionato" aria-pressed="true">PER CAMPIONATO</button>
  <button type="button" data-vista="orario" aria-pressed="false">IN ORDINE DI ORARIO</button>
  <button type="button" data-vista="altri" aria-pressed="false" class="altri">ALTRI SPORT <span class="n">({n_altri})</span></button>
</nav>
<nav class="filtri" aria-label="Filtra per giorno">{bottoni}</nav>
<main>
<div id="vista-campionato" class="vista">
{sezioni}
</div>
<div id="vista-orario" class="vista" hidden>
{orario}
</div>
<div id="vista-altri" class="vista" hidden>
<p class="intro-altri">Dirette streaming gratuite di altri sport: SRF, RTS, RSI (Svizzera) e ARD (Germania). Tocca l'emittente per aprire la diretta.</p>
{altri}
</div>
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
  var bottoni = [].slice.call(document.querySelectorAll('nav.filtri button'));
  var filtroAttivo = 'tutti';
  function partite() {{ return [].slice.call(document.querySelectorAll('li.partita')); }}
  function aggiornaSezioni() {{
    [].forEach.call(document.querySelectorAll('section.comp, section.giorno-sez'), function (s) {{
      s.hidden = !s.querySelector('li.partita:not([hidden])');
    }});
    // giorni senza più partite: bottone disattivato
    var restano = {{}};
    partite().forEach(function (p) {{ restano[p.dataset.giorno] = true; }});
    bottoni.forEach(function (b) {{
      if (b.dataset.filtro === 'tutti') return;
      b.disabled = !restano[b.dataset.filtro];
      if (b.disabled) b.title = 'Nessuna partita rimasta'; else b.removeAttribute('title');
    }});
    var n = document.querySelectorAll('#vista-campionato li.partita').length;
    var na = document.querySelector('nav.viste .altri .n');
    if (na) na.textContent = '(' + document.querySelectorAll('#vista-altri li.partita').length + ')';
    var cont = document.getElementById('n-partite');
    if (cont) cont.textContent = n;
    var vuoto = document.getElementById('vuoto');
    if (vuoto) vuoto.hidden = n > 0;
  }}
  function filtra(f) {{
    var b0 = bottoni.filter(function (b) {{ return b.dataset.filtro === f; }})[0];
    if (!b0 || b0.disabled) f = 'tutti';
    filtroAttivo = f;
    bottoni.forEach(function (b) {{ b.setAttribute('aria-pressed', b.dataset.filtro === f ? 'true' : 'false'); }});
    partite().forEach(function (p) {{ p.hidden = !(f === 'tutti' || p.dataset.giorno === f); }});
    aggiornaSezioni();
    try {{ sessionStorage.setItem('filtro', f); }} catch (e) {{}}
  }}
  bottoni.forEach(function (b) {{ b.addEventListener('click', function () {{ filtra(b.dataset.filtro); }}); }});
  // due viste: per campionato / in ordine di orario (scelta ricordata nel browser)
  var tastiVista = [].slice.call(document.querySelectorAll('nav.viste button'));
  function vista(v) {{
    if (v !== 'orario' && v !== 'altri') v = 'campionato';
    tastiVista.forEach(function (b) {{ b.setAttribute('aria-pressed', b.dataset.vista === v ? 'true' : 'false'); }});
    document.getElementById('vista-campionato').hidden = v !== 'campionato';
    document.getElementById('vista-orario').hidden = v !== 'orario';
    document.getElementById('vista-altri').hidden = v !== 'altri';
    try {{ localStorage.setItem('vista', v); }} catch (e) {{}}
  }}
  tastiVista.forEach(function (b) {{ b.addEventListener('click', function () {{ vista(b.dataset.vista); }}); }});
  var daUrl = /[?&]vista=(orario|campionato|altri)/.exec(location.search);  // es. ...?vista=orario
  var scelta = daUrl ? daUrl[1] : null;
  if (!scelta) {{ try {{ scelta = localStorage.getItem('vista'); }} catch (e) {{}} }}
  vista(scelta);
  // stato: in corso (fino a 2h15m dall'inizio), tra poco (entro 1 ora); finite -> tolte dalla pagina
  function stato() {{
    var ora = Date.now() / 1000, tolte = false;
    partite().forEach(function (p) {{
      var ts = +p.dataset.ts, s = p.querySelector('.stato'), c = '', t = '';
      var fine = p.dataset.fine ? +p.dataset.fine : ts + DURATA;
      if (ora >= fine) {{ p.parentNode.removeChild(p); tolte = true; return; }}
      if (ora >= ts) {{ c = 'in-corso'; t = 'IN CORSO'; }}
      else if (ts - ora <= 3600) {{ c = 'tra-poco'; t = 'TRA ' + Math.max(1, Math.round((ts - ora) / 60)) + ' MIN'; }}
      p.classList.remove('in-corso', 'tra-poco');
      if (c) p.classList.add(c);
      s.textContent = t;
    }});
    if (tolte) filtra(filtroAttivo); else aggiornaSezioni();
  }}
  stato();
  var salvato = null;
  try {{ salvato = sessionStorage.getItem('filtro'); }} catch (e) {{}}
  filtra(salvato || 'tutti');
  setInterval(stato, 60000);
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
    ap.add_argument("--senza-altri-sport", action="store_true", help="non legge SRF/RTS/RSI/ARD")
    ap.add_argument("--out", default=str(RADICE / "site"))
    ap.add_argument("--ora", help="data/ora di riferimento ISO (per test), es. 2026-10-10T18:00+02:00")
    ap.add_argument("--json", action="store_true", help="scrive anche palinsesto.json")
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
    gruppi, falliti, senza = raccogli(canali, inizio, fine, conf_los, st, tb, conf_dazn, conf_altri)
    n_tutte = sum(len(g["partite"]) for g in gruppi)
    gruppi = togli_finite(gruppi, dt.datetime.now(ROMA))
    st["finite_tolte"] = n_tutte - sum(len(g["partite"]) for g in gruppi)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in (RADICE / "static").iterdir():
        if f.is_file():
            shutil.copy2(f, out / f.name)
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
    if "dazn" in st:
        print(f"  DAZN gratis per paese: {st['dazn']} · unite a partite già presenti: {len(st['uniti_dazn'])} "
              f"· solo DAZN: {st['solo_dazn']}")
        for r in st["dazn_dettagli"]:
            print("  ", r)
    if "calcio_stream" in st:
        print(f"  Altri sport: {len(st['altri_sport'])} eventi · calcio in streaming: {st['calcio_stream']} "
              f"(uniti a partite già presenti: {len(st['uniti_stream'])})")
    for x in st.get("femminili_tolte", []):
        print("  femminile esclusa:", x)
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
