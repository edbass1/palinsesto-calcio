"""ALTRI SPORT da LiveOnSat (NFL, NBA, NHL, rugby, F1, boxe...) su canali in chiaro di tutto il mondo,
più le partite NFL gratis in streaming elencate da TechRadar (5 UK, 7plus, TVNZ+, Virgin Media Play, Twitch)."""
import datetime as dt
import html
import json
import re
import time
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import liveonsat as L
import unisci as U

ROMA = ZoneInfo("Europe/Rome")
ET = ZoneInfo("America/New_York")
NFL_CONF = Path(__file__).resolve().parent.parent / "nfl_gratis.json"
UA = L.UA


def titolo_bello(t):
    t = re.sub(r"\s+v\s+", " - ", t.strip())
    return t


def analizza_pagina(h, sport, durata, conf, teleboy, inizio, fine, escluso):
    """Eventi (formato altri_sport) di una pagina LiveOnSat; tutte le partite (anche senza canali, per NFL)."""
    regole, alias = conf.get("canali_in_chiaro", []), conf.get("alias_canali", [])
    regole = list(regole) + list(conf.get("canali_per_sport", {}).get(sport, []))  # es. Idman TV per il basket
    escludi = ["dazn"] + [x for x in conf.get("escludi_canali", []) if x]
    out = []
    for p in L.analizza(h, regole, alias, escludi, teleboy):
        if not (inizio.timestamp() <= p["ts"] < fine.timestamp()):
            continue
        tit = re.sub(r"\s+", " ", p["titolo"]).strip()
        if re.fullmatch(r"[-\s]*(\w\s){3,}\w?[-\s]*", tit + " ") or re.search(r"(\b\w\b\s){4,}", tit):
            continue  # "- N F L - R E D - Z O N E -" e simili
        emittenti = []
        for n, fta in [(n, True) for n in p["canali_fta"]] + [(n, False) for n in p["canali_teleboy"]]:
            if escluso(n):
                continue
            tb = teleboy.trova(n) if teleboy is not None else None
            emittenti.append({"nome": n, "pagina": None, "link": teleboy.link(tb) if tb else None, "vpn": "SVIZZERA" if tb else "",
                              "fta": fta, "teleboy": bool(tb), "teleboy_nome": tb})
        out.append({"id": f"los:{p['ts']}:{tit.lower()}", "ts": p["ts"], "fine": p["ts"] + durata * 60, "sport": sport,
                    "titolo": titolo_bello(tit), "titolo_orig": f"{tit} {p['comp']}", "titolo_src": tit, "evento": True,
                    "lingua": "en", "descrizione": p["comp"], "comp": p["comp"], "da_los": True, "emittenti": emittenti})
    return out


# ---------- NFL gratis (TechRadar) ----------
def ora_et(giorno, ora):
    m = re.fullmatch(r"(\d{1,2})(?:[.:](\d\d))?\s*([ap]m)", ora.strip().lower())
    if not m:
        return None
    h = int(m.group(1)) % 12 + (12 if m.group(3) == "pm" else 0)
    d = dt.datetime.combine(dt.date.fromisoformat(giorno), dt.time(h, int(m.group(2) or 0)), ET)
    return int(d.timestamp())


MESI_EN = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                            "september", "october", "november", "december"])}


def leggi_techradar(h, anno):
    """Partite dalla tabella 'NFL 2026 Week N schedule': [{giorno, ora_et, squadre, canali, link}]."""
    i = h.find('-schedule"><span>')
    if i < 0:
        return []
    j = h.find("<h2", i + 10)
    blocco = h[i:j if j > 0 else i + 30000]
    link = {}
    for url, testo in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(?:<strong>)?(.*?)(?:</strong>)?</a>', blocco, re.S):
        nome = re.sub(r"^Stream FREE on\s+", "", html.unescape(re.sub(r"<[^>]+>", "", testo))).strip()
        link.setdefault(nome, url)
    testo = re.sub(r"<br\s*/?>|</p>", "\n", blocco)
    testo = html.unescape(re.sub(r"<[^>]+>", "", testo))
    giorno, out = None, []
    for riga in (r.strip() for r in testo.splitlines()):
        m = re.match(r"^[A-Z][a-z]+day,\s+([A-Z][a-z]+)\s+(\d{1,2})$", riga)
        if m and m.group(1).lower() in MESI_EN:
            giorno = dt.date(anno, MESI_EN[m.group(1).lower()], int(m.group(2))).isoformat()
            continue
        m = re.match(r"^(.+?)\s+vs\.?\s+(.+?)(?:\s*\(in [^)]*\))?:\s*([\d.:]+\s*[ap]m)\s*ET(?:\s*\|\s*(.*))?$", riga, re.I)
        if not (m and giorno):
            continue
        canali = []
        if m.group(4):
            for c in re.split(r",|&| and ", re.sub(r"^Stream FREE on\s+", "", m.group(4).strip(), flags=re.I)):
                c = c.strip()
                if c:
                    canali.append(c)
        out.append({"giorno": giorno, "ora_et": m.group(3).replace(" ", ""), "squadre": [m.group(1).strip(), m.group(2).strip()],
                    "canali": canali, "link": {c: link.get(c) for c in canali}})
    return out


def scarica_techradar(url, tentativi=2):
    err = None
    for i in range(tentativi):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace"), None
        except Exception as e:  # noqa: BLE001
            err = str(e)[:80]
            time.sleep(2 * (i + 1))
    return None, err


def eventi_nfl(partite, conf, inizio, fine):
    """Partite NFL gratis -> eventi (formato altri_sport) con i soli canali gratis TechRadar."""
    out = []
    for g in partite:
        ts = ora_et(g["giorno"], g["ora_et"])
        if not ts or not (inizio.timestamp() <= ts < fine.timestamp()) or not g.get("canali"):
            continue
        em = []
        for c in g["canali"]:
            info = conf.get("canali", {}).get(c) or {"nome": c, "vpn": None, "url": (g.get("link") or {}).get(c)}
            em.append({"nome": info["nome"], "pagina": info.get("url"), "link": info.get("url"), "vpn": info.get("vpn"),
                       "streaming_nfl": True})
        a, b = g["squadre"]
        out.append({"id": f"nfl:{g['giorno']}:{a}:{b}".lower(), "ts": ts, "fine": ts + 210 * 60, "sport": "Football americano",
                    "titolo": f"{a} - {b}", "titolo_orig": f"{a} {b} NFL", "titolo_src": f"{a} - {b}", "evento": True,
                    "lingua": "en", "da_los": True, "nfl_soprannomi": [a, b], "emittenti": em})
    return out


def fn_raccogli(conf_los, teleboy, inizio, fine, scarica_los=None, scarica_tr=None, nfl_conf=None, stat=None):
    """Funzione senza argomenti per altri_sport.raccogli_altri -> (eventi, errore)."""
    scarica_los = scarica_los or (lambda u: L.scarica(u, 2, True))
    scarica_tr = scarica_tr or scarica_techradar

    def f():
        motivo = U.regola_canali(conf_los)
        mai = [x.lower() for x in conf_los.get("mai_escludere", ["idman"]) if x]
        escludi = ["dazn"] + [x.lower() for x in conf_los.get("escludi_canali", []) if x]

        def escluso(n):
            nl = n.lower()
            if any(w in nl for w in mai):
                return False
            return any(x in nl for x in escludi) or bool(motivo(n))

        eventi, falliti = [], []
        for url, (sport, durata) in conf_los.get("pagine_altri_sport", {}).items():
            h, err = scarica_los(url)
            if not h:
                falliti.append(url.rsplit("/", 1)[-1])
                continue
            eventi += analizza_pagina(h, sport, durata, conf_los, teleboy, inizio, fine, escluso)
            time.sleep(conf_los.get("pausa_secondi", 0.7))
        nc = nfl_conf if nfl_conf is not None else (json.loads(NFL_CONF.read_text(encoding="utf-8")) if NFL_CONF.exists() else {})
        partite, fonte = [], "copia salvata (nfl_gratis.json)"
        if nc.get("fonte"):
            h, err = scarica_tr(nc["fonte"])
            if h:
                partite = leggi_techradar(h, inizio.year)
                fonte = "TechRadar (letta ora)"
        if not partite:
            partite = nc.get("partite", [])
            fonte = "copia salvata (nfl_gratis.json)"
        nfl = eventi_nfl(partite, nc, inizio, fine)
        if stat is not None:
            stat.update({"los_pagine_fallite": falliti, "nfl_fonte": fonte, "nfl_gratis": len(nfl),
                         "los_altri": len(eventi)})
        eventi += nfl
        err = (f"LiveOnSat altri sport: {len(falliti)} pagine su {len(conf_los.get('pagine_altri_sport', {}))}"
               if falliti and len(falliti) == len(conf_los.get("pagine_altri_sport", {})) else None)
        return eventi, err
    return f
