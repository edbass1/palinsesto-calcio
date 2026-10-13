"""Unione delle due fonti: stessa partita se l'orario differisce al massimo di 15 minuti
e i nomi delle squadre (normalizzati) si somigliano."""
import difflib
import re
import unicodedata

TOLLERANZA_S = 15 * 60

# parole da ignorare nei nomi delle squadre (sigle societarie ecc.)
SIGLE = set("""fc cf afc ac as ss ssc sc sv vfb vfl tsg fsv us ud cd sd rc rcd ca cs club calcio football futbol
futebol de la le el the of and sk fk nk bk if ik aik ks kv krc cfc ec se sa sad sporting_ spvgg hsc bsc 1 2""".split())

# alias (già normalizzati): nome -> forma canonica
ALIAS = {
    "internazionale": "inter", "inter milan": "inter", "inter milano": "inter",
    "milan": "milan", "ac milan": "milan",
    "bayern munich": "bayern munchen", "bayern": "bayern munchen", "fc bayern munchen": "bayern munchen",
    "man utd": "manchester united", "man united": "manchester united", "manchester utd": "manchester united",
    "man city": "manchester city",
    "psg": "paris saint germain", "paris sg": "paris saint germain", "paris st germain": "paris saint germain",
    "paris": "paris saint germain",
    "athletic bilbao": "athletic", "athletic club": "athletic",
    "atletico madrid": "atletico", "atletico de madrid": "atletico", "atl madrid": "atletico",
    "tottenham": "tottenham hotspur", "spurs": "tottenham hotspur",
    "wolves": "wolverhampton wanderers", "wolverhampton": "wolverhampton wanderers",
    "nottm forest": "nottingham forest", "nott m forest": "nottingham forest",
    "newcastle": "newcastle united", "west ham": "west ham united", "leeds": "leeds united",
    "brighton": "brighton hove albion", "brighton and hove albion": "brighton hove albion",
    "koln": "koln", "cologne": "koln", "fortuna cologne": "fortuna koln", "1 fc koln": "koln",
    "nuremberg": "nurnberg", "1 fc nurnberg": "nurnberg",
    "monchengladbach": "borussia monchengladbach", "gladbach": "borussia monchengladbach",
    "dortmund": "borussia dortmund", "leverkusen": "bayer leverkusen", "frankfurt": "eintracht frankfurt",
    "leipzig": "rb leipzig", "rasenballsport leipzig": "rb leipzig",
    "olympique marseille": "marseille", "olympique de marseille": "marseille", "om": "marseille",
    "olympique lyonnais": "lyon", "olympique lyon": "lyon", "ol": "lyon",
    "celta vigo": "celta", "celta de vigo": "celta", "deportivo la coruna": "deportivo",
    "siviglia": "sevilla", "slavia praga": "slavia praha", "slavia prague": "slavia praha",
    "real betis": "betis", "betis sevilla": "betis", "sevilla": "sevilla",
    "sporting lisbon": "sporting cp", "sporting": "sporting cp",
    "olympiacos": "olympiakos", "olympiakos piraeus": "olympiakos",
    "csu craiova": "universitatea craiova", "cs universitatea craiova": "universitatea craiova", "u craiova": "universitatea craiova",
    "stella rossa": "crvena zvezda", "red star belgrade": "crvena zvezda", "red star": "crvena zvezda",
    "fk crvena zvezda": "crvena zvezda", "crvena zvezda beograd": "crvena zvezda",
    "bayern monaco": "bayern munchen", "stoccarda": "stuttgart", "vfb stuttgart": "stuttgart", "friburgo": "freiburg",
    "colonia": "koln", "lione": "lyon", "marsiglia": "marseille", "bruges": "club brugge", "brugge": "club brugge",
    "como 1907": "como", "hellas verona": "verona",
    "usa": "united states", "korea republic": "south korea", "turkiye": "turkey", "czechia": "czech republic",
    "republic of ireland": "ireland", "ir iran": "iran",
}
# sostituzioni di parole
PAROLE = {"utd": "united", "st": "saint", "munich": "munchen", "cologne": "koln", "nuremberg": "nurnberg",
          "&": "and", "saint-germain": "saint germain"}


def norm_squadra(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    if s.strip() in ALIAS:
        return ALIAS[s.strip()]
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s in ALIAS:
        return ALIAS[s]
    parole = [PAROLE.get(w, w) for w in s.split()]
    s2 = " ".join(parole)
    if s2 in ALIAS:
        return ALIAS[s2]
    ridotto = " ".join(w for w in parole if w not in SIGLE and not w.isdigit()) or s2
    return ALIAS.get(ridotto, ridotto)


# marcatori di squadre diverse (giovanili, femminili, seconde squadre): devono coincidere da entrambe le parti
MARCATORI = re.compile(r"^(u\d\d|under\d*|sub\d*|youth|juniors?|primavera|women|womens|w|femminile|feminino|femenino|"
                       r"frauen|ladies|b|ii|iii|reserves?|amateure|2)$")
# parole che, se in più, indicano un'ALTRA squadra (Inter / Inter Miami, Real / Real Sociedad...)
DISTINTIVE = set("miami city sociedad madrid betis valladolid oviedo zaragoza murcia salt lake york galaxy".split())


def marcatori(nome: str):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\bu[- ]?(\d\d)\b", r"u\1", s)
    return {w for w in re.split(r"[^a-z0-9]+", s) if w and MARCATORI.match(w) and w != "2"}


def somiglianza(a: str, b: str) -> float:
    if marcatori(a) != marcatori(b):
        return 0.0  # Roma / Roma U19, Barcelona / Barcelona B
    a, b = norm_squadra(a), norm_squadra(b)
    if a == b:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    if (ta ^ tb) & DISTINTIVE:
        return 0.0  # Manchester United / Manchester City, Inter / Inter Miami
    r = difflib.SequenceMatcher(None, a, b).ratio()
    if ta and tb and (ta <= tb or tb <= ta):
        piccolo, extra = (ta, tb - ta) if ta <= tb else (tb, ta - tb)
        if not (extra & DISTINTIVE) and max(len(w) for w in piccolo) >= 3:
            r = max(r, 0.9)  # "Leeds" / "Leeds United", "PSV" / "PSV Eindhoven"
    elif ta and tb and min(len(a), len(b)) >= 5 and (a.replace(" ", "") in b.replace(" ", "") or b.replace(" ", "") in a.replace(" ", "")):
        r = max(r, 0.85)  # "Monchengladbach" / "Borussia M gladbach"-like containment
    return r


def stessa_partita(ts1, casa1, osp1, ts2, casa2, osp2) -> float:
    """Punteggio 0..2 se è la stessa partita, altrimenti 0."""
    if abs(ts1 - ts2) > TOLLERANZA_S:
        return 0.0
    migliore = 0.0
    for c2, o2 in ((casa2, osp2), (osp2, casa2)):  # anche a squadre invertite
        sc, so = somiglianza(casa1, c2), somiglianza(osp1, o2)
        if (sc >= 0.8 and so >= 0.6) or (sc >= 0.6 and so >= 0.8):
            migliore = max(migliore, sc + so)
    return migliore


def regex_femminile(marcatori):
    """Regex delle parole del calcio femminile: parole intere (anche con s/'s finale)."""
    parole = "|".join(re.escape(m.lower()) for m in sorted(set(marcatori), key=len, reverse=True) if m.strip())
    return re.compile(r"(?<![\w])(?:" + parole + r")(?:s|'s|’s)?(?![\w])" if parole else r"(?!x)x", re.I)


RE_COMP_W = re.compile(r"\(w\)", re.I)                 # "Friendly International (W)"
RE_SQUADRA_W = re.compile(r"(?:\sW|\s?\(W\))$")        # "Arsenal W", "Lyon (W)" (W maiuscola, alla fine)


def femminile(rx, competizione="", squadre=()):
    """True se la partita è di calcio femminile: una parola-chiave nella competizione o in una squadra,
    "(W)" nella competizione, oppure ENTRAMBE le squadre che finiscono con " W" / "(W)"."""
    competizione = competizione or ""
    squadre = [(s or "").strip() for s in squadre]
    if rx.search(competizione) or RE_COMP_W.search(competizione) or any(rx.search(s) for s in squadre):
        return True
    casa_osp = [s for s in squadre[:2] if s]
    return len(casa_osp) == 2 and all(RE_SQUADRA_W.search(s) for s in casa_osp)


def chiave_canale(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", re.sub(r"\b(hd|uk|tv)\b", "", s))


def regola_canali(conf):
    """Funzione nome -> motivo (testo) se il canale è russo/iraniano da escludere, altrimenti None.
    conf = liveonsat.json (chiavi "escludi_russi_iraniani" e "mai_escludere"); paese_teleboy(nome) -> "ru"/"ir"/... opzionale."""
    r = (conf or {}).get("escludi_russi_iraniani") or {}
    paesi = re.compile(r"(?<![\wа-я])(?:" + "|".join(map(re.escape, r.get("paesi") or ["(?!x)x"])) + r")(?![\wа-я])", re.I)
    nomi = [re.compile(x, re.I) for x in r.get("nomi", [])]
    pt = {x.lower() for x in r.get("paesi_teleboy", [])}
    mai = [x.lower() for x in (conf or {}).get("mai_escludere", []) if x]

    def motivo(nome, paese_teleboy=None):
        n = re.sub(r"\s+", " ", nome or "").strip()
        if any(x in n.lower() for x in mai):
            return None
        m = paesi.search(n)
        if m:
            return f"paese «{m.group(0)}» nel nome"
        for rx in nomi:
            if rx.search(n):
                return f"nome noto ({rx.pattern})"
        if paese_teleboy and paese_teleboy.lower() in pt:
            return f"paese Teleboy {paese_teleboy}"
        return None
    return motivo
