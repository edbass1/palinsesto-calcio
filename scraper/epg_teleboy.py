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
LINGUE = {"it": "it", "de": "de", "at": "de", "ch": "de", "fr": "fr", "gb": "en", "en": "en", "us": "en"}


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


def _rx(lista, default):
    parole = lista if lista is not None else default
    return re.compile(r"(?<![\w])(?:" + "|".join(parole) + r")(?![\w])", re.I) if parole else re.compile(r"(?!x)x")


RE_ANNO = re.compile(r"\b(19[5-9]\d|20\d\d)\b")


def _norm(t):
    return re.sub(r"\W+", " ", t.lower()).strip()


def analizza(xml, teleboy, conf, inizio, fine, diag=None):
    """Eventi in diretta (formato altri_sport) sui canali gratuiti di Teleboy.
    La guida non ha <category>: diretta = <premiere/>, oppure 'live/diretta/direkt/en direct' in titolo, sottotitolo o
    descrizione, oppure (solo sui canali sportivi, conf 'canali_sport') una gara riconoscibile (squadre 'A - B' / 'vs',
    nome di torneo). Tolti: repliche/sintesi/magazine/show, programmi con anno vecchio (<date> o anno nel titolo),
    lo stesso titolo già andato in onda prima sullo stesso canale, durata < durata_minima_min.
    diag (lista), se data, riceve (canale, inizio, titolo, motivo o None se tenuto) per ogni programma con uno sport."""
    rx_prog, rx_ev = A.regole()
    rx_salvo = A._rx_salvo()
    rx_live = _rx(conf.get("parole_diretta"), [r"live", r"diretta", r"in diretta", r"direkt", r"en direct"])
    rx_rep = _rx(conf.get("parole_replica"), [r"replica", r"highlights?", r"sintesi", r"wiederholung", r"zusammenfassung",
                                              r"magazin", r"r[ée]sum[ée]", r"rediffusion", r"differita", r"riviviamo", r"momenti salienti"])
    rx_torneo = _rx(conf.get("parole_torneo"), [r"atp", r"wta", r"masters", r"open", r"grand prix", r"gran premio", r"gp",
                                                r"weltcup", r"world cup", r"coppa", r"coupe", r"cup", r"championships?", r"campionat[oi]",
                                                r"meisterschaft", r"trophy", r"giro", r"tour", r"world ?tour", r"regata", r"rennen", r"gara", r"race"])
    rx_titoli_no = _rx(conf.get("escludi_titoli"), [])
    canali_sport = [re.compile(x, re.I) for x in conf.get("canali_sport", [])]
    sport_canale = conf.get("sport_del_canale", {})
    solo_esplicita = [re.compile(x, re.I) for x in conf.get("canali_solo_diretta_esplicita", [])]
    radice = ET.fromstring(xml)
    alias = conf.get("alias", {})
    salta = set(conf.get("salta_paesi", []))
    minimo = int(conf.get("durata_minima_min", 20)) * 60
    anno = inizio.year
    canali = {}
    for c in radice.findall("channel"):
        n = alias.get(c.get("id")) or teleboy.trova(c.findtext("display-name") or "")
        if n and teleboy.paese(n) not in salta:
            canali[c.get("id")] = n
    prima_volta = {}  # (canale, titolo normalizzato) -> fine della prima messa in onda nella guida
    programmi = []
    dirette_altrove = {}  # titolo normalizzato -> inizi delle messe in onda in diretta (<premiere/> o 'live') su qualsiasi canale
    for p in radice.iter("programme"):
        if p.get("channel") not in canali:
            if p.find("premiere") is not None or rx_live.search(p.findtext("title") or ""):
                try:
                    dirette_altrove.setdefault(_norm(p.findtext("title") or ""), []).append(_ts(p.get("start")))
                except (TypeError, ValueError):
                    pass
            continue
        try:
            ts, ts_fine = _ts(p.get("start")), _ts(p.get("stop"))
        except (TypeError, ValueError):
            continue
        titolo = (p.findtext("title") or "").strip()
        sotto = (p.findtext("sub-title") or "").strip()
        if p.find("premiere") is not None or rx_live.search(titolo):
            dirette_altrove.setdefault(_norm(titolo), []).append(ts)
        k = (p.get("channel"), _norm(f"{titolo} {sotto}"))
        if k not in prima_volta or ts < prima_volta[k][0]:
            prima_volta[k] = (ts, ts_fine)
        programmi.append((p, ts, ts_fine, titolo, sotto, k))
    eventi = []
    tenuti = {}  # (canale, titolo) -> evento già tenuto: la parte successiva subito dopo lo allunga
    for p, ts, ts_fine, titolo, sotto, k in sorted(programmi, key=lambda x: x[1]):
        if not (inizio.timestamp() <= ts < fine.timestamp()):
            continue
        n = canali[p.get("channel")]
        desc = (p.findtext("desc") or "").strip()
        esplicita = any(r.search(n) for r in solo_esplicita)  # guida piena di repliche (SuperTennis): serve 'live' o prima visione
        sportivo = any(r.search(n) for r in canali_sport) and not esplicita
        prima = p.find("premiere") is not None
        # stesso titolo in diretta su un altro canale alla stessa ora (es. Il Lombardia su RSI e Rai 2): è diretta anche qui
        simultanea = not prima and any(abs(t - ts) <= 30 * 60 for t in dirette_altrove.get(_norm(titolo), []))
        sport = A.sport_di(titolo) or A.sport_di(sotto) or next((v for c, v in sport_canale.items() if re.search(c, n, re.I)), None)
        if not sport and sportivo:
            sport = A.sport_di(desc)
        if not sport or sport == "Programma sportivo":
            continue  # non è sport (o è un programma generico)
        testo = f"{titolo} {sotto}"
        tutto = f"{testo} {desc}"
        live_parola = bool(rx_live.search(tutto))
        live_titolo = bool(rx_live.search(testo))  # 'Live-Übertragung' nella descrizione resta anche nelle repliche
        data = (p.findtext("date") or "")[:4]
        anni = [int(x) for x in RE_ANNO.findall(titolo)] + ([int(data)] if data.isdigit() else [])
        motivo = None
        m = None
        if ts_fine - ts < minimo:
            motivo = "troppo breve"
        elif rx_rep.search(tutto):
            motivo = f"replica/sintesi («{rx_rep.search(tutto).group(0)}»)"
        elif rx_prog.search(testo) or rx_titoli_no.search(testo):
            motivo = f"programma («{(rx_prog.search(testo) or rx_titoli_no.search(testo)).group(0)}»)"
        elif rx_salvo and rx_salvo.search(testo) and not A.due_partecipanti(testo):
            motivo = f"programma («{rx_salvo.search(testo).group(0)}», senza due partecipanti)"
        elif sport == "Football americano" and not (A.due_partecipanti(testo) or A.due_partecipanti(desc)):
            motivo = "football americano senza due squadre"
        elif anni and min(anni) < anno and not live_parola:
            motivo = f"vecchio ({min(anni)})"
        elif k in tenuti and tenuti[k]["fine"] >= ts - 15 * 60:
            tenuti[k]["fine"] = max(tenuti[k]["fine"], ts_fine)  # seconda parte della stessa diretta
            motivo = "seconda parte della stessa diretta (unita)"
        elif prima_volta[k][1] < ts - 15 * 60 and not live_titolo:  # già andato in onda (non la parte subito prima)
            motivo = "replica (stesso titolo già in onda prima)"
        elif not (A.RE_PARTECIPANTI.search(testo) or A.due_partecipanti(testo) or rx_torneo.search(testo)
                  or ((prima or live_parola or simultanea) and rx_ev.search(tutto))):
            motivo = "non sembra una gara"
        elif not (prima or live_parola or sportivo or simultanea):
            motivo = ("non in diretta (canale con guida piena di repliche: serve 'live' o prima visione)" if esplicita
                      else "non in diretta (canale non sportivo, niente 'live' né prima visione)")
        if diag is not None:
            diag.append((n, ts, titolo + (f" | {sotto}" if sotto else ""), motivo))
        if motivo:
            continue
        tit = re.sub(r"\s*\b(live|en direct|in diretta|diretta|direkt)\b\s*:?", " ", titolo, flags=re.I).strip(" :-")
        # "Sport: Titolo" -> si toglie lo sport iniziale, come per SRF
        testa, sep, resto = tit.partition(":")
        if sep and A.sport_di(testa) == sport and resto.strip() and len(testa.split()) <= 3:
            tit = resto.strip()
        if sotto and sotto.lower() not in tit.lower() and not re.match(r"^\d{4}$", sotto):
            tit = f"{tit}, {sotto}"
        if sport == "Calcio":  # "Super League: Lugano - Luzern" -> "Super League, Lugano - Luzern" (come SRF)
            tit = tit.replace(": ", ", ")
        tenuti[k] = {"id": f"teleboy:{p.get('channel')}:{ts}", "ts": ts, "fine": ts_fine, "sport": sport, "titolo": tit,
                       "titolo_orig": f"{titolo} {sotto} {desc}", "titolo_src": titolo, "evento": True,
                       "lingua": LINGUE.get(teleboy.paese(n) or "", "de"), "descrizione": desc, "da_epg": True,
                       "emittenti": [{"nome": n, "pagina": PAGINA, "link": teleboy.link(n) or PAGINA, "vpn": "SVIZZERA",
                                      "teleboy": True, "teleboy_nome": n}]}
        eventi.append(tenuti[k])
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
