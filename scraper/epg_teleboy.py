"""Dirette sportive sui canali gratuiti di Teleboy, dalla guida TV XMLTV pubblica di epgshare01 (dati Swisscom).
L'EPG di Teleboy non è pubblico; i canali sono gli stessi (svizzeri, tedeschi, austriaci, francesi, inglesi...)."""
import datetime as dt
import gzip
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

import altri_sport as A

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
PAGINA = "https://www.teleboy.ch/it/live"
RE_LIVE = re.compile(r"(?<![\w])(live|en direct|in diretta|direkt)(?![\w])", re.I)
LINGUE = {"de": "de", "at": "de", "ch": "de", "fr": "fr", "gb": "en", "en": "en", "us": "en"}


def scarica(url, tentativi=3):
    err = None
    for i in range(tentativi):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                dati = r.read()
            return (gzip.decompress(dati) if dati[:2] == b"\x1f\x8b" else dati), None
        except Exception as e:  # noqa: BLE001
            err = str(e)[:80]
            time.sleep(2 * (i + 1))
    return None, err


def _ts(s):
    return int(dt.datetime.strptime(s.strip()[:20].strip(), "%Y%m%d%H%M%S %z").timestamp())


def analizza(xml, teleboy, conf, inizio, fine):
    """Eventi in diretta (formato altri_sport) sui canali gratuiti di Teleboy."""
    rx_prog, rx_ev = A.regole()
    radice = ET.fromstring(xml)
    alias = conf.get("alias", {})
    salta = set(conf.get("salta_paesi", ["it"]))
    minimo = int(conf.get("durata_minima_min", 20)) * 60
    canali = {}
    for c in radice.findall("channel"):
        n = alias.get(c.get("id")) or teleboy.trova(c.findtext("display-name") or "")
        if n and teleboy.paese(n) not in salta:
            canali[c.get("id")] = n
    eventi = []
    for p in radice.iter("programme"):
        n = canali.get(p.get("channel"))
        if not n:
            continue
        try:
            ts, ts_fine = _ts(p.get("start")), _ts(p.get("stop"))
        except (TypeError, ValueError):
            continue
        if not (inizio.timestamp() <= ts < fine.timestamp()) or ts_fine - ts < minimo:
            continue
        titolo = (p.findtext("title") or "").strip()
        sotto = (p.findtext("sub-title") or "").strip()
        desc = (p.findtext("desc") or "").strip()
        diretta = p.find("premiere") is not None or RE_LIVE.search(titolo) or RE_LIVE.search(sotto)
        if not diretta:
            continue  # repliche e differite
        sport = A.sport_di(titolo) or A.sport_di(sotto)
        if not sport or sport == "Programma sportivo":
            continue  # non è sport (o è un programma generico)
        testo = f"{titolo} {sotto}"
        if rx_prog.search(testo):
            continue  # magazine, studio, presentazioni, analisi...
        if not (A.RE_PARTECIPANTI.search(testo) or rx_ev.search(testo + " " + desc) or ":" in titolo):
            continue
        tit = re.sub(r"\s*\b(live|en direct|in diretta)\b\s*:?", " ", titolo, flags=re.I).strip(" :-")
        # "Sport: Titolo" -> si toglie lo sport iniziale, come per SRF
        testa, sep, resto = tit.partition(":")
        if sep and A.sport_di(testa) == sport and resto.strip():
            tit = resto.strip()
        if sotto and sotto.lower() not in tit.lower() and not re.match(r"^\d{4}$", sotto):
            tit = f"{tit}, {sotto}"
        if sport == "Calcio":  # "Super League: Lugano - Luzern" -> "Super League, Lugano - Luzern" (come SRF)
            tit = tit.replace(": ", ", ")
        eventi.append({"id": f"teleboy:{p.get('channel')}:{ts}", "ts": ts, "fine": ts_fine, "sport": sport, "titolo": tit,
                       "titolo_orig": f"{titolo} {sotto} {desc}", "titolo_src": titolo, "evento": True,
                       "lingua": LINGUE.get(teleboy.paese(n) or "", "de"), "descrizione": desc, "da_epg": True,
                       "emittenti": [{"nome": n, "pagina": PAGINA, "link": teleboy.link(n) or PAGINA, "vpn": "SVIZZERA",
                                      "teleboy": True}]})
    return eventi


def fn_raccogli(teleboy, conf, inizio, fine, scarica_fn=None):
    """Funzione senza argomenti per altri_sport.raccogli_altri -> (eventi, errore)."""
    scarica_fn = scarica_fn or scarica

    def f():
        errori = []
        for url in conf.get("fonti", []):
            xml, err = scarica_fn(url)
            if xml:
                try:
                    return analizza(xml, teleboy, conf, inizio, fine), None
                except ET.ParseError as e:
                    errori.append(f"XML non valido: {e}"[:80])
            else:
                errori.append(err)
        return [], (errori[0] if errori else "nessuna fonte")
    return f
