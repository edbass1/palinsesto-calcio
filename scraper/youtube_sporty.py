"""Dirette di calcio dai canali YouTube (es. Sporty TV Africa): feed RSS + scheda Live + pagina del video.

Nessuna chiave API: solo pagine pubbliche. Per ogni video "LIVE | A vs B | Campionato" si legge dalla pagina
del video l'orario d'inizio (programmato o reale) e se la diretta è già finita."""
import datetime as dt
import html
import json
import re
import urllib.request
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
CONF = RADICE / "youtube.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
# SOCS/CONSENT: evita la pagina del consenso dei cookie che YouTube mostra agli indirizzi europei
INTESTAZIONI = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8", "Cookie": "SOCS=CAI; CONSENT=YES+cb"}

RE_LIVE = re.compile(r"\b(live|ao vivo|en vivo|en direct|in diretta)\b|🔴", re.I)
RE_VS = re.compile(r"\s+(?:vs\.?|v|x|×|-|–)\s+", re.I)


def conf():
    return json.loads(CONF.read_text(encoding="utf-8")) if CONF.exists() else {}


def scarica(url, timeout=25):
    """(testo, errore)"""
    try:
        sep = "&" if "?" in url else "?"
        req = urllib.request.Request(url + f"{sep}hl=en&gl=US", headers=INTESTAZIONI)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            t = r.read().decode("utf-8", "replace")
        if "consent.youtube.com" in t[:5000] or "before you continue" in t[:20000].lower():
            return None, "pagina del consenso cookie"
        return t, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"[:120]


def video_rss(xml):
    """[(videoId, titolo)] dal feed RSS del canale."""
    return [(v, html.unescape(t)) for v, t in
            re.findall(r"<yt:videoId>([\w-]{11})</yt:videoId>.*?<title>([^<]*)</title>", xml or "", re.S)]


def video_scheda_live(pagina):
    """[(videoId, titolo, startTime o None)] dalla scheda Live del canale (ytInitialData), se YouTube la mostra."""
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", pagina or "", re.S)
    if not m:
        return []
    out = []

    def giro(o):
        if isinstance(o, dict):
            if "videoRenderer" in o:
                v = o["videoRenderer"]
                t = "".join(r.get("text", "") for r in (v.get("title") or {}).get("runs", []))
                st = (v.get("upcomingEventData") or {}).get("startTime")
                out.append((v.get("videoId"), t, int(st) if st else None))
            for x in o.values():
                giro(x)
        elif isinstance(o, list):
            for x in o:
                giro(x)
    try:
        giro(json.loads(m.group(1)))
    except ValueError:
        return []
    return [x for x in out if x[0]]


def dettagli_video(pagina):
    """{'inizio': ts, 'fine': ts|None, 'in_corso': bool, 'titolo': str} dalla pagina del video, o None se non è una diretta."""
    if not pagina:
        return None
    lbd = re.search(r'"liveBroadcastDetails":\{([^{}]*)\}', pagina)
    sched = re.search(r'"scheduledStartTime":"(\d+)"', pagina)
    tit = re.search(r'<meta name="title" content="([^"]*)"', pagina) or re.search(r'"title":"((?:[^"\\]|\\.)*)","lengthSeconds"', pagina)
    titolo = html.unescape(tit.group(1)) if tit else ""

    def iso(campo):
        m = re.search(rf'"{campo}":"([^"]+)"', lbd.group(1)) if lbd else None
        return int(dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).timestamp()) if m else None
    inizio = int(sched.group(1)) if sched else iso("startTimestamp")
    if inizio is None:
        return None
    return {"inizio": inizio, "fine": iso("endTimestamp"), "in_corso": bool(lbd and '"isLiveNow":true' in lbd.group(1)),
            "titolo": titolo}


def analizza_titolo(titolo, c=None):
    """'LIVE | Bolton Wanderers vs Stoke City | EFL Championship | SportyTV' -> (casa, ospite, competizione) o None."""
    c = c if c is not None else conf()
    t = titolo or ""
    if not RE_LIVE.search(t):
        return None
    tl = t.lower()
    if any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", tl) for w in c.get("salta", [])):
        return None
    pezzi = [p.strip() for p in re.split(r"\s*[|•]\s*|\s+[-–]\s+(?=[^|]*$)(?![^|]*\bvs?\b)", RE_LIVE.sub(" ", t)) if p.strip(" :-–")]
    pezzi = [re.sub(r"^[\s:–-]+|[\s:–-]+$", "", p) for p in pezzi]
    pezzi = [p for p in pezzi if p and not re.fullmatch(r"sporty ?tv( africa)?|\d\d/\d\d|\d{4}(/\d\d)?", p, re.I)]
    for i, p in enumerate(pezzi):
        sq = RE_VS.split(p)
        if len(sq) == 2 and all(len(x.strip()) >= 2 for x in sq) and not re.search(r"\d+\s*[-–]\s*\d+", p):
            comp = next((x for x in pezzi[i + 1:] + pezzi[:i] if x), "")  # nome originale; etichetta italiana in palinsesto
            return sq[0].strip(), sq[1].strip(), comp
    return None


def raccogli(inizio, fine, ora, c=None, scarica_fn=None, stat=None):
    """([partite], [avvisi]). Partita: ts, casa, ospite, comp, canale, pagina, video, vpn, in_corso."""
    c = c if c is not None else conf()
    scarica_fn = scarica_fn or scarica
    partite, avvisi = [], []
    st = stat if stat is not None else {}
    for can in c.get("canali", []):
        visti, raggiunto = {}, False
        xml, err = scarica_fn(f'https://www.youtube.com/feeds/videos.xml?channel_id={can["channel_id"]}')
        if xml:
            raggiunto = True
            for v, t in video_rss(xml):
                visti.setdefault(v, (t, None))
        pag, err2 = scarica_fn(f'https://www.youtube.com/{can["handle"]}/streams')
        if pag:
            raggiunto = True
            for v, t, s in video_scheda_live(pag):
                visti[v] = (t, s)
        st.setdefault("video", 0)
        st["video"] += len(visti)
        if not raggiunto:
            avvisi.append(f'{can["nome"]}: YouTube non raggiungibile ({err or err2})')
            continue
        for v, (t, s) in visti.items():
            sq = analizza_titolo(t, c)
            if not sq:
                continue
            pv, e = scarica_fn(f"https://www.youtube.com/watch?v={v}")
            d = dettagli_video(pv)
            if d is None and s:
                d = {"inizio": s, "fine": None, "in_corso": False, "titolo": t}
            if d is None:
                st.setdefault("senza_orario", []).append(t)
                continue
            if d["fine"]:  # diretta già finita
                st.setdefault("finite", []).append(t)
                continue
            if not (inizio.timestamp() <= d["inizio"] < fine.timestamp()) and not d["in_corso"]:
                continue
            casa, ospite, comp = sq
            partite.append({"ts": d["inizio"], "casa": casa, "ospite": ospite, "comp": comp, "canale": can["nome"],
                            "pagina": can["pagina"], "video": f"https://www.youtube.com/watch?v={v}", "vpn": can.get("vpn"),
                            "in_corso": d["in_corso"], "titolo": t})
    st["dirette"] = len(partite)
    return partite, avvisi
