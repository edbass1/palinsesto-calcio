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
    (r"fussball|fußball|calcio|football", "Calcio"),
    (r"formel 1|formula 1|formule 1", "Formula 1"),
    (r"motorrad|motomondiale|moto ?gp|moto ?[23]\b", "Motomondiale"),
    (r"rad\b|radsport|ciclismo|cyclisme", "Ciclismo"),
    (r"ski alpin|sci alpino|ski alpin|riesenslalom|slalom|abfahrt|super-g", "Sci alpino"),
    (r"biathlon", "Biathlon"),
    (r"langlauf|sci di fondo|ski de fond", "Sci di fondo"),
    (r"skispringen|salto con gli sci|saut à ski", "Salto con gli sci"),
    (r"tennis", "Tennis"),
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


def unisci_eventi(eventi):
    """Stesso evento su più emittenti: stesso id swisstxt, oppure stesso sport, emittente diversa,
    inizio entro 45 minuti e titoli simili (es. GP di F1 su SRF, RTS e RSI)."""
    import difflib
    uniti = []
    for e in sorted(eventi, key=lambda e: e["ts"]):
        gia = None
        for u in uniti:
            if e["id"] in u["ids"]:
                gia = u
                break
            if (u["sport"] == e["sport"] and e["sport"] not in ("Sport", "Programma sportivo", "Calcio")
                    and not {x["nome"] for x in u["emittenti"]} & {x["nome"] for x in e["emittenti"]}
                    and abs(u["ts"] - e["ts"]) <= 45 * 60):
                gia = u
                break
            if e["sport"] == "Calcio" == u["sport"] and abs(u["ts"] - e["ts"]) <= 45 * 60:
                a, b = calcio_squadre(u), calcio_squadre(e)
                if a and b and difflib.SequenceMatcher(None, (a[0] + a[1]).lower(), (b[0] + b[1]).lower()).ratio() > 0.6:
                    gia = u
                    break
        if gia is None:
            uniti.append(dict(e, ids={e["id"]}, emittenti=list(e["emittenti"]), testi=[e["titolo_orig"]]))
            continue
        gia["ids"].add(e["id"])
        gia["testi"].append(e["titolo_orig"])
        gia["fine"] = max(gia["fine"], e["fine"])
        for x in e["emittenti"]:
            if x["nome"] not in [y["nome"] for y in gia["emittenti"]]:
                gia["emittenti"].append(x)
        if e["emittenti"][0]["nome"] == "RSI" and e["sport"] != "Calcio":  # titolo in italiano, se c'è
            gia["titolo"] = e["titolo"]
            gia["lingua"] = "it"
    return uniti


def raccogli_altri(inizio, fine, ora, rx_femminile, srg=SRG, scarica_srg_fn=None, scarica_ard_fn=None,
                   conf=None, programmi_tolti=None, scarica_dazn_fn=None):
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
