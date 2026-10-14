"""Etichette in più sulle schede delle partite di calcio:
- info partita: infortunati e squalificati da FotMob (JSON pubblico, nessuna chiave);
- rivalità: elenco curato in rivalita.json;
Tutto facoltativo: se una fonte non risponde, l'etichetta semplicemente non compare."""
import datetime as dt
import json
import re
import time
import urllib.request
import gzip
from pathlib import Path

try:
    from unisci import stessa_partita, somiglianza, norm_squadra
except ImportError:  # pragma: no cover
    from scraper.unisci import stessa_partita, somiglianza, norm_squadra

RADICE = Path(__file__).resolve().parent.parent
CACHE = RADICE / "dati" / "cache_extra.json"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
MAX_DETTAGLI = 220      # richieste FotMob matchDetails per esecuzione
TTL_S = 3 * 3600        # cache dei dettagli


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or b[:2] == b"\x1f\x8b":
            b = gzip.decompress(b)
    return json.loads(b.decode("utf-8"))


def _ts(iso):
    return int(dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


# ---------------- assenze (FotMob) ----------------
MESI = {"January": "gennaio", "February": "febbraio", "March": "marzo", "April": "aprile", "May": "maggio", "June": "giugno",
        "July": "luglio", "August": "agosto", "September": "settembre", "October": "ottobre", "November": "novembre", "December": "dicembre"}


def rientro_it(s):
    if not s:
        return ""
    s = s.strip()
    if s.lower() == "doubtful":
        return "in dubbio"
    if s.lower() == "unknown":
        return "rientro incerto"
    m = re.match(r"(Early|Mid|Late)\s+(\w+)\s+(\d{4})$", s)
    if m and m.group(2) in MESI:
        return f'rientro {dict(Early="inizio", Mid="metà", Late="fine")[m.group(1)]} {MESI[m.group(2)]}'
    return ""


TIPO = {"injury": "infortunato", "suspension": "squalificato", "red_card": "squalificato", "yellow_card": "squalificato"}


def assenze_da_dettagli(d):
    """{'casa': [(nome, motivo)], 'ospite': [...]} dal JSON matchDetails di FotMob; solo infortuni e squalifiche."""
    lu = (d.get("content") or {}).get("lineup") or {}
    out = {}
    for lato, k in (("casa", "homeTeam"), ("ospite", "awayTeam")):
        lista = []
        for p in (lu.get(k) or {}).get("unavailable") or []:
            u = p.get("unavailability") or {}
            t = TIPO.get(u.get("type"))
            if not t or not p.get("name"):
                continue
            r = rientro_it(u.get("expectedReturn")) if t == "infortunato" else ""
            lista.append((p["name"], t + (f", {r}" if r else "")))
        out[lato] = lista
    return out if (out.get("casa") or out.get("ospite")) else None


def partite_fotmob(giorni, log=print):
    out = []
    for g in giorni:
        try:
            d = _get(f"https://www.fotmob.com/api/data/matches?date={g:%Y%m%d}")
        except Exception as ex:  # noqa: BLE001
            log(f"  FotMob {g}: {ex}")
            continue
        for lg in d.get("leagues") or []:
            for m in lg.get("matches") or []:
                st = m.get("status") or {}
                if st.get("finished") or st.get("cancelled") or not st.get("utcTime"):
                    continue
                out.append({"id": m["id"], "ts": _ts(st["utcTime"]), "casa": m["home"].get("longName") or m["home"]["name"],
                            "ospite": m["away"].get("longName") or m["away"]["name"]})
    return out


# ---------------- rivalità ----------------
def carica_rivalita(f=RADICE / "rivalita.json"):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))["coppie"]
    except (OSError, ValueError, KeyError):
        return []


def stessa_squadra(x, y):
    """Più severa dei doppioni: nomi uguali (o alias) oppure uno contenuto nell'altro parola per parola
    ('Milan' / 'AC Milan'), mai 'Deportivo Alavés' / 'Deportivo La Coruña'."""
    if somiglianza(x, y) < 0.9:
        return False
    a, b = set(norm_squadra(x).split()), set(norm_squadra(y).split())
    if a == b:
        return True
    piccolo = a if a <= b else b if b <= a else None
    return bool(piccolo) and not (len(piccolo) == 1 and piccolo & GENERICHE)


GENERICHE = set("deportivo real sporting atletico racing club united city athletic nacional america union dinamo dynamo "
                "olympique sport sportive internacional independiente universidad".split())


def rivalita_di(casa, ospite, coppie):
    for c in coppie:
        a, b = c["squadre"]
        for x, y in ((casa, ospite), (ospite, casa)):
            if any(stessa_squadra(x, v) for v in a.split("|")) and any(stessa_squadra(y, v) for v in b.split("|")):
                return c["perche"]
    return None


def abbina(e, lista):
    best, sc = None, 0
    for x in lista:
        s = stessa_partita(e["ts"], e["casa"], e["ospite"] or "", x["ts"], x["casa"], x["ospite"])
        if s > sc:
            best, sc = x, s
    if best is None:
        return None, False
    # stessa partita a squadre invertite? (per sapere chi è "casa" nella fonte)
    invertite = somiglianza(e["casa"], best["ospite"]) > somiglianza(e["casa"], best["casa"])
    return best, invertite


def arricchisci(gruppi, giorni, rete=True, log=print, cache_file=CACHE):
    """Aggiunge a ogni partita di calcio e['_info'] (assenze) ed e['_riv'] (frase).. Restituisce i conteggi."""
    partite = [e for g in gruppi for e in g["partite"] if e.get("ospite")]
    coppie = carica_rivalita()
    st = {"rivalita": 0, "info": 0, "fotmob": "spento"}
    for e in partite:
        r = rivalita_di(e["casa"], e["ospite"], coppie)
        if r:
            e["_riv"] = r
            st["rivalita"] += 1
    if not rete:
        return st
    try:
        cache = json.loads(Path(cache_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    ora = time.time()
    cache = {k: v for k, v in cache.items() if ora - v.get("t", 0) < TTL_S}
    # assenze
    try:
        fm = partite_fotmob(giorni, log)
        st["fotmob"] = f"{len(fm)} partite"
        chieste = 0
        for e in sorted(partite, key=lambda x: x["ts"]):
            m, inv = abbina(e, fm)
            if not m:
                continue
            k = str(m["id"])
            if k not in cache:
                if chieste >= MAX_DETTAGLI:
                    continue
                chieste += 1
                try:
                    cache[k] = {"t": ora, "a": assenze_da_dettagli(_get(f"https://www.fotmob.com/api/data/matchDetails?matchId={k}"))}
                except Exception as ex:  # noqa: BLE001
                    log(f"  FotMob dettagli {k}: {ex}")
                    continue
                time.sleep(0.3)
            a = cache[k]["a"]
            if a:
                e["_info"] = {"casa": a["ospite"], "ospite": a["casa"]} if inv else a
                st["info"] += 1
        st["fotmob"] += f", {chieste} dettagli scaricati"
    except Exception as ex:  # noqa: BLE001
        log(f"  FotMob: {ex}")
    try:
        Path(cache_file).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_file).write_text(json.dumps(cache), encoding="utf-8")
    except OSError:
        pass
    return st
