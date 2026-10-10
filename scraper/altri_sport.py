"""Altri sport in streaming gratuito: SRF, RTS, RSI (Svizzera, API pubblica SRG "integration layer")
e ARD Mediathek (Germania, API pubblica "page-gateway"). Le partite di calcio trovate qui vanno nella
sezione calcio; tutto il resto nella sezione "Altri sport"."""
import datetime as dt
import json
import re
from pathlib import Path
import time
import urllib.request

import traduci
from zoneinfo import ZoneInfo

ROMA = ZoneInfo("Europe/Rome")
UTC = dt.timezone.utc
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
IL = "https://il.srgssr.ch/integrationlayer/2.0/{bu}/mediaList/video/{lista}"
SRG = {"srf": "SRF", "rts": "RTS", "rsi": "RSI"}
# pagine indicate dall'utente: link principale per ogni emittente
PAGINE = {"SRF": "https://www.srf.ch/play/tv/sport-livestreams", "RTS": "https://www.rts.ch/play/tv/rts-livestreams",
          "RSI": "https://www.rsi.ch/palinsesto/streaming/",
          "ARD": "https://www.ardmediathek.de/sammlung/die-sport-livestreams-der-ard/livestreams-ard-"}
ARD_PAGINA = "https://api.ardmediathek.de/page-gateway/pages/ard/editorial/ebc4fa69-c557-47c5-ba61-6488211bc602?pageSize=50"
ARD_SITO = "https://www.ardmediathek.de/sammlung/die-sport-livestreams-der-ard/livestreams-ard-"

# parola iniziale del titolo (de/fr/it) -> sport in italiano
SPORT = [
    (r"nfl|american football|football américain|football americano", "Football americano"),
    (r"fussball|fußball|calcio|football", "Calcio"),
    (r"formel 1|formula 1|formule 1", "Formula 1"),
    (r"motorrad|motomondiale|moto ?gp|moto ?[23]\b", "Motomondiale"),
    (r"rad\b|radsport|ciclismo|cyclisme", "Ciclismo"),
    (r"ski alpin|sci alpino|ski alpin|riesenslalom|slalom|abfahrt|super-g", "Sci alpino"),
    (r"biathlon", "Biathlon"),
    (r"langlauf|sci di fondo|ski de fond", "Sci di fondo"),
    (r"skispringen|salto con gli sci|saut à ski", "Salto con gli sci"),
    (r"(?<!tisch)tennis(?! de table)", "Tennis"),
    (r"eishockey|hockey su ghiaccio|hockey sur glace|hockey", "Hockey su ghiaccio"),
    (r"unihockey|floorball", "Unihockey"),
    (r"kunstturnen|ginnastica|gymnastique|turnen", "Ginnastica artistica"),
    (r"curling", "Curling"),
    (r"handball|pallamano", "Pallamano"),
    (r"basketball|basket", "Basket"),
    (r"volleyball|pallavolo|volley", "Pallavolo"),
    (r"leichtathletik|atletica|athlétisme|marathon|maratona", "Atletica"),
    (r"schwimmen|nuoto|natation", "Nuoto"),
    (r"box|boxe|pugilato", "Boxe"),
    (r"tanz|danza|danse", "Danza sportiva"),
    (r"golf", "Golf"),
    (r"reiten|equitazione|hippisme|springreiten", "Equitazione"),
    (r"schwingen|lotta svizzera|lutte suisse", "Lotta svizzera"),
    (r"rudern|canottaggio|aviron", "Canottaggio"),
    (r"segeln|vela|voile", "Vela"),
    (r"triathlon", "Triathlon"),
    (r"uci|gravel|paris-tours|giro d|tour de france|vuelta|radrennen|cyclo-cross|querfeldein|lombardei", "Ciclismo"),
    (r"snooker", "Snooker"),
    (r"darts|freccette|fléchettes", "Freccette"),
    (r"dtm|superbike|motorsport|nascar|rallye|rally|wec|indycar|formel e|formula e|gt masters|motocross|sport auto", "Motori"),
    (r"rugby", "Rugby"),
    (r"badminton", "Badminton"),
    (r"tischtennis|tennistavolo|tennis de table|table tennis", "Tennistavolo"),
    (r"judo|ringen|lutte|wrestling", "Lotta"),
    (r"bobsport|bob-weltcup|zweierbob|viererbob|monobob|rodeln|skeleton|slittino", "Bob e slittino"),
    (r"eiskunstlauf|pattinaggio|patinage", "Pattinaggio"),
    (r"skicross|snowboard|freeski", "Sport invernali"),
    (r"nfl|american football|football américain", "Football americano"),
    (r"sportschau|sportpanorama|sport", "Programma sportivo"),
]
# squadre di basket ARD (i titoli dicono solo "A gegen B")
BASKET_ARD = re.compile(r"gladiators trier|telekom baskets|alba berlin|ratiopharm ulm|bayern basketball", re.I)


def sport_di(testo):
    t = testo.lower()
    for rx, nome in SPORT:
        if re.search(r"(?<![a-zà-ü])(?:" + rx + r")", t):
            return nome
    return None


def json_url(url, tentativi=3):
    err = None
    for i in range(tentativi):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r), None
        except Exception as e:  # noqa: BLE001
            err = str(e)[:80]
            time.sleep(1 + i)
    return None, err


def _ts(s):
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


# ---------- SRG (SRF, RTS, RSI) ----------
def titolo_srg(bu, titolo):
    """(sport, resto del titolo)."""
    titolo = titolo.strip()
    if bu == "rts":
        m = re.match(r"^([A-ZÀ-Ü0-9 ]+?)\s+(?=[A-ZÀ-Ü][a-zà-ü']|[A-Z]{2,4}\b(?![A-Z ]*$))", titolo)
        testa = m.group(1) if m else titolo.split(" ")[0]
        return sport_di(testa) or sport_di(titolo), titolo[len(testa):].strip() or titolo
    testa, sep, resto = titolo.partition(":")
    if sep and len(testa) <= 30:
        return sport_di(testa) or sport_di(titolo), resto.strip()
    testa, sep, resto = titolo.partition(",")
    return sport_di(testa) or sport_di(titolo), titolo


def analizza_srg(bu, media, solo_sport=True):
    out = []
    for m in media:
        if m.get("type") not in (None, "SCHEDULED_LIVESTREAM"):
            continue
        sport, resto = titolo_srg(bu, m.get("title") or "")
        if not sport and solo_sport:
            continue
        inizio = _ts(m["date"])
        durata = (m.get("duration") or 0) // 1000
        fine = inizio + durata if 0 < durata <= 14 * 3600 else (_ts(m["validTo"]) if m.get("validTo") else inizio + 3 * 3600)
        idx = str(m.get("cesimId") or m["urn"].rsplit(":", 1)[-1])
        # id evento sportivo swisstxt: c'è solo per le gare (mai per i programmi), ma RTS/RSI spesso non lo mettono
        evento = bool(m.get("cesimId")) or ":swisstxt:" in (m.get("urn") or "")
        out.append({"id": f"swisstxt:{idx}", "ts": inizio, "fine": fine, "sport": sport or "Sport", "titolo": resto,
                    "titolo_orig": m.get("title") or "", "titolo_src": m.get("title") or "", "evento": evento,
                    "lingua": {"srf": "de", "rts": "fr", "rsi": "it"}.get(bu, "de"),
                    "emittenti": [{"nome": SRG[bu], "pagina": PAGINE[SRG[bu]],
                                   "link": f"https://www.{bu}.ch/play/tv/-/video/-?urn=urn:swisstxt:video:{bu}:{idx}",
                                   "vpn": None if m.get("playableAbroad") else "SVIZZERA"}]})
    return out


def scarica_srg(bu):
    """Eventi sportivi in diretta streaming di una unità SRG; (eventi, errore)."""
    eventi, errori = [], []
    url = IL.format(bu=bu, lista="scheduledLivestreams?vector=portalplay&pageSize=100&eventType=SPORT")
    for _ in range(3):  # al massimo 3 pagine
        d, err = json_url(url)
        if err:
            errori.append(err)
            break
        eventi += analizza_srg(bu, d.get("mediaList") or [], solo_sport=False)
        url = d.get("next")
        if not url:
            break
    # dirette già iniziate (non più nell'elenco "prossimi")
    d, err = json_url(IL.format(bu=bu, lista="scheduledLivestreams/livecenter?pageSize=100"))
    if d:
        eventi += analizza_srg(bu, d.get("mediaList") or [])
    elif err:
        errori.append(err)
    return eventi, (errori[0] if errori and not eventi else None)


# ---------- ARD ----------
def analizza_ard(pagina, dettaglio_fn):
    teasers = [t for w in pagina.get("widgets", []) for t in w.get("teasers", [])]
    out = []
    for t in teasers:
        if not t.get("broadcastedOn"):
            continue
        out.append({"t": t, "ts": _ts(t["broadcastedOn"])})
    eventi = []
    for x in out:
        t = x["t"]
        det = dettaglio_fn(t) or {}
        sinossi = det.get("synopsis") or ""
        titolo = t.get("longTitle") or t.get("mediumTitle") or ""
        show = (t.get("show") or {}).get("title") or ""
        fine = _ts(det["availableTo"]) if det.get("availableTo") else x["ts"] + 3 * 3600
        if fine - x["ts"] > 14 * 3600:
            fine = x["ts"] + 3 * 3600
        sp_sinossi = sport_di(sinossi)
        sport = (sport_di(titolo) or ("Basket" if BASKET_ARD.search(titolo) else None)
                 or (sp_sinossi if sp_sinossi not in (None, "Programma sportivo") else None)  # es. "Handball Bundesliga"
                 or ("Calcio" if re.search(r"3\. Liga|Bundesliga|Fußball|DFB", show + " " + sinossi) else None)
                 or sp_sinossi or sport_di(show))
        eventi.append({"id": f"ard:{t['id']}", "ts": x["ts"], "fine": fine, "sport": sport or "Sport", "titolo": titolo,
                       "titolo_orig": f"{titolo} {show} {sinossi}", "titolo_src": titolo,
                       "descrizione": sinossi, "evento": None, "lingua": "de",  # ARD: nessun campo che distingua gara e programma
                       "emittenti": [{"nome": "ARD " + ((t.get("publicationService") or {}).get("name") or "").strip(),
                                      "pagina": PAGINE["ARD"], "link": f"https://www.ardmediathek.de/video/{t['id']}",
                                      "vpn": "GERMANIA"}]})
    return eventi


def scarica_ard(inizio, fine):
    pagina, err = json_url(ARD_PAGINA)
    if err:
        return [], err

    def dettaglio(t):
        ts = _ts(t["broadcastedOn"])
        if not (inizio.timestamp() - 6 * 3600 <= ts < fine.timestamp()):
            return None  # fuori finestra: non serve il dettaglio
        href = ((t.get("links") or {}).get("target") or {}).get("href")
        d = json_url(href)[0] if href else None
        w = (d or {}).get("widgets") or [{}]
        return w[0]
    return analizza_ard(pagina, dettaglio), None


# ---------- solo dirette di gare, niente programmi ----------
CONF = Path(__file__).resolve().parent.parent / "altri_sport.json"


def _rx_parole(parole):
    parole = [p for p in parole if p]
    if not parole:
        return re.compile(r"(?!x)x")
    alt = "|".join(p if re.search(r"[?\\\[]", p) else re.escape(p) for p in parole)
    return re.compile(r"(?<![\wÀ-ÿ])(?:" + alt + r")(?![\wÀ-ÿ])", re.I)


def regole_conf():
    return json.loads(CONF.read_text(encoding="utf-8")) if CONF.exists() else {}


def regole(conf=None):
    """(regex programmi, regex parole-evento) da altri_sport.json."""
    if conf is None:
        conf = json.loads(CONF.read_text(encoding="utf-8")) if CONF.exists() else {}
    return _rx_parole(conf.get("escludi_programmi", [])), _rx_parole(conf.get("parole_evento", []))


RE_PARTECIPANTI = re.compile(r"\S\s+(?:-|–|gegen|vs\.?|contre|contro)\s+\S|[A-Za-zÀ-ÿ]-[A-ZÀ-Ü][a-zà-ÿ]", re.I)


def e_programma(e, rx_prog, rx_ev):
    """Motivo (testo) se l'elemento è un programma sportivo e non la diretta di una gara, altrimenti None."""
    titolo = e.get("titolo_src") or e.get("titolo") or ""
    m = rx_prog.search(titolo)
    if m:
        return f"parola «{m.group(0)}» nel titolo"
    if e.get("evento") is False and e.get("sport") not in ("Sport", "Programma sportivo"):
        return None  # SRG: il titolo inizia con uno sport preciso ("TENNIS ...", "Sci alpino: ...")
    if not e.get("evento"):  # ARD, o SRG senza id evento: serve un indizio di gara nel titolo o nella descrizione
        testo = titolo + " " + (e.get("descrizione") or "")
        if not (RE_PARTECIPANTI.search(titolo) or rx_ev.search(testo)):
            return "nessuna gara/partita riconoscibile"
    return None


# ---------- unione ----------
def calcio_squadre(ev):
    """(casa, ospite, competizione) per un evento di calcio, o None."""
    t = ev["titolo"]
    comp, _, ultimo = t.rpartition(",")
    ultimo = ultimo.strip()
    for sep in (" - ", " gegen ", " – ", "-"):
        if sep in ultimo:
            a, b = ultimo.split(sep, 1)
            if a.strip() and b.strip():
                return a.strip(), b.strip(), comp.strip()
    return None


PAROLE_VUOTE = {"live", "rennen", "gara", "course", "race", "finale", "final", "runde", "round", "grand", "prix", "premio",
                "weltcup", "männer", "frauen", "women", "men's", "damen", "herren", "elite", "world", "championship"}


def _parola_comune(a, b):
    """Gli eventi della guida TV si uniscono solo se hanno una parola in comune (5 lettere iniziali, es. Singapur/Singapore)."""
    def parole(e):
        t = " ".join([e.get("titolo") or ""] + list(e.get("testi") or [e.get("titolo_orig") or ""]))
        return {w[:5] for w in re.findall(r"[\wÀ-ÿ]{4,}", t.lower()) if w not in PAROLE_VUOTE and not w.isdigit()}
    return bool(parole(a) & parole(b))


RE_SEP_SQUADRE = re.compile(r"\s+(?:-|–|v|vs\.?|at|@|gegen|contro|contre)\s+", re.I)


SPORT_SQUADRE = {"Football americano", "Basket", "Hockey su ghiaccio", "Rugby", "Rugby a 13", "Football australiano",
                 "Sport gaelici", "Pallamano", "Pallavolo", "Baseball", "Tennis", "Tennistavolo", "Boxe", "Freccette",
                 "Snooker", "Unihockey", "Badminton", "Lotta"}


def squadre_evento(e):
    """Due squadre/atleti dal titolo ('A - B', 'A v B', 'A at B', 'A gegen B'), o None (solo sport a squadre/sfide)."""
    if e.get("sport") not in SPORT_SQUADRE:
        return None
    if e.get("nfl_soprannomi"):
        return list(e["nfl_soprannomi"])
    t = (e.get("titolo_src") or e.get("titolo") or "")
    t = t.rsplit(":", 1)[-1].rsplit(",", 1)[-1].strip()
    parti = RE_SEP_SQUADRE.split(t)
    return [x.strip() for x in parti] if len(parti) == 2 and all(x.strip() for x in parti) else None


def _stesse_squadre(a, b):
    """Ogni squadra di a ha una parola (5 lettere iniziali) in comune con una squadra di b, e viceversa."""
    def parole(nome):
        return {w[:5] for w in re.findall(r"[\wÀ-ÿ]{3,}", nome.lower()) if w not in ("new", "the", "city", "fc")}
    pa, pb = [parole(x) for x in a], [parole(x) for x in b]
    return all(any(x & y for y in pb) for x in pa) and all(any(x & y for x in pa) for y in pb)


def _chiave(x):
    return (x.get("teleboy_nome") or x["nome"]).lower()


def _priorita(e):
    """Titolo da tenere quando si uniscono fonti diverse: streaming SRG/ARD/DAZN > LiveOnSat > guida TV > TechRadar."""
    if e.get("nfl_soprannomi"):
        return 0
    if e.get("da_epg"):
        return 1
    if e.get("da_los"):
        return 2
    return 3


def unisci_eventi(eventi):
    """Stesso evento su più emittenti: stesso id swisstxt, oppure stesso sport, emittente diversa,
    inizio entro 45 minuti e titoli simili (es. GP di F1 su SRF, RTS e RSI). Con due squadre nel titolo
    (NFL, NBA, rugby...) devono coincidere le squadre; per guida TV e LiveOnSat serve una parola in comune."""
    import difflib
    uniti = []
    for e in sorted(eventi, key=lambda e: (e["ts"], -_priorita(e))):
        gia = None
        for u in uniti:
            if e["id"] in u["ids"]:
                gia = u
                break
            if (u["sport"] == e["sport"] and e["sport"] not in ("Sport", "Programma sportivo", "Calcio")
                    and abs(u["ts"] - e["ts"]) <= 45 * 60):
                sa, sb = u.get("_squadre") or squadre_evento(u), squadre_evento(e)
                if sa and sb:
                    if _stesse_squadre(sa, sb):
                        gia = u
                        break
                    continue
                if ({_chiave(x) for x in u["emittenti"]} & {_chiave(x) for x in e["emittenti"]}):
                    continue
                deboli = any(x.get("da_epg") or x.get("da_los") for x in (u, e))
                if not deboli or _parola_comune(u, e):
                    gia = u
                    break
            if e["sport"] == "Calcio" == u["sport"] and abs(u["ts"] - e["ts"]) <= 45 * 60:
                a, b = calcio_squadre(u), calcio_squadre(e)
                if a and b and difflib.SequenceMatcher(None, (a[0] + a[1]).lower(), (b[0] + b[1]).lower()).ratio() > 0.6:
                    gia = u
                    break
        if gia is None:
            uniti.append(dict(e, ids={e["id"]}, emittenti=list(e["emittenti"]), testi=[e["titolo_orig"]],
                              _squadre=squadre_evento(e), _prio=_priorita(e), _fonti=[e]))
            continue
        gia["_fonti"].append(e)
        gia["ids"].add(e["id"])
        gia["testi"].append(e["titolo_orig"])
        gia["fine"] = max(gia["fine"], e["fine"])
        if not gia.get("_squadre") or e.get("nfl_soprannomi") is None and squadre_evento(e):
            gia["_squadre"] = gia.get("_squadre") or squadre_evento(e)
        if _priorita(e) > gia["_prio"]:  # titolo e prime emittenti dalla fonte migliore
            for k in ("titolo", "lingua", "titolo_src", "da_epg", "da_los"):
                gia[k] = e.get(k)
            gia["_prio"] = _priorita(e)
            nuove = [x for x in e["emittenti"] if _chiave(x) not in {_chiave(y) for y in gia["emittenti"]}]
            gia["emittenti"] = nuove + gia["emittenti"]
        else:
            for x in e["emittenti"]:
                if _chiave(x) not in {_chiave(y) for y in gia["emittenti"]}:
                    gia["emittenti"].append(x)
        if e["emittenti"] and e["emittenti"][0]["nome"] == "RSI" and e["sport"] != "Calcio":  # titolo in italiano, se c'è
            gia["titolo"] = e["titolo"]
            gia["lingua"] = "it"
    for u in uniti:
        # due squadre: si preferisce il titolo con i nomi completi ("New York Giants - Washington Commanders"
        # invece di "Giants @ Commanders"), qualunque sia la fonte
        if u.get("_squadre"):
            def lung(x):
                t = (x.get("titolo") or "").rsplit(":", 1)[-1].rsplit(",", 1)[-1].strip()
                sq = RE_SEP_SQUADRE.split(t)
                return sum(len(y.strip()) for y in sq) if len(sq) == 2 else 0
            migliore = max(u.get("_fonti", []), key=lung, default=None)
            if migliore is not None and lung(migliore) > lung(u):
                for k in ("titolo", "lingua", "titolo_src"):
                    u[k] = migliore.get(k)
        u.pop("_fonti", None)
        # un canale LiveOnSat che è anche su Teleboy: basta una riga (quella con il link Teleboy)
        u["emittenti"] = [x for x in u["emittenti"] if x.get("fta") is not False or x.get("teleboy")]
    return uniti


def raccogli_altri(inizio, fine, ora, rx_femminile, srg=SRG, scarica_srg_fn=None, scarica_ard_fn=None,
                   conf=None, programmi_tolti=None, scarica_dazn_fn=None, scarica_tb_fn=None, scarica_los_fn=None):
    """(eventi altri sport, partite di calcio, avvisi). Toglie gli eventi già finiti, i programmi sportivi
    (magazine, highlights, studio...: vedi altri_sport.json) e il calcio femminile.
    programmi_tolti (lista), se data, riceve "Emittente gg/mm hh:mm Titolo – motivo" per ogni programma tolto."""
    rx_prog, rx_ev = regole(conf)
    scarica_srg_fn = scarica_srg_fn or scarica_srg
    scarica_ard_fn = scarica_ard_fn or scarica_ard
    tutti, falliti = [], []
    for bu in srg:
        ev, err = scarica_srg_fn(bu)
        if err:
            falliti.append(SRG[bu])
        tutti += ev
    ev, err = scarica_ard_fn(inizio, fine)
    if err:
        falliti.append("ARD")
    tutti += ev
    if scarica_los_fn is not None:  # LiveOnSat altri sport (canali in chiaro nel mondo) + NFL gratis (TechRadar)
        ev, err = scarica_los_fn()
        if err:
            falliti.append("LiveOnSat")
        tutti += ev
    if scarica_tb_fn is not None:  # canali gratuiti di Teleboy (guida TV pubblica)
        ev, err = scarica_tb_fn()
        if err:
            falliti.append("guida TV Teleboy")
        tutti += ev
    if scarica_dazn_fn is not None:  # DAZN Italia, eventi gratis (solo sport diversi dal calcio)
        ev, err = scarica_dazn_fn()
        if err:
            falliti.append("DAZN Italia")
        tutti += [e for e in ev if e["sport"] != "Calcio"]
    tutti = [e for e in tutti if inizio.timestamp() <= e["ts"] < fine.timestamp() and e["fine"] > ora.timestamp()]
    tenuti = []
    for e in tutti:
        motivo = e_programma(e, rx_prog, rx_ev)
        if motivo is None:
            tenuti.append(e)
        elif programmi_tolti is not None:
            quando = dt.datetime.fromtimestamp(e["ts"], ROMA).strftime("%d/%m %H:%M")
            programmi_tolti.append(f'{e["emittenti"][0]["nome"]} {quando} {e.get("titolo_src") or e["titolo"]} – {motivo}')
    tutti = tenuti
    altri, calcio = [], []
    uniti = unisci_eventi(tutti)
    uniti = [e for e in uniti if e["emittenti"]]  # partite LiveOnSat senza nessun canale gratis: via
    for e in uniti:  # titoli in italiano (glossario traduzioni.json); l'originale resta se la traduzione è parziale
        if e.get("lingua", "it") != "it" and e["sport"] != "Calcio":
            it, completa = traduci.traduci(e["titolo"])
            if it != e["titolo"]:
                e["titolo_originale"] = None if completa else e["titolo"]
                e["titolo"] = it
    for e in uniti:
        testi = " ".join(e["testi"])
        if e["sport"] == "Calcio":
            if rx_femminile.search(testi) or re.search(r"\bfrauen|\bfemminil|\bféminin|\bwomen", testi, re.I):
                continue  # niente calcio femminile
            sq = calcio_squadre(e)
            if sq:
                casa, ospite = (traduci.nazione(x) for x in sq[:2])  # nazionali: "Schweiz" -> "Svizzera"
                calcio.append(dict(e, casa=casa, ospite=ospite, comp=sq[2]))
                continue
        altri.append(e)
    avvisi = [f"Altri sport: non raggiungibile {', '.join(falliti)}"] if falliti else []
    return altri, calcio, avvisi


# competizioni (titoli SRG/ARD) -> etichette della sezione calcio
COMP_CALCIO = [
    (r"champions league", 4, "UEFA CHAMPIONS LEAGUE"),
    (r"europa league", 5, "UEFA EUROPA LEAGUE"),
    (r"conference league", 6, "UEFA CONFERENCE LEAGUE"),
    (r"schweizer cup|coppa svizzera|coupe de suisse", 51, "COPPA SVIZZERA"),
    (r"super league", 52, "SUPER LEAGUE (Svizzera)"),
    (r"challenge league", 53, "CHALLENGE LEAGUE (Svizzera)"),
    (r"wm-qualifikation|qualificazioni mondiali|qualifications? (pour la )?coupe du monde", 32, "NAZIONALI – QUALIFICAZIONI MONDIALI"),
    (r"3\. liga", 54, "3. LIGA (Germania)"),
    (r"dfb-pokal", 55, "COPPA DI GERMANIA (DFB-Pokal)"),
]


def competizione_calcio(testo):
    for rx, ordine, etichetta in COMP_CALCIO:
        if re.search(rx, testo or "", re.I):
            return ordine, etichetta
    return 80, "CALCIO SVIZZERA E GERMANIA (dirette streaming)"
