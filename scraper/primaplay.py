"""Programma ufficiale Prima Sport (Prima Play): www.primaplay.ro/transmisiuni.

La pagina è HTML statico (nessuna API): una scheda per giorno ('Astăzi 11.10', 'L 12.10', ...), in ogni scheda
una tabella con righe «ora <br> canale | titolo». Orari in ora della Romania (Europe/Bucharest, EET/EEST).
Titoli: calcio senza prefisso ('Como - Roma', a volte 'Fotbal: Roma - Inter, Serie A' o 'UYL: Man City - PSG'),
altri sport con prefisso romeno ('Tenis M - ATP: Shanghai Masters', 'Handbal F - CL: CSM București - Esbjerg').
"""
import datetime as dt
import html
import json
import re
import unicodedata
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

RADICE = Path(__file__).resolve().parent.parent
BUCAREST = ZoneInfo("Europe/Bucharest")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def carica_conf(percorso=None):
    return json.loads(Path(percorso or RADICE / "primaplay.json").read_text(encoding="utf-8"))


def scarica(url, tentativi=2):
    err = None
    for _ in range(tentativi):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ro,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=30) as r:
                h = r.read().decode("utf-8", "replace")
            if "program-live" not in h:
                err = "pagina senza programma"
                continue
            return h, None
        except Exception as e:  # noqa: BLE001
            err = str(e)[:120]
    return None, err


def _senza_accenti(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def _testo(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


def _anno(giorno, mese, oggi):
    cand = []
    for a in (oggi.year - 1, oggi.year, oggi.year + 1):
        try:
            cand.append(dt.date(a, mese, giorno))
        except ValueError:
            pass
    return min(cand, key=lambda d: abs((d - oggi).days))


def righe(h, oggi):
    """[(datetime aware, canale come in tabella, titolo, icone)] di tutte le schede."""
    date = {}
    for tab, gg, mm in re.findall(r'href="#(tab\d+)"[^>]*>[^<]*<span>(\d{1,2})\.(\d{1,2})</span>', h):
        date.setdefault(tab, _anno(int(gg), int(mm), oggi))
    out = []
    for m in re.finditer(r'<div class="tab-pane[^"]*" id="(tab\d+)"(.*?)(?=<div class="tab-pane|</section>|$)', h, re.S):
        giorno = date.get(m.group(1))
        if giorno is None:
            continue
        for r in re.findall(r"<tr>(.*?)</tr>", m.group(2), re.S):
            td = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
            if len(td) < 2:
                continue
            q = re.match(r"\s*(\d{1,2}):(\d{2})\s*<br\s*/?>(.*)$", td[0], re.S)
            if not q:
                continue
            quando = dt.datetime(giorno.year, giorno.month, giorno.day, int(q.group(1)), int(q.group(2)), tzinfo=BUCAREST)
            out.append((quando, _testo(q.group(3)), _testo(td[1]), re.findall(r"tvs/([\w-]+)\.svg", r)))
    return out


def nome_canale(c, conf):
    for k in conf.get("canali", []):
        m = re.match(k["regex"], c.strip(), re.I)
        if m:
            return m.expand(k["nome"])
    return None


def squadra(n, conf):
    n = n.strip()
    tab = conf.get("squadre", {})
    if n in tab:
        return tab[n]
    sa = {_senza_accenti(k).lower(): v for k, v in tab.items()}
    if _senza_accenti(n).lower() in sa:
        return sa[_senza_accenti(n).lower()]
    for k, v in conf.get("parole_squadre", {}).items():
        n = re.sub(rf"\b{re.escape(k)}\b", v, n)
    return n


def analizza_titolo(t, conf):
    """-> dict(sport, genere 'M'/'F'/'', comp, resto) oppure None se è un titolo da saltare."""
    t = re.sub(r"\s*[\(\[]?\b(live|în direct|in direct)\b[\)\]]?\s*", " ", t, flags=re.I).strip(" -")
    if any(re.search(rx, _senza_accenti(t), re.I) for rx in conf.get("salta", [])):
        return None
    sport_tab = {_senza_accenti(k).lower(): v for k, v in conf.get("sport", {}).items()}
    m = re.match(r"^([^:]{1,60}):\s*(.+)$", t)
    if not m:
        return {"sport": "Calcio", "genere": "", "comp": "", "resto": t}
    pre, resto = m.group(1).strip(), m.group(2).strip()
    sg, _, comp = pre.partition(" - ")
    g = re.match(r"^(.*?)(?:\s+([MF]))?$", sg.strip())
    base, genere = g.group(1).strip(), g.group(2) or ""
    sport = sport_tab.get(_senza_accenti(base).lower())
    if sport:
        pref = {_senza_accenti(k).lower(): v for k, v in conf.get("titolo_sport", {}).items()}.get(_senza_accenti(base).lower(), "")
        return {"sport": sport, "genere": genere, "comp": comp.strip() or pref, "resto": resto}
    # prefisso che non è uno sport: sigla di competizione di calcio ("UYL: ...")
    return {"sport": "Calcio", "genere": "", "comp": pre, "resto": resto}


def _sep(resto):
    p = re.split(r"\s+[-–]\s+|\s+vs?\.?\s+", resto, maxsplit=1)
    return (p[0].strip(), p[1].strip()) if len(p) == 2 else None


def raccogli(conf, inizio, fine, scarica_fn=None, oggi=None, stat=None):
    """(partite di calcio, eventi ALTRI SPORT, errore). Partite: {ts, casa, ospite, comp, comp_los, canale, genere}."""
    st = stat if stat is not None else {}
    h, err = (scarica_fn or scarica)(conf.get("url", "https://www.primaplay.ro/transmisiuni"))
    if err:
        st["errore"] = err
        return [], [], f"Prima Play (programma Prima Sport) ({err})"
    oggi = oggi or dt.datetime.now(BUCAREST).date()
    calcio, altri = [], []
    st.update({"righe": 0, "saltate_canale": [], "saltate_titolo": [], "repliche": 0})
    durate = conf.get("durata_min", {})
    for quando, can, tit, _icone in righe(h, oggi):
        st["righe"] += 1
        nome = nome_canale(can, conf)
        if not nome:
            st["saltate_canale"].append(f"{can}: {tit}")
            continue
        ts = int(quando.timestamp())
        if not (inizio.timestamp() <= ts < fine.timestamp()):
            continue
        a = analizza_titolo(tit, conf)
        if a is None:
            st["repliche"] += 1
            continue
        if a["sport"] == "Calcio":
            sq = _sep(a["resto"])
            if not sq:
                st["saltate_titolo"].append(tit)
                continue
            casa, ospite = sq
            comp = a["comp"]
            if not comp and "," in ospite:  # "Roma - Inter, Serie A"
                ospite, comp = (x.strip() for x in ospite.rsplit(",", 1))
            comp_los = conf.get("competizioni_calcio", {}).get(comp, comp)
            calcio.append({"ts": ts, "casa": squadra(casa, conf), "ospite": squadra(ospite, conf), "casa_ro": casa,
                           "ospite_ro": ospite, "comp": comp, "comp_los": comp_los, "canale": nome, "genere": a["genere"],
                           "titolo": tit})
            continue
        tab = conf.get("competizioni", {})
        comp = (tab.get(a["sport"], {}).get(a["comp"]) or tab.get("*", {}).get(a["comp"]) or a["comp"]) if a["comp"] else ""
        femm = " femminile" if a["genere"] == "F" else ""
        titolo = f"{comp}{femm}: {a['resto']}" if comp else (f"{a['resto']} ({femm.strip()})" if femm else a["resto"])
        dur = durate.get(a["sport"], durate.get("default", 120))
        altri.append({"id": f"pp:{ts}:{nome}:{tit.lower()}", "ts": ts, "fine": ts + dur * 60, "sport": a["sport"],
                      "titolo": titolo, "titolo_orig": tit, "titolo_src": tit, "evento": True, "lingua": "it",
                      "descrizione": comp, "comp": comp, "da_epg": True, "da_pp": True,
                      "emittenti": [{"nome": nome, "pagina": None, "link": None, "vpn": None, "fta": False, "pp": True}]})
    st["calcio"], st["altri"] = len(calcio), len(altri)
    return calcio, altri, None
