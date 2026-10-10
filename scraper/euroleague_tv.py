"""Partite di EuroLeague/EuroCup sui canali scelti, dalle pagine ufficiali «TV Listings».

La pagina (euroleaguebasketball.net) elenca per ogni partita i canali paese per paese, ma non l'orario:
l'orario si prende dal calendario pubblico (feeds.incrowdsports.com, lo stesso del sito). Il sito è dietro
un controllo anti-bot di Vercel che risponde 429 ai programmi semplici: in quel caso si apre la pagina con
Chrome headless (come un normale browser), se c'è."""
import datetime as dt
import difflib
import gzip
import html
import json
import re
import shutil
import subprocess
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
FEED = "https://feeds.incrowdsports.com/provider/euroleague-feeds/v2/competitions/{c}/seasons/{c}{anno}/{cosa}"
MESI = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                        "september", "october", "november", "december"])}
RE_DATA = re.compile(r"\b(\d{1,2}) (" + "|".join(MESI) + r") (20\d\d)\b", re.I)
RE_PARTITA = re.compile(r"^(.+?)\s+vs\.?\s+(.+?)$", re.I)
RE_CANALI = re.compile(r"^([^:]{2,90}):\s*(.+)$")


def scarica_semplice(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
                                                   "Accept": "text/html,application/json,*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            t = r.read()
            if t[:2] == b"\x1f\x8b":
                t = gzip.decompress(t)
            return t.decode("utf-8", "replace"), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"[:120]


def scarica_pagina(url):
    """(html, errore). Prima una richiesta normale; se risponde il controllo anti-bot, Chrome headless."""
    t, err = scarica_semplice(url)
    if t and "Vercel Security Checkpoint" not in t and "<h4" in t:
        return t, None
    chrome = next((shutil.which(x) for x in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser") if shutil.which(x)), None)
    if not chrome:
        return None, err or "controllo anti-bot e Chrome non disponibile"
    try:
        r = subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=20000",
                            "--dump-dom", url], capture_output=True, timeout=120)
        t = r.stdout.decode("utf-8", "replace")
        if 'id="pghdr"' in t:
            return t, None
        return None, "pagina non letta (anche con Chrome)"
    except Exception as e:
        return None, f"Chrome: {type(e).__name__}"


def righe(pagina):
    """Testo della pagina, una riga per titolo/paragrafo, dal titolo «TV Listings» in giù."""
    i = pagina.find('id="pghdr"')
    if i < 0:
        return []
    corpo = pagina[i:]
    j = corpo.find("<footer")
    corpo = corpo[: j if j > 0 else None]
    t = re.sub(r"<(?:/?(?:h\d|p|li|div|br|tr)\b)[^>]*>", "\n", corpo)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return [re.sub(r"\s+", " ", x).strip() for x in t.split("\n") if x.strip()]


def canali_della_riga(testo):
    """'NOVA (NOVASPORTS START), RTSH 1 and RTSH SPORT' -> ['NOVA', 'NOVASPORTS START', 'RTSH 1', 'RTSH SPORT']"""
    out = []
    for p in re.split(r",|\band\b|/", testo):
        for q in re.split(r"[()]", p):
            q = q.strip(" -")
            if q:
                out.append(q.upper())
    return out


def analizza(pagina, canali_conf):
    """[{'giorno': date, 'casa', 'ospite', 'canali': [chiave di canali_conf]}] — solo partite con almeno un canale scelto."""
    giorno, partita, out = None, None, []
    chiavi = {k.upper(): k for k in canali_conf}
    for r in righe(pagina):
        m = RE_DATA.search(r)
        if m and len(r) < 80:
            giorno = dt.date(int(m.group(3)), MESI[m.group(2).lower()], int(m.group(1)))
            continue
        m = RE_PARTITA.match(r)
        if m and ":" not in r and len(r) < 120 and giorno:
            partita = {"giorno": giorno, "casa": m.group(1).strip(), "ospite": m.group(2).strip(), "canali": []}
            out.append(partita)
            continue
        m = RE_CANALI.match(r)
        if m and partita is not None:
            for c in canali_della_riga(m.group(2)):
                if c in chiavi and chiavi[c] not in partita["canali"]:
                    partita["canali"].append(chiavi[c])
    return [p for p in out if p["canali"]]


def stagione(giorno):
    return giorno.year if giorno.month >= 7 else giorno.year - 1


def orari(comp, giorni, scarica_json):
    """Partite del calendario ufficiale dei giorni dati: [(data UTC, casa, ospite)]."""
    out, visti = [], set()
    for anno in sorted({stagione(g) for g in giorni}):
        t, _ = scarica_json(FEED.format(c=comp, anno=anno, cosa="rounds"))
        try:
            turni = json.loads(t)["data"] if t else []
        except ValueError:
            turni = []
        for r in turni:
            ini, fin = r["minGameStartDate"][:10], r["maxGameStartDate"][:10]
            if not any(ini <= g.isoformat() <= fin for g in giorni) or (r["phaseTypeCode"], r["round"]) in visti:
                continue
            visti.add((r["phaseTypeCode"], r["round"]))
            t, _ = scarica_json(FEED.format(c=comp, anno=anno, cosa=f'games?phaseTypeCode={r["phaseTypeCode"]}&roundNumber={r["round"]}'))
            try:
                for g in json.loads(t)["data"] if t else []:
                    quando = dt.datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
                    out.append((quando, g["home"]["name"], g["away"]["name"]))
            except (ValueError, KeyError):
                continue
    return out


def _simile(a, b):
    n = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    return difflib.SequenceMatcher(None, n(a), n(b)).ratio()


def raccogli(conf, inizio, fine, scarica_pagina_fn=None, scarica_json=None, stat=None):
    """(eventi ALTRI SPORT, errore). conf = altri_sport.json -> euroleague_tv."""
    scarica_pagina_fn = scarica_pagina_fn or scarica_pagina
    scarica_json = scarica_json or scarica_semplice
    canali = conf.get("canali", {})
    eventi, falliti = [], []
    st = stat if stat is not None else {}
    for pg in conf.get("pagine", []):
        h, err = scarica_pagina_fn(pg["url"])
        if not h:
            falliti.append(f'{pg["nome"]} ({err})')
            continue
        partite = analizza(h, canali)
        st[pg["nome"]] = {"partite_con_canali": len(partite)}
        if not partite:
            continue
        cal = orari(pg["codice"], sorted({p["giorno"] for p in partite}), scarica_json)
        for p in partite:
            cand = [(max(_simile(p["casa"], c), 0) + _simile(p["ospite"], o), q) for q, c, o in cal
                    if abs((q.astimezone(inizio.tzinfo).date() - p["giorno"]).days) <= 1]
            punti, quando = max(cand, key=lambda x: x[0], default=(0, None))
            if quando is None or punti < 1.2:
                st.setdefault("senza_orario", []).append(f'{p["casa"]} - {p["ospite"]}')
                continue
            ts = int(quando.timestamp())
            if not (inizio.timestamp() - 2 * 3600 <= ts < fine.timestamp()):
                continue
            em = [{"nome": canali[k]["nome"], "pagina": None, "link": None, "vpn": canali[k].get("vpn"), "fta": True}
                  for k in p["canali"]]
            tit = f'{p["casa"]} - {p["ospite"]}'
            eventi.append({"id": f'el:{pg["codice"]}:{ts}:{tit.lower()}', "ts": ts, "fine": ts + conf.get("durata_min", 120) * 60,
                           "sport": "Basket", "titolo": f'{pg["nome"]}: {tit}', "titolo_orig": f'{pg["nome"]} {tit}',
                           "titolo_src": tit, "evento": True, "lingua": "en", "descrizione": pg["nome"], "comp": pg["nome"],
                           "da_los": True, "emittenti": em})
    st["eventi"] = len(eventi)
    err = f'TV Listings {", ".join(falliti)}' if falliti else None
    return eventi, err


def fn_raccogli(conf, inizio, fine, stat=None, **kw):
    return lambda: raccogli(conf, inizio, fine, stat=stat, **kw)
