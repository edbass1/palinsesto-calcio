"""Scooore (canale di calcio su Zattoo/Samsung TV Plus): guida pubblica XMLTV di i.mjh.nz (Samsung TV Plus Svizzera,
file su raw.githubusercontent.com). Formato: titolo = squadra di casa, sottotitolo = ospite, descrizione = competizione.
La guida NON dice se è in diretta (ci sono anche differite e repliche): una partita di Scooore si usa solo se coincide
(stesse squadre, inizio entro 'tolleranza_min') con una partita già trovata da un'altra fonte -> si aggiunge il canale."""
import datetime as dt
import gzip
import re
import urllib.request
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
FONTE = "https://i.mjh.nz/SamsungTVPlus/ch.xml.gz"


def scarica(url=FONTE):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
        return (gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:100]


def _ts(s):
    return int(dt.datetime.strptime(s.strip()[:20].strip(), "%Y%m%d%H%M%S %z").timestamp())


def partite(xml, nome_canale=r"^scooore\b"):
    """[{ts, casa, ospite, comp}] dalla guida (solo righe con casa | ospite)."""
    r = ET.fromstring(xml)
    ids = {c.get("id") for c in r.findall("channel") if re.search(nome_canale, c.findtext("display-name") or "", re.I)}
    out = []
    for p in r.iter("programme"):
        if p.get("channel") not in ids:
            continue
        casa, ospite = (p.findtext("title") or "").strip(), (p.findtext("sub-title") or "").strip()
        comp = (p.findtext("desc") or "").strip()
        if not casa or not ospite or re.search(r"highlights|alle tore|magazin|zusammenfassung|best of", f"{casa} {ospite} {comp}", re.I):
            continue
        try:
            out.append({"ts": _ts(p.get("start")), "casa": casa, "ospite": ospite, "comp": re.sub(r"\s*\(.*?\)\s*$", "", comp)})
        except (TypeError, ValueError):
            continue
    return out
