"""Nomi degli sport in tutte le lingue delle fonti -> nome italiano delle sezioni.

La tabella è in sport.json (si possono aggiungere alias). Un'etichetta intera
(«Basquetebol», «Ténis», «Hockey sur glace», «Equitazione | Salto ostacoli»)
diventa il nome già usato dal sito (Basket, Tennis, Hockey su ghiaccio, …).
"""
import json
import re
import unicodedata
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
# resto di un'etichetta che non cambia sport («Basket femminile», «Tennis donne»)
QUALIFICATORI = {
    "f", "m", "w", "u17", "u18", "u19", "u20", "u21", "u23",
    "femminile", "femminili", "maschile", "maschili", "donne", "uomini", "donna", "uomo",
    "women", "womens", "men", "mens", "woman", "ladies", "lady", "gentlemen", "gents",
    "frauen", "herren", "damen", "dames", "messieurs", "feminin", "feminine", "masculin",
    "feminino", "masculino", "femenino", "femenina", "masculina", "femmes", "hommes",
    "mulheres", "homens", "mujeres", "hombres", "damas", "kobiety", "live", "diretta",
    "3x3",
}
_TRAD = str.maketrans({
    "ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "ł": "l", "đ": "d", "ð": "d", "þ": "th",
    "ı": "i", "Ł": "l", "Ø": "o", "Æ": "ae", "Œ": "oe", "Đ": "d",
})


def chiave(s):
    """Minuscole, senza accenti, trattini e «|» diventano spazi."""
    s = (s or "").translate(_TRAD)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("|", " ").replace("/", " ").replace("'", " ").replace("’", " ").replace("-", " ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _carica(percorso=None):
    dati = json.loads(Path(percorso or RADICE / "sport.json").read_text(encoding="utf-8"))
    exact, alias_di, filtro = {}, {}, {}
    for voce in dati.get("sport", []):
        can = (voce.get("it") or "").strip()
        if not can:
            continue
        if voce.get("filtro"):
            filtro[can] = voce["filtro"]
        visti, gia = [], set()
        for a in [can] + list(voce.get("alias") or []):
            k = chiave(a)
            if not k:
                continue
            altro = exact.get(k)
            if altro is not None and altro != can:
                raise ValueError(f"alias {a!r} vale per {can!r} e per {altro!r}")
            exact[k] = can
            if k not in gia:
                gia.add(k)
                visti.append(a)
        alias_di[can] = visti
    prefix = sorted(exact.items(), key=lambda x: len(x[0]), reverse=True)
    return exact, alias_di, filtro, prefix


EXACT, ALIAS_DI, FILTRO, _PREFIX = _carica()


def normalizza(nome):
    """Etichetta di sport (qualunque lingua) -> nome italiano. Se non è uno sport noto, resta com'è."""
    raw = re.sub(r"\s+", " ", (nome or "").replace("\u00a0", " ")).strip()
    if not raw:
        return raw
    k = chiave(raw)
    if k in EXACT:
        return EXACT[k]
    if "|" in raw:
        sinistra = chiave(raw.split("|", 1)[0])
        if sinistra in EXACT:
            return EXACT[sinistra]
    for alias, can in _PREFIX:
        if not k.startswith(alias + " "):
            continue
        resto = k[len(alias) + 1:].split()
        if " " in alias or len(alias) >= 8 or all(p in QUALIFICATORI or p.isdigit() for p in resto):
            return can
    return raw


def conosciuto(nome):
    """True se l'etichetta è un nome di sport della tabella (anche in un'altra lingua)."""
    raw = re.sub(r"\s+", " ", (nome or "")).strip()
    if not raw:
        return False
    if chiave(raw) in EXACT:
        return True
    if "|" in raw and chiave(raw.split("|", 1)[0]) in EXACT:
        return True
    return normalizza(raw) != raw


def applica(evento):
    """Scrive lo sport italiano sull'evento. Conserva il nome della fonte se era diverso."""
    orig = re.sub(r"\s+", " ", (evento.get("sport") or "").replace("\u00a0", " ")).strip()
    can = normalizza(orig) or orig or "Sport"
    if orig and chiave(orig) != chiave(can):
        evento.setdefault("sport_orig", orig)
    evento["sport"] = can
    return evento


def filtro_di(sport):
    """Pulsante «Per sport» (basket, tennis, volley, f1, moto, nfl) o None."""
    return FILTRO.get(normalizza(sport or "")) or None


def mappa_ricerca():
    """Nome italiano in minuscole senza accenti -> parole con cui la ricerca deve trovarlo."""
    return {chiave(can): " ".join(alias) for can, alias in ALIAS_DI.items()}
