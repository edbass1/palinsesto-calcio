"""Traduzione in italiano dei titoli sportivi (tedesco, francese, inglese) con un glossario modificabile
(traduzioni.json), senza servizi esterni. I nomi propri restano com'erano."""
import json
import re
from pathlib import Path

CONF = Path(__file__).resolve().parent.parent / "traduzioni.json"
L = r"\wÀ-ÿ"
# parole straniere rimaste (nomi comuni tedeschi/francesi): la traduzione è solo parziale
SUFFISSI_STRANIERI = re.compile(r"(ung|heit|keit|schaft|spiel|rennen|lauf|runde|tag|tion|ment|ée|ique|eur|meister|turnier|wettkampf|kampf|auftakt)(en|e|s|es)?$", re.I)


def _rx(testo):
    if testo.startswith("re:"):
        return re.compile(testo[3:], re.I)
    p = re.escape(testo).replace(r"\ ", r"\s+")
    inizio = rf"(?<![{L}'’-])" if re.match(rf"[{L}]", testo) else ""
    fine = rf"(?![{L}-])" if re.search(rf"[{L}.]$", testo) else ""
    return re.compile(inizio + p + fine, re.I)


class Traduttore:
    def __init__(self, conf=None):
        if conf is None:
            conf = json.loads(CONF.read_text(encoding="utf-8")) if CONF.exists() else {}
        self.paesi = []
        self.nazioni = {}  # nome straniero -> nome italiano (solo stati: per le nazionali)
        for p in conf.get("paesi", []):
            for n in sorted(p.get("nomi", []), key=len, reverse=True):
                self.paesi.append((n, p["it"], p.get("di") or "di " + p["it"]))
                if not p.get("citta"):
                    self.nazioni[n.lower()] = p["it"]
        self.paesi.sort(key=lambda x: len(x[0]), reverse=True)
        nomi = "|".join(re.escape(n) for n, _, _ in self.paesi) or "(?!x)x"
        self.rx_gp = re.compile(
            rf"(?<![{L}])(GP|Gran Premio|Grand Prix|Großer Preis|Grosser Preis)\s+"
            rf"(?:(?:von|de|du|des|of|the|di|del|della)\s+|d['’])?({nomi})(?![{L}])", re.I)
        self.rx_paese = [(re.compile(rf"(?<![{L}-])" + re.escape(n) + rf"(?![{L}-])", re.I), it) for n, it, _ in self.paesi]
        self.di = {n.lower(): di for n, _, di in self.paesi}
        self.frasi = [(_rx(a), b, a.startswith("re:")) for a, b in conf.get("frasi", [])]
        self.italiane = {x.lower() for x in conf.get("parole_italiane", [])}
        self.chiavi = {a.lower() for a, _ in conf.get("frasi", []) if not a.startswith("re:")}

    def traduci(self, titolo):
        """(titolo italiano, completa?). completa=False se restano parole che sembrano straniere."""
        if not titolo:
            return titolo, True
        pezzi = []

        def segna(testo):
            pezzi.append(testo)
            return f"\x00{len(pezzi) - 1}\x00"

        t = titolo
        t = self.rx_gp.sub(lambda m: segna(("GP" if m.group(1).upper() == "GP" else "Gran Premio") + " "
                                           + self.di[m.group(2).lower()]), t)
        for rx, it in self.rx_paese:
            t = _sub_fuori(rx, t, lambda m, it=it: segna(it))
        for rx, it, e_rx in self.frasi:
            t = _sub_fuori(rx, t, lambda m, it=it, e_rx=e_rx: segna(m.expand(it) if e_rx else it))
        resto = re.sub(r"\x00\d+\x00", " ", t)
        completa = True
        for w in re.findall(rf"[{L}][{L}'’-]*", resto):
            if w.lower() in self.italiane or w.isdigit():
                continue
            if (w[0].islower() or SUFFISSI_STRANIERI.search(w)
                    or any(x.lower() in self.chiavi for x in re.split(r"[-'’]", w) if x)):
                completa = False
                break
        out = re.sub(r"\x00(\d+)\x00", lambda m: pezzi[int(m.group(1))], t)
        out = re.sub(r"\s+([,.:;])", r"\1", out)
        out = re.sub(r"\s{2,}", " ", out).strip(" ,-–")
        out = re.sub(r"\b(di|d') (?=[aeiouAEIOU])", "d'", out)  # di Indonesia -> d'Indonesia
        out = re.sub(r"\bdi (il|i) ", lambda m: "del " if m.group(1) == "il" else "dei ", out)
        if out and out[0].islower():
            out = out[0].upper() + out[1:]
        return out or titolo, completa


def _sub_fuori(rx, testo, fn):
    """Sostituisce solo fuori dai pezzi già tradotti."""
    parti = re.split(r"(\x00\d+\x00)", testo)
    return "".join(p if p.startswith("\x00") else rx.sub(fn, p) for p in parti)


_T = None


def nazione(squadra):
    """'Schweiz' -> 'Svizzera' (nazionali); qualsiasi altro nome resta com'è."""
    traduci("")
    return _T.nazioni.get((squadra or "").strip().lower(), squadra)


def traduci(titolo):
    global _T
    if _T is None:
        _T = Traduttore()
    return _T.traduci(titolo)


if __name__ == "__main__":
    import sys
    for x in sys.argv[1:]:
        print(x, "->", traduci(x))
