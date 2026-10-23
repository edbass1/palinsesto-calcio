"""Digi Sport Romania (Digi Sport 1-4): www.digisport.ro/program-tv/digisport-N.

HTML statico: per ogni giorno '<h3>Luni 12 Octombrie</h3>' e tabelle con righe
«icona (data-schedule=categoria) | ora | titolo». Le dirette hanno '<span class="tag"> LIVE </span>' (o 'Live');
'Premiera' = prima visione in differita. Ore della Romania (Europe/Bucharest); dopo mezzanotte le righe restano
sotto il giorno precedente. Una partita lunga è spezzata in più righe (intervallati dal notiziario): si uniscono.
Titoli: 'Champions League: Lens-Sporting<br>Etapa 2', 'Tenis WTA: Wuhan<br>Ziua 1', 'Moto: Campionatul Mondial de Superbike Spania<br>WorldSBK FP1'.
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
MESI = {"ianuarie": 1, "februarie": 2, "martie": 3, "aprilie": 4, "mai": 5, "iunie": 6, "iulie": 7, "august": 8,
        "septembrie": 9, "octombrie": 10, "noiembrie": 11, "decembrie": 12}


def carica_conf(percorso=None):
    return json.loads(Path(percorso or RADICE / "digisport.json").read_text(encoding="utf-8"))


def _sa(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def scarica(url, tentativi=2):
    err = None
    for _ in range(tentativi):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ro,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=30) as r:
                h = r.read().decode("utf-8", "replace")
            if "schedule-table" not in h:
                err = "pagina senza programma"
                continue
            return h, None
        except Exception as e:  # noqa: BLE001
            err = str(e)[:120]
    return None, err


def _anno(giorno, mese, oggi):
    cand = [dt.date(a, mese, giorno) for a in (oggi.year - 1, oggi.year, oggi.year + 1)]
    return min(cand, key=lambda d: abs((d - oggi).days))


def righe(h, oggi):
    """[(datetime aware, categoria, etichetta 'LIVE'/'PREMIERA'/'', titolo, dettaglio)] in ordine."""
    out, giorno, ultimo = [], None, None
    # dal 22/10/2026 il sito usa <h3 class="schedule-title"> e spazi dentro le celle (<td> 07:20 </td>)
    patt = re.compile(r'<h3(?:\s+class="schedule-title")?>\s*\w+\s+(\d{1,2})\s+(\w+)\s*</h3>|'
                      r'<tr[^>]*>\s*<td class="schedule-icon" data-schedule="([^"]*)">\s*</td>'
                      r'\s*<td>\s*(\d{1,2}):(\d{2})\s*</td>\s*<td>(.*?)</td>\s*</tr>', re.S)
    for m in patt.finditer(h):
        if m.group(1):
            mese = MESI.get(_sa(m.group(2)).lower())
            giorno = _anno(int(m.group(1)), mese, oggi) if mese else None
            ultimo = None
            continue
        if giorno is None:
            continue
        ora, minuti = int(m.group(4)), int(m.group(5))
        quando = dt.datetime(giorno.year, giorno.month, giorno.day, ora, minuti, tzinfo=BUCAREST)
        if ultimo is not None and quando < ultimo - dt.timedelta(hours=3):  # dopo mezzanotte, stesso <h3>
            giorno = giorno + dt.timedelta(days=1)
            quando = quando + dt.timedelta(days=1)
        ultimo = quando
        corpo = m.group(6)
        tag = " ".join(re.findall(r'<span class="tag">(.*?)</span>', corpo, re.S))
        etichetta = "LIVE" if re.search(r"\blive\b", tag, re.I) else ("PREMIERA" if re.search(r"premier", tag, re.I) else "")
        corpo = re.sub(r'<span class="tag">.*?</span>', " ", corpo, flags=re.S)
        titolo, _, dettaglio = corpo.partition("<br>")
        pulisci = lambda x: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()  # noqa: E731
        out.append((quando, m.group(3), etichetta, pulisci(titolo), pulisci(dettaglio)))
    return out


def squadre(resto, conf):
    """'Union Saint-Gilloise-Real Sociedad' -> ('Union Saint-Gilloise', 'Real Sociedad'): si divide al trattino
    che non segue una parola di 'parole_unite' (Saint-, Sankt-...); se ce ne sono più, quello più centrale."""
    unite = [_sa(x).lower() for x in conf.get("parole_unite", [])]
    cand = []
    for m in re.finditer(r"\s*-\s*", resto):
        a, b = resto[:m.start()].strip(), resto[m.end():].strip()
        if not a or not b:
            continue
        ultima = _sa(a.split()[-1]).lower()
        if ultima in unite or _sa(a).lower() in unite:
            continue
        cand.append((abs(len(a) - len(b)), a, b))
    if not cand:
        return None
    _, a, b = min(cand)
    tab = conf.get("squadre", {})
    return tab.get(a, a), tab.get(b, b), a, b


def raccogli(conf, inizio, fine, scarica_fn=None, oggi=None, stat=None):
    """(partite di calcio [formato Prima Play], eventi ALTRI SPORT, errore o None)."""
    st = stat if stat is not None else {}
    st.update({"righe": 0, "dirette": 0, "calcio_escluso": [], "saltate": 0, "canali_falliti": []})
    oggi = oggi or dt.datetime.now(BUCAREST).date()
    salta = [re.compile(x, re.I) for x in conf.get("salta", [])]
    escluso = [re.compile(x, re.I) for x in conf.get("calcio_escluso", [])]
    sport_tab = {k.lower(): v for k, v in conf.get("sport_elite", {}).items()}
    durate = conf.get("durata_min", {})
    calcio, altri, errori = [], [], []
    for c in conf.get("canali", []):
        h, err = (scarica_fn or scarica)(c["programma"])
        if err:
            errori.append(c["nome"])
            st["canali_falliti"].append(f'{c["nome"]}: {err}')
            continue
        ultimo_sport = {}  # sport -> ultimo evento con nome (le righe successive 'Tenis' senza dettagli lo allungano)
        visti = {}  # titolo completo -> evento già preso (le righe successive della stessa diretta lo allungano)
        for quando, _cat, etichetta, titolo, dettaglio in righe(h, oggi):
            st["righe"] += 1
            if etichetta != "LIVE":
                continue
            ts = int(quando.timestamp())
            chiave = f"{titolo}|{dettaglio}"
            nudo = not dettaglio and ":" not in titolo and len(titolo.split()) == 1  # 'Tenis': continua la diretta prima
            if not nudo and chiave in visti and ts - visti[chiave]["ts_ultimo"] <= 4 * 3600:
                visti[chiave]["ts_ultimo"] = ts
                ev = visti[chiave].get("ev")
                if ev is not None and "fine" in ev:
                    ev["fine"] = max(ev["fine"], ts + 60 * 60)
                continue
            if not nudo:
                visti[chiave] = {"ts_ultimo": ts}
            if any(r.search(_sa(titolo)) for r in salta) or any(r.search(_sa(dettaglio)) for r in salta):
                st["saltate"] += 1
                continue
            if not (inizio.timestamp() <= ts < fine.timestamp()):
                continue
            pre, sep, resto = titolo.partition(":")
            pre, resto = pre.strip(), resto.strip()
            prima = _sa(pre).lower()
            sport = next((v for k, v in sport_tab.items() if prima == k or prima.startswith(k + " ")), None)
            if sport is None and sep and resto and not re.match(r"^(handbal|volei|futsal|hochei|polo|rugby|box|atletism|ciclism|darts|snooker)\b", prima):
                # calcio: 'Competizione: Casa-Ospite'
                if any(r.search(pre) for r in escluso):
                    st["calcio_escluso"].append(f"{quando:%d/%m %H:%M} {titolo}")
                    continue
                sq = squadre(resto, conf)
                if not sq:
                    st["saltate"] += 1
                    continue
                casa, ospite, casa_ro, ospite_ro = sq
                calcio.append({"ts": ts, "casa": casa, "ospite": ospite, "casa_ro": casa_ro, "ospite_ro": ospite_ro,
                               "comp": pre, "comp_los": conf.get("competizioni_calcio", {}).get(pre, pre),
                               "canale": c["nome"], "genere": "", "titolo": titolo, "link": c["live"]})
                st["dirette"] += 1
                continue
            if sport is None:
                st["saltate"] += 1
                continue
            if sport == "Motori" and re.search(conf.get("moto_motogp", "(?!x)x"), f"{titolo} {dettaglio}", re.I):
                sport = "Motomondiale"
            if not resto and not dettaglio:
                prec = ultimo_sport.get(sport)
                if prec is not None and ts <= prec["fine"] + 3 * 3600:  # continua la diretta precedente (stesso torneo)
                    prec["fine"] = max(prec["fine"], ts + 2 * 3600)
                    continue
                st["saltate"] += 1  # 'Tenis' senza torneo: non si sa cosa sia
                continue
            # 'Tenis WTA: Wuhan' -> 'WTA Wuhan'; 'Moto: Campionatul Mondial de Superbike Spania' + 'WorldSBK FP1'
            testa = " ".join(pre.split()[1:])
            nome = " ".join(x for x in (testa, resto) if x)
            nome = re.sub(r"Campionatul Mondial de Superbike", "Superbike", nome)
            nome = re.sub(r"\bSpania\b", "Spagna", nome)
            det = re.sub(r"\bZiua (\d+)", r"giorno \1", dettaglio)
            det = {"Semifinala": "semifinale", "Finala": "finale", "Sferturi": "quarti di finale"}.get(det, det)
            titolo_it = f"{nome} – {det}" if det else nome
            dur = durate.get(sport, durate.get("default", 120))
            ev = {"id": f"digi:{ts}:{c['nome']}:{chiave.lower()}", "ts": ts, "fine": ts + dur * 60, "sport": sport,
                  "titolo": titolo_it, "titolo_orig": f"{titolo} {dettaglio}".strip(), "titolo_src": titolo, "evento": True,
                  "lingua": "it", "descrizione": testa or resto, "comp": testa or resto, "da_epg": True,
                  "emittenti": [{"nome": c["nome"], "pagina": None, "link": c["live"], "vpn": None, "fta": False, "ufficiale": True}]}
            if chiave in visti:
                visti[chiave]["ev"] = ev
            ultimo_sport[sport] = ev
            altri.append(ev)
            st["dirette"] += 1
    st["calcio"], st["altri"] = len(calcio), len(altri)
    if len(errori) == len(conf.get("canali", [])) and errori:
        return calcio, altri, "Digi Sport (programma non raggiungibile)"
    return calcio, altri, None
