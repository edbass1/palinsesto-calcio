"""Canali disponibili su Teleboy (tv.teleboy.ch, IPTV svizzera).

L'elenco si legge dalla pagina pubblica https://www.teleboy.ch/tv/sender, che carica i canali via JavaScript:
per questo si usa Chrome headless (--dump-dom). Se non riesce, si usa la copia in teleboy_canali.json.
"""
import html
import json
import re
import shutil
import subprocess
import unicodedata

PAGINA = "https://www.teleboy.ch/tv/sender"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
RE_NOME = re.compile(r'<div class="no-focus" title="([^"{}]+)"')
RE_NOME_ID = re.compile(r'<div class="no-focus" title="([^"{}]+)".*?/shared/stations/(\d+)/', re.S)
LINK_CANALE = "https://tv.teleboy.ch/live(player:live/{id})"  # es. ITV = 346

# parole di "paese" che si possono togliere per il confronto, con il paese Teleboy corrispondente
PAESI = {"schweiz": "ch", "suisse": "ch", "svizzera": "ch", "switzerland": "ch", "deutschland": "de", "germany": "de",
         "uk": "gb", "england": "gb", "austria": "at", "osterreich": "at", "italia": "it", "italy": "it", "france": "fr"}
NUMERI = {"one": "1", "un": "1", "uno": "1", "eins": "1", "two": "2", "zwei": "2", "deux": "2", "due": "2",
          "three": "3", "drei": "3", "trois": "3", "tre": "3", "four": "4", "vier": "4"}
DECORAZIONI = {"hd", "uhd", "fhd", "4k", "digital", "la", "tv"}
EQUIVALENTI = {"daserste": "arddaserste", "ard": "arddaserste", "erste": "arddaserste", "itv": "itv1", "sport1": "sport1"}


def _parole(nome):
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower().replace("+", " plus ")
    s = re.sub(r"(\d)", r" \1 ", s)
    return [NUMERI.get(w, w) for w in re.findall(r"[a-z0-9]+", s) if w not in DECORAZIONI]


def chiave(nome, togli_paese=False):
    """Chiave di confronto; con togli_paese restituisce (chiave_senza_paese, paese) se c'è una parola di paese."""
    w = _parole(nome)
    if togli_paese:
        paesi = [PAESI[x] for x in w if x in PAESI]
        if not paesi:
            return None, None
        k = "".join(x for x in w if x not in PAESI)
        return EQUIVALENTI.get(k, k), paesi[0]
    k = "".join(w)
    return EQUIVALENTI.get(k, k)


def leggi_pagina(timeout=90):
    """Nomi dei canali letti dalla pagina Teleboy con Chrome headless; None se non disponibile."""
    chrome = next((shutil.which(b) for b in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
                   if shutil.which(b)), None)
    if not chrome:
        print("Teleboy: Chrome non trovato, uso la copia salvata")
        return None
    try:
        r = subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=20000",
                            "--user-agent=" + UA, "--dump-dom", PAGINA], capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        print(f"Teleboy: lettura pagina non riuscita ({e}), uso la copia salvata")
        return None
    nomi = list(dict.fromkeys(html.unescape(x).strip() for x in RE_NOME.findall(r.stdout)))
    global ID_LETTI
    ID_LETTI = {html.unescape(n).strip(): int(i) for n, i in RE_NOME_ID.findall(r.stdout)}
    if len(nomi) < 100:
        titolo = re.search(r"<title>(.*?)</title>", r.stdout, re.S)
        print(f"Teleboy: pagina letta ma {len(nomi)} canali (exit {r.returncode}, {len(r.stdout)} byte, "
              f"titolo {titolo.group(1).strip()[:60] if titolo else '-'!r}), uso la copia salvata")
        return None
    return nomi


ID_LETTI = {}


class Teleboy:
    def __init__(self, conf, nomi_letti=None):
        alias = conf.get("alias", {})
        noti = {c["nome"].strip(): c for c in conf.get("canali", [])}
        nomi = nomi_letti if nomi_letti else list(noti)
        self.fonte = "pagina Teleboy (letta ora)" if nomi_letti else "copia salvata (teleboy_canali.json)"
        self.canali = {}  # chiave -> (nome Teleboy, paese)
        for n in nomi:
            info = noti.get(n, {})
            if info.get("pagamento") or re.search(r"^mySports|\+$", n, re.I):
                continue  # pacchetti a pagamento
            paese = info.get("paese")
            for k in {chiave(n), chiave(alias.get(n, n))}:
                self.canali.setdefault(k, (n, paese))
        self.n = len({v[0] for v in self.canali.values()})
        self.ids = {c["nome"].strip(): c.get("id") for c in conf.get("canali", []) if c.get("id")}
        self.ids.update(ID_LETTI if nomi_letti else {})
        self.modello_link = conf.get("link_canale") or LINK_CANALE

    def paese(self, nome_teleboy):
        for n, p in self.canali.values():
            if n == nome_teleboy:
                return p
        return None

    def link(self, nome_teleboy):
        """Link diretto al canale nel player Teleboy, se si conosce il numero del canale."""
        i = self.ids.get(nome_teleboy)
        return self.modello_link.format(id=i) if i else None

    def trova(self, nome):
        """Nome del canale Teleboy corrispondente a `nome`, oppure None."""
        k = chiave(nome)
        if k in self.canali:
            return self.canali[k][0]
        k2, paese = chiave(nome, togli_paese=True)
        if k2 and k2 in self.canali and self.canali[k2][1] in (paese, None):
            return self.canali[k2][0]
        return None


def carica(percorso, aggiorna=True):
    with open(percorso, encoding="utf-8") as f:
        conf = json.load(f)
    return Teleboy(conf, leggi_pagina() if aggiorna else None)
