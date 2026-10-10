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
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
FILE_DATI = RADICE / "dati" / "basket_tv.json"

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


def partite_pagina(pg, h, canali, scarica_json, st):
    """Partite di una pagina TV Listings con i canali scelti e l'orario ufficiale:
    [{'comp', 'codice', 'ts', 'casa', 'ospite', 'canali': [chiavi]}]"""
    partite = analizza(h, canali)
    st[pg["nome"]] = {"partite_con_canali": len(partite)}
    if not partite:
        return []
    cal = orari(pg["codice"], sorted({p["giorno"] for p in partite}), scarica_json)
    out = []
    for p in partite:
        cand = [(_simile(p["casa"], c) + _simile(p["ospite"], o), q) for q, c, o in cal
                if abs((q.date() - p["giorno"]).days) <= 1]
        punti, quando = max(cand, key=lambda x: x[0], default=(0, None))
        if quando is None or punti < 1.2:
            st.setdefault("senza_orario", []).append(f'{p["casa"]} - {p["ospite"]}')
            continue
        out.append({"comp": pg["nome"], "codice": pg["codice"], "ts": int(quando.timestamp()),
                    "casa": p["casa"], "ospite": p["ospite"], "canali": p["canali"]})
    return out


def a_eventi(partite, conf, inizio, fine):
    canali = conf.get("canali", {})
    out = []
    for p in partite:
        ts = p["ts"]
        if not (inizio.timestamp() - 2 * 3600 <= ts < fine.timestamp()):
            continue
        em = [{"nome": canali[k]["nome"], "pagina": None, "link": None, "vpn": canali[k].get("vpn"), "fta": True}
              for k in p["canali"] if k in canali]
        if not em:
            continue
        tit = f'{p["casa"]} - {p["ospite"]}'
        out.append({"id": f'el:{p["codice"]}:{ts}:{tit.lower()}', "ts": ts, "fine": ts + conf.get("durata_min", 120) * 60,
                    "sport": "Basket", "titolo": f'{p["comp"]}: {tit}', "titolo_orig": f'{p["comp"]} {tit}',
                    "titolo_src": tit, "evento": True, "lingua": "en", "descrizione": p["comp"], "comp": p["comp"],
                    "da_los": True, "emittenti": em})
    return out


def leggi_dati(percorso=None):
    f = Path(percorso) if percorso else FILE_DATI
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def raccogli(conf, inizio, fine, scarica_pagina_fn=None, scarica_json=None, stat=None, file_dati=None):
    """(eventi ALTRI SPORT, None). Se una pagina non si legge si usano i dati di dati/basket_tv.json
    (scritti da scripts/aggiorna_basket.sh su un'altra macchina), validi finché le partite sono future.
    Gli errori finiscono solo nel log (stat['errori']), mai nella pagina."""
    scarica_pagina_fn = scarica_pagina_fn or scarica_pagina
    scarica_json = scarica_json or scarica_semplice
    st = stat if stat is not None else {}
    partite, errori = [], []
    dati = None
    for pg in conf.get("pagine", []):
        h, err = scarica_pagina_fn(pg["url"])
        if h:
            partite += partite_pagina(pg, h, conf.get("canali", {}), scarica_json, st)
            st.setdefault("fonte", {})[pg["nome"]] = "pagina letta ora"
            continue
        dati = dati if dati is not None else (leggi_dati(file_dati) or {})
        dal_file = [p for p in dati.get("partite", []) if p.get("codice") == pg["codice"]]
        if dati.get("partite") is not None:
            partite += dal_file
            st.setdefault("fonte", {})[pg["nome"]] = f'dati/basket_tv.json ({dati.get("aggiornato", "?")}, {len(dal_file)} partite)'
        else:
            errori.append(f'{pg["nome"]}: {err}')
            st.setdefault("fonte", {})[pg["nome"]] = "non letta, nessun file dati"
    eventi = a_eventi(partite, conf, inizio, fine)
    st["eventi"] = len(eventi)
    if errori:
        st["errori"] = errori
    return eventi, None


def fn_raccogli(conf, inizio, fine, stat=None, **kw):
    return lambda: raccogli(conf, inizio, fine, stat=stat, **kw)


def esporta(percorso, conf=None):
    """Legge ora le pagine (con Chrome se serve) e scrive dati/basket_tv.json. Restituisce il numero di partite."""
    if conf is None:
        conf = json.loads((RADICE / "altri_sport.json").read_text(encoding="utf-8")).get("euroleague_tv", {})
    st, partite, lette = {}, [], 0
    for pg in conf.get("pagine", []):
        h, err = scarica_pagina(pg["url"])
        if not h:
            print(f"{pg['nome']}: non letta ({err})")
            continue
        lette += 1
        pp = partite_pagina(pg, h, conf.get("canali", {}), scarica_semplice, st)
        print(f"{pg['nome']}: {len(pp)} partite con i canali scelti")
        partite += pp
    if not lette:
        return None
    dati = {"_nota": "Scritto da scripts/aggiorna_basket.sh: partite EuroLeague/EuroCup con i canali scelti (altri_sport.json -> euroleague_tv) e orario ufficiale (UTC, epoch). Il build lo usa se non riesce a leggere le pagine.",
            "aggiornato": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "partite": partite}
    Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    Path(percorso).write_text(json.dumps(dati, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return len(partite)


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--esporta":
        n = esporta(sys.argv[2])
        sys.exit(0 if n is not None else 1)
    print("uso: python3 scraper/euroleague_tv.py --esporta dati/basket_tv.json")
    sys.exit(2)
