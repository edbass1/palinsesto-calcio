"""Seconda fonte: LiveOnSat (liveonsat.com). Solo partite con canali in chiaro (FTA).

Struttura della pagina (verificata sull'HTML reale):
  <span class = comp_head>Italian Serie A - Week 6</span>
  <div class = blockfix > ... <div class = fLeft style="...">Genoa v Fiorentina</div>
      <div class="fLeft_time_live dynamic-time" data-timestamp="1791637200"> ST: 13:00 </div>
      <a href="#" class = chan_live_free ... onmouseout="return nd();">BBC One HD </a>
  - data-timestamp = secondi Unix (UTC) del calcio d'inizio
  - classe chan_live_free = canale in chiaro (mostrato in rosso, #A52A2A, dal CSS del sito)
  - chan_live_not_free / chan_live_iptvcable = pay/criptato/streaming; chan_other_* = differite; *_postponed = rinviata
"""
import datetime as dt
import html
import re
import time
import urllib.error
import urllib.request

UTC = dt.timezone.utc
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

RE_TOKEN = re.compile(r'<h2 class = time_head>(.*?)</h2>|<span class = comp_head>(.*?)</span>|<div class = blockfix >', re.S)
RE_TITOLO = re.compile(r'<div class = fLeft style="[^"]*">(.*?)</div>', re.S)
RE_TS = re.compile(r'data-timestamp="(\d+)"')
RE_ST = re.compile(r'ST:\s*(\d{1,2}):(\d\d)')
RE_CANALE = re.compile(r'class = (chan_\w+)\b.*?onmouseout="return nd\(\);">([^<]+)</a>', re.S)

# competizioni LiveOnSat -> (ordine, etichetta italiana); stesse etichette della fonte LiveSoccerTV
COMPETIZIONI_LOS = [
    (r"^Italian Serie A$", 1, "SERIE A"),
    (r"^Italian Serie B", 2, "SERIE B"),
    (r"^Italian Serie C", 7, "SERIE C"),
    (r"^(Italian )?Coppa Italia", 3, "COPPA ITALIA"),
    (r"^English Premier League$", 10, "PREMIER LEAGUE"),
    (r"^Spanish La Liga \(Primera\)$", 11, "LALIGA"),
    (r"^German 1\. Bundesliga$", 12, "BUNDESLIGA"),
    (r"^French Ligue 1$", 13, "LIGUE 1"),
    (r"^UEFA Champions League", 4, "UEFA CHAMPIONS LEAGUE"),
    (r"^UEFA Europa League", 5, "UEFA EUROPA LEAGUE"),
    (r"^UEFA (Europa )?Conference League", 6, "UEFA CONFERENCE LEAGUE"),
    (r"^UEFA Super Cup", 7, "SUPERCOPPA EUROPEA"),
    (r"^UEFA Youth League", 25, "UEFA YOUTH LEAGUE"),
    (r"^UEFA Wom[ae]n'?s Champions League", 26, "UEFA WOMEN'S CHAMPIONS LEAGUE"),
    (r"^UEFA Nations League", 30, "NAZIONALI – UEFA NATIONS LEAGUE"),
    (r"Women.*World Cup.*Qualif", 36, "NAZIONALI FEMMINILI – QUALIFICAZIONI MONDIALI 2027"),
    (r"^English Championship$", 40, "CHAMPIONSHIP (Inghilterra)"),
    (r"^German 2\. Bundesliga$", 41, "2. BUNDESLIGA"),
    (r"^Dutch Eredivisie$", 42, "EREDIVISIE (Olanda)"),
    (r"^Portuguese Liga 1$", 43, "PRIMEIRA LIGA (Portogallo)"),
    (r"^(Türkiye|Turkish) Süper Lig$", 44, "SÜPER LIG (Turchia)"),
    (r"^Greek Super League 1$", 45, "SUPER LEAGUE (Grecia)"),
    (r"^Romanian Superliga$", 46, "LIGA I (Romania)"),
    (r"^Romanian Liga 2$", 47, "LIGA II (Romania)"),
    (r"^Saudi Pro League$", 60, "SAUDI PRO LEAGUE (Arabia Saudita)"),
    (r"^Brazilian Série A$", 70, "BRASILEIRÃO SERIE A (Brasile)"),
    (r"^Brazilian Série B$", 71, "SERIE B BRASILE"),
    (r"^Brazilian Série C$", 72, "SERIE C BRASILE"),
    (r"^Argentinean Primera División$", 73, "LIGA PROFESIONAL (Argentina)"),
    (r"^Mexican Liga MX", 74, "LIGA MX (Messico)"),
    (r"^USL Championship", 75, "USL CHAMPIONSHIP (USA)"),
    (r"^Major League Soccer", 76, "MLS (USA)"),
    (r"^Friendly International \(W\)", 37, "NAZIONALI FEMMINILI – AMICHEVOLI"),
    (r"^(International Friendl|Friendly International$)", 31, "NAZIONALI – AMICHEVOLI"),
    (r"^FIFA World Cup.*Qualif", 32, "NAZIONALI – QUALIFICAZIONI MONDIALI"),
]


# aggettivo/paese inglese all'inizio del nome -> paese in italiano (per le competizioni non in elenco)
PAESI_LOS = [
    ("Northern Ireland", "Irlanda del Nord"), ("English", "Inghilterra"), ("Scottish", "Scozia"), ("Cymru", "Galles"),
    ("Welsh", "Galles"), ("Irish", "Irlanda"), ("German", "Germania"), ("French", "Francia"), ("Spanish", "Spagna"),
    ("Italian", "Italia"), ("Portuguese", "Portogallo"), ("Dutch", "Olanda"), ("Belgian", "Belgio"),
    ("Swiss", "Svizzera"), ("Austrian", "Austria"), ("Greek", "Grecia"), ("Türkiye", "Turchia"), ("Turkish", "Turchia"),
    ("Polish", "Polonia"), ("Czech", "Rep. Ceca"), ("Slovak", "Slovacchia"), ("Romanian", "Romania"),
    ("Croatian", "Croazia"), ("Serbian", "Serbia"), ("Danish", "Danimarca"), ("Swedish", "Svezia"),
    ("Norwegian", "Norvegia"), ("Russian", "Russia"), ("Ukrainian", "Ucraina"), ("Azerbaijan", "Azerbaigian"),
    ("South Korean", "Corea del Sud"), ("Japanese", "Giappone"), ("Australian", "Australia"), ("Brazilian", "Brasile"),
    ("Argentinean", "Argentina"), ("Mexican", "Messico"), ("Colombian", "Colombia"), ("Saudi", "Arabia Saudita"),
    ("Israeli", "Israele"), ("Cypriot", "Cipro"), ("Bulgarian", "Bulgaria"), ("Hungarian", "Ungheria"),
    ("Latvian", "Lettonia"), ("Lithuanian", "Lituania"), ("Slovenian", "Slovenia"), ("Albanian", "Albania"),
    ("Kosovo", "Kosovo"), ("Montenegrin", "Montenegro"), ("North Macedonian", "Macedonia del Nord"),
    ("Bosnia-Herzegovina", "Bosnia"), ("Belarus", "Bielorussia"), ("South African", "Sudafrica"),
    ("Chinese", "Cina"), ("Indian", "India"), ("Moroccan", "Marocco"), ("Egyptian", "Egitto"), ("US", "USA"),
]


def competizione_los(nome: str):
    base = re.sub(r"\s+-\s+.*$", "", nome).strip()
    for rx, ordine, etichetta in COMPETIZIONI_LOS:
        if re.search(rx, base, re.I):
            return ordine, etichetta
    for agg, paese in PAESI_LOS:
        if base.startswith(agg + " ") or base == agg:
            resto = base[len(agg):].strip() or base
            if agg == "Cymru":
                resto = base
            return (8 if paese == "Italia" else 80), f"{resto.upper()} ({paese})"
    return 80, base.upper()


def scarica(url: str, tentativi: int = 4):
    """LiveOnSat risponde a volte 502 (Cloudflare): si riprova con attesa crescente."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9", "Cookie": "ljtz=UTC; ljoffset=0",
    })
    errore = ""
    for i in range(tentativi):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                testo = r.read().decode("utf-8", "replace")
                if "blockfix" in testo or "time_head" in testo:
                    return testo, None
                errore = "pagina inattesa (possibile blocco)"
        except urllib.error.HTTPError as e:
            errore = f"HTTP {e.code}"
            if e.code == 404:
                break
        except Exception as e:
            errore = f"errore di rete: {type(e).__name__}"
        time.sleep(3 * (i + 1))
    return None, errore


def pulisci_canale(nome: str, alias):
    n = html.unescape(nome)
    n = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", n)          # emoji 📺
    n = re.sub(r"\((\$/)?geo/R\)|\[\$\]|\[(app|APP|online|s/cast)\]|\(\$\)", "", n)
    n = re.sub(r"\s+(HD|UHD|4K)(\s+max)?\s*$", "", n.strip())
    n = re.sub(r"\s+", " ", n).strip()
    for a in alias:
        if re.search(a["regex"], n, re.I):
            return a["nome"]
    return n


def in_chiaro(nome: str, regole) -> bool:
    return any(re.search(r["regex"], nome, re.I) for r in regole)


def analizza(h: str, regole, alias, escludi=("dazn",), teleboy=None):
    """Restituisce le partite della pagina con i soli canali in chiaro (anche liste vuote)."""
    out = []
    comp = None
    giorno = None
    tokens = list(RE_TOKEN.finditer(h))
    for i, m in enumerate(tokens):
        if m.group(1) is not None:
            giorno = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
            continue
        if m.group(2) is not None:
            comp = html.unescape(m.group(2)).strip()
            continue
        fine = tokens[i + 1].start() if i + 1 < len(tokens) else len(h)
        b = h[m.end():fine]
        t = RE_TITOLO.search(b)
        if not t:
            continue
        titolo = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", t.group(1)))).strip()
        ts = RE_TS.search(b)
        if ts:
            quando = int(ts.group(1))
        else:  # riserva: "ST: hh:mm" è in UTC grazie al cookie ljtz=UTC; data dalla riga del giorno
            st = RE_ST.search(b)
            if not (st and giorno):
                continue
            try:
                d = dt.datetime.strptime(re.sub(r"(\d+)(st|nd|rd|th)", r"\1", giorno) + f" {dt.date.today().year}",
                                         "%A, %d %B %Y")
            except ValueError:
                continue
            quando = int(d.replace(hour=int(st.group(1)), minute=int(st.group(2)), tzinfo=UTC).timestamp())
        canali, extra, tutti = [], [], []
        for classe, nome in RE_CANALE.findall(b):
            if not classe.startswith("chan_live_") or classe == "chan_live_postponed":
                continue  # differite / rinviate
            pulito = pulisci_canale(nome, alias)
            tutti.append(pulito)
            nome_l = (pulito + " " + nome).lower()
            if any(x.lower() in nome_l for x in escludi):
                continue  # canali esclusi (DAZN, Megogo, ... vedi "escludi_canali" in liveonsat.json)
            if classe == "chan_live_free" or in_chiaro(pulito, regole) or in_chiaro(html.unescape(nome).strip(), regole):
                if pulito not in canali:
                    canali.append(pulito)
            elif teleboy is not None and teleboy.trova(pulito) and pulito not in extra:
                extra.append(pulito)  # non in chiaro, ma visibile su Teleboy
        extra = [c for c in extra if c not in canali]
        out.append({"ts": quando, "titolo": titolo, "comp": comp or "Altro", "canali_fta": canali,
                    "canali_teleboy": extra, "n_canali": len(tutti)})
    return out


def raccogli_los(conf, inizio, fine, scarica_fn=None, teleboy=None):
    """Scarica le pagine LiveOnSat; partite nella finestra con almeno un canale in chiaro, senza doppioni."""
    scarica_fn = scarica_fn or scarica
    pausa = conf.get("pausa_secondi", 0.7)
    regole, alias = conf.get("canali_in_chiaro", []), conf.get("alias_canali", [])
    escludi = ["dazn"] + [x for x in conf.get("escludi_canali", []) if x]
    partite, falliti = {}, []
    for url in conf.get("pagine", []):
        h, err = scarica_fn(url)
        if err:
            falliti.append(f"LiveOnSat {url.rsplit('/', 1)[-1]} ({err})")
            continue
        for p in analizza(h, regole, alias, escludi, teleboy):
            quando = dt.datetime.fromtimestamp(p["ts"], UTC)
            if not (inizio <= quando < fine) or not (p["canali_fta"] or p["canali_teleboy"]):
                continue
            k = (p["ts"], re.sub(r"\W+", "", p["titolo"].lower()))
            if k in partite:
                for campo in ("canali_fta", "canali_teleboy"):
                    for c in p[campo]:
                        if c not in partite[k][campo]:
                            partite[k][campo].append(c)
            else:
                partite[k] = p
        if pausa:
            time.sleep(pausa)  # cortesia verso il sito
    return list(partite.values()), falliti
