"""Altri sport in streaming gratuito: SRF, RTS, RSI (Svizzera, API pubblica SRG "integration layer")
e ARD Mediathek (Germania, API pubblica "page-gateway"). Le partite di calcio trovate qui vanno nella
sezione calcio; tutto il resto nella sezione "Altri sport"."""
import datetime as dt
import json
import re
from pathlib import Path
import time
import urllib.request

import sport_nomi
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

# parola nello sport o nel titolo (it/en/pt/es/fr/de/ro/nl/pl/...) -> sport in italiano.
# L'ordine conta: la prima espressione che compare vince (football americano prima di football,
# tennis da tavolo prima del tennis, hockey su pista prima di hockey).
SPORT = [
    (r"nfl|american football|football am[ée]ricain|football americano|f[uú]tbol americano|futebol americano|fotbal american", "Football americano"),
    (r"australian football|aussie rules|football australiano", "Football australiano"),
    (r"gaelic football|sport gaelici|giochi gaelici|\bgaa\b", "Sport gaelici"),
    (r"calcio a 5|futsal|futebol de sal[aã]o|f[uú]tbol sala|zaalvoetbal", "Calcio a 5"),
    (r"fu(?:ß|ss)ball|futebol(?! americano)|f[uú]tbol(?! americano)|voetbal|fotbal(?! american)|soccer|calcio(?! a 5)|football(?! americano)(?! am[ée]ricain)", "Calcio"),
    (r"formel 1|formula 1|formule 1|formula one", "Formula 1"),
    (r"motorrad|motomondiale|moto ?gp|moto ?[23]\b", "Motomondiale"),
    (r"rad\b|radsport|ciclismo|cyclisme|cycling|wielrennen|kolarstwo|ciclism\b|wielersport", "Ciclismo"),
    (r"ski alpin|sci alpino|alpiner ski|alpine skiing|esqu[ií] alpino|riesenslalom|slalom|abfahrt|super-g", "Sci alpino"),
    (r"biathlon|biatlo|biatlon", "Biathlon"),
    (r"langlauf|sci di fondo|ski de fond|esqu[ií] de fundo|cross-country ski", "Sci di fondo"),
    (r"skispringen|salto con gli sci|saut [aà] ski|ski jumping|salto de esqu[ií]", "Salto con gli sci"),
    (r"\bsci\b|\bski\b|\bschi\b|esqu[ií]|narty|skidor|skisport|skifahren|\bskiing\b", "Sci"),
    (r"tischtennis|tennistavolo|tennis de table|tennis de mesa|tenis de mesa|tenis de masa|t[eé]nis de mesa|tennis da tavolo|table tennis|ping[- ]?pong|tafeltennis", "Tennistavolo"),
    (r"(?<!tisch)(?<!table )tennis(?! de table)(?!tavolo)(?! de mesa)(?! da tavolo)|t[eé]nis(?! de mesa)(?! de table)(?! da tavolo)", "Tennis"),
    (r"beach ?volley|beachvolleyball|volley(?:ball)? de plage|v[oô]lei de praia|volei pe plaja|voley playa|volley playa|strandvolley", "Beach volley"),
    (r"hockey pista|hockey su pista|rollhockey|rink hockey|roller hockey|hockey sur patins|h[oó]quei em patins|hockey sobre patines", "Hockey pista"),
    (r"hockey su prato|field hockey|hockey sur gazon|feldhockey|h[oó]quei em campo", "Hockey su prato"),
    (r"eishockey|hockey su ghiaccio|hockey sur glace|h[oó]quei no gelo|hockey sobre hielo|ijshockey|ice hockey|hochei(?: pe gheata)?|ishockey|hockey", "Hockey su ghiaccio"),
    (r"baseball|softball|beisebol|b[eé]isbol", "Baseball"),
    (r"wasserball|pallanuoto|water ?polo|polo aqu[aá]tico|polo pe apa|vaterpolo", "Pallanuoto"),
    (r"fechten|scherma|escrime|esgrima|schermen|scrima", "Scherma"),
    (r"bogenschie|tiro con l'arco|tir [aà] l'arc|archery|tiro com arco|tiro con arco", "Tiro con l'arco"),
    (r"klettern|arrampicata|escalade|escalada|climbing", "Arrampicata"),
    (r"\bmma\b|mixed martial|artes marciais|artes marciales|arts martiaux mixtes", "MMA"),
    (r"kick ?box", "Kickboxing"),
    (r"muay ?thai", "Muay Thai"),
    (r"unihockey|floorball", "Unihockey"),
    (r"kunstturnen|ginnastica|gymnastique|turnen|gimnastica|gymnastics", "Ginnastica artistica"),
    (r"curling", "Curling"),
    (r"handball|pallamano|handebol|andebol|balonmano|handbal|handbol", "Pallamano"),
    (r"euroleague|eurocup|nba|basketball|basket-ball|basquetebol|basquete|baloncesto|b[aá]squetbol|basquet\b|baschet|pallacanestro|basketbol|basket", "Basket"),
    (r"volleyball|pallavolo|volley|v[oô]lei\b|voleibol", "Pallavolo"),
    (r"leichtathletik|atletica|athl[eé]tisme|atletismo|atletism\b|atletiek|athletics|marathon|maratona", "Atletica"),
    (r"schwimmen|nuoto|natation|swimming|nata[cç][aã]o|nataci[oó]n|zwemmen|\binot\b", "Nuoto"),
    (r"box|boxe|pugilato|boxeo|boxen|boksen|pugilismo", "Boxe"),
    (r"eiskunstlauf|pattinaggio|patinage|figure skating|danse sur glace|eistanz|ice dance|danza su ghiaccio", "Pattinaggio"),
    (r"tanzsport|danza sportiva|danse sportive|tanz|danza|danse", "Danza sportiva"),
    (r"golf", "Golf"),
    (r"reiten|equitazione|hippisme|springreiten|equita[cç][aã]o|equitaci[oó]n", "Equitazione"),
    (r"schwingen|lotta svizzera|lutte suisse", "Lotta svizzera"),
    (r"rudern|canottaggio|aviron|rowing", "Canottaggio"),
    (r"segeln|vela|voile|sailing", "Vela"),
    (r"triathlon|triatlo|triatl[oó]n", "Triathlon"),
    (r"uci|gravel|paris-tours|giro d|tour de france|vuelta|radrennen|cyclo-cross|querfeldein|lombardei", "Ciclismo"),
    (r"snooker", "Snooker"),
    (r"darts|freccette|fl[eé]chettes|dardos|darten", "Freccette"),
    (r"dtm|superbike|motorsport|desportos motorizados|deportes de motor|nascar|rallye|rally|wec|indycar|formel e|formula e|gt masters|motocross|sport auto|automobilismo|\bmotor\b", "Motori"),
    (r"rugby league|rugby a 13|rugby [aà] xiii", "Rugby a 13"),
    (r"rugby", "Rugby"),
    (r"badminton", "Badminton"),
    (r"judo", "Judo"),
    (r"ringen|lutte|wrestling|luta|lucha|worstelen|lupte", "Lotta"),
    (r"bobsport|bob-weltcup|zweierbob|viererbob|monobob|rodeln|skeleton|slittino|bobsleigh", "Bob e slittino"),
    (r"skicross|snowboard|freeski", "Sport invernali"),
    (r"sport estremi|extreme sports|adventure sports|desportos radicais|deportes extremos", "Sport estremi"),
    (r"sportschau|sportpanorama|sport", "Programma sportivo"),
]
# squadre di basket ARD (i titoli dicono solo "A gegen B")
BASKET_ARD = re.compile(r"gladiators trier|telekom baskets|alba berlin|ratiopharm ulm|bayern basketball", re.I)


def sport_di(testo):
    """Sport italiano di un titolo. Prima le espressioni note, poi l'etichetta iniziale
    («Basquetebol: …», «Ténis: …») tramite sport.json."""
    t = testo.lower()
    for rx, nome in SPORT:
        if re.search(r"(?<![a-zà-ü])(?:" + rx + r")", t):
            return nome
    testa = re.split(r"[:|,]", testo, maxsplit=1)[0].strip()
    if testa and len(testa.split()) <= 6 and sport_nomi.conosciuto(testa):
        return sport_nomi.normalizza(testa)
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
                                   "vpn": "SVIZZERA"}]})  # siti SRG: con VPN Svizzera (richiesta utente)
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


RE_DUE = re.compile(r"\S\s+(?:vs\.?|v|@|at|-|–|gegen|contro|contre)\s+\S", re.I)
RE_PREFISSO_LEGA = re.compile(r"^\s*(?:NFL|NBA|NHL|MLB|NCAA|College Football|Football|American Football|Fußball|Tennis|Basketball|Eishockey|Rugby)\s*[-–:|]\s*", re.I)


def due_partecipanti(testo):
    """True se nel testo ci sono due squadre/atleti ('A vs B', 'A @ B', 'A - B'), senza contare 'NFL - ...'."""
    return bool(RE_DUE.search(RE_PREFISSO_LEGA.sub("", testo or "")))


def _rx_salvo():
    parole = regole_conf().get("escludi_salvo_partecipanti", [])
    return re.compile(r"(?<![\w])(?:" + "|".join(parole) + r")(?![\w])", re.I) if parole else None


def e_programma(e, rx_prog, rx_ev, rx_salvo=None):
    """Motivo (testo) se l'elemento è un programma sportivo e non la diretta di una gara, altrimenti None."""
    titolo = e.get("titolo_src") or e.get("titolo") or ""
    m = rx_prog.search(titolo)
    if m:
        return f"parola «{m.group(0)}» nel titolo"
    rx_salvo = rx_salvo if rx_salvo is not None else _rx_salvo()
    m = rx_salvo.search(titolo) if rx_salvo else None
    if m and not due_partecipanti(titolo):
        return f"programma «{m.group(0)}» senza due partecipanti"
    # vale per lo sport già chiamato «Football americano». «Fútbol americano» e simili
    # erano una sezione visibile: unificarli non deve togliere le schede senza due squadre
    if (e.get("sport") == "Football americano" and not e.get("sport_orig")
            and not (due_partecipanti(titolo) or due_partecipanti(e.get("titolo") or "")
                     or due_partecipanti(e.get("descrizione") or ""))):
        return "football americano senza due squadre"
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


def squadre_per_calcio(ev, largo=False):
    """Come calcio_squadre. Con largo anche «A x B» e «A vs B» (Futebol, Football)."""
    sq = calcio_squadre(ev)
    if sq or not largo:
        return sq
    t = ev.get("titolo") or ""
    comp, _, ultimo = t.rpartition(",")
    ultimo = ultimo.strip()
    m = re.search(r"\s+(?:x|vs\.?|v|@)\s+", ultimo, re.I)
    if not m:
        return None
    a, b = ultimo[:m.start()].strip(), ultimo[m.end():].strip()
    return (a, b, comp.strip()) if a and b else None


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
    (NFL, NBA, rugby...) devono coincidere le squadre; per guida TV e LiveOnSat serve una parola in comune.
    Lo sport è prima portato al nome italiano, così «Basquetebol» e «Basket» sono lo stesso evento."""
    import difflib
    for e in eventi:
        sport_nomi.applica(e)
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
        if e.get("sport_orig") and not gia.get("sport_orig"):
            gia["sport_orig"] = e["sport_orig"]
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
        u["emittenti"] = [x for x in u["emittenti"] if x.get("fta") is not False or x.get("teleboy") or x.get("pp") or x.get("ufficiale")]
    return uniti


CALCIO_GENERICO = []  # ultima raccolta: eventi di calcio senza squadre (es. "UEFA Champions League") tolti da ALTRI SPORT
CALCIO_TOLTO_ALTRI = []  # ... e la loro descrizione per il log
RE_CALCIO_ALTRI = re.compile(r"\buefa\b|\bfu(?:ß|ss)ball|\bsoccer\b|\bvoetbal|\bcalcio\b(?! a 5)|\bfootball\b(?! americano)(?! americain)", re.I)


def e_calcio(e):
    """True se un evento degli altri sport è in realtà calcio (sport 'Calcio' o 'UEFA', 'Fußball', 'calcio'... nel titolo).
    Non tocca 'Champions League' di pallamano/pallavolo (EHF, CEV): serve proprio la parola UEFA o calcio/football."""
    if e.get("sport") == "Calcio":
        return True
    if e.get("sport") in ("Football americano", "Calcio a 5", "Futsal", "Rugby", "Football australiano"):
        return False
    testo = " ".join(str(x) for x in (e.get("titolo"), e.get("titolo_src")) if x)
    return bool(RE_CALCIO_ALTRI.search(testo)) and not re.search(r"american|nfl|rugby|futsal|australian|gaelic", testo, re.I)


BASKET_TOLTI = []  # ultima raccolta: "titolo – motivo" delle partite di basket tolte (per il log)


def _escluso_donne(rx):
    """True se la regex di basket_esclusi è basket femminile (non 3x3 né G League)."""
    p = rx.pattern
    return "3x3" not in p and "League" not in p


def filtro_basket(cat=None):
    """Funzione evento -> None (tenere) o motivo (togliere).

    basket_ammessi e le esclusioni che non sono il femminile (3x3, G League) valgono solo
    per gli eventi che la fonte chiamava già Basket: erano già filtrati prima.
    Basquetebol, Basketball, Baloncesto e gli altri nomi si spostano nella sezione Basket
    e restano in pagina. Il basket femminile si toglie comunque.
    """
    if cat is None:
        try:
            cat = json.loads((Path(__file__).resolve().parent.parent / "categorie.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cat = {}
    ammessi = [(v["nome"], [re.compile(r, re.I) for r in v.get("regex", [])], v.get("solo_titolo", False))
               for v in cat.get("basket_ammessi", [])]
    esclusi = [re.compile(r, re.I) for r in cat.get("basket_esclusi", [])]
    donne = [r for r in esclusi if _escluso_donne(r)]

    def fn(e):
        if e.get("sport") != "Basket" or not ammessi:
            return None
        testo = " | ".join(str(x) for x in [e.get("sport"), e.get("sport_orig"), e.get("titolo"), e.get("titolo_orig"),
                                            e.get("titolo_src"), e.get("comp"), e.get("descrizione"),
                                            *(e.get("testi") or [])] if x)
        for r in donne:
            if r.search(testo):
                return f"escluso ({r.pattern})"
        if e.get("sport_orig") and sport_nomi.chiave(e["sport_orig"]) != "basket":
            return None
        for r in esclusi:
            if r.search(testo):
                return f"escluso ({r.pattern})"
        titoli = " | ".join(str(x) for x in [e.get("titolo"), e.get("titolo_src")] if x)
        for nome, rxs, solo_t in ammessi:
            if any(r.search(titoli if solo_t else testo) for r in rxs):
                return None
        return "competizione non nella lista basket_ammessi"
    return fn


def fonte_calcio(e):
    """True se la fonte lo chiamava già Calcio. Futebol, Football e Soccer no."""
    return sport_nomi.chiave(e.get("sport_orig") or e.get("sport") or "") == "calcio"


def gia_calcio(e):
    """True se, col nome della fonte, l'evento era già instradato al calcio (sport o titolo)."""
    return e_calcio({"sport": e.get("sport_orig") or e.get("sport"), "titolo": e.get("titolo"),
                     "titolo_src": e.get("titolo_src")})


def raccogli_altri(inizio, fine, ora, rx_femminile, srg=SRG, scarica_srg_fn=None, scarica_ard_fn=None,
                   conf=None, programmi_tolti=None, scarica_dazn_fn=None, scarica_tb_fn=None, scarica_los_fn=None,
                   scarica_el_fn=None, scarica_pp_fn=None, categorie=None):
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
    if scarica_pp_fn is not None:  # programma ufficiale Prima Sport (Prima Play), sport diversi dal calcio
        ev, err = scarica_pp_fn()
        if err:
            falliti.append("Prima Play")
        tutti += ev
    if scarica_el_fn is not None:  # EuroLeague/EuroCup sui canali scelti (pagine ufficiali TV Listings)
        ev, err = scarica_el_fn()
        if err:
            falliti.append(err)
        tutti += ev
    if scarica_tb_fn is not None:  # canali gratuiti di Teleboy (guida TV pubblica)
        ev, err = scarica_tb_fn()
        if err:
            falliti.append("guida TV Teleboy")
        tutti += ev
    if scarica_dazn_fn is not None:  # DAZN Italia, eventi gratis (solo sport diversi dal calcio)
        ev, err = scarica_dazn_fn()
        if err:
            falliti.append(f"DAZN altri sport: {err}")
        # solo il calcio già chiamato «Calcio» (raccolto con le partite). Futebol, Football,
        # Soccer e Fußball entrano e finiscono nella sezione calcio, senza sparire
        tutti += [e for e in ev if not fonte_calcio(e)]
    for e in tutti:
        sport_nomi.applica(e)  # stesso sport, qualunque lingua della fonte, prima di unire e filtrare
    tutti = [e for e in tutti if inizio.timestamp() <= e["ts"] < fine.timestamp() and e["fine"] > ora.timestamp()]
    tenuti = []
    rx_salvo = _rx_salvo()
    for e in tutti:
        motivo = e_programma(e, rx_prog, rx_ev, rx_salvo)
        if motivo is None:
            tenuti.append(e)
        elif programmi_tolti is not None:
            quando = dt.datetime.fromtimestamp(e["ts"], ROMA).strftime("%d/%m %H:%M")
            programmi_tolti.append(f'{e["emittenti"][0]["nome"]} {quando} {e.get("titolo_src") or e["titolo"]} – {motivo}')
    tutti = tenuti
    altri, calcio = [], []
    uniti = unisci_eventi(tutti)
    uniti = [e for e in uniti if e["emittenti"]]  # partite LiveOnSat senza nessun canale gratis: via
    basket = filtro_basket(categorie)  # basket: solo le competizioni ammesse (categorie.json -> basket_ammessi)
    BASKET_TOLTI[:] = []
    tenuti = []
    for e in uniti:
        motivo = basket(e)
        if motivo:
            BASKET_TOLTI.append(f'{dt.datetime.fromtimestamp(e["ts"], ROMA):%d/%m %H:%M} {e["titolo"]} [{e.get("comp") or e.get("descrizione") or ""}] – {motivo}')
        else:
            tenuti.append(e)
    uniti = tenuti
    for e in uniti:  # titoli in italiano (glossario traduzioni.json); l'originale resta se la traduzione è parziale
        if e.get("lingua", "it") != "it" and e["sport"] != "Calcio":
            it, completa = traduci.traduci(e["titolo"])
            if it != e["titolo"]:
                e["titolo_originale"] = None if completa else e["titolo"]
                e["titolo"] = it
    CALCIO_GENERICO[:] = []
    CALCIO_TOLTO_ALTRI[:] = []
    for e in uniti:
        testi = " ".join(e["testi"])
        if e["sport"] == "Calcio" or e_calcio(e):
            # il calcio non entra in ALTRI SPORT. Quello che la fonte chiamava già calcio segue
            # le regole di prima (femminile tolto; senza squadre solo come canale in più).
            # Futebol, Football, Soccer e gli altri nomi si spostano nel calcio e restano schede
            gia = gia_calcio(e)
            if gia and (rx_femminile.search(testi) or re.search(r"\bfrauen|\bfemminil|\bféminin|\bwomen", testi, re.I)):
                continue
            sq = squadre_per_calcio(e, largo=not gia)
            if sq:
                casa, ospite = (traduci.nazione(x) for x in sq[:2])  # nazionali: "Schweiz" -> "Svizzera"
                calcio.append(dict(e, casa=casa, ospite=ospite, comp=sq[2], da_etichetta=not gia))
            elif gia:  # "UEFA Champions League" senza squadre: si prova solo ad aggiungere il canale a una partita già nota
                CALCIO_GENERICO.append(e)
                CALCIO_TOLTO_ALTRI.append(f'{dt.datetime.fromtimestamp(e["ts"], ROMA):%d/%m %H:%M} {e["titolo"]} '
                                          f'({", ".join(x["nome"] for x in e["emittenti"])})')
            else:
                calcio.append(dict(e, casa=e.get("titolo") or "Calcio", ospite="", comp="", da_etichetta=True))
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
    return 80, COMP_SCONOSCIUTA


# competizione non riconosciuta: la partita streaming si usa solo per aggiungere il canale a una partita già nota,
# mai come scheda nuova (niente più sezione "CALCIO SVIZZERA E GERMANIA (dirette streaming)" con repliche notturne)
COMP_SCONOSCIUTA = "CALCIO (dirette streaming)"
