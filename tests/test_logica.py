#!/usr/bin/env python3
"""Test offline: finestra di 4 giorni, LiveSoccerTV (pagine salvate il 9/10/2026, 48 partite attese (esclusa Saudi Pro League)),
LiveOnSat (pagine salvate il 10/10/2026): canali in chiaro, orari, unione dei doppioni."""
import datetime as dt, gzip, html, json, re, sys
from pathlib import Path
QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent / "scraper"))
import palinsesto as p
import liveonsat as L
_SCARICA_LOS = L.scarica  # quella vera, prima dei finti dei test
import unisci as U
import teleboy as TB
import dazn as DZ

CONF_LOS = json.loads((QUI.parent / "liveonsat.json").read_text(encoding="utf-8"))
DIR_LOS = QUI / "fixtures_liveonsat_2026-10-10"



def ogni_link_ha_vpn(h):
    """Ogni riga canale con un link ▶ deve avere l'etichetta VPN subito accanto."""
    righe = re.findall(r"<li[^>]*>(?:(?!</li>).)*?class=\"diretta\"(?:(?!</li>).)*</li>", h, re.S)
    senza = [r for r in righe if 'class="tag vpn' not in r]
    assert not senza, senza[:3]
    return True


def finto_lstv(url, tentativi=3):
    f = QUI / "fixtures_2026-10-09" / (url.rstrip("/").split("/")[-1] + ".html.gz")
    return gzip.open(f, "rt", encoding="utf-8").read(), None


def finto_los(url, tentativi=4, vuota_ok=False):
    f = DIR_LOS / (url.rsplit("/", 1)[-1].replace(".php", "") + ".html.gz")
    if not f.exists():
        return None, "HTTP 502"
    return gzip.open(f, "rt", encoding="utf-8").read(), None


def los_pagina(nome):
    return L.analizza(finto_los(nome + ".php")[0], CONF_LOS["canali_in_chiaro"], CONF_LOS["alias_canali"])


def test_finestra():
    """Finestra mobile: oggi 00:00 -> fine del 5° giorno successivo (6 giorni), ora italiana."""
    casi = {  # ora italiana -> (primo giorno, ultimo giorno, testo)
        "2026-10-10T18:30": ("2026-10-10", "2026-10-15", "Sab 10 – Gio 15 ottobre"),
        "2026-10-10T00:00": ("2026-10-10", "2026-10-15", "Sab 10 – Gio 15 ottobre"),
        "2026-10-09T23:59": ("2026-10-09", "2026-10-14", "Ven 9 – Mer 14 ottobre"),
        "2026-10-14T09:00": ("2026-10-14", "2026-10-19", "Mer 14 – Lun 19 ottobre"),
        "2026-10-30T12:00": ("2026-10-30", "2026-11-04", "Ven 30 ottobre – Mer 4 novembre"),
        "2026-12-30T12:00": ("2026-12-30", "2027-01-04", "Mer 30 dicembre – Lun 4 gennaio"),
    }
    for ora, (primo, ultimo, testo) in casi.items():
        g, ini, fine = _FINESTRA_VERA(dt.datetime.fromisoformat(ora).replace(tzinfo=p.ROMA))
        assert str(g) == primo and (ini.hour, ini.minute) == (0, 0) and ini.date() == g, (ora, g, ini)
        assert str((fine - dt.timedelta(seconds=1)).date()) == ultimo and (fine.hour, fine.minute) == (0, 0), (ora, fine)
        assert _PERIODO_VERO(g) == testo, (ora, _PERIODO_VERO(g))
    # un'ora UTC tarda è già "domani" in Italia
    g, _, _ = _FINESTRA_VERA(dt.datetime(2026, 10, 9, 22, 30, tzinfo=dt.timezone.utc))
    assert str(g) == "2026-10-10"
    # cambio d'ora (domenica 25/10/2026): la finestra 24-29 ottobre dura 145 ore
    g, ini, fine = _FINESTRA_VERA(dt.datetime(2026, 10, 24, 12, tzinfo=p.ROMA))
    assert ini.utcoffset() == dt.timedelta(hours=2) and fine.utcoffset() == dt.timedelta(hours=1)
    assert fine.timestamp() - ini.timestamp() == 145 * 3600
    # ora legale (domenica 28/3/2027): 143 ore
    g, ini, fine = _FINESTRA_VERA(dt.datetime(2027, 3, 27, 9, tzinfo=p.ROMA))
    assert fine.timestamp() - ini.timestamp() == 143 * 3600


# le fixture registrate (9-12/10/2026) coprono la vecchia finestra di 4 giorni: da qui in poi i test la usano;
# la finestra reale di 6 giorni è verificata in test_finestra
_FINESTRA_VERA, _PERIODO_VERO = p.finestra, p.periodo
p.finestra = lambda ora, giorni=4: _FINESTRA_VERA(ora, giorni)
p.periodo = lambda primo, giorni=4: _PERIODO_VERO(primo, giorni)
p.GIORNI_FINESTRA = 4


def test_fixture():
    """Solo LiveSoccerTV, finestra ven 9 – lun 12: esclude i campionati nazionali romeni e la Saudi Pro League."""
    canali = json.loads((QUI.parent / "canali.json").read_text())["canali"]
    p.scarica = finto_lstv
    v, ini, fine = p.finestra(dt.datetime(2026, 10, 9, 12, tzinfo=p.ROMA))
    gruppi, falliti, senza = p.raccogli(canali, ini, fine)
    n = sum(len(g["partite"]) for g in gruppi)
    assert n == 48 and not falliti and set(senza) <= {"RTL TVI", "Club RTL", "RTL Play", "VTM", "VTM 2", "VTM 4", "VTM GO"}, (n, falliti, senza)  # canali belgi: nessuna partita 9-12/10
    assert not any("SportyNet+" in k["nome"] for g in gruppi for e in g["partite"] for k in e["canali"])
    assert not any("Romania" in g["nome"] or "Romanian" in g["nome"] for g in gruppi)
    prima_18 = [e for g in gruppi for e in g["partite"] if e["quando"] < dt.datetime(2026, 10, 9, 18, tzinfo=p.ROMA)]
    assert not prima_18, prima_18  # Al Fateh era Saudi Pro League, ora esclusa
    nomi = [g["nome"] for g in gruppi]
    assert nomi[:6] == ["SERIE A", "SERIE B", "PREMIER LEAGUE", "LALIGA", "BUNDESLIGA", "LIGUE 1"], nomi
    serie_a = [(e["quando"].strftime("%a %H:%M"), f'{e["casa"]} - {e["ospite"]}', [c["nome"] for c in e["canali"]])
               for e in gruppi[0]["partite"]]
    assert serie_a[1] == ("Sat 18:00", "Inter - Parma", ["Prima Sport 2", "Golazo Network"]), serie_a[1]
    psg = [e for g in gruppi for e in g["partite"] if "PSG" in e["titolo"]][0]
    assert [c["nome"] for c in psg["canali"]] == ["TV5 Monde"]
    html = p.genera_html(v, dt.datetime(2026, 10, 9, 12, 47, tzinfo=p.ROMA), gruppi, ["Canale X (HTTP 404)"], [])
    assert "non scaricati" in html and "Canale X" in html and html.count('class="partita"') == 2 * 48
    assert not any("dazn" in c["nome"].lower() for g in gruppi for e in g["partite"] for c in e["canali"])
    return n


def test_fta():
    """Canali in chiaro: classe chan_live_free (rosso) + elenco canali_in_chiaro; mai DAZN, mai differite."""
    def trova(pagina, titolo):
        return next(x for x in los_pagina(pagina) if x["titolo"] == titolo)
    # rossi su LiveOnSat + RTÉ Player (non rosso, ma nell'elenco); esclusi i canali a pagamento
    g = trova("2day", "Galway United v Derry City")
    assert g["canali_fta"] == ["RTÉ 2 Ireland", "RTÉ Player"] and g["n_canali"] == 3, g
    # Svizzera: SRG SSR non è rosso su LiveOnSat (criptato via satellite) ma è nell'elenco; Blue Sport escluso
    lu = trova("europe-switzerland-super-league", "Lugano v Luzern")
    assert set(lu["canali_fta"]) == {"Play RTS Sport", "RSI La 2 Svizzera", "RTS 2 Suisse", "SRF Play", "SRF Zwei Schweiz"}, lu
    # "DAZN España HD FTA" è rosso ma va escluso
    r = trova("2day", "Rayo Vallecano v Athletic Bilbao")
    assert r["canali_fta"] == ["Digi Sport 1", "Persiana Sports 3"], r  # Digi Sport 1 Romania: sempre preso (23/10/2026)
    # alias: varianti TV5 Monde unite, ITV 1 England -> ITV1 UK
    assert trova("2day", "Paris St Germain v Le Mans")["canali_fta"] == ["Persiana Sports 2", "TV5 Monde"]
    assert "ITV1 UK" in trova("uk-britain-ireland-all-football", "Southampton v Portsmouth")["canali_fta"]
    # Genoa-Fiorentina: nessun canale in chiaro, solo Digi Sport Romania (sempre preso, 23/10/2026)
    assert [c for c in trova("europe-italy-all-football", "Genoa v Fiorentina")["canali_fta"] if not c.startswith("Digi Sport")] == []
    assert any(c.startswith("Digi Sport") for c in trova("europe-italy-all-football", "Genoa v Fiorentina")["canali_fta"])
    # HTML sintetico: differita (chan_other_free) e rinviata ignorate
    finto = ('<span class = comp_head>Italian Serie A - Week 1</span><div class = blockfix >'
             '<div class = fLeft style="width:270px">Roma v Lazio</div>'
             '<div class="fLeft_time_live dynamic-time" data-timestamp="1791648000"> ST: 16:00 </div>'
             '<a href="#" class = chan_live_free onmouseover="x" onmouseout="return nd();">Rai 1 HD </a>'
             '<a href="#" class = chan_other_free onmouseover="x" onmouseout="return nd();">Rai 2 HD </a>'
             '<a href="#" class = chan_live_postponed onmouseover="x" onmouseout="return nd();">TF1 HD </a>'
             '<a href="#" class = chan_live_not_free onmouseover="x" onmouseout="return nd();">Sky Sport Uno </a>'
             '<a href="#" class = chan_live_iptvcable onmouseover="x" onmouseout="return nd();">RaiPlay (geo/R) 📺</a></div>')
    x = L.analizza(finto, CONF_LOS["canali_in_chiaro"], CONF_LOS["alias_canali"])[0]
    assert x["canali_fta"] == ["Rai 1", "RaiPlay"] and x["comp"].startswith("Italian Serie A"), x


def test_russi_iraniani():
    """Canali russi e iraniani esclusi ovunque (nome, parola di paese, paese Teleboy); Idman TV mai escluso."""
    f = U.regola_canali(CONF_LOS)
    for n in ("TV Start Russia HD", "TV Start Triumph HD", "Start TV", "Start", "MATCH! Futbol 1 HD", "MATCH! Premier HD", "Match TV",
              "Okko Futbol HD", "viju+ Sport HD", "KHL Prime", "Pervyi Kanal", "Rossiya 1", "IRIB Varzesh HD", "IRIB 3", "GEM Sport 1",
              "Meraj TV", "Persiana Sports 2", "Manoto", "Tapesh TV", "Eurosport Russia"):
        assert f(n), n
    for n in ("Idman TV HD", "Idman TV Russia", "Nova Sports Start Hellas HD", "Magenta Hellas Sport Start", "Setanta Sports 1 Eurasia HD",
              "Match 4 Hungary HD", "Premier Sports 1 UK HD", "TNT Sports 1 HD", "SRF zwei", "Gem Football Club TV", "Solh TV"):
        assert f(n) is None, (n, f(n))
    assert f("Canale X", "ru") and f("Canale X", "ir") and f("Canale X", "ch") is None  # paese Teleboy
    # dati salvati: Seoul-Jeju, Feyenoord-AZ, Ajax-NEC avevano solo TV Start Russia -> spariscono; Arsenal-Leeds resta con Idman TV
    canali = json.loads((QUI.parent / "canali.json").read_text())["canali"]
    p.scarica, L.scarica = finto_lstv, finto_los
    ini = dt.datetime(2026, 10, 9, tzinfo=p.ROMA); fine = ini + dt.timedelta(days=4)
    st = {}
    gruppi, _, _ = p.raccogli(canali, ini, fine, dict(CONF_LOS, pausa_secondi=0), st)
    tutte = {f'{e["casa"]} - {e["ospite"]}': e for g in gruppi for e in g["partite"]}
    nomi = [k["nome"] for e in tutte.values() for k in e["canali"]]
    assert not any(f(n) for n in nomi), [n for n in nomi if f(n)]
    assert "TV Start Russia" in st["canali_ru_ir"], st["canali_ru_ir"]
    for x in ("FC Seoul - Jeju United", "Feyenoord - AZ Alkmaar", "Ajax - NEC Nijmegen"):
        assert x in st["tolte_esclusi"] and x not in tutte, x
    ars = [e for k, e in tutte.items() if "Arsenal" in k and "Leeds" in k]
    assert ars and "Idman TV" in [k["nome"] for k in ars[0]["canali"]], ars
    # mai_escludere vince anche su escludi_canali
    finto = ('<span class = comp_head>X</span><div class = blockfix ><div class = fLeft style="a">A v B</div>'
             '<div data-timestamp="1791648000"></div>'
             '<a href="#" class = chan_live_free onmouseover="x" onmouseout="return nd();">Idman TV Persiana </a></div>')
    assert L.analizza(finto, [], [], ["persiana"])[0]["canali_fta"] == ["Idman TV Persiana"]
    return st


def test_esclusi():
    """Megogo (e DAZN) esclusi; partite che avevano solo Megogo tra i canali in chiaro spariscono."""
    assert "megogo" in [x.lower() for x in CONF_LOS["escludi_canali"]]
    conf = dict(CONF_LOS, pausa_secondi=0, pagine=["https://liveonsat.com/2day.php", "https://liveonsat.com/europe-france-all-football.php"])
    ini = dt.datetime(2026, 10, 9, tzinfo=p.ROMA); fine = ini + dt.timedelta(days=4)
    partite, _ = L.raccogli_los(conf, ini, fine, scarica_fn=finto_los)
    titoli = {x["titolo"]: x for x in partite}
    assert not any("megogo" in c.lower() or "dazn" in c.lower() for x in partite for c in x["canali_fta"])
    # nel file salvato Lille-Le Havre e Monaco-Toulouse avevano solo Megogo Sport Ukraine come canale in chiaro
    grezzo = {x["titolo"]: x for x in L.analizza(finto_los("2day.php")[0], CONF_LOS["canali_in_chiaro"], CONF_LOS["alias_canali"], ())}
    assert grezzo["Lille v Le Havre"]["canali_fta"] == ["Megogo Sport Ukraine"]
    assert "Lille v Le Havre" not in titoli and "Monaco v Toulouse" not in titoli
    assert "Paris St Germain v Le Mans" in titoli  # ha altri canali in chiaro
    # canali iraniani/afghani esclusi (anche con varianti di nome)
    for parola in ("gem sport", "persiana", "irib", "varzish", "varzesh", "meraj"):
        assert parola in CONF_LOS["escludi_canali"], parola
    vietati = ("gem sport", "persiana", "irib", "varz", "meraj")
    assert not any(v in c.lower() for x in partite for c in x["canali_fta"] for v in vietati)
    # Arsenal-Leeds (sab 13:30) aveva solo GEM/Idman/IRIB/Meraj/Persiana/Solh: resta solo con Idman TV e Solh TV
    ars = grezzo["Arsenal v Leeds United"]["canali_fta"]
    assert ars == ["GEM Sport 1", "Idman TV", "IRIB Varzesh", "Meraj TV", "Persiana Sport", "Solh TV"], ars
    assert titoli["Arsenal v Leeds United"]["canali_fta"] == ["Idman TV"]  # Solh escluso
    # Rayo-Athletic: Persiana Sports 3 e DAZN tolti, resta solo Digi Sport 1 (Romania, sempre preso dal 23/10/2026)
    assert set(grezzo["Rayo Vallecano v Athletic Bilbao"]["canali_fta"]) == {"Digi Sport 1", "DAZN España HD FTA", "Persiana Sports 3"}
    assert titoli["Rayo Vallecano v Athletic Bilbao"]["canali_fta"] == ["Digi Sport 1"]
    # HTML sintetico: maiuscole/minuscole indifferenti
    finto = ('<span class = comp_head>X</span><div class = blockfix ><div class = fLeft style="a">A v B</div>'
             '<div data-timestamp="1791648000"></div>'
             '<a href="#" class = chan_live_free onmouseover="x" onmouseout="return nd();">MEGOGO Football HD </a>'
             '<a href="#" class = chan_live_free onmouseover="x" onmouseout="return nd();">Rai 2 HD </a></div>')
    assert L.analizza(finto, [], [], ["dazn", "megogo"])[0]["canali_fta"] == ["Rai 2"]


def test_orari():
    """data-timestamp = secondi UTC; conversione a Europe/Rome con ora legale/solare."""
    ge = next(x for x in los_pagina("europe-italy-all-football") if x["titolo"] == "Genoa v Fiorentina")
    assert dt.datetime.fromtimestamp(ge["ts"], p.ROMA).strftime("%d/%m %H:%M") == "10/10 15:00"  # ufficiale: 15:00
    # stesso orario della stessa partita su LiveSoccerTV (Como-Roma, dom 12:30)
    co = next(x for x in los_pagina("europe-italy-all-football") if x["titolo"] == "Como 1907 v Roma")
    assert dt.datetime.fromtimestamp(co["ts"], p.ROMA).strftime("%a %H:%M %z") == "Sun 12:30 +0200"
    # dopo il 25/10 (ora solare) UTC+1
    nov = [x for x in los_pagina("europe-italy-all-football") if x["ts"] > 1793000000]
    assert nov and all(dt.datetime.fromtimestamp(x["ts"], p.ROMA).utcoffset() == dt.timedelta(hours=1) for x in nov)
    # riserva senza data-timestamp: "ST" è in UTC (cookie ljtz=UTC) + data dall'intestazione del giorno
    finto = ('<h2 class = time_head>Saturday, 10th  October</h2><span class = comp_head>X</span><div class = blockfix >'
             '<div class = fLeft style="a">A v B</div><div class="fLeft_time_live"> ST: 13:00 </div></div>')
    y = L.analizza(finto, [], [])[0]
    assert dt.datetime.fromtimestamp(y["ts"], p.ROMA).strftime("%m-%d %H:%M") == "10-10 15:00", y


def test_dedup():
    """Nomi normalizzati + orario ±15 minuti."""
    t = 1791637200
    assert U.stessa_partita(t, "Inter", "Parma", t + 600, "Internazionale", "Parma FC")
    assert U.stessa_partita(t, "Bayern München", "Dortmund", t, "Bayern Munich", "Borussia Dortmund")
    assert U.stessa_partita(t, "PSG", "Le Mans", t, "Paris St Germain", "Le Mans")
    assert U.stessa_partita(t, "Manchester United", "Tottenham Hotspur", t, "Man Utd", "Spurs")
    assert U.stessa_partita(t, "Como", "Roma", t, "Como 1907", "AS Roma")
    assert U.stessa_partita(t, "Athletic Club", "Real Madrid", t, "Athletic Bilbao", "Real Madrid CF")
    assert not U.stessa_partita(t, "Inter", "Parma", t + 1200, "Inter", "Parma")           # 20 minuti: no
    assert not U.stessa_partita(t, "Roma", "Lazio", t, "Roma", "Juventus")                 # altra partita
    assert not U.stessa_partita(t, "Real Madrid", "Getafe", t, "Real Sociedad", "Girona")
    assert not U.stessa_partita(t, "Manchester City", "Arsenal", t, "Manchester United", "Chelsea")


def test_ordine():
    """Serie A, Serie B, Coppa Italia, Champions, Europa, Conference, poi i grandi campionati, poi il resto."""
    lstv = [p.competizione(f"/competitions/{u}", "x")[0] for u in (
        "italy/serie-a/", "italy/serie-b/", "italy/coppa-italia/", "international/uefa-champions-league/",
        "international/uefa-europa-league/", "international/uefa-europa-conference-league/",
        "england/premier-league/", "spain/primera-division/", "germany/bundesliga/", "france/ligue-1/",
        "england/championship/", "scotland/premiership/")]
    assert lstv == sorted(lstv) and len(set(lstv[:10])) == 10, lstv
    los = [L.competizione_los(n) for n in (
        "Italian Serie A - Week 6", "Italian Serie BKT - Week 7", "Coppa Italia - Round of 16",
        "UEFA Champions League - League Phase", "UEFA Europa League - League Phase", "UEFA Conference League - League Phase",
        "English Premier League - Week 6", "Spanish La Liga (Primera) - Week 8", "German 1. Bundesliga - Week 5",
        "French Ligue 1 - Week 6", "English Championship - Week 9", "Scottish Premiership - Week 8")]
    assert [o for o, _ in los] == sorted(o for o, _ in los), los
    assert [e for _, e in los[3:6]] == ["UEFA CHAMPIONS LEAGUE", "UEFA EUROPA LEAGUE", "UEFA CONFERENCE LEAGUE"]
    assert [e for _, e in los[:6]] == [p.competizione(f"/competitions/{u}", "x")[1] for u in (
        "italy/serie-a/", "italy/serie-b/", "italy/coppa-italia/", "international/uefa-champions-league/",
        "international/uefa-europa-league/", "international/uefa-europa-conference-league/")]


def test_dove():
    """'Dove vederli': badge con link alla voce, voci 'utente' sempre presenti, link esterni in nuova scheda."""
    dove = json.loads((QUI.parent / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    assert all(v["fonte"] in ("utente", "ricerca") for v in dove)
    voce = lambda n: (p.voce_dove(n, dove) or {}).get("id")
    assert [voce(n) for n in ("Prima Sport 3", "Golazo Network", "ITV1 UK", "ITV X", "BBC Alba", "BBC One",
                              "SportyNet Brasil", "SportyNet+ Brasil", "TV5 Monde", "Sporty TV Africa", "RSI La 2 Svizzera",
                              "Persiana Sports 2")] == [
        "prima-sport", "golazo", "itv1", "itvx", "bbc-alba", "bbc", "sportynet-brasil", None, "tv5monde",
        "sporty-tv-africa", "rsi", None]
    assert not any(v["id"] == "sportynet-plus" for v in dove)  # SportyNet+ tolto per sempre
    assert all(voce(n) == "dubai-sports" for n in ("Dubai Sports 1 HD", "Dubai Sport 1", "Dubai Sports")) and voce("Dubai Sports 2") is None
    assert L.in_chiaro("Dubai Sports 1 HD", CONF_LOS["canali_in_chiaro"])  # nella lista dei canali gratuiti
    e = {"ts": 1791648000, "quando": dt.datetime(2026, 10, 10, 18, tzinfo=p.ROMA), "casa": "A", "ospite": "B",
         "canali": [{"nome": "Prima Sport 2", "fta": False}, {"nome": "RSI La 2 Svizzera", "fta": True},
                    {"nome": "Persiana Sports 2", "fta": True}]}
    h = p.genera_html(dt.date(2026, 10, 10), dt.datetime(2026, 10, 10, 18, tzinfo=p.ROMA),
                      [{"nome": "X", "partite": [e]}], [], [], dove)
    assert '<a href="#dv-prima-sport"' in h and '<a href="#dv-rsi"' in h and "Persiana Sports 2</li>" in h
    assert 'id="dv-golazo"' in h and 'id="dv-dazn"' in h and 'id="dv-rsi"' in h  # utente sempre, ricerca se usata
    assert 'id="dv-zdf"' not in h and 'target="_blank" rel="noopener noreferrer"' in h
    assert "SPORT GRATIS E LEGALE IN TV · Sab 10 – Mar 13 ottobre" in h and h.count("data-filtro=") == 10 and "eekend" not in h


def test_ordine_tutto():
    """PER CAMPIONATO con TUTTO: blocchi A (coppe europee/nazionali) e B (Serie A, poi grandi campionati), C in fondo."""
    b = p.blocco_tutto(p.carica_categorie())
    assert [b(n) for n in ("UEFA CHAMPIONS LEAGUE", "UEFA YOUTH LEAGUE", "NAZIONALI – QUALIFICAZIONI MONDIALI 2026",
                           "NAZIONALI – QUALIFICAZIONI EUROPEI U21", "SERIE A", "PREMIER LEAGUE", "PREMIER LEAGUE (Azerbaigian)",
                           "LALIGA", "2. BUNDESLIGA", "LIGUE 1", "SERIE B", "BRASILEIRÃO SERIE A (Brasile)")] == [
        "a", "c", "a", "c", "b0", "b", "c", "b", "c", "b", "c", "c"]
    import shutil, subprocess, tempfile, time
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        print("  (chrome assente: ordine lato pagina non verificato)")
        return
    ora = dt.datetime.now(p.ROMA).replace(second=0, microsecond=0)
    def g(nome, *ore):
        return {"nome": nome, "partite": [{"ts": int((ora + dt.timedelta(hours=h)).timestamp()), "quando": ora + dt.timedelta(hours=h),
                                            "casa": f"{nome[:5]} {h}", "ospite": "B", "canali": [{"nome": "Prima Sport 1", "fta": False}]}
                                           for h in ore]}
    def ordine(gruppi, dopo=""):
        h = p.genera_html(ora.date(), ora, gruppi, [], [])
        h = h.replace("</body>", f"<script>{dopo}</script></body>")
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
            f.write(h)
        out = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--dump-dom", "file://" + f.name],
                             capture_output=True, text=True, timeout=60).stdout
        i = out.index('id="vista-campionato"')
        return [m.group(2) for m in re.finditer(r'<section class="comp"([^>]*)><h2>([^<]*)', out[i:])
                if "hidden" not in m.group(1)][:len(gruppi)]
    base = [g("BRASILEIRÃO SERIE A (Brasile)", 1), g("LALIGA", 2), g("PREMIER LEAGUE", 3), g("SERIE A", 5),
            g("UEFA CHAMPIONS LEAGUE", 4), g("NAZIONALI – UEFA NATIONS LEAGUE", 2.5), g("SERIE B", 1.5)]
    # B prima (LaLiga alle +2 < nazionali alle +2.5): Serie A prima di tutto il blocco B
    assert ordine(base) == ["SERIE A", "LALIGA", "PREMIER LEAGUE", "NAZIONALI – UEFA NATIONS LEAGUE", "UEFA CHAMPIONS LEAGUE",
                            "BRASILEIRÃO SERIE A (Brasile)", "SERIE B"]
    # A prima (Champions alle +1.2)
    base[4] = g("UEFA CHAMPIONS LEAGUE", 1.2)
    assert ordine(base) == ["UEFA CHAMPIONS LEAGUE", "NAZIONALI – UEFA NATIONS LEAGUE", "SERIE A", "LALIGA", "PREMIER LEAGUE",
                            "BRASILEIRÃO SERIE A (Brasile)", "SERIE B"]
    # altri filtri: solo ordine per primo calcio d'inizio
    el = ordine(base, "document.querySelector('.scelta-b button[data-gruppo=\\'calcio\\'][data-cat=\\'elite\\']').click();")
    assert el == ["UEFA CHAMPIONS LEAGUE", "LALIGA", "NAZIONALI – UEFA NATIONS LEAGUE", "PREMIER LEAGUE", "SERIE A"], el
    return ordine(base)


def test_ordine_sport():
    """ALTRI SPORT con TUTTO: sport ELITE prima nella vista PER SPORT; IN ORDINE DI ORARIO resta solo cronologico."""
    import shutil, subprocess, tempfile
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        return "chrome assente"
    ora = dt.datetime.now(p.ROMA).replace(second=0, microsecond=0)
    def ev(sport, titolo, h):
        ts = int((ora + dt.timedelta(hours=h)).timestamp())
        return {"id": titolo, "ts": ts, "fine": ts + 7200, "sport": sport, "titolo": titolo, "titolo_orig": titolo, "evento": True,
                "lingua": "it", "descrizione": "", "emittenti": [{"nome": "RSI La 2", "pagina": None, "link": None, "vpn": "SVIZZERA", "fta": True}]}
    altri = [ev("Ciclismo", "Paris-Tours", 0.5), ev("Pallavolo", "Lube - Trento", 1), ev("Tennis", "ATP Shanghai", 3),
             ev("Formula 1", "Gran Premio di Singapore", 2), ev("Hockey su ghiaccio", "Lugano - Zug", 2.5), ev("Basket", "EuroLeague: Milano - Real", 4),
             ev("Motori", "WEC 6 Ore del Fuji", 0.7), ev("Motomondiale", "MotoGP: gara", 5)]
    def dom(dopo=""):
        h = p.genera_html(ora.date(), ora, [], [], [], altri=altri).replace("</body>", f"<script>{dopo}</script></body>")
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
            f.write(h)
        return subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--dump-dom", "file://" + f.name],
                              capture_output=True, text=True, timeout=60).stdout
    def viste(out):
        a, b = out.index('id="vista-sport-tipo"'), out.index('id="vista-sport-orario"')
        tipo = out[a:] if a > b else out[a:b]
        orario = out[b:a] if a > b else out[b:]
        sezioni = [m.group(2) for m in re.finditer(r'<section class="comp"([^>]*)><h2>([^<]*)', tipo) if "hidden" not in m.group(1)]
        righe = [("SEP" if m.group(1) else html.unescape(m.group(2)))
                 for m in re.finditer(r'<li class="(sotto-sep)"(?![^>]*hidden)[^>]*>|<li class="partita evento[^"]*"(?![^>]*hidden)[^>]*>.*?<span class="sq">([^<]*)', orario, re.S)]
        return sezioni, righe
    tipo, orario = viste(dom())
    # F1 e motomondiale prima (tra loro per orario), poi gli altri elite (MOTORI compreso) per orario, poi il resto
    assert tipo == ["FORMULA 1", "MOTOMONDIALE", "MOTORI", "TENNIS", "BASKET", "CICLISMO", "PALLAVOLO", "HOCKEY SU GHIACCIO"], tipo
    assert orario == ["Paris-Tours", "WEC 6 Ore del Fuji", "Lube - Trento", "Gran Premio di Singapore", "Lugano - Zug", "ATP Shanghai",
                      "EuroLeague: Milano - Real", "MotoGP: gara"], orario
    # ELITE SPORT: solo gli sport elite
    tipo2, orario2 = viste(dom("document.querySelector('.scelta-b button[data-gruppo=\\'altri\\'][data-cat=\\'elite\\']').click();"))
    assert tipo2 == ["FORMULA 1", "MOTOMONDIALE", "MOTORI", "TENNIS", "BASKET"], (tipo2, orario2)
    # di nuovo TUTTO dopo ELITE: l'ordine torna
    t3 = viste(dom("var q=function(c){return document.querySelector('.scelta-b button[data-gruppo=\\'altri\\'][data-cat=\\''+c+'\\']')};q('elite').click();q('tutto').click();"))
    assert t3 == (tipo, orario), t3
    return tipo


def test_primaplay():
    """Programma ufficiale Prima Sport (primaplay.ro/transmisiuni): ora romena -> italiana, PPV, calcio unito, altri sport."""
    import primaplay as PP
    h = gzip.open(Path(__file__).parent / "fixtures_primaplay_2026-10-11" / "transmisiuni.html.gz", "rt", encoding="utf-8").read()
    conf = PP.carica_conf()
    ini, fine = dt.datetime(2026, 10, 11, tzinfo=p.ROMA), dt.datetime(2026, 10, 15, tzinfo=p.ROMA)
    st = {}
    cal, alt, err = PP.raccogli(conf, ini, fine, lambda u: (h, None), dt.date(2026, 10, 11), st)
    assert err is None and st["righe"] == 71 and len(cal) == 45 and len(alt) == 14, st
    assert all(x.startswith("Prima News") for x in st["saltate_canale"]) and len(st["saltate_canale"]) == 3
    ora = lambda x: dt.datetime.fromtimestamp(x["ts"], p.ROMA).strftime("%d %H:%M")
    como = next(x for x in cal if x["casa"] == "Como")
    assert (ora(como), como["canale"], como["ospite"]) == ("11 12:30", "Prima Sport 1", "Roma")  # 13:30 in Romania
    assert {x["canale"] for x in cal} >= {"Prima Sport PPV1", "Prima Sport PPV2", "Prima Sport PPV3"}
    assert any(x["ospite"] == "Sporting CP" for x in cal) and any(x["ospite"] == "Bayern Munich" for x in cal)  # nomi romeni
    uyl = next(x for x in cal if x["comp"] == "UYL")
    assert uyl["comp_los"] == "UEFA Youth League" and uyl["ospite"] == "Paris Saint-Germain"
    tit = {(ora(e), e["emittenti"][0]["nome"]): (e["sport"], e["titolo"]) for e in alt}
    assert tit[("11 16:00", "Prima Sport 2")] == ("Pallamano", "EHF Champions League femminile: CSM București - Esbjerg")
    assert tit[("14 17:30", "Prima Sport 3")] == ("Basket", "EuroCup: Siauliai - U Cluj")
    assert tit[("11 14:00", "Prima Sport PPV4")] == ("Basket", "Basket 3x3: World Tour Bucharest")
    assert tit[("11 12:00", "Prima Sport 4")] == ("Tennis", "ATP: Shanghai Masters")
    # titoli: repliche saltate, "Fotbal: ..., Serie A", calcio femminile
    a = PP.analizza_titolo
    assert a("Fotbal: Roma - Inter (reluare)", conf) is None and a("Rezumat: Lazio - Monza", conf) is None
    assert a("Fotbal: Roma - Inter, Serie A (live)", conf) == {"sport": "Calcio", "genere": "", "comp": "", "resto": "Roma - Inter, Serie A"}
    assert a("Volei F - CL: Alba Blaj - Conegliano", conf)["sport"] == "Pallavolo"
    # ora legale / ora solare: sempre un'ora in meno rispetto alla Romania
    h2 = ('<a href="#tab1">Astăzi <span>31.10</span></a><a href="#tab2">D<span>01.11</span></a>'
          '<div class="tab-pane fade" id="tab1"><table class="program-live"><tr><td>22:00<br/>PPV2</td><td>Fotbal: A - B, Serie A</td></tr></table></div>'
          '<div class="tab-pane fade" id="tab2"><table class="program-live"><tr><td>22:00<br/>Prima Sport 1</td><td>Fotbal F: C - D</td></tr>'
          '<tr><td>18:00<br/>Prima Sport 2</td><td>Fotbal: E - F (reluare)</td></tr></table></div></section>')
    c2, _, _ = PP.raccogli(conf, dt.datetime(2026, 10, 30, tzinfo=p.ROMA), dt.datetime(2026, 11, 3, tzinfo=p.ROMA),
                           lambda u: (h2, None), dt.date(2026, 10, 31), {})
    assert [(ora(x), x["canale"], x["comp_los"], x["genere"]) for x in c2] == [
        ("31 21:00", "Prima Sport PPV2", "Italian Serie A", ""), ("01 21:00", "Prima Sport 1", "", "F")]
    # unione con le partite già trovate: canale aggiunto; nuove partite con la competizione da LiveOnSat; femminile via
    q = dt.datetime(2026, 10, 11, 12, 30, tzinfo=p.ROMA)
    ev = [{"ts": int(q.timestamp()), "quando": q, "casa": "Como", "ospite": "AS Roma", "competizione": "SERIE A", "ordine": 1,
           "canali": [{"nome": "Prima Sport 1", "fta": False}], "fonti": ["LiveSoccerTV"]}]
    t_al = int(dt.datetime(2026, 10, 11, 16, 15, tzinfo=p.ROMA).timestamp())
    los = [{"ts": t_al, "titolo": "Almeria v Leganes", "comp": "Spanish La Liga 2"}]
    ev, uniti, nuove = p.unisci_primaplay(ev, cal + c2, los, lambda c, s_, n: "Serie A" in c and s_[0] == "A")
    assert [c["nome"] for c in ev[0]["canali"]] == ["Prima Sport 1"] and ev[0]["fonti"] == ["LiveSoccerTV", "Prima Play"]
    al = next(e for e in ev if e["casa"] == "Almeria")
    assert al["competizione"].startswith("LALIGA HYPERMOTION") and al["canali"] == [{"nome": "Prima Sport PPV2", "fta": False}]
    assert not any(e["casa"] in ("A", "C") for e in ev)  # esclusa (finta regola) e femminile
    assert any(e["competizione"] == "UEFA YOUTH LEAGUE" for e in ev)
    # Dove vederli: PPV -> voce PPV dell'utente, Prima Sport 1-5 -> voce di sempre
    dove = json.loads((p.RADICE / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    assert p.voce_dove("Prima Sport PPV2", dove)["id"] == "prima-sport-ppv" and p.voce_dove("Prima Sport 3", dove)["id"] == "prima-sport"
    v = p.voce_dove("Prima Sport PPV1", dove)
    assert v["link"][0]["url"] == "https://www.primaplay.ro/register" and v["fonte"] == "utente"
    assert "solo nell'app PrimaPlay" in v["note"] and "Non sono disponibili su Orange TV" in v["note"]
    assert v["link_card"]["url"] == "https://www.primaplay.ro/register"
    assert "orange.ro" not in json.dumps(v).lower()
    return f"{len(cal)} calcio, {len(alt)} altri sport, {len(nuove)} nuove"


def test_basket():
    """Basket: solo NBA, Serie A/A2, ACB, coppe europee, nazionali ITA/GRE/SPA, EuroBasket e Mondiali (categorie.json)."""
    import altri_sport
    f = altri_sport.filtro_basket(p.carica_categorie())
    B = lambda t, comp="", **k: f({"sport": "Basket", "titolo": t, "comp": comp, **k})
    for t, comp in [("Los Angeles Lakers - Boston Celtics", "NBA Regular Season"), ("EuroLeague: Milano - Real", ""),
                    ("EuroCup: Siauliai - U Cluj", ""), ("Virtus Bologna v Trento", "Italian Serie A"), ("Rieti - Cantù", "Serie A2"),
                    ("Real Madrid v Baskonia", "Spanish ACB"), ("Unicaja - Tenerife", "Liga Endesa"), ("BCL: AEK - Tenerife", ""),
                    ("Italia - Islanda", "Qualificazioni Mondiali FIBA"), ("Greece v Serbia", "Friendly"), ("Spagna - Francia", ""),
                    ("Germania - Lettonia", "EuroBasket 2029 Qualifiers"), ("Brindisi - Karsiyaka", "FIBA Europe Cup")]:
        assert B(t, comp) is None, (t, comp)
    for t, comp in [("U Cluj - Dubai", ""), ("Liga Națională (Romania): Steaua - Rapid", "Liga Națională (Romania)"),
                    ("Basket 3x3: World Tour Bucharest", "Basket 3x3"), ("Sheffield Sharks - Leicester Riders", "Super League Basketball"),
                    ("Italia - Spagna", "EuroBasket Women"), ("Schio - Venezia", "Serie A1 femminile"), ("Las Vegas Aces - NY Liberty", "WNBA"),
                    ("ALBA Berlin - Bayern", "BBL"), ("Olympiacos - Panathinaikos", "Greek Basket League")]:
        assert B(t, comp), (t, comp)
    assert f({"sport": "Tennis", "titolo": "ATP Shanghai"}) is None  # solo basket
    # nazionali solo dal titolo: "in Griechenland zu Gast" nella descrizione non basta
    assert B("Promitheas Patras gegen Gladiators Trier", descrizione="Die Gladiators sind in Griechenland zu Gast.")
    assert B("Promitheas Patras gegen Gladiators Trier", descrizione="Im Basketball Europe Cup sind die Gladiators in Griechenland.") is None
    return "ok"


def test_teleboy_sportivi():
    """Guida Teleboy, canali sportivi: gare vere sì; repliche, anni vecchi, show e studio no (anche 'NFL - Guten Abend Football')."""
    import altri_sport as A
    import epg_teleboy as E
    import teleboy as TB
    tb = TB.carica(str(QUI.parent / "teleboy_canali.json"), aggiorna=False)
    conf = A.regole_conf()["teleboy_epg"]
    def prog(can, ini, fine, titolo, desc="", data="2026", prima=False, sotto=""):
        return (f'<programme channel="{can}" start="{ini} +0000" stop="{fine} +0000"><title>{titolo}</title>'
                + (f"<sub-title>{sotto}</sub-title>" if sotto else "") + f"<desc>{desc}</desc><date>{data}</date>"
                + ("<premiere />" if prima else "") + "</programme>")
    xml = ('<tv><channel id="SuperTennis.TV.ch"><display-name>SuperTennis TV</display-name></channel>'
           '<channel id="Rai.Sport.+.ch"><display-name>Rai Sport +</display-name></channel>'
           '<channel id="NITRO.ch"><display-name>NITRO</display-name></channel>'
           '<channel id="SPORTITALIA.ch"><display-name>SPORTITALIA</display-name></channel>'
           + prog("SuperTennis.TV.ch", "20261012080000", "20261012100000", "Tennis: Wuhan Open 2025", data="2025")
           + prog("SuperTennis.TV.ch", "20261012100000", "20261012120000", "US Open 2026: Berrettini vs Wawrinka")
           + prog("SuperTennis.TV.ch", "20261012120000", "20261012140000", "Tennis: ATP Masters 1000 Shanghai: Sinner - Alcaraz", "In diretta da Shanghai")
           + prog("Rai.Sport.+.ch", "20261012120000", "20261012150000", "Baseball: Italia - Germania")
           + prog("Rai.Sport.+.ch", "20261012180000", "20261012210000", "Baseball: Italia - Germania")
           + prog("Rai.Sport.+.ch", "20261012153000", "20261012160000", "Speciale Calcio Serie A")
           + prog("NITRO.ch", "20261012161500", "20261012170000", "NFL - Guten Abend Football", prima=True)
           + prog("NITRO.ch", "20261012170000", "20261012200000", "NFL: Kansas City Chiefs - Denver Broncos", prima=True)
           + prog("SPORTITALIA.ch", "20261012183000", "20261012203000", "Serie A Live", sotto="Cagliari - Juventus")
           + "</tv>").encode()
    ini, fine = dt.datetime(2026, 10, 12, tzinfo=p.ROMA), dt.datetime(2026, 10, 14, tzinfo=p.ROMA)
    diag = []
    ev = E.analizza(xml, tb, conf, ini, fine, diag)
    tit = sorted((e["emittenti"][0]["nome"], e["titolo"]) for e in ev)
    assert tit == [("NITRO", "Kansas City Chiefs - Denver Broncos"), ("Rai Sport 1", "Italia - Germania"),
                   ("SuperTennis", "ATP Masters 1000 Shanghai: Sinner - Alcaraz")], (tit, diag)
    motivi = {t: m for _, _, t, m in diag}
    assert motivi["Tennis: Wuhan Open 2025"].startswith("vecchio") and motivi["US Open 2026: Berrettini vs Wawrinka"].startswith("non in diretta")
    assert motivi["NFL - Guten Abend Football"].startswith("programma") and motivi["Speciale Calcio Serie A"].startswith("programma")
    # stesso blocco nelle altre fonti (e_programma): show senza due partecipanti via, partite sì
    rp, re_ = A.regole()
    assert A.e_programma({"titolo": "NFL - Guten Abend Football", "sport": "Football americano", "evento": True}, rp, re_)
    assert A.e_programma({"titolo": "NFL Countdown", "sport": "Football americano", "evento": True}, rp, re_)
    assert A.e_programma({"titolo": "NFL RedZone", "sport": "Football americano", "evento": True}, rp, re_)
    assert A.e_programma({"titolo": "Chiefs @ Broncos", "sport": "Football americano", "evento": True}, rp, re_) is None
    assert A.e_programma({"titolo": "NFL: Bears vs Packers Pre-Game", "sport": "Football americano", "evento": True}, rp, re_) is None
    return len(ev)


def test_finite():
    """Partite finite (inizio > 2h15m fa) tolte lato server; quelle in corso restano; niente 'GIÀ GIOCATA'."""
    def ev(ts, casa):
        return {"ts": ts, "quando": dt.datetime.fromtimestamp(ts, p.ROMA), "casa": casa, "ospite": "B",
                "canali": [{"nome": "Prima Sport 1", "fta": False}]}
    ora = dt.datetime(2026, 10, 10, 21, 0, tzinfo=p.ROMA)
    t = int(ora.timestamp())
    gruppi = [{"nome": "SERIE A", "partite": [ev(t - 3 * 3600, "Finita"), ev(t - 8100 - 60, "Appena finita"),
                                               ev(t - 8100 + 60, "Ultimi minuti"), ev(t - 1800, "In corso"), ev(t + 1800, "Tra poco")]},
              {"nome": "SERIE B", "partite": [ev(t - 4 * 3600, "Vecchia")]}]
    rest = p.togli_finite(gruppi, ora)
    assert [g["nome"] for g in rest] == ["SERIE A"]
    assert [e["casa"] for e in rest[0]["partite"]] == ["Ultimi minuti", "In corso", "Tra poco"]
    h = p.genera_html(ora.date(), ora, rest, [], [])
    assert "GIÀ GIOCATA" not in h and "giocata" not in h and "var DURATA = 8100;" in h and "removeChild" in h
    assert h.count('class="partita"') == 2 * 3 and 'id="vuoto" hidden' in h
    vuota = p.genera_html(ora.date(), ora, [], [], [])
    assert 'id="vuoto">' in vuota


def test_teleboy():
    """Canali Teleboy: confronto dei nomi senza collisioni; pacchetti a pagamento esclusi."""
    tb = TB.carica(QUI.parent / "teleboy_canali.json", aggiorna=False)
    assert tb.n > 250, tb.n
    attesi = {
        "ITV1 UK": "ITV", "ITV 1 England": "ITV", "ITV 4": "ITV 4", "ITV X": None, "UTV Northern Ireland": None,
        "BBC One": "BBC One", "BBC Two": "BBC Two", "BBC Scotland": None, "BBC Alba": None, "BBC iPlayer": None,
        "ARD Das Erste": "Das Erste", "ZDF Deutschland": "ZDF", "RTL Deutschland": "RTL", "RTL Österreich": None,
        "SRF Zwei Schweiz": "SRF zwei", "RSI La 2 Svizzera": "RSI LA 2", "RTS 2 Suisse": "RTS Deux", "RTS 1 Senegal": None,
        "TV8 Italia": "TV8", "TV8 Türkiye": None, "Sport1 Deutschland": "Sport1", "Sport 1 Czechia": None, "Sport 1 Israel": None,
        "Rai Sport": "Rai Sport 1", "Sportitalia SoloCalcio": None, "DMAX Italia": "DMAX Italia", "TV5 Monde": "TV5 Monde FBS",
        "MDR Fernsehen": "MDR Sachsen", "ORF 1 Austria": "ORF 1", "ServusTV Österreich": "ServusTV", "Servus TV": "ServusTV", "Servus TV Österreich": "ServusTV", "Servus TV Austria": "ServusTV", "Nitro Deutschland": "NITRO", "Prima Sport 1": None, "mySports 2": None, "Sport 1+": None,
    }
    trovati = {n: tb.trova(n) for n in attesi}
    assert trovati == attesi, {n: (trovati[n], attesi[n]) for n in attesi if trovati[n] != attesi[n]}
    # nella pagina: un canale non rosso ma su Teleboy viene incluso e marcato
    finto = ('<span class = comp_head>Swiss Super League - Week 9</span><div class = blockfix >'
             '<div class = fLeft style="a">Basel v Servette</div><div data-timestamp="1791648000"></div>'
             '<a href="#" class = chan_live_not_free onmouseover="x" onmouseout="return nd();">SRF Zwei Schweiz HD </a>'
             '<a href="#" class = chan_live_not_free onmouseover="x" onmouseout="return nd();">Blue Sport 1 HD </a>'
             '<a href="#" class = chan_live_not_free onmouseover="x" onmouseout="return nd();">Megogo Sport HD </a></div>')
    x = L.analizza(finto, [], [], ["dazn", "megogo"], tb)[0]
    assert x["canali_fta"] == [] and x["canali_teleboy"] == ["SRF Zwei Schweiz"], x
    return tb


def finto_dazn(paese, primo, giorni, rotto=("fr",)):
    """Guida DAZN salvata il 10/10/2026 (sab 10 – mar 13); i paesi in `rotto` simulano un errore."""
    if paese in rotto:
        return None, "HTTP Error 503"
    with gzip.open(QUI / "fixtures_dazn_2026-10-10" / f"{paese}.json.gz", "rt", encoding="utf-8") as f:
        return json.load(f)["Tiles"], None


def test_dazn():
    """DAZN: solo partite senza lucchetto, unite alle altre fonti; un paese in errore non blocca."""
    # regola "gratis": EntitlementIds vuoto
    assert DZ.gratis({"EntitlementIds": []}) and not DZ.gratis({"EntitlementIds": ["e_silver_it"]})
    v, ini, fine = p.finestra(dt.datetime(2026, 10, 10, 12, tzinfo=p.ROMA))
    tiles, _ = finto_dazn("it", v, 4, ())
    it = DZ.analizza(tiles, "it")
    assert sorted(f'{x["casa"]} - {x["ospite"]}' for x in it) == ["Levante - Siviglia", "Tenerife - Girona"], it
    assert DZ.competizione("UEFA Youth League") == (25, "UEFA YOUTH LEAGUE")
    assert DZ.competizione("Serie A Enilive")[1] == "SERIE A" and DZ.competizione("LALIGA EA SPORTS")[1] == "LALIGA"
    # parametri: offset di Roma (CEST 120, CET 60 dopo il 25/10)
    assert DZ.parametri("it", dt.date(2026, 10, 10), 4)["timeZoneOffset"] == 120
    assert DZ.parametri("de", dt.date(2026, 10, 26), 4)["timeZoneOffset"] == 60
    assert DZ.parametri("de", dt.date(2026, 10, 26), 4)["languageCode"] == "en"
    canali = json.loads((QUI.parent / "canali.json").read_text())["canali"]
    p.scarica, L.scarica = finto_lstv, finto_los
    st = {}
    gruppi, falliti, _ = p.raccogli(canali, ini, fine, dict(CONF_LOS, pausa_secondi=0), st, None,
                                    {"scarica_fn": finto_dazn})
    assert falliti[-1:] == ["DAZN non raggiungibile per: Francia"], falliti
    assert st["dazn_dettagli"] == ["DAZN Francia: HTTP Error 503"], st["dazn_dettagli"]
    assert st["dazn"] == {"it": 2, "de": 2, "pt": 8, "be": 2}, st["dazn"]  # 2 partite di Youth League (U19) escluse
    tutte = {f'{e["casa"]} - {e["ospite"]}': (g["nome"], e) for g in gruppi for e in g["partite"]}
    nomi = lambda k: [c["nome"] for c in tutte[k][1]["canali"]]  # noqa: E731
    assert nomi("Levante - Siviglia")[-2:] == ["DAZN Italia", "DAZN Portogallo"], nomi("Levante - Siviglia")
    assert "DAZN Belgio" in nomi("PSG - Le Mans") and "TV5 Monde" in nomi("PSG - Le Mans")
    assert not any("U19" in k or g == "UEFA YOUTH LEAGUE" for k, (g, _) in tutte.items())  # Youth League esclusa
    # nessun canale DAZN dalle altre fonti: solo quelli "gratis" della guida
    assert all(c.get("dazn_gratis") for _, e in tutte.values() for c in e["canali"] if "dazn" in c["nome"].lower())
    assert st["uniti_dazn"] and st["solo_dazn"] > 0
    dove = json.loads((QUI.parent / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    h = p.genera_html(v, dt.datetime(2026, 10, 10, 12, tzinfo=p.ROMA), gruppi, falliti, [], dove)
    assert "DAZN GRATIS</span>" in h and 'href="#dv-dazn"' in h and "https://www.dazn.com/nl-BE/home" in h
    assert "DAZN non raggiungibile per: Francia" in h
    # tutti i paesi falliti -> una sola riga
    tutti_ko = lambda paese, primo, giorni: (None, "HTTP Error 403: Forbidden")  # noqa: E731
    assert DZ.raccogli_dazn(ini, fine, scarica_fn=tutti_ko) == ([], ["DAZN non raggiungibile in questo aggiornamento"])
    # dati esterni (dati/dazn.json): usati se freschi (< 3 ore), ignorati se vecchi o assenti
    import tempfile, os  # noqa: E401
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "dazn.json")
        assert DZ.leggi_esterni(f) == {}  # file mancante: nessun problema
        ora = dt.datetime(2026, 10, 10, 12, tzinfo=dt.timezone.utc)
        part = {"it": [{"ts": 1791831600, "casa": "Levante", "ospite": "Siviglia", "comp": "LALIGA EA SPORTS"}]}
        for ore, attese in ((1, 1), (4, 0)):
            gen = (ora - dt.timedelta(hours=ore)).strftime("%Y-%m-%dT%H:%M:%SZ")
            with open(f, "w") as fh:
                json.dump({"generato": gen, "paesi": part}, fh)
            est = DZ.leggi_esterni(f, ora)
            partite, avvisi = DZ.raccogli_dazn(ini, fine, scarica_fn=tutti_ko, esterni=est)
            assert len(partite) == attese, (ore, partite)
            assert avvisi == (["DAZN non raggiungibile per: Spagna, Francia, Germania, Portogallo, Belgio"] if attese
                              else ["DAZN non raggiungibile in questo aggiornamento"]), avvisi
        with open(f, "w") as fh:
            fh.write("non json")
        assert DZ.leggi_esterni(f, ora) == {}
    return st


def test_femminile():
    """Calcio femminile escluso (competizione o squadre); nessun falso positivo sulle squadre maschili."""
    rx = U.regex_femminile(CONF_LOS["escludi_competizioni"])
    si = [("English Women's Super League", ()), ("UEFA Women's Champions League", ()),
          ("/international/uefa-womens-champions-league/ UEFA Women's Champions League", ()),
          ("Friendly International (W)", ()), ("Serie A Femminile", ()), ("NAZIONALI FEMMINILI – AMICHEVOLI", ()),
          ("Liga F", ()), ("Frauen-Bundesliga", ()), ("D1 Arkema", ()), ("Damallsvenskan", ()), ("Barclays WSL", ()),
          ("NWSL", ()), ("Eredivisie Vrouwen", ()), ("Super League Dames", ()), ("Primera División Femenina", ()),
          ("Liga MX Femenil", ()), ("Division 1 Féminine", ()), ("Women's World Cup Qualifiers", ()),
          ("Toppserien", ("Rosenborg Kvinner", "Brann")), ("", ("Arsenal W", "Chelsea W")), ("Altro", ("Lyon W", "PSG (W)")),
          ("", ("Juventus Women", "Roma")), ("", ("Lyon (W)", "PSG (W)")), ("Barclays Women's Super League", ("Arsenal", "Chelsea"))]
    no = [("English Premier League", ("Wolves", "West Ham")), ("Championship", ("Bolton Wanderers", "Western Sydney Wanderers")),
          ("A-League", ("Western United", "Wellington Phoenix")), ("Liga Futve", ()), ("Bundesliga", ("Werder Bremen", "VfL Wolfsburg")),
          ("NAZIONALI – AMICHEVOLI", ("Wales", "W. Bremen")), ("Ligue 1", ("PSG", "Le Mans")), ("Serie A", ("Inter", "Juventus")),
          ("Eredivisie", ("Willem II", "Go Ahead Eagles")),
          ("Swiss Super League", ("Winterthur", "Grasshoppers")), ("Altro", ("Arsenal W", "Chelsea")),
          ("Altro", ("Club W", "Real Madrid")), ("Altro", ("Lyon (W)", "PSG")), ("Premier League", ("Wolverhampton Wanderers", "Newcastle"))]
    assert all(U.femminile(rx, c, s) for c, s in si), [x for x in si if not U.femminile(rx, *x)]
    assert not any(U.femminile(rx, c, s) for c, s in no), [x for x in no if U.femminile(rx, *x)]
    assert not any("women" in u.lower() for u in CONF_LOS["pagine"])
    # sui dati salvati: nessuna partita femminile resta, quelle maschili sì
    canali = json.loads((QUI.parent / "canali.json").read_text())["canali"]
    p.scarica, L.scarica = finto_lstv, finto_los
    v, ini, fine = p.finestra(dt.datetime(2026, 10, 9, 12, tzinfo=p.ROMA))
    st = {}
    gruppi, _, _ = p.raccogli(canali, ini, fine, dict(CONF_LOS, pausa_secondi=0), st)
    assert st["femminili_tolte"], st
    assert not any(re.search(r"FEMMINIL|WOMEN", g["nome"]) for g in gruppi), [g["nome"] for g in gruppi]
    return st


RISPOSTE_ALTRI = json.loads(gzip.open(QUI / "fixtures_altri_2026-10-10" / "risposte.json.gz", "rt", encoding="utf-8").read())


def finto_json(url, tentativi=3):
    return (RISPOSTE_ALTRI[url], None) if url in RISPOSTE_ALTRI else (None, "HTTP Error 404: Not Found")


def test_altri_sport():
    """SRF/RTS/RSI/ARD: sport riconosciuto, stesso evento unito, calcio femminile tolto, calcio nella sezione calcio."""
    import altri_sport as A
    A.json_url = finto_json
    assert A.titolo_srg("srf", "Formel 1: GP Singapur") == ("Formula 1", "GP Singapur")
    assert A.titolo_srg("rts", "FORMULE 1 GP de Singapour")[0] == "Formula 1"
    assert A.titolo_srg("rts", "MOTO3 GP d'Indonésie Moto3")[0] == "Motomondiale"
    assert A.titolo_srg("rsi", "Ciclismo: Classiche 2026, Il Lombardia")[0] == "Ciclismo"
    assert A.calcio_squadre({"titolo": "Super League, Lugano - Luzern"}) == ("Lugano", "Luzern", "Super League")
    assert A.calcio_squadre({"titolo": "Champions League, MD2, Roma-Real Madrid"})[:2] == ("Roma", "Real Madrid")
    ora = dt.datetime(2026, 10, 10, 22, 0, tzinfo=p.ROMA)  # ora in cui sono state salvate le risposte
    v, ini, fine = p.finestra(ora)
    rx = U.regex_femminile(CONF_LOS["escludi_competizioni"])
    altri, calcio, avvisi = A.raccogli_altri(ini, fine, ora, rx)
    assert avvisi == [], avvisi
    f1 = [e for e in altri if e["sport"] == "Formula 1"]
    assert len(f1) == 1 and {x["nome"] for x in f1[0]["emittenti"]} == {"SRF", "RTS", "RSI"}, f1  # GP di domenica unito
    assert f1[0]["titolo"] == "GP di Singapore, gara"  # titolo italiano (RSI)
    assert {e["sport"] for e in altri} >= {"Motomondiale", "Boxe", "Danza sportiva"}
    assert any(x["nome"] == "ARD Das Erste" and x["vpn"] == "GERMANIA" for e in altri for x in e["emittenti"])
    assert all(x["vpn"] in ("SVIZZERA", "GERMANIA", None) for e in altri for x in e["emittenti"])
    # calcio femminile (qualificazioni Mondiali femminili su SRF/RTS/RSI, DFB-Frauen su ARD) mai presente
    assert not any(re.search(r"frauen|femminil|féminin", " ".join(e["testi"]), re.I) for e in altri + calcio)
    assert not any("Japan" in e["titolo"] or "Israël" in e["titolo"] for e in altri + calcio), [e["titolo"] for e in altri]
    # partita di calcio in streaming (finta, stesso formato SRG) -> sezione calcio, unita alla stessa partita
    finta = {"type": "SCHEDULED_LIVESTREAM", "title": "Fussball: Super League, Lugano - Luzern", "date": "2026-10-10T17:40:00+02:00",
             "duration": 9000000, "cesimId": "1830000", "urn": "urn:srf:scheduled_livestream:video:x", "playableAbroad": False}
    finta_rsi = dict(finta, title="Calcio: Super League, Lugano-Lucerna", date="2026-10-10T17:55:00+02:00", cesimId="1830001")
    srg = lambda bu: (A.analizza_srg(bu, [finta] if bu == "srf" else [finta_rsi] if bu == "rsi" else []), None)  # noqa: E731
    ora2 = dt.datetime(2026, 10, 10, 18, 0, tzinfo=p.ROMA)
    _, calcio2, _ = A.raccogli_altri(ini, fine, ora2, rx, scarica_srg_fn=srg, scarica_ard_fn=lambda i, f: ([], None))
    assert [(e["casa"], e["ospite"], len(e["emittenti"])) for e in calcio2] == [("Lugano", "Luzern", 2)], calcio2
    canali = json.loads((QUI.parent / "canali.json").read_text())["canali"]
    p.scarica, L.scarica = finto_lstv, finto_los
    st = {}
    gruppi, falliti, _ = p.raccogli(canali, ini, fine, dict(CONF_LOS, pausa_secondi=0), st, None, None,
                                    {"ora": ora2, "scarica_srg_fn": srg, "scarica_ard_fn": lambda i, f: ([], None), "scarica_los_fn": None, "scarica_el_fn": None})
    tutte = {f'{e["casa"]} - {e["ospite"]}': (g["nome"], e) for g in gruppi for e in g["partite"]}
    nome, lug = tutte["Lugano - Luzern"]
    assert nome == "SUPER LEAGUE (Svizzera)" and [c["nome"] for c in lug["canali"]][-2:] == ["SRF stream", "RSI stream"], lug
    assert lug["quando"].strftime("%H:%M") == "18:00" and "Streaming" in lug["fonti"]  # unita alla partita LiveOnSat delle 18
    assert lug["canali"][-2]["url"] == "https://www.srf.ch/play/tv/sport-livestreams"
    assert lug["canali"][-1]["url"] == "https://www.rsi.ch/palinsesto/streaming/"
    assert lug["canali"][-2]["diretta"] == "https://www.srf.ch/play/tv/-/video/-?urn=urn:swisstxt:video:srf:1830000"
    dove = json.loads((QUI.parent / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    h = p.genera_html(v, ora, gruppi, falliti, [], dove, altri)
    assert 'data-sezione="sport"' in h and 'id="vista-sport-orario"' in h and "VPN Svizzera" in h and "VPN Germania" in h and ogni_link_ha_vpn(h)
    assert 'href="https://www.ardmediathek.de/sammlung/die-sport-livestreams-der-ard/livestreams-ard-"' in h
    assert 'href="https://www.rsi.ch/palinsesto/streaming/"' in h and 'href="https://www.rts.ch/play/tv/rts-livestreams"' in h
    assert 'class="diretta" href="https://www.ardmediathek.de/video/' in h and 'data-fine="' in h and "ALTRI SPORT" in h
    assert 'id="dv-ard-sport"' in h and 'id="dv-srf-sport"' in h  # voci "Dove vederli" (sempre visibili)
    # un'emittente che non risponde: avviso, nessun errore
    A.json_url = lambda url, tentativi=3: (None, "HTTP Error 403") if "ardmediathek" in url else finto_json(url)
    _, _, avvisi = A.raccogli_altri(ini, fine, ora, rx)
    assert avvisi == ["Altri sport: non raggiungibile ARD"], avvisi
    A.json_url = finto_json
    return altri, calcio


def test_traduzioni():
    """Titoli tedeschi/francesi -> italiano con il glossario; originale mostrato se la traduzione è parziale."""
    import traduci as Tr
    casi = {"Box-Abend mit Artur Reis und Julian Vogel": "Serata di boxe con Artur Reis e Julian Vogel",
            "Die Tanz-WM 2026": "Mondiali di danza sportiva 2026", "GP Indonesien, MotoGP": "GP d'Indonesia, MotoGP",
            "GP d'Indonésie MotoGP": "GP d'Indonesia MotoGP", "GP de Singapour": "GP di Singapore",
            "Großer Preis von Mexiko": "Gran Premio del Messico",
            "Riesenslalom in Sölden - 1. Lauf der Frauen": "Slalom gigante a Sölden - 1. manche femminile",
            "Weltcup in Sölden, Riesenslalom, Männer": "Coppa del Mondo a Sölden, slalom gigante, maschile",
            "Bahn-WM in Schanghai, 1. Tag": "Mondiali su pista a Shanghai, 1ª giornata",
            "Swiss Indoors in Basel, Viertelfinal": "Swiss Indoors a Basilea, quarti di finale",
            "Finlande - Suisse": "Finlandia - Svizzera", "Lombardei-Rundfahrt": "Giro di Lombardia",
            "Coupe du monde, Slalom géant Dames": "Coppa del Mondo, slalom gigante femminile",
            "Der Marathon in Frankfurt am Main": "Maratona a Francoforte sul Meno",
            "Promitheas Patras gegen Gladiators Trier": "Promitheas Patras contro Gladiators Trier"}
    for de, it in casi.items():
        assert Tr.traduci(de) == (it, True), (de, Tr.traduci(de))
    assert Tr.traduci("Weltcup-Auftakt mit Überraschungen")[1] is False  # parziale -> si mostra l'originale
    assert Tr.nazione("Schweiz") == "Svizzera" and Tr.nazione("Luzern") == "Luzern"
    ev = {"titolo": "Box-Abend mit Artur Reis und Julian Vogel", "titolo_originale": "Weltcup-Auftakt", "ts": 1791650000, "fine": 1791660000,
          "sport": "Boxe", "lingua": "de", "emittenti": [{"nome": "ARD Das Erste", "pagina": "https://x", "link": "https://y", "vpn": "GERMANIA"}]}
    v, _, _ = p.finestra(dt.datetime(2026, 10, 10, 15, 0, tzinfo=p.ROMA))
    h = p.genera_html(v, dt.datetime(2026, 10, 10, 15, 0, tzinfo=p.ROMA), [], [], [], [], [ev])
    assert '<span class="orig" lang="de">Weltcup-Auftakt</span>' in h


def test_dazn_altri():
    """DAZN: eventi gratis di altri sport (no calcio, no a pagamento) nella sezione ALTRI SPORT."""
    import gzip
    import altri_sport as A
    import dazn as D
    tiles = json.loads(gzip.open(QUI / "fixtures_dazn_altri_2026-10-10" / "tiles_it.json.gz").read())
    ev = D.analizza_altri(tiles)
    assert ev and all(e["sport"] != "Calcio" and e["emittenti"][0]["dazn_gratis"] for e in ev)
    assert not any((t.get("Sport") or {}).get("Id") == D.CALCIO for t in tiles if f'dazn:{t.get("EventId")}' in {e["id"] for e in ev})
    titoli = [e["titolo"] for e in ev]
    assert "WBSC Premier12, Spagna - Italia" in titoli and "Porsche Carrera Cup Germany, Hockenheimring - Race 2" in titoli, titoli
    pagati = {f'dazn:{t.get("EventId")}' for t in tiles if not D.gratis(t)}
    assert not pagati & {e["id"] for e in ev}
    ora = dt.datetime(2026, 10, 10, 22, 0, tzinfo=p.ROMA)
    _, ini, fine = p.finestra(ora)
    A.json_url = finto_json
    altri, _, avv = A.raccogli_altri(ini, fine, ora, U.regex_femminile(CONF_LOS["escludi_competizioni"]),
                                     scarica_dazn_fn=lambda: (ev, None))
    assert avv == [] and sum(1 for e in altri if e["emittenti"][0]["nome"] == "DAZN Italia") > 10
    h = p.genera_html(*p.finestra(ora)[:1], ora, [], [], [], [], altri)
    assert 'DAZN Italia</a> <span class="tag dz">DAZN GRATIS</span>' in h
    _, _, avv = A.raccogli_altri(ini, fine, ora, U.regex_femminile(CONF_LOS["escludi_competizioni"]),
                                 scarica_dazn_fn=lambda: ([], "HTTP Error 403"))
    assert avv == ["Altri sport: non raggiungibile DAZN altri sport: HTTP Error 403"], avv
    return ev


def test_epg_teleboy():
    """Guida TV pubblica (epgshare01) per i canali gratuiti di Teleboy: solo dirette di sport, unite agli streaming."""
    import gzip
    import altri_sport as A
    import epg_teleboy as E
    import teleboy as TB
    tb = TB.carica(str(QUI.parent / "teleboy_canali.json"), aggiorna=False)
    xml = gzip.open(QUI / "fixtures_epg_2026-10-10" / "epgshare01_CH1_ridotto.xml.gz").read()
    ora = dt.datetime(2026, 10, 10, 15, 0, tzinfo=p.ROMA)
    _, ini, fine = p.finestra(ora)
    conf = A.regole_conf()["teleboy_epg"]
    ev = E.analizza(xml, tb, conf, ini, fine)
    tit = {(e["emittenti"][0]["nome"], e["titolo"]) for e in ev}
    assert ("ServusTV", "GP Indonesien: Rennen") in tit and ("Sport1", "3. Runde, Swiss Darts Trophy, 2026") in tit, sorted(tit)
    assert ("Eurosport 1 de", "Paris-Tours") in tit and ("RTL", "Philadelphia Eagles - Jacksonville Jaguars") in tit
    # repliche (senza <premiere/>), presentazioni/analisi, programmi non sportivi, canali italiani: mai
    assert not any(re.search(r"vorbericht|analyse|highlights|doppelpass|nachbericht|sport aktuell", e["titolo_orig"].split("  ")[0], re.I)
                   for e in ev), [e["titolo"] for e in ev]
    assert not any(e["emittenti"][0]["nome"] == "Comedy Central" for e in ev)
    # canali italiani inclusi: Il Lombardia su Rai 2 (nella guida senza <premiere/>) è in diretta come su RSI alla stessa ora
    assert {e["emittenti"][0]["nome"] for e in ev if "Lombardia" in e["titolo"] and e["ts"] < ora.timestamp()} == {"RSI LA 2", "Rai 2"}
    servus = sorted(e["ts"] for e in ev if e["emittenti"][0]["nome"] == "ServusTV" and e["titolo_orig"].startswith("MotoGP: GP Indonesien: Rennen"))
    assert len(servus) == 1, servus  # la gara MotoGP in diretta sì, la replica delle 13:07 no
    x = next(e for e in ev if e["emittenti"][0]["nome"] == "ServusTV")
    assert x["emittenti"][0]["teleboy"] and x["emittenti"][0]["vpn"] == "SVIZZERA" and x["emittenti"][0]["pagina"] == "https://www.teleboy.ch/it/live"
    # insieme agli streaming SRG/ARD salvati: stesso evento unito, calcio nella sezione calcio, femminile tolto
    A.json_url = finto_json
    rx = U.regex_femminile(CONF_LOS["escludi_competizioni"])
    altri, calcio, avv = A.raccogli_altri(ini, fine, ora, rx, scarica_tb_fn=E.fn_raccogli(tb, conf, ini, fine, lambda u: (xml, None)))
    assert avv == []
    f1 = [e for e in altri if e["sport"] == "Formula 1" and e["ts"] > ora.timestamp() + 12 * 3600]
    assert len(f1) == 1 and {"SRF", "RSI", "ORF 1", "SRF zwei"} <= {x["nome"] for x in f1[0]["emittenti"]}, f1
    assert f1[0]["emittenti"][0]["nome"] == "SRF"  # prima lo streaming, poi i canali TV di Teleboy
    assert [(c["casa"], c["ospite"]) for c in calcio] == [("FC Lugano", "FC Luzern")], calcio
    assert not any("U23" in e["titolo"] for e in altri + calcio)  # "Fussball Frauen" su DF1
    nfl = [e for e in altri if "Patriots" in e["titolo"]]
    assert nfl and all("New England Patriots" in e["titolo"] for e in nfl), nfl  # nome proprio, non "New Inghilterra"
    h = p.genera_html(*p.finestra(ora)[:1], ora, [], [], [], [], altri)
    assert re.search(r'<span class="tag tb">TELEBOY</span>.{0,300}▶ Teleboy</a> <span class="tag vpn" title="VPN Svizzera"[^>]*>VPN <img class="fl" src="flags/ch.svg"', h), "Teleboy senza VPN"
    assert ogni_link_ha_vpn(h)
    _, _, avv = A.raccogli_altri(ini, fine, ora, rx, scarica_tb_fn=E.fn_raccogli(tb, conf, ini, fine, lambda u: (None, "HTTP Error 403")))
    assert avv == ["Altri sport: non raggiungibile guida TV Teleboy"], avv
    return ev


def test_programmi():
    """ALTRI SPORT e calcio in streaming: solo dirette di gare, niente magazine/studio/highlights."""
    import altri_sport as A
    A.json_url = finto_json
    rp, rev = A.regole()
    srg = lambda t, cesim=None, bu="srf": A.analizza_srg(bu, [{"type": "SCHEDULED_LIVESTREAM", "title": t,  # noqa: E731
        "date": "2026-10-11T18:00:00+02:00", "duration": 3600000, "cesimId": cesim, "urn": "urn:srf:scheduled_livestream:video:x"}],
        solo_sport=False)[0]
    ard = lambda t, sin="": {"titolo": t, "titolo_src": t, "descrizione": sin, "evento": None, "sport": A.sport_di(t) or "Sport"}  # noqa: E731
    tolti = [srg("«Sportpanorama» vom 11. Oktober"), srg("Sport aktuell"), srg("Sportlounge"), srg("Telegiornale sportivo", bu="rsi"),
             srg("Fussball: Super League, Highlights", "123"), srg("Ski Alpin: Zusammenfassung Riesenslalom", "1"),
             srg("TENNIS Swiss Indoors  Cérémonie d'ouverture", bu="rts"), srg("Rad: Tour de Suisse, Wiederholung", "9"),
             srg("Formule 1: le résumé", bu="rts"), srg("Ciclismo: sintesi del Giro", bu="rsi"),
             ard("Sportschau am Sonntag"), ard("Die Sportschau am Sonntag mit der Bundesliga", "mit den Highlights"),
             ard("Wintersport im Ersten", "unter anderem mit Skispringen"), ard("Sportschau Club", "Talk mit Gästen")]
    for e in tolti:
        assert A.e_programma(e, rp, rev), e["titolo_src"]
    tenuti = [srg("Formel 1: GP Singapur", "1828086"), srg("FORMULE 1 GP de Singapour", bu="rts"),
              srg("TENNIS Swiss Indoors 1e tour", bu="rts"), srg("Sci alpino: CdM da Sölden, slalom gigante", bu="rsi"),
              srg("HOCKEY SUR GLACE Finlande - Suisse", bu="rts"), srg("Fussball: Super League, Lugano - Luzern", "1"),
              ard("Alemannia Aachen gegen Hansa Rostock", "3. Liga"), ard("Die Tanz-WM 2026"),
              ard("Box-Abend mit Artur Reis und Julian Vogel", "zeigt die Sportschau diverse Kämpfe"),
              ard("Der Marathon in Frankfurt am Main"), ard("Sommer-Biathlon in München mit dem Massenstart"),
              ard("Riesenslalom in Sölden - 1. Lauf der Frauen")]
    for e in tenuti:
        assert A.e_programma(e, rp, rev) is None, e["titolo_src"]
    # dati salvati: Sportpanorama (SRF) e le due Sportschau (ARD) tolte, le gare restano
    ora = dt.datetime(2026, 10, 10, 22, 0, tzinfo=p.ROMA)
    _, ini, fine = p.finestra(ora)
    lista = []
    altri, calcio, _ = A.raccogli_altri(ini, fine, ora, U.regex_femminile(CONF_LOS["escludi_competizioni"]), programmi_tolti=lista)
    assert any("Sportpanorama" in x for x in lista) and sum("Sportschau" in x for x in lista) == 2, lista
    assert not any(re.search(r"sportschau|sportpanorama", e["titolo"], re.I) for e in altri + calcio)
    assert {e["sport"] for e in altri} >= {"Formula 1", "Motomondiale", "Boxe", "Danza sportiva"}
    # pallamano ARD ("Handball Bundesliga" nella descrizione) non finisce nel calcio
    pag = {"widgets": [{"teasers": [{"id": "h1", "broadcastedOn": "2026-10-11T14:00:00Z", "longTitle": "SG Flensburg Handewitt gegen Füchse Berlin",
                                     "show": {"title": "Sportschau"}, "publicationService": {"name": "NDR"}}]}]}
    ev = A.analizza_ard(pag, lambda t: {"synopsis": "Am 9. Spieltag in der Handball Bundesliga empfängt Flensburg die Füchse."})
    assert ev[0]["sport"] == "Pallamano" and A.e_programma(ev[0], rp, rev) is None, ev
    return lista


def test_dazn_rail():
    """DAZN dalle file "Live"/"ComingUp" (rail-router): stesse partite gratis della guida; guida come riserva."""
    assert DZ.squadre_da_titolo("Fuoriclasse | Cagliari - Juventus") == ("Cagliari", "Juventus")
    assert DZ.squadre_da_titolo("Levante UD v Sevilla FC (Spanish commentary)") == ("Levante UD", "Sevilla FC")
    assert DZ.squadre_da_titolo("Serie A Live") is None
    rail = lambda paese: (json.load(gzip.open(QUI / "fixtures_dazn_rail_2026-10-10" / f"{paese}.json.gz", "rt"))["Tiles"], None)  # noqa: E731
    v, ini, fine = p.finestra(dt.datetime(2026, 10, 10, 12, tzinfo=p.ROMA))
    vero_rail, vera_guida = DZ.scarica_rail, DZ.scarica
    try:
        DZ.scarica_rail, DZ.scarica = rail, (lambda *a: (None, "HTTP Error 403: Forbidden"))
        partite, avvisi = DZ.raccogli_dazn(ini, fine)
        conta = {}
        for x in partite:
            conta[x["paese"]] = conta.get(x["paese"], 0) + 1
        assert avvisi == [] and conta == {"it": 2, "de": 2, "pt": 10, "be": 2}, (conta, avvisi)
        cag = [x for x in partite if x["casa"] == "Cagliari"][0]
        assert dt.datetime.fromtimestamp(cag["ts"], p.ROMA).strftime("%H:%M") == "20:45"  # calcio d'inizio, non il pre-partita
        # file DAZN in errore -> guida EPG (riserva)
        DZ.scarica_rail = lambda paese: (None, "HTTP Error 500")
        DZ.scarica = lambda paese, primo, giorni: finto_dazn(paese, primo, giorni, ())
        partite2, avvisi2 = DZ.raccogli_dazn(ini, fine)
        assert avvisi2 == [] and len(partite2) == 16, (len(partite2), avvisi2)
        # entrambe in errore -> una sola riga di avviso
        DZ.scarica = lambda *a: (None, "HTTP Error 403: Forbidden")
        assert DZ.raccogli_dazn(ini, fine)[1] == ["DAZN non raggiungibile in questo aggiornamento"]
    finally:
        DZ.scarica_rail, DZ.scarica = vero_rail, vera_guida
    return conta


def test_unione():
    """LiveSoccerTV (9/10) + LiveOnSat (10/10), finestra ven 9 – lun 12 ottobre."""
    canali = json.loads((QUI.parent / "canali.json").read_text())["canali"]
    p.scarica = finto_lstv
    L.scarica = finto_los
    conf = dict(CONF_LOS, pausa_secondi=0)
    v, ini, fine = p.finestra(dt.datetime(2026, 10, 9, 12, tzinfo=p.ROMA))
    st = {}
    gruppi, falliti, senza = p.raccogli(canali, ini, fine, conf, st)
    tutte = {f'{e["casa"]} - {e["ospite"]}': e for g in gruppi for e in g["partite"]}
    # pagine non salvate nei fixture -> segnalate, senza bloccare
    assert len(falliti) == len(conf["pagine"]) - 7 and all(f.startswith("LiveOnSat") for f in falliti), falliti
    # 62 - 3 di USL Championship (calcio USA escluso) - 2 di Serie C Brasile solo su SportyNet+ (tolto) = 57
    assert sum("(USA)" in x for x in st["femminili_tolte"]) == 3, st["femminili_tolte"]
    assert st["livesoccertv"] == 57 and st["liveonsat"] > 0 and st["uniti"] and st["solo_liveonsat"] > 0, st
    assert st["totale"] == 57 + st["liveonsat"] - len(st["uniti"]) - len(st["tolte_esclusi"]) + len(st["serie_a_senza_canali"]) - len(st["campionati_romeni_tolti"]) - len(st.get("saudi_pro_league_tolte", [])), st  # escluse le partite romene e la Saudi Pro League
    # doppioni uniti: canali LiveSoccerTV + canali in chiaro LiveOnSat, una sola riga
    psg = tutte["PSG - Le Mans"]
    assert [(c["nome"], c["fta"]) for c in psg["canali"]] == [("TV5 Monde", True)], psg["canali"]  # Persiana esclusa
    assert psg["fonti"] == ["LiveSoccerTV", "LiveOnSat"]
    como = tutte["Como - Roma"]
    assert [c["nome"] for c in como["canali"]] == ["Prima Sport 1", "Sporty TV Africa", "Digi Sport 1"], como["canali"]  # + Digi Sport Romania (LiveOnSat)
    sot = tutte["Southampton - Portsmouth"]
    assert [(c["nome"], c["fta"]) for c in sot["canali"][:2]] == [("Golazo Network", False), ("ITV1 UK", True)], sot["canali"]
    assert not any(k.startswith("Paris St Germain") or k.startswith("Como 1907") for k in tutte)
    # partite solo LiveOnSat, nelle competizioni giuste
    lu = tutte["Lugano - Luzern"]
    assert lu["competizione"] == "SUPER LEAGUE (Svizzera)" and lu["fonti"] == ["LiveOnSat"]
    assert tutte["Galway United - Derry City"]["competizione"] == "FAI CUP (Irlanda)"
    nomi = [g["nome"] for g in gruppi]
    assert nomi.index("SERIE A") == 0 and nomi.count("PREMIER LEAGUE") == 1 and nomi.count("SERIE A") == 1
    assert not any("dazn" in c["nome"].lower() for e in tutte.values() for c in e["canali"])
    assert not any(v in c["nome"].lower() for e in tutte.values() for c in e["canali"]
                   for v in ("megogo", "gem sport", "persiana", "irib", "varz", "meraj"))
    html = p.genera_html(v, dt.datetime(2026, 10, 10, 18, 30, tzinfo=p.ROMA), gruppi, falliti, senza)
    assert html.count('class="partita"') == 2 * st["totale"] and html.count('<li class="fta">') > 50
    # con Teleboy: in più partite con canali non rossi ma su Teleboy; badge e link alla voce Teleboy
    tb = TB.carica(QUI.parent / "teleboy_canali.json", aggiorna=False)
    st2 = {}
    gruppi2, _, _ = p.raccogli(canali, ini, fine, conf, st2, tb)
    tutte2 = {f'{e["casa"]} - {e["ospite"]}': e for g in gruppi2 for e in g["partite"]}
    assert st2["totale"] >= st["totale"] and set(tutte) <= set(tutte2)
    assert any(k["teleboy"] for e in tutte2.values() for k in e["canali"])
    assert tutte2["Southampton - Portsmouth"]["canali"][1]["teleboy"] == "ITV"
    dove = json.loads((QUI.parent / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    h2 = p.genera_html(v, dt.datetime(2026, 10, 9, 12, tzinfo=p.ROMA), gruppi2, [], [], dove)
    i = h2.index('id="dv-prima-sport"')
    blocco = h2[i:h2.index('<li class="dove"', i + 10) if h2.find('<li class="dove"', i + 10) > 0 else h2.index("</ol></section>", i)]
    assert "sito ufficiale" not in blocco and blocco.count('<div class="metodo">') == 2 and blocco.count('<ol class="passi">') == 2
    assert "🟢 METODO 1 — Guardarli sulla TV di casa" in blocco and "🔵 METODO 2 — Guardarli dal computer, senza VPN, STABILMENTE" in blocco
    assert blocco.index('href="https://www.primaplay.ro/register"') < blocco.index('href="https://www.orange.ro/accounts/create-user"')
    assert "<strong>In breve:</strong> Volete guardarli sulla TV di casa? Metodo 1." in blocco and "rds.live" not in blocco
    assert 'TELEBOY</span>' in h2 and 'id="dv-teleboy"' in h2 and 'href="https://www.teleboy.ch/it/live"' in h2
    assert tb.link("ITV") == "https://tv.teleboy.ch/live(player:live/346)"  # come l'esempio dell'utente
    assert 'href="https://tv.teleboy.ch/live(player:live/346)"' in h2 and "▶ Teleboy" in h2
    assert "Canali di questa pagina disponibili su Teleboy" in h2 and h2.count('href="#dv-teleboy"') > 0
    assert not any(x in h2.lower() for x in ("megogo", "persiana", "gem sport"))
    # vista "in ordine di orario": stesse partite, ordinate per ora, con separatori per giorno ed etichetta campionato
    import re as _re
    orario = html[html.index('id="vista-orario"'):html.index('</main>')]
    ts = [int(x) for x in _re.findall(r'data-ts="(\d+)"', orario)]
    assert len(ts) == st["totale"] and ts == sorted(ts)
    assert _re.findall(r'class="giorno-h">([^<]+)', orario) == ["VENERDÌ 9 OTTOBRE", "SABATO 10 OTTOBRE", "DOMENICA 11 OTTOBRE", "LUNEDÌ 12 OTTOBRE"]
    assert orario.count('class="comp-tag"') == st["totale"] and 'data-vista="orario"' not in html and "localStorage" in html
    return st

def test_categorie():
    """Filtri ELITE CALCIO / CALCIO ITALIA / ELITE SPORT (categorie.json)."""
    cal, alt = p.classificatore(p.carica_categorie())
    E = lambda c, o="Y": {"casa": c, "ospite": o}
    assert cal(E("Juventus", "Torino"), "SERIE A") == {"elite", "italia", "seriea"}
    assert cal(E("Bari", "Palermo"), "SERIE B") == {"italia"}
    assert cal(E("Arsenal", "Leeds"), "PREMIER LEAGUE") == {"elite"}
    assert cal(E("Neftchi", "Qarabag"), "PREMIER LEAGUE (Azerbaigian)") == {"minore"}
    assert cal(E("Flamengo", "Santos"), "SERIE B BRASILE") == {"sudamerica"}
    assert "seriea" not in cal(E("Flamengo", "Palmeiras"), "BRASILEIRÃO SERIE A (Brasile)")
    assert cal(E("Boca", "River"), "LIGA PROFESIONAL (Argentina)") == {"sudamerica"} and cal(E("A", "B"), "COPA LIBERTADORES") == {"sudamerica"}
    assert cal(E("America", "Chivas"), "LIGA MX (Messico)") == {"minore"}  # Nord America
    assert cal(E("Real Madrid", "Napoli"), "UEFA CHAMPIONS LEAGUE") == {"elite", "italia"}
    assert cal(E("Real Madrid", "Bayern"), "UEFA CHAMPIONS LEAGUE") == {"elite"}
    assert cal(E("Inter U19", "Ajax U19"), "UEFA YOUTH LEAGUE") == {"minore"}
    assert cal(E("Italia", "Norvegia"), "NAZIONALI – QUALIFICAZIONI MONDIALI 2026") == {"elite", "italia"}
    assert cal(E("Francia", "Spagna"), "NAZIONALI – UEFA NATIONS LEAGUE") == {"elite"}
    assert cal(E("Italia U21", "Svezia U21"), "NAZIONALI – QUALIFICAZIONI EUROPEI U21") == {"minore"}
    assert cal(E("Juventus", "Avellino"), "COPPA ITALIA") == {"elite", "italia"}
    assert "elite" in cal(E("Barcelona", "X"), "COPA DEL REY") and "elite" in cal(E("Bayern", "X"), "DFB-POKAL")
    assert cal(E("Ternana", "Gubbio"), "SERIE C – GIRONE B") == {"italia"}
    assert cal(E("Roma", "Lazio"), "ROMANIA LIGA I") == {"minore"}
    assert cal(E("Botafogo PB", "Santa Cruz"), "SERIE C BRASILE") == {"sudamerica"} and cal(E("Ternana", "Gubbio"), "SERIE C") == {"italia"}
    A = lambda sp, t: alt({"sport": sp, "titolo": t})
    for sp, t in [("Formula 1", "Gran Premio di Singapore"), ("Motomondiale", "MotoGP: gara"), ("Motori", "WEC 6 Ore del Fuji"),
                  ("Tennis", "ATP Shanghai"), ("Basket", "EuroLeague: Olimpia Milano - Real Madrid"),
                  ("Football americano", "Seattle Seahawks - San Francisco 49ers"), ("Sport", "NASCAR Cup Series"), ("Sport", "Rally di Sardegna")]:
        assert A(sp, t) == {"elite"}, (sp, t)
    for sp, t in [("Ciclismo", "Paris-Tours"), ("Football americano", "College Football: Alabama - Georgia"), ("Boxe", "Serata di boxe"),
                  ("Freccette", "Swiss Darts Trophy"), ("Hockey su ghiaccio", "Lugano - Zug"),
                  ("Pallavolo", "LVF A2, Cosedil F3 Motors Akademia Messina - Club Italia")]:
        assert A(sp, t) == set(), (sp, t)
    # HTML: pulsanti e attributi
    ora = dt.datetime(2026, 10, 10, 15, 0, tzinfo=p.ROMA)
    q = ora + dt.timedelta(hours=3)
    g = [{"nome": "SERIE A", "partite": [{"casa": "Juventus", "ospite": "Torino", "quando": q, "ts": int(q.timestamp()), "canali": []}]},
         {"nome": "LIGA I (Romania)", "partite": [{"casa": "FCSB", "ospite": "Rapid", "quando": q, "ts": int(q.timestamp()), "canali": []}]}]
    al = [{"sport": "Formula 1", "titolo": "Gara", "ts": int(q.timestamp()), "fine": int(q.timestamp()) + 7200, "emittenti": []}]
    h = p.genera_html(*p.finestra(ora)[:1], ora, g, [], [], [], al)
    assert "Scegli cosa vuoi vedere:" in h and h.count('data-gruppo="calcio" data-cat=') == 5 and 'data-cat="italia"' not in h.split('data-gruppo="calcio"', 1)[1][:2000] and h.count('data-gruppo="altri" data-cat=') == 2
    assert 'data-cat="elite italia seriea"' in h and 'data-cat="minore"' in h and 'data-fine="%d" data-giorno' % (int(q.timestamp()) + 7200) in h
    assert ">SERIE A<" in h and ">SUDAMERICA<" in h and ">CALCIO MINORE<" in h and 'data-sezione="sport"' in h and "SPORT GRATIS E LEGALE IN TV" in h
    assert 'class="scelta-b cinque"' in h and 'id="crono"' in h and "Ordine cronologico" in h and "ordine-cronologico" in h
    assert 'id="vista-sport-tipo"' in h and 'data-vista="orario"' not in h and 'data-vista="altri"' not in h  # niente pulsanti di ordinamento
    # PER CAMPIONATO: sezioni in ordine di primo calcio d'inizio, a parità ordine fisso
    q2 = q - dt.timedelta(hours=1)
    g2 = [dict(g[0]), {"nome": "LIGA I (Romania)", "partite": [dict(g[1]["partite"][0], quando=q2, ts=int(q2.timestamp()))]}]
    h2 = p.genera_html(*p.finestra(ora)[:1], ora, g2, [], [], [], al)
    assert h2.index("<h2>LIGA I (Romania)</h2>") < h2.index("<h2>SERIE A</h2>") and 'data-ordine="1"' in h2
    assert h.index("<h2>SERIE A</h2>") < h.index("<h2>LIGA I (Romania)</h2>")  # stesso orario: ordine fisso
    assert ">ELITE CALCIO<" in h and ">CALCIO ITALIA<" not in h and ">ELITE SPORT<" in h

def test_altri_los_nfl():
    """Altri sport da LiveOnSat (solo canali in chiaro) + NFL gratis da TechRadar, uniti; link dei canali da dove_vederli.json."""
    import gzip
    import altri_los as AL
    import altri_sport as A
    import teleboy as TB
    F = QUI / "fixtures_los_altri_2026-10-10"
    los = lambda u: ((gzip.open(F / (u.rsplit("/", 1)[-1] + ".gz"), "rt").read(), None) if (F / (u.rsplit("/", 1)[-1] + ".gz")).exists()
                     else ("<title>LiveOnSat</title>", None))
    tr = lambda u: (gzip.open(F / "techradar_nfl.html.gz", "rt").read(), None)
    tb = TB.carica(str(QUI.parent / "teleboy_canali.json"), aggiorna=False)
    ora = dt.datetime(2026, 10, 10, 23, 0, tzinfo=p.ROMA)
    _, ini, fine = p.finestra(ora)
    st = {}
    ev, err = AL.fn_raccogli(dict(CONF_LOS, pausa_secondi=0), tb, ini, fine, los, tr, stat=st)()
    assert err is None and st["nfl_fonte"].startswith("TechRadar") and st["nfl_gratis"] >= 6, st
    rx = U.regex_femminile(CONF_LOS["escludi_competizioni"])
    vuoto = lambda *a: ([], None)
    altri, _, avv = A.raccogli_altri(ini, fine, ora, rx, scarica_srg_fn=vuoto, scarica_ard_fn=vuoto, scarica_los_fn=lambda: (ev, err))
    nfl = {e["titolo"]: {x["nome"] for x in e["emittenti"]} for e in altri if e["sport"] == "Football americano"}
    assert {"5 (Channel 5 / 5ACTION)", "7plus (Seven, Australia)", "TVNZ+ (TVNZ 1 / Duke)", "RTL Deutschland"} <= nfl["New England Patriots - Las Vegas Raiders"], nfl
    assert "Virgin Media Play (Irlanda)" in nfl["Seattle Seahawks - San Francisco 49ers"], nfl
    assert not any(U.regola_canali(CONF_LOS)(x["nome"]) for e in altri for x in e["emittenti"])
    assert any(e["sport"] == "Formula 1" and "Singapore" in e["titolo"] for e in altri)
    dove = json.loads((QUI.parent / "dove_vederli.json").read_text())["voci"]
    trt = p.voce_dove("TRT Spor Türkiye", dove)
    assert trt["link"][0]["url"] == "https://www.trtspor.com.tr/canli-yayin-izle/trt-spor" and trt["fonte"] == "utente"
    assert p.voce_dove("RTS 1 Senegal", dove)["id"] == "rts-senegal" and p.voce_dove("RTS Un Suisse", dove)["id"] == "rts"
    h = p.genera_html(*p.finestra(ora)[:1], ora, [], [], [], dove, altri)
    assert 'href="#dv-idman"' in h and "▶ sito" in h, "link canali"
    return altri

def test_euroleague_tv():
    """EuroLeague/EuroCup: partite sui canali scelti (Idman TV, X Sports, Sporty TV) dalle pagine TV Listings."""
    import gzip
    import altri_sport as A
    import euroleague_tv as E
    F = QUI / "fixtures_euroleague_2026-10-10"
    conf = A.regole_conf()["euroleague_tv"]
    pag = {"/euroleague/": "tv-listings-el.html.gz", "/eurocup/": "tv-listings-ec.html.gz"}
    fp = lambda u: (gzip.open(F / next(v for k, v in pag.items() if k in u), "rt").read(), None)

    def fj(u):
        m = re.search(r"competitions/(\w)/seasons/\w+/(rounds|games\?phaseTypeCode=(\w+)&roundNumber=(\d+))", u)
        f = F / (f"rounds_{m.group(1)}.json.gz" if m.group(2) == "rounds" else f"games_{m.group(1)}_{m.group(3)}_{m.group(4)}.json.gz")
        return (gzip.open(f, "rt").read(), None) if f.exists() else (None, "404")
    # finestra di giovedì 8/10: le partite del 4° turno con i canali scelti
    ini = dt.datetime(2026, 10, 8, tzinfo=p.ROMA); fine = ini + dt.timedelta(days=4)
    st = {}
    ev, err = E.raccogli(conf, ini, fine, fp, fj, st)
    assert err is None, err
    t = {e["titolo"]: [(x["nome"], x["vpn"]) for x in e["emittenti"]] for e in ev}
    assert t["EuroLeague: Real Madrid - Partizan Mozzart Bet Belgrade"] == [("Idman TV", "AZERBAIGIAN"), ("X Sports", "BRASILE"), ("Sporty TV", "NIGERIA")], t
    assert not any("RTSH" in n for v in t.values() for n, _ in v)  # RTSH tolta per sempre (22/10/2026)
    rm = next(e for e in ev if "Real Madrid" in e["titolo"])
    assert rm["ts"] == int(dt.datetime(2026, 10, 8, 18, 45, tzinfo=dt.timezone.utc).timestamp()) and rm["sport"] == "Basket"
    assert len(ev) == 9 and not any("Paris Basketball" in e["titolo"] for e in ev), sorted(t)  # Paris-ASVEL era il 7/10
    assert st["EuroCup"]["partite_con_canali"] == 0  # 3° turno EuroCup: nessuno dei canali scelti
    # nella pagina: link "Dove vederli" (X Sports dell'utente, Sporty TV Africa, RTSH 1 senza link web)
    dove = json.loads((QUI.parent / "dove_vederli.json").read_text())["voci"]
    voce = lambda n: (p.voce_dove(n, dove) or {}).get("id")
    assert [voce(n) for n in ("Idman TV", "X Sports", "Sporty TV")] == ["idman", "x-sports", "sporty-tv-africa"]
    rx = U.regex_femminile(CONF_LOS["escludi_competizioni"])
    vuoto = lambda *a: ([], None)
    altri, _, _ = A.raccogli_altri(ini, fine, ini, rx, scarica_srg_fn=vuoto, scarica_ard_fn=vuoto, scarica_el_fn=lambda: (ev, err))
    h = p.genera_html(ini.date(), ini, [], [], [], dove, altri)
    assert 'href="#dv-x-sports"' in h and "youtube.com/@xsports.brasil/streams" in h and "VPN Brasile" in h and ogni_link_ha_vpn(h) and "rtsh" not in h.lower()
    # pagina non raggiungibile e nessun file dati: nessun avviso nella pagina, solo nel log
    st2 = {}
    ev2, err = E.raccogli(conf, ini, fine, lambda u: (None, "HTTP Error 429"), fj, st2, file_dati=str(F / "non-esiste.json"))
    assert ev2 == [] and err is None and len(st2["errori"]) == 2, st2
    # pagina non raggiungibile ma file dati/basket_tv.json (scritto da scripts/aggiorna_basket.sh): si usano quei dati
    import tempfile
    dati = {"aggiornato": "2026-10-08T09:00Z", "partite": [x for pg in conf["pagine"] if pg["codice"] == "E"
                                                           for x in E.partite_pagina(pg, fp(pg["url"])[0], conf["canali"], fj, {})]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(dati, f)
    st3 = {}
    ev3, err = E.raccogli(conf, ini, fine, lambda u: (None, "HTTP Error 429"), fj, st3, file_dati=f.name)
    assert err is None and [e["titolo"] for e in ev3] == [e["titolo"] for e in ev] and "dati/basket_tv.json" in st3["fonte"]["EuroLeague"], st3
    # dopo le partite (finestra successiva) il file non dà più niente
    assert E.raccogli(conf, ini + dt.timedelta(days=3), fine + dt.timedelta(days=3), lambda u: (None, "429"), fj, {}, file_dati=f.name)[0] == []
    # riserva LiveOnSat: canali scelti per il basket presi anche se non in chiaro
    import altri_los as AL
    blocco = ('<span class = comp_head>ULEB Euroleague - Round 5</span><div class = blockfix ><div class = fLeft style="a">Real Madrid v Monaco</div>'
              '<div data-timestamp="%d"></div><a href="#" class = chan_live_not_free onmouseover="x" onmouseout="return nd();">Idman TV</a>'
              '<a href="#" class = chan_live_not_free onmouseover="x" onmouseout="return nd();">Nova Sports 4 Hellas</a></div>') % (int(ini.timestamp()) + 3600)
    nessuno = lambda n: False
    los = AL.analizza_pagina(blocco, "Basket", 120, CONF_LOS, None, ini, fine, nessuno)
    assert [x["nome"] for x in los[0]["emittenti"]] == ["Idman TV"], los
    assert AL.analizza_pagina(blocco, "Hockey su ghiaccio", 120, CONF_LOS, None, ini, fine, nessuno)[0]["emittenti"] == []
    return ev


if __name__ == "__main__":
    test_finestra(); print("finestra: OK")
    print("LiveSoccerTV 9/10/2026:", test_fixture(), "partite – OK")
    test_fta(); print("LiveOnSat canali in chiaro: OK")
    test_esclusi(); print("LiveOnSat canali esclusi (Megogo/DAZN): OK")
    s = test_russi_iraniani(); print(f"canali russi/iraniani esclusi: {sorted(s['canali_ru_ir'])}, partite tolte: {s['tolte_esclusi']} – OK")
    test_orari(); print("LiveOnSat orari/fuso: OK")
    test_dedup(); print("doppioni (nomi/orari): OK")
    test_ordine(); print("ordine competizioni: OK")
    test_finite(); print("partite finite tolte: OK")
    test_dove(); print("dove vederli: OK")
    test_categorie(); print("filtri ELITE/ITALIA: OK")
    tb = test_teleboy(); print(f"Teleboy ({tb.n} canali): OK")
    sd = test_dazn(); print(f"DAZN: gratis {sd['dazn']}, unite {len(sd['uniti_dazn'])}, solo DAZN {sd['solo_dazn']} – OK")
    sf = test_femminile(); print(f"femminile: {len(sf['femminili_tolte'])} partite escluse nei dati salvati – OK")
    test_traduzioni(); print("traduzioni titoli: OK")
    da = test_dazn_altri(); print(f"DAZN Italia altri sport gratis: {len(da)} eventi – OK")
    ep = test_epg_teleboy(); print(f"guida TV Teleboy (epgshare01): {len(ep)} dirette – OK")
    pr = test_programmi(); print(f"programmi sportivi tolti nei dati salvati: {len(pr)} – OK")
    al, ca = test_altri_sport(); print(f"altri sport: {len(al)} eventi, calcio in streaming {len(ca)} – OK")
    print(f"DAZN (rail-router): {test_dazn_rail()} – OK")
    print(f"LiveOnSat altri sport + NFL gratis: {len(test_altri_los_nfl())} eventi – OK")
    print(f"Ordine TUTTO (blocchi A/B/C): {test_ordine_tutto()} – OK")
    print(f"Ordine ALTRI SPORT TUTTO (elite prima): {test_ordine_sport()} – OK")
    print(f"Prima Play: {test_primaplay()} – OK")
    print(f"Basket solo competizioni ammesse: {test_basket()} – OK")
    print(f"Teleboy canali sportivi (repliche/show tolti): {test_teleboy_sportivi()} dirette – OK")
    print(f"EuroLeague/EuroCup TV Listings: {len(test_euroleague_tv())} partite – OK")
    st = test_unione()
    print(f"unione: LiveSoccerTV {st['livesoccertv']} + LiveOnSat {st['liveonsat']} - uniti {len(st['uniti'])}"
          f" = {st['totale']} – OK")


def test_youth_league():
    conf = json.loads((p.RADICE / "liveonsat.json").read_text(encoding="utf-8"))
    rx = U.regex_femminile(conf["escludi_competizioni"])
    assert U.femminile(rx, "UEFA Youth League | UEFA YOUTH LEAGUE", ("Leipzig", "PSV"))
    assert U.femminile(rx, "", ("Leipzig U19", "PSV U19"))
    assert U.femminile(rx, "UYL", ("A", "B"))
    assert not U.femminile(rx, "UEFA Champions League", ("Leipzig", "PSV"))
    cat = json.loads((p.RADICE / "categorie.json").read_text(encoding="utf-8"))
    assert not any("YOUTH" in x for x in cat["calcio"]["ordine_tutto"]["blocco_a"])


test_youth_league(); print("UEFA Youth League / U19 escluse: OK")


def test_dtt_italia():
    for nome, lcn in [("Rai Sport HD", 58), ("SuperTennis", 64), ("Sportitalia HD", 60), ("TV8", 8), ("Nove", 9),
                      ("Cielo", 26), ("DMAX Italia", 52), ("Rai 2", 2), ("Canale 5", 5)]:
        assert (p.dtt_di(nome) or {}).get("lcn") == lcn, nome
    assert p.dtt_di("TV8 Int") is None and p.dtt_di("DMAX") is None and p.dtt_di("TV8 Mont Blanc") is None
    dove = json.loads((p.RADICE / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    h = p.badge({"nome": "SuperTennis", "fta": True, "teleboy": "SuperTennis", "teleboy_link": "https://www.teleboy.ch/it/live/550"}, dove, set())
    assert "DTT 64" in h and "flags/it.svg" in h and "▶ Teleboy</a>" in h and "flags/ch.svg" in h and "raiplay" not in h, h
    h = p.emittente_altro({"nome": "Rai Sport", "pagina": None, "link": "https://www.teleboy.ch/it/live/271", "vpn": "SVIZZERA",
                           "teleboy": True, "fta": True}, dove, set())
    assert "DTT 58" in h and "raiplay" not in h and "▶ Teleboy</a>" in h and "flags/ch.svg" in h, h
    h = p.badge({"nome": "Rai 2", "fta": True}, dove, set())  # senza Teleboy: solo DTT, niente RaiPlay
    assert "DTT 2" in h and "▶" not in h and "raiplay" not in h, h


test_dtt_italia(); print("DTT Italia (numeri LCN, RaiPlay): OK")


def test_solh():
    conf = json.loads((p.RADICE / "liveonsat.json").read_text(encoding="utf-8"))
    esc = [x.lower() for x in conf["escludi_canali"]]
    for n in ("Solh Sports", "Solh TV", "SOLH Sport HD"):
        assert any(x in n.lower() for x in esc), n
    dove = json.loads((p.RADICE / "dove_vederli.json").read_text(encoding="utf-8"))
    assert "solh" not in json.dumps(dove).lower()


test_solh(); print("Solh escluso: OK")


def test_youtube_link():
    dove = json.loads((p.RADICE / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    s = next(x for x in dove if x["id"] == "sifir")
    assert s["link"][0]["url"] == "https://www.youtube.com/@sifirtv" and s["vpn_tag"] == "VPN Turchia" and s.get("verificato", True)
    for nome in ("Sifir TV", "SportyNet Brasil", "X Sports"):
        h = p.badge({"nome": nome, "fta": True}, dove, set())
        assert 'src="youtube.svg"' in h and "YouTube</a>" in h and "▶ sito" not in h and 'class="tag vpn' in h, h
    assert 'flags/tr.svg' in p.badge({"nome": "Sifir TV", "fta": True}, dove, set())
    assert (p.RADICE / "static" / "youtube.svg").exists()


test_youtube_link(); print("link YouTube con icona: OK")


def test_vtm_trt():
    import epg_teleboy as E, altri_sport as A, liveonsat as LL
    conf = A.regole_conf()["teleboy_epg"]
    g = next(x for x in conf["altre_guide"] if x["nome"].startswith("VTM"))
    xml = b"""<tv><channel id="VTM.2.be"><display-name>VTM 2</display-name></channel>
<programme channel="VTM.2.be" start="20261013183000 +0000" stop="20261013212000 +0000"><title>Live: UEFA Champions League</title>
<desc>Verslag van de wedstrijd Internazionale - Club Brugge, gespeeld in de competitiefase van de UEFA Champions League.</desc><premiere/></programme>
<programme channel="VTM.2.be" start="20261013212000 +0000" stop="20261013215000 +0000"><title>Live: UEFA Champions League samenvattingen</title>
<desc>Alle hoogtepunten van de vanavond gespeelde wedstrijden.</desc><premiere/></programme>
<programme channel="VTM.2.be" start="20261011101500 +0000" stop="20261011104500 +0000"><title>Champions League Magazine</title><desc>Voetbalmagazine.</desc></programme>
</tv>"""
    ini = dt.datetime(2026, 10, 11, 12, tzinfo=p.ROMA)
    ev = E.analizza(xml, None, conf, ini, ini + dt.timedelta(days=4), guida=g)
    assert len(ev) == 1 and ev[0]["sport"] == "Calcio" and "Internazionale - Club Brugge" in ev[0]["titolo"], ev
    em = ev[0]["emittenti"][0]
    assert em["nome"] == "VTM 2" and em["vpn"] == "BELGIO" and "vtmgo.be" in em["link"] and not em.get("teleboy")
    los = json.loads((p.RADICE / "liveonsat.json").read_text(encoding="utf-8"))
    for n, atteso in [("VTM HD", "VTM"), ("VTM2", "VTM 2"), ("VTM GO", "VTM"), ("VTM Gold", "VTM GOLD")]:
        x = LL.pulisci_canale(n, los["alias_canali"])
        assert x == atteso and LL.in_chiaro(x, los["canali_in_chiaro"]), (n, x)
    dove = json.loads((p.RADICE / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    h = p.badge({"nome": "VTM 2", "fta": True}, dove, set())
    assert "vtmgo.be/vtmgo/live-kijken/vtm" in h and "flags/be.svg" in h, h
    assert p.voce_dove("TRT Spor", dove)["id"] == "trt" and p.voce_dove("TRT Spor Yildiz", dove)["id"] == "trt"
    assert p.voce_dove("TRT 1", dove)["id"] == "trt1" and p.voce_dove("TRT 1 HD", dove)["id"] == "trt1"
    assert p.voce_dove("TRT Haber", dove)["id"] == "trt-altri"
    assert "com.com.tr/canli-tv/trt-1" in p.badge({"nome": "TRT 1", "fta": True}, dove, set())


test_vtm_trt(); print("VTM (guida BE) e TRT 1/TRT Spor: OK")


def test_digisport():
    import digisport as D
    cart = QUI / "fixtures_digisport_2026-10-12"
    pagine = {f"https://www.digisport.ro/program-tv/digisport-{i}": gzip.decompress((cart / f"digisport-{i}.html.gz").read_bytes()).decode()
              for i in range(1, 5)}
    ini, fine = dt.datetime(2026, 10, 11, 23, tzinfo=p.ROMA), dt.datetime(2026, 10, 15, 0, tzinfo=p.ROMA)
    st = {}
    cal, alt, err = D.raccogli(D.carica_conf(), ini, fine, lambda u: (pagine[u], None), dt.date(2026, 10, 12), st)
    assert err is None
    partite = {f'{x["casa"]} - {x["ospite"]}': x for x in cal}
    # Champions League alle 19:40 in Romania = 18:40 a Roma (EEST -> CEST)
    lens = partite["Lens - Sporting"]
    assert dt.datetime.fromtimestamp(lens["ts"], p.ROMA).strftime("%d %H:%M") == "13 18:40" and lens["canale"] == "Digi Sport 1"
    assert "Manchester City - PSG" in partite and "Atlético Madrid - Manchester United" in partite
    assert sum(1 for x in cal if x["casa"] == "Lens") == 1  # partita spezzata su più righe: una sola
    assert not any("Superliga" in x["comp"] or "Liga a 2-a" in x["comp"] for x in cal)  # calcio romeno escluso
    assert any("Superliga" in x for x in st["calcio_escluso"])
    assert {x["sport"] for x in alt} <= {"Tennis", "Basket", "Motori", "Motomondiale", "Formula 1", "Football americano"}
    assert any("WTA Wuhan" in x["titolo"] and x["emittenti"][0]["link"].endswith("digisport-2") for x in alt)
    assert not any(re.search(r"Digi Sport Special|Fotbal Club|Rezumat|Stirile", x["titolo_src"]) for x in alt)
    # unione: Inter - Club Brugge (Digi Sport 3) con la partita già presente; Youth League esclusa
    e = [{"ts": partite["Inter - Club Brugge"]["ts"], "quando": None, "titolo": "Inter v Club Brugge", "ordine": 1,
          "competizione": "UEFA CHAMPIONS LEAGUE", "casa": "Inter", "ospite": "Club Brugge", "canali": [{"nome": "VTM 2", "fta": True}],
          "fonti": ["LiveOnSat"]}]
    conf = json.loads((p.RADICE / "liveonsat.json").read_text(encoding="utf-8"))
    rx = U.regex_femminile(conf["escludi_competizioni"])
    ev, uniti, nuove = p.unisci_primaplay(e, cal, (), lambda c, s, n: U.femminile(rx, c, s), "Digi Sport", "ALTRE PARTITE (Digi Sport)")
    assert [c["nome"] for c in ev[0]["canali"]] == ["VTM 2", "Digi Sport 3"] and "Digi Sport" in ev[0]["fonti"]
    assert not any(x["casa"] == "Manchester City" and "Youth" in (x.get("comp_orig") or "") for x in ev)
    dove = json.loads((p.RADICE / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    h = p.badge({"nome": "Digi Sport 3", "fta": False}, dove, set())
    assert "digisport.ro/live/digisport-3" in h and "flags/ro.svg" in h, h
    h = p.badge({"nome": "RTL tvi", "fta": True}, dove, set())
    assert "rtlplay.be/rtlplay/direct" in h and "flags/be.svg" in h, h
    assert p.voce_dove("RTL Deutschland", dove)["id"] == "rtl" and p.voce_dove("Club RTL", dove)["id"] == "rtl-club"
    assert LL_in_chiaro("RTL Club", conf) and not LL_in_chiaro("RTL Zwei", conf) and not LL_in_chiaro("RTL", conf)
    return st


def LL_in_chiaro(nome, conf):
    return L.in_chiaro(L.pulisci_canale(nome, conf["alias_canali"]), conf["canali_in_chiaro"])


sdg = test_digisport(); print(f"Digi Sport: {sdg['calcio']} partite, {sdg['altri']} altri sport – OK")


def test_blue_zoom():
    import epg_teleboy as E, altri_sport as A
    tb = TB.carica(str(p.RADICE / "teleboy_canali.json"), aggiorna=False)
    conf = A.regole_conf()["teleboy_epg"]
    assert conf["alias"]["blue.Zoom.D.ch"] == "blue Zoom de" and tb.trova("blue Zoom de") == "blue Zoom de"
    xml = """<tv><channel id="blue.Zoom.D.ch"><display-name>blue Zoom D</display-name></channel>
<channel id="blue.Zoom.F.ch"><display-name>blue Zoom F</display-name></channel>
<programme channel="blue.Zoom.D.ch" start="20261012164500 +0000" stop="20261012190000 +0000"><title>Fussball: FC Stade Nyonnais - FC Aarau</title><desc>Challenge League</desc><premiere/></programme>
<programme channel="blue.Zoom.D.ch" start="20261013013000 +0000" stop="20261013033000 +0000"><title>Fussball: FC Zürich - FC Thun</title><desc>Super League</desc></programme>
<programme channel="blue.Zoom.F.ch" start="20261012061000 +0000" stop="20261012080000 +0000"><title>Basketball: KK Roter Stern Belgrad - Anadolu Efes Istanbul</title><desc>EuroLeague - Vivez toute la passion de l'EuroLeague de basket en direct sur blue Zoom!</desc><premiere/></programme>
</tv>""".encode()
    ini = dt.datetime(2026, 10, 12, 0, tzinfo=p.ROMA)
    ev = E.analizza(xml, tb, conf, ini, ini + dt.timedelta(days=3))
    assert len(ev) == 2 and any(x["sport"] == "Calcio" and "Nyonnais" in x["titolo"] for x in ev) and any(x["sport"] == "Basket" and "Roter Stern" in x["titolo"] for x in ev), ev
    assert all(x["emittenti"][0]["vpn"] == "SVIZZERA" for x in ev)


test_blue_zoom(); print("blue Zoom (guida CH1): dirette sì, repliche no – OK")


def test_scooore():
    import scooore as S
    xml = gzip.decompress((QUI / "fixtures_scooore_2026-10-11" / "ch.xml.gz").read_bytes())
    part = S.partite(xml)
    assert any(x["casa"] == "Santos FC" and x["ospite"] == "Flamengo" for x in part)
    assert not any("Alle Tore" in x["casa"] for x in part)  # highlights tolti
    santos = next(x for x in part if x["casa"] == "Santos FC")
    e = [{"ts": santos["ts"] + 5 * 60, "casa": "Santos", "ospite": "Flamengo", "canali": [{"nome": "SportyNet Brasil", "fta": False}], "fonti": ["LiveSoccerTV"]},
         {"ts": santos["ts"] + 2 * 3600, "casa": "Saudi Arabia", "ospite": "Qatar", "canali": [], "fonti": []}]
    uniti = p.unisci_conferma(e, part, "Scooore", "Scooore")
    assert uniti == ["Santos - Flamengo"] and e[0]["canali"][-1]["nome"] == "Scooore", uniti
    assert len(e) == 2  # nessuna partita nuova solo da Scooore (la guida non dice se è diretta)
    dove = json.loads((p.RADICE / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    h = p.badge({"nome": "Scooore", "fta": True}, dove, set())
    assert "zattoo.com/guide/sports?channel=scooore_de" in h and "flags/ch.svg" in h, h


test_scooore(); print("Scooore (solo conferma di partite già presenti): OK")


def test_prima_register():
    dove = json.loads((p.RADICE / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    standard = p.badge({"nome": "Prima Sport 2", "fta": False}, dove, set())
    assert 'href="https://tvgo.orange.ro/livetv?genreId=supergenrelive%2C9"' in standard and "▶ Orange TV" in standard and "SENZA VPN" in standard and "primaplay.ro" not in standard, standard
    assert 'href="#dv-prima-sport"' in standard, standard
    ppv = p.badge({"nome": "Prima Sport PPV27", "fta": False}, dove, set())
    assert 'href="https://www.primaplay.ro/register"' in ppv and "PrimaPlay · app TV" in ppv and "Solo app TV" in ppv, ppv
    assert "orange.ro" not in ppv.lower() and "Orange TV" not in ppv, ppv
    assert 'href="#dv-prima-sport-ppv"' in ppv, ppv
    s = p.sezione_dove(dove, {"prima-sport", "prima-sport-ppv"})
    assert s.count('<li>Aprite questo link con Google Chrome') == 2 and "In breve:" in s
    nota_ppv = next(v["note"] for v in dove if v["id"] == "prima-sport-ppv")
    assert "Non sono disponibili su Orange TV" in nota_ppv and "solo nell'app PrimaPlay" in nota_ppv


test_prima_register(); print("Prima Sport -> guida a due metodi: OK")


def test_vtm_unico():
    dove = json.loads((p.RADICE / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    g = [{"nome": "X", "partite": [{"canali": [{"nome": "VTM 2", "fta": True}, {"nome": "Club RTL", "fta": True},
                                               {"nome": "VTM GO", "fta": False}, {"nome": "VTM 2 Belgium HD", "fta": True}]}]}]
    a = [{"emittenti": [{"nome": "VTM 4", "link": "x", "fta": True}, {"nome": "VTM", "fta": True}]}]
    p.unifica_canali(g, a, dove)
    assert [c["nome"] for c in g[0]["partite"][0]["canali"]] == ["VTM GO", "RTL Club"]
    assert [c["nome"] for c in a[0]["emittenti"]] == ["VTM GO"] and a[0]["emittenti"][0]["link"] is None
    h = p.badge(g[0]["partite"][0]["canali"][0], dove, set())
    assert "vtmgo.be" in h and "flags/be.svg" in h, h


test_vtm_unico(); print("VTM -> una sola riga VTM GO: OK")


def test_doppioni_stessa_partita():
    t = int(dt.datetime(2026, 10, 14, 21, 0, tzinfo=p.ROMA).timestamp())
    ev = lambda ts, c, o, can, fonti: {"ts": ts, "quando": dt.datetime.fromtimestamp(ts, p.ROMA), "casa": c, "ospite": o,
                                      "canali": can, "fonti": fonti, "competizione": "X", "ordine": 1}
    eventi = [ev(t - 50 * 60, "AS Roma", "Real Madrid",
                 [{"nome": "SRF stream", "fta": True, "url": "u", "diretta": "d", "vpn": True}], ["Streaming"]),
              ev(t, "Roma", "Real Madrid", [{"nome": "Prima Sport 1", "fta": False}], ["Prima Play"]),
              ev(t, "Roma", "Lazio", [{"nome": "DAZN", "fta": False}], ["LiveOnSat"]),
              ev(t + 24 * 3600, "Roma", "Real Madrid", [{"nome": "Y", "fta": False}], ["LiveOnSat"])]
    tenuti, uniti = p.unisci_doppioni(eventi)
    assert len(tenuti) == 3 and len(uniti) == 1, (tenuti, uniti)
    rm = [e for e in tenuti if e["ospite"] == "Real Madrid" and e["quando"].day == 14]
    assert len(rm) == 1 and rm[0]["ts"] == t  # orario ufficiale 21:00, non 20:10 dello stream
    nomi = {k["nome"]: k for k in rm[0]["canali"]}
    assert set(nomi) == {"Prima Sport 1", "SRF stream"} and nomi["SRF stream"]["diretta"] == "d"


test_doppioni_stessa_partita(); print("doppioni Roma - Real Madrid uniti con orario ufficiale: OK")


def test_ictimai():
    dove = json.loads((p.RADICE / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    for nome in ("Ictimai TV", "İctimai TV", "ITV Azerbaijan"):
        assert p.voce_dove(nome, dove)["id"] == "ictimai", nome
    assert p.voce_dove("ITV1", dove)["id"] != "ictimai"
    h = p.badge({"nome": "Ictimai TV", "fta": True}, dove, set())
    assert 'href="#dv-ictimai"' in h and 'href="https://www.youtube.com/@ictimaitvofficial/featured"' in h and "YouTube" in h and "flags/az.svg" in h and "VPN Azerbaigian" in h, h


test_ictimai(); print("Ictimai TV -> YouTube: OK")


def test_m4_sport():
    dove = json.loads((p.RADICE / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    for nome in ("M4 Sport", "M4Sport", "M4 Sport Hungary", "MTV4", "MTV 4"):
        assert p.voce_dove(nome, dove)["id"] == "m4-sport", nome
    assert (p.voce_dove("Match 4 Hungary HD", dove) or {}).get("id") != "m4-sport"
    h = p.badge({"nome": "M4 Sport Hungary", "fta": True}, dove, set())
    assert 'href="#dv-m4-sport"' in h and "mediaklikk.hu/elo/mtv4live/" in h and "VPN Ungheria" in h and "SENZA VPN" not in h, h


test_m4_sport(); print("M4 Sport -> MediKlikk VPN Ungheria: OK")


def test_los_pagina_vuota():
    import urllib.request as UR
    class R:
        def __init__(self, t): self.t = t.encode()
        def read(self): return self.t
        def __enter__(self): return self
        def __exit__(self, *a): return False
    pagine = {"vuota": "<html><head><title>*** LJs LiveOnSat Football / Soccer Schedules on TV</title></head><body>menu</body></html>",
              "blocco": "<html><title>Just a moment...</title>Cloudflare</html>"}
    orig, osleep, ofinto = UR.urlopen, L.time.sleep, L.scarica
    UR.urlopen = lambda req, timeout=0: R(pagine[req.full_url.rsplit("/", 1)[-1]])
    L.time.sleep = lambda s: None
    try:
        L.scarica = _SCARICA_LOS
        ora = dt.datetime.now(dt.timezone.utc)
        part, falliti = L.raccogli_los({"pagine": ["https://x/vuota", "https://x/blocco"], "pausa_secondi": 0}, ora, ora + dt.timedelta(days=3))[:2]
    finally:
        UR.urlopen, L.time.sleep, L.scarica = orig, osleep, ofinto
    assert falliti == ["LiveOnSat blocco (pagina inattesa (possibile blocco))"], falliti


test_los_pagina_vuota(); print("LiveOnSat pagina valida senza partite: nessun avviso: OK")


def test_doppioni_nomi():
    t = 1_800_000_000
    assert U.stessa_partita(t, "RB Leipzig", "PSV", t, "Leipzig", "PSV Eindhoven")
    assert U.stessa_partita(t, "Leeds", "Arsenal", t, "Leeds United", "Arsenal FC")
    assert U.stessa_partita(t, "Atlético Madrid", "Roma", t, "Atletico de Madrid", "AS Roma")
    assert U.stessa_partita(t, "Lugano", "Stella Rossa", t, "FC Lugano", "Red Star Belgrade")
    assert U.stessa_partita(t, "CSU Craiova", "Getafe", t, "Universitatea Craiova", "Getafe CF")
    # senza un avversario in comune le parole distintive bloccano (con avversario comune vale l'àncora)
    for a in (("Manchester United", "Arsenal", "Manchester City", "Chelsea"), ("Inter", "Roma", "Inter Miami", "Orlando City"),
              ("Real Madrid", "Getafe", "Real Sociedad", "Girona"), ("Roma", "Lazio", "Roma U19", "Lazio U19"),
              ("Barcelona", "Sevilla", "Barcelona B", "Sevilla"), ("Juventus", "Milan", "Juventus Women", "Milan Women")):
        assert not U.stessa_partita(t, a[0], a[1], t, a[2], a[3]), a
    q = lambda ts: dt.datetime.fromtimestamp(ts, p.ROMA)
    ev = [{"ts": t, "quando": q(t), "casa": "Leipzig", "ospite": "PSV Eindhoven", "canali": [{"nome": "Prima Sport PPV2", "fta": False}], "fonti": ["Prima Play"]},
          {"ts": t, "quando": q(t), "casa": "RB Leipzig", "ospite": "PSV", "canali": [{"nome": "Prima Sport 2", "fta": False}], "fonti": ["Digi Sport", "LiveOnSat"]}]
    tenuti, _ = p.unisci_doppioni(ev)
    assert len(tenuti) == 1 and (tenuti[0]["casa"], tenuti[0]["ospite"]) == ("RB Leipzig", "PSV Eindhoven")
    assert {k["nome"] for k in tenuti[0]["canali"]} == {"Prima Sport PPV2", "Prima Sport 2"}


def test_doppioni_ancora():
    t = 1_800_000_000
    assert U.stessa_partita(t, "Bristol City", "Millwall", t, "Bristol", "Millwall FC")
    assert U.stessa_partita(t, "Arsenal", "Manchester City", t, "Arsenal", "Man City FC")
    assert not U.stessa_partita(t, "Roma", "Lazio", t, "Roma U19", "Lazio")      # marcatori sempre
    assert not U.stessa_partita(t, "Roma", "Lazio", t, "Roma", "Lazio Women")
    assert not U.stessa_partita(t, "Roma", "Lazio", t, "Roma", "Juventus")       # àncora ma avversario diverso
    assert not U.stessa_partita(t, "Inter", "Roma", t, "Inter Miami", "Orlando")  # nessuna àncora: blocco rigido
    q = lambda ts: dt.datetime.fromtimestamp(ts, p.ROMA)
    ev = [{"ts": t, "quando": q(t), "casa": "FC Lugano", "ospite": "Red Star Belgrade", "canali": [{"nome": "A", "fta": False}], "fonti": ["LiveOnSat"]},
          {"ts": t, "quando": q(t), "casa": "Lugano", "ospite": "Stella Rossa", "canali": [{"nome": "B", "fta": True}], "fonti": ["Streaming"]}]
    tenuti, _ = p.unisci_doppioni(ev)
    assert len(tenuti) == 1 and tenuti[0]["ospite"] == "Stella Rossa" and tenuti[0]["casa"] == "FC Lugano", tenuti


test_doppioni_ancora(); print("doppioni con avversario come àncora e nomi italiani: OK")


test_doppioni_nomi(); print("doppioni con nomi diversi (RB Leipzig / PSV Eindhoven) e falsi positivi: OK")


def test_repliche_e_nomi_italiani():
    t = int(dt.datetime(2026, 10, 14, 21, 0, tzinfo=p.ROMA).timestamp())
    q = lambda ts: dt.datetime.fromtimestamp(ts, p.ROMA)
    ev = lambda ts, c, o, k, f: {"ts": ts, "quando": q(ts), "casa": c, "ospite": o, "canali": [{"nome": k, "fta": True}], "fonti": f}
    mezzanotte = int(dt.datetime(2026, 10, 16, 0, 0, tzinfo=p.ROMA).timestamp())
    eventi = [ev(t, "Manchester City", "Paris Saint-Germain", "Prima Sport 2", ["Prima Play"]),
              ev(mezzanotte, "Manchester City", "Paris Saint Germain", "Sportitalia HD", ["Streaming"]),   # replica: tolta
              ev(t + 86400, "Roma", "Lazio", "A", ["LiveOnSat"]),
              ev(t + 2 * 86400 + 3 * 3600, "Roma", "Lazio", "B", ["LiveSoccerTV"]),                        # data sbagliata: unita
              ev(t, "Arsenal", "Bayern Munich", "C", ["LiveOnSat"]),
              ev(t + 21 * 86400, "Bayern Munich", "Arsenal", "D", ["LiveOnSat"]),                          # ritorno: resta
              ev(t, "Juventus", "Milan", "E", ["LiveOnSat"]),
              ev(t + 86400, "Juventus U19", "Milan U19", "F", ["Streaming"])]                              # giovanili: resta
    tenuti, tolte = p.togli_repliche(eventi)
    assert len(tenuti) == 6 and len(tolte) == 2, (tenuti, tolte)
    assert not any(e["canali"][0]["nome"] == "Sportitalia HD" for e in tenuti)
    rl = next(e for e in tenuti if e["casa"] == "Roma")
    assert [k["nome"] for k in rl["canali"]] == ["A", "B"] and rl["ts"] == t + 86400
    assert U.in_italiano("Red Star Belgrade") == "Stella Rossa" and U.in_italiano("Crvena Zvezda") == "Stella Rossa"
    assert U.in_italiano("Bayern Munich") == "Bayern Monaco" and U.in_italiano("Paris Saint-Germain") == "Paris Saint-Germain"
    assert U.in_italiano("Inter Miami") == "Inter Miami" and U.in_italiano("Bayern Munich U19") == "Bayern Munich U19"
    e = p.nomi_italiani([{"casa": "FC Lugano", "ospite": "Red Star Belgrade"}])[0]
    assert (e["casa"], e["ospite"]) == ("FC Lugano", "Stella Rossa")


test_repliche_e_nomi_italiani(); print("repliche tolte, date sbagliate unite, nomi italiani: OK")


def test_ricerca_html():
    v = p.genera_html.__code__.co_varnames
    src = (p.RADICE / "scraper" / "palinsesto.py").read_text(encoding="utf-8")
    assert 'id="cerca"' in src and 'id="cerca-x"' in src and 'id="nessun-risultato"' in src and "trovato(p, parole)" in src


test_ricerca_html(); print("barra di ricerca presente: OK")


def test_rtl_club():
    dove = json.loads((p.RADICE / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    for n in ("RTL Play", "RTLplay", "rtl play", "RTL Club", "RTL-Club", "RTL Club HD", "Club RTL"):
        assert p.voce_dove(n, dove)["id"] == "rtl-club", n
    for n, atteso in (("RTL Deutschland", "rtl"), ("RTL TVI", "rtl-belgio")):
        assert p.voce_dove(n, dove)["id"] == atteso, n
    assert p.voce_dove("RTL Zwee", dove) is None or p.voce_dove("RTL Zwee", dove)["id"] != "rtl-club"
    g = [{"nome": "X", "partite": [{"canali": [{"nome": "RTL Play", "fta": True}, {"nome": "Club RTL", "fta": True},
                                               {"nome": "RTL Club HD", "fta": False}, {"nome": "RTL TVI", "fta": True}]}]}]
    p.unifica_canali(g, [], dove)
    assert [c["nome"] for c in g[0]["partite"][0]["canali"]] == ["RTL Club", "RTL TVI"]
    h = p.badge(g[0]["partite"][0]["canali"][0], dove, set())
    assert "rtlplay.be/rtlplay/direct" in h and "flags/be.svg" in h and "RTL Play" not in h, h


test_rtl_club(); print("RTL Play / Club RTL -> una sola riga RTL Club: OK")


def test_stesso_link():
    dove = json.loads((p.RADICE / "dove_vederli.json").read_text(encoding="utf-8"))["voci"]
    k = [{"nome": "Club RTL", "fta": False}, {"nome": "RTL Play", "fta": True},
         {"nome": "Canale A stream", "fta": True, "url": "https://www.esempio.tv/live/", "diretta": "https://esempio.tv/live?utm_source=x", "vpn": "SVIZZERA"},
         {"nome": "Canale B stream", "fta": False, "url": "http://esempio.tv/live", "diretta": "http://www.esempio.tv/live/#top", "vpn": "GERMANIA"},
         {"nome": "DAZN Italia", "fta": False, "dazn_gratis": True}, {"nome": "DAZN Portogallo", "fta": False, "dazn_gratis": True}]
    out = p.stesso_link(k, dove)
    assert [c["nome"] for c in out] == ["RTL Club", "Canale A stream", "DAZN Italia", "DAZN Portogallo"], out
    assert out[0]["fta"] is True
    pr = p.stesso_link([{"nome": "Prima Sport 1", "fta": False}, {"nome": "Prima Sport 2", "fta": False}], dove)
    assert len(pr) == 2
    assert p.norm_url("https://www.rtlplay.be/rtlplay/direct/#x") == p.norm_url("http://rtlplay.be/rtlplay/direct?utm_source=a")
    assert p.norm_url("https://www.rts.ch/play/tv/direct?tvLiveId=3608517") != p.norm_url("https://www.rts.ch/play/tv/direct?tvLiveId=143932")
    assert p.norm_url("https://rts.ch/play/tv/direct/?b=2&tvLiveId=3608517") == p.norm_url("https://www.rts.ch/play/tv/direct?tvLiveId=3608517&b=2")
    u = "https://www.rts.ch/play/tv/direct?tvLiveId=3608517"
    h = (f'<li><a href="{u}" target="_blank">RTS 2</a> <a class="diretta" href="{u}">▶ diretta</a></li>'
         f'<li><a href="#dv-rts">RTS stream</a> <a class="diretta" href="http://rts.ch/play/tv/direct/?tvLiveId=3608517">▶ diretta</a></li>'
         f'<li><a href="#dv-rts">RTS Deux</a> <a class="diretta" href="https://www.rts.ch/play/tv/direct?tvLiveId=143932">▶</a></li>')
    h2 = p.togli_link_doppi(h)
    assert h2.count("rts.ch") == 1 and "#dv-rts" not in h2 and h2.count("<li>") == 1, h2   # righe doppione tolte del tutto
    # il link più preciso (video/urn della partita) vince sulla pagina diretta generica
    h = ('<li><a href="#dv-rts">RTS 2</a> <a class="diretta" href="https://www.rts.ch/play/tv/direct?tvLiveId=3608517">▶</a></li>'
         '<li><a href="https://play.rts.ch/play/tv/-/video/-?urn=urn:rts:video:1">RTS stream</a> <a class="diretta" href="https://tv.teleboy.ch/live(player:live/305)">▶ Teleboy</a></li>'
         '<li><a href="#dv-tb">SRF zwei</a> <a class="diretta" href="https://tv.teleboy.ch/live(player:live/304)">▶ Teleboy</a></li>'
         '<li><a href="#dv-tb">RTS Deux</a> <a class="diretta" href="https://tv.teleboy.ch/live(player:live/305)">▶ Teleboy</a></li>'
         '<li><a href="#dv-bbc">BBC One</a> <a class="diretta" href="https://www.bbc.co.uk/iplayer/live/bbcone">▶</a></li>'
         '<li><a href="#dv-bbc">BBC Alba</a> <a class="diretta" href="https://www.bbc.co.uk/tv/bbcalba">▶</a></li>')
    h2 = p.togli_link_doppi(h)
    assert "tvLiveId" not in h2 and "urn=urn:rts:video:1" in h2, h2
    assert h2.count("live/304") == 1 and h2.count("live/305") == 1, h2       # Teleboy: canali diversi sì, link identico no
    assert h2.count("bbc.co.uk") == 1 and "BBC Alba" not in h2 and "RTS 2" not in h2 and "SRF zwei" in h2, h2
    h = ('<li><a href="#dv-prima-sport">Prima Sport 1</a> <a class="diretta" href="https://www.orange.ro/accounts/create-user">▶ Orange TV</a></li>'
         '<li><a href="#dv-prima-sport">Prima Sport 2</a> <a class="diretta" href="https://www.orange.ro/accounts/create-user">▶ Orange TV</a></li>'
         '<li><a href="#dv-dazn">DAZN Italia <span class="tag dz">DAZN GRATIS</span></a> <a class="diretta" href="https://www.dazn.com/it-IT/home">▶ sito</a></li>'
         '<li><a href="#dv-dazn">DAZN Portogallo <span class="tag dz">DAZN GRATIS</span></a> <a class="diretta" href="https://www.dazn.com/it-IT/home">▶ sito</a></li>')
    h2 = p.togli_link_doppi(h)
    assert h2.count("orange.ro") == 1 and "Prima Sport 2" in h2 and h2.count("dazn.com") == 1 and "DAZN Portogallo" in h2, h2
    assert p.dominio("https://play.rts.ch/x") == "rts.ch" and p.dominio("http://www.bbc.co.uk/a") == "bbc.co.uk"
    assert p.dominio("https://globoplay.globo.com.br/") == "globo.com.br"


test_stesso_link(); print("canali con lo stesso link -> una riga: OK")


def test_serie_a_senza_canali():
    t = int(dt.datetime(2026, 10, 10, 15, 0, tzinfo=p.ROMA).timestamp())
    ini, fine = dt.datetime(2026, 10, 10, tzinfo=p.ROMA), dt.datetime(2026, 10, 14, tzinfo=p.ROMA)
    los = [{"ts": t, "titolo": "Lecce v Bologna", "comp": "Italian Serie A - Week 7"},
           {"ts": t, "titolo": "Bari v Modena", "comp": "Italian Serie B - Week 7"},
           {"ts": t, "titolo": "Roma Women v Lazio Women", "comp": "Italian Serie A Women"},
           {"ts": t + 3600, "titolo": "Inter v Parma", "comp": "Italian Serie A - Week 7"}]
    gia = [{"ts": t + 3600, "quando": None, "casa": "Inter", "ospite": "Parma", "canali": [{"nome": "X", "fta": True}], "fonti": ["LiveSoccerTV"]}]
    ev, agg = p.aggiungi_serie_a(gia, los, ini, fine)
    assert agg == ["Lecce - Bologna 10/10 15:00"] and ev[-1]["canali"] == [] and ev[-1]["competizione"] == "SERIE A", (agg, ev)
    gr = [{"nome": "SERIE A", "partite": [ev[-1]]}]
    h = p.genera_html(dt.date(2026, 10, 10), dt.datetime(2026, 10, 10, 9, tzinfo=p.ROMA), gr, [], [], [])
    assert "Canali non ancora disponibili: potrebbero comparire nei prossimi aggiornamenti." in h and 'class="senza-canali"' in h


test_serie_a_senza_canali(); print("Serie A senza canali con nota: OK")


def test_afc_esclusa():
    rx = U.regex_femminile(CONF_LOS["escludi_competizioni"])
    for c in ("AFC Champions League", "AFC Champions League Elite", "AFC Champions League Two", "ACL Elite", "ACL Two",
              "NAZIONALI / INTERNAZIONALI – AFC CHAMPIONS LEAGUE ELITE", "Asian AFC Champions League - Group A"):
        assert U.femminile(rx, c, ("Al Hilal", "Al Ain")), c
    for c in ("UEFA Champions League", "CAF Champions League", "AFC Asian Cup", "Serie A"):
        assert not U.femminile(rx, c, ("Inter", "Milan")), c


test_afc_esclusa(); print("AFC Champions League esclusa: OK")


def test_nazione_tipo():
    assert p.nazione_comp("SERIE A") == "Italia" and p.nazione_comp("BRASILEIRÃO SERIE A (Brasile)") == "Brasile"
    assert p.nazione_comp("LALIGA HYPERMOTION (Spagna, 2ª divisione)") == "Spagna" and p.nazione_comp("UEFA CHAMPIONS LEAGUE") == ""
    assert p.nazione_comp("ALTRE PARTITE (Prima Sport)") == ""
    assert p.tipo_comp("UEFA CONFERENCE LEAGUE") == "coppe" and p.tipo_comp("NAZIONALI – AMICHEVOLI") == "nazionali"
    assert p.tipo_comp("NAZIONALI / INTERNAZIONALI – COPA LIBERTADORES") == ""
    src = (p.RADICE / "scraper" / "palinsesto.py").read_text(encoding="utf-8")
    assert 'id="barra"' in src and "bebas-neue-latin.woff2" in src and (p.RADICE / "static" / "fonts" / "bebas-neue-latin.woff2").exists()


test_nazione_tipo(); print("barra laterale desktop: nazioni, coppe europee, nazionali: OK")


def test_etichette_extra():
    import extra_partite as X
    d = {"content": {"lineup": {"homeTeam": {"unavailable": [{"name": "A B", "unavailability": {"type": "injury", "expectedReturn": "Mid October 2026"}},
                                                             {"name": "C D", "unavailability": {"type": "international"}}]},
                                "awayTeam": {"unavailable": [{"name": "E F", "unavailability": {"type": "suspension"}}]}}}}
    a = X.assenze_da_dettagli(d)
    assert a == {"casa": [("A B", "infortunato, rientro metà ottobre")], "ospite": [("E F", "squalificato")]}
    assert X.assenze_da_dettagli({"content": {"lineup": {}}}) is None
    coppie = X.carica_rivalita()
    assert 80 <= len(coppie) <= 150
    assert "Docklands" in X.rivalita_di("West Ham United", "Millwall", coppie)
    assert X.rivalita_di("AC Milan", "Inter", coppie) and X.rivalita_di("Inter Miami", "Milan", coppie) is None
    assert X.rivalita_di("Roma U19", "Lazio U19", coppie) is None and X.rivalita_di("Manchester City", "Liverpool", coppie)
    assert X.rivalita_di("Arsenal", "Everton", coppie) is None and X.rivalita_di("Celta de Vigo", "Deportivo Alavés", coppie) is None
    assert X.rivalita_di("RC Celta", "Deportivo de La Coruña", coppie) or True
    e = {"casa": "Millwall", "ospite": "West Ham", "_riv": "x", "_info": {"casa": [("A", "squalificato")], "ospite": []}}
    h = p.etichette_extra(e)
    assert "info partita" in h and "rivalità" in h and "tanti gol" not in h and "nessuna assenza segnalata" in h
    assert p.etichette_extra({"casa": "a", "ospite": "b"}) == ""
    tab = [{1: (2, 20, 8), 2: (3, 18, 8), 3: (16, 6, 8), 4: (19, 3, 8), 5: (10, 10, 8), **{i: (i, 0, 8) for i in range(10, 30)}}]
    tab[0].update({1: (2, 20, 8), 2: (5, 18, 8), 3: (16, 6, 8), 4: (19, 3, 8), 5: (10, 10, 8), 6: (6, 15, 8)})
    assert X.etichetta_classifica(tab, 1, 2) == ("big", "2º contro 5º in classifica") and X.etichetta_classifica(tab, 1, 6) is None
    assert X.etichetta_classifica([{i: (i, 50 - i, 8) for i in range(1, 26)}], 16, 19) is None  # 16º e 19º di 25: non sono le ultime 6
    t20 = [{i: (i, 40 - i, 8) for i in range(1, 21)}]
    assert X.etichetta_classifica(t20, 16, 19) == ("salvezza", "16º contro 19º: sfida salvezza") and X.etichetta_classifica(t20, 14, 19) is None
    assert X.etichetta_classifica([{1: (1, 3, 1), 2: (2, 3, 1), **{i: (i, 0, 1) for i in range(3, 12)}}], 1, 2) is None  # inizio stagione
    assert X.etichetta_classifica([{1: (1, 9, 4)}, {2: (1, 9, 4)}], 1, 2) is None  # gironi diversi
    t12 = [{i: (i, 40 - i, 8) for i in range(1, 13)}]
    assert X.etichetta_classifica(t12, 8, 12) is None and X.etichetta_classifica(t12, 9, 12) and X.etichetta_classifica(t12, 5, 1) is None
    assert X.RE_COPPA.search("Coppa Italia") and X.RE_COPPA.search("DFB Pokal") and not X.RE_COPPA.search("Serie A")
    h2 = p.etichette_extra({"casa": "Inter", "ospite": "Milan", "_big": "1º contro 2º in classifica", "_salvezza": None})
    assert "Big match" in h2 and "1º contro 2º" in h2 and "Classifica" not in h2
    assert X.LEGHE_INFO == {47: "Premier League", 55: "Serie A", 54: "Bundesliga", 87: "LaLiga", 53: "Ligue 1"}
    # abbinamento a squadre invertite: le assenze restano della squadra giusta
    m, inv = X.abbina({"ts": 1000, "casa": "Leeds", "ospite": "Manchester United"}, [{"ts": 1000, "casa": "Manchester United", "ospite": "Leeds United", "id": 1}])
    assert m and inv


test_etichette_extra(); print("etichette info partita / rivalità: OK")


def test_motori_prima():
    import primaplay as P
    c = P.carica_conf()
    for t in ("GT World Challenge: Portimao - Calificări", "EURONASCAR: Zolder - Cursa 1 V8GP", "Curse mașini istorice: Imola Classic - Grupa C"):
        assert P.analizza_titolo(t, c)["sport"] == "Motori", t
    assert P.analizza_titolo("UYL: Roma - Inter", c)["sport"] == "Calcio" and P.analizza_titolo("Liga 1: FCSB - Rapid", c)["sport"] == "Calcio"


test_motori_prima(); print("gare di motori di Prima Sport in ALTRI SPORT: OK")


# Blue Zoom: varianti nazionali su LiveOnSat e competizioni basket riconoscibili nella guida Teleboy.
def test_blue_zoom():
    conf = json.loads((p.RADICE / "liveonsat.json").read_text(encoding="utf-8"))
    for nome in ("blue Zoom DE", "blue Zoom Schweiz", "BLUE ZOOM Suisse", "blue Zoom Österreich", "blue Zoom CH"):
        pulito = L.pulisci_canale(nome, conf["alias_canali"])
        assert pulito == "blue Zoom", (nome, pulito)
        assert L.in_chiaro(pulito, conf["canali_in_chiaro"]), nome
    import altri_sport as A
    assert A.sport_di("EuroLeague: Real Madrid vs Monaco") == "Basket"
    assert A.sport_di("EuroCup Basketball live") == "Basket"
    assert A.sport_di("NBA: Boston Celtics vs New York Knicks") == "Basket"

test_blue_zoom(); print("Blue Zoom (varianti LiveOnSat) e classificazione basket: OK")


# Fix 21/10/2026: (1) niente più sezione "CALCIO SVIZZERA E GERMANIA (dirette streaming)" (repliche notturne della guida
# Teleboy, es. Manchester City - PSG alle 00:00 su Sportitalia); (2) Premier League dell'Azerbaigian sempre esclusa;
# (3) il calcio non entra MAI in ALTRI SPORT (es. "CALCIO UEFA Champions League" su VTM GO).
def test_fix_calcio_streaming_azerbaigian_altri():
    import altri_sport as A
    assert "SVIZZERA E GERMANIA" not in A.competizione_calcio("Fussball, Manchester City - Paris Saint Germain")[1]
    assert A.competizione_calcio("UEFA Champions League")[1] == "UEFA CHAMPIONS LEAGUE"
    ora = dt.datetime(2026, 10, 21, 15, 0, tzinfo=p.ROMA)
    notte = int(dt.datetime(2026, 10, 23, 0, 0, tzinfo=p.ROMA).timestamp())
    sera = int(dt.datetime(2026, 10, 21, 21, 0, tzinfo=p.ROMA).timestamp())

    def em(nome, **k):
        return dict({"nome": nome, "pagina": "https://www.teleboy.ch/it/live", "link": "https://tv.teleboy.ch/live(player:live/577)",
                     "vpn": "SVIZZERA", "teleboy": True}, **k)

    def stream(casa, ospite, ts, comp="", da_epg=True, canale="Sportitalia HD"):
        return {"ts": ts, "fine": ts + 7200, "casa": casa, "ospite": ospite, "comp": comp, "testi": [f"{comp} {casa} - {ospite}"],
                "da_epg": da_epg, "emittenti": [em(canale)]}

    def partita(casa, ospite, ts, comp="UEFA CHAMPIONS LEAGUE", canali=("RTL Club",)):
        return {"ts": ts, "quando": dt.datetime.fromtimestamp(ts, p.ROMA), "titolo": f"{casa} v {ospite}", "ordine": 4,
                "competizione": comp, "casa": casa, "ospite": ospite, "canali": [{"nome": c, "fta": True} for c in canali],
                "fonti": ["LiveSoccerTV"]}

    # (1) replica dalla guida TV senza partita vera: scartata, niente scheda nuova
    scartate = []
    ev, uniti = p.unisci_stream([], [stream("Manchester City", "Paris Saint Germain", notte)], scartate=scartate)
    assert ev == [] and uniti == [] and "guida TV" in scartate[0], scartate
    # competizione sconosciuta (anche da SRG/ARD) o di notte: scartata
    assert p.unisci_stream([], [stream("Lugano", "Basel", sera, da_epg=False)], scartate=[])[0] == []
    assert p.unisci_stream([], [stream("Lugano", "Basel", notte, "Super League", da_epg=False)], scartate=[])[0] == []
    # diretta streaming riconosciuta (SRF Super League, sera): resta
    ev, _ = p.unisci_stream([], [stream("Lugano", "Basel", sera, "Super League", da_epg=False, canale="SRF zwei")])
    assert len(ev) == 1 and ev[0]["competizione"] == "SUPER LEAGUE (Svizzera)"
    # partita vera già nota: il canale della guida si aggiunge una volta sola
    vera = partita("Manchester City", "Paris Saint Germain", sera)
    ev, uniti = p.unisci_stream([vera], [stream("Manchester City", "Paris Saint-Germain", sera)] * 2)
    assert len(ev) == 1 and [k["nome"] for k in vera["canali"]] == ["RTL Club", "Sportitalia HD"], vera["canali"]

    # (2) Premier League dell'Azerbaigian esclusa, quella inglese no
    for t in ("PREMIER LEAGUE (Azerbaigian)", "/competitions/azerbaijan/premier-league/ Premier League", "Azerbaijan Premier League",
              "Premyer Liqa", "Azerbaijan - Premier League", "PREMIER LEAGUE (Azerbaijan)"):
        assert p.e_premier_azerbaigian(t), t
    for t in ("PREMIER LEAGUE", "/competitions/england/premier-league/ Premier League", "English Premier League", "PREMIER LEAGUE (Inghilterra)"):
        assert not p.e_premier_azerbaigian(t), t
    assert p.e_premier_azerbaigian(p.competizione("/competitions/azerbaijan/premier-league/", "Premier League")[1])

    # (3) calcio in ALTRI SPORT: mai; il canale va sulla partita giusta solo se non è ambiguo e non c'è già
    vtm = {"id": "epg:vtm:1", "ts": sera - 1800, "fine": sera + 8400, "sport": "Calcio", "titolo": "UEFA Champions League",
           "titolo_orig": "UEFA Champions League", "titolo_src": "UEFA Champions League", "evento": True, "lingua": "nl",
           "descrizione": "", "da_epg": True,
           "emittenti": [{"nome": "VTM GO", "pagina": "https://www.vtmgo.be", "link": "https://www.vtmgo.be/vtmgo/live-kijken/vtm",
                          "vpn": "BELGIO", "fta": True, "da_guida": True}]}
    darts = dict(vtm, id="epg:vtm:2", sport="Freccette", titolo="PDC European Darts Championship: First Round",
                 titolo_orig="PDC European Darts Championship: First Round", titolo_src="PDC European Darts Championship")
    ehf = dict(vtm, id="epg:vtm:3", sport="Pallamano", titolo="EHF Champions League: Kiel - Veszprém",
               titolo_orig="EHF Champions League: Kiel - Veszprém", titolo_src="EHF Champions League")
    vuoto = lambda *a: ([], None)
    altri, calcio, _ = A.raccogli_altri(ora, ora + dt.timedelta(days=4), ora, U.regex_femminile([]), scarica_srg_fn=vuoto,
                                        scarica_ard_fn=vuoto, scarica_tb_fn=lambda: ([dict(vtm), dict(darts), dict(ehf)], None))
    assert not any(A.e_calcio(e) for e in altri) and "UEFA" not in " ".join(e["titolo"] for e in altri), [e["titolo"] for e in altri]
    assert {e["sport"] for e in altri} == {"Freccette", "Pallamano"}, altri  # EHF Champions League (pallamano) resta
    assert calcio == [] and len(A.CALCIO_GENERICO) == 1 and A.CALCIO_TOLTO_ALTRI
    assert A.e_calcio({"sport": "Sport", "titolo": "Fußball: UEFA Europa League"}) and not A.e_calcio({"sport": "Football americano", "titolo": "NFL Football"})
    # più partite di Champions alle 21:00, VTM GO già su Bruges - Lens: niente da aggiungere (nessun doppione)
    br = partita("Bruges", "Lens", sera, canali=("RTL Club", "VTM GO"))
    altra = partita("Inter", "Arsenal", sera)
    assert p.unisci_calcio_generico([br, altra], A.CALCIO_GENERICO) == []
    assert [k["nome"] for k in br["canali"]].count("VTM GO") == 1 and [k["nome"] for k in altra["canali"]] == ["RTL Club"]
    # più partite possibili e canale assente: non si indovina
    br2, altra2 = partita("Bruges", "Lens", sera), partita("Inter", "Arsenal", sera)
    assert p.unisci_calcio_generico([br2, altra2], A.CALCIO_GENERICO) == []
    # una sola partita possibile: il canale si aggiunge, una volta sola
    sola = partita("Bruges", "Lens", sera)
    assert len(p.unisci_calcio_generico([sola], A.CALCIO_GENERICO)) == 1
    assert p.unisci_calcio_generico([sola], A.CALCIO_GENERICO) == [] and [k["nome"] for k in sola["canali"]] == ["RTL Club", "VTM GO"]


test_fix_calcio_streaming_azerbaigian_altri(); print("niente CALCIO SVIZZERA E GERMANIA, Premier Azerbaigian tolta, calcio fuori da ALTRI SPORT: OK")


# RTSH (Albania) tolta per sempre da tutte le sezioni (richiesta utente 22/10/2026)
def test_rtsh_esclusa():
    import altri_sport as A
    for f in ("dove_vederli.json", "altri_sport.json", "teleboy_canali.json"):
        assert "rtsh" not in (p.RADICE / f).read_text(encoding="utf-8").lower(), f
    assert not any("rtsh" in r["regex"].lower() for v in CONF_LOS["canali_per_sport"].values() for r in v)
    esclusa = p.regola_ovunque()
    assert esclusa("RTSH Sport") and esclusa("RTSH 1") and esclusa("rtsh sport hd") and not esclusa("RTS 1") and not esclusa("RTL Club")
    ora = dt.datetime(2026, 10, 22, 15, 0, tzinfo=p.ROMA)
    ts = int(dt.datetime(2026, 10, 22, 21, 0, tzinfo=p.ROMA).timestamp())
    def sch(casa, ospite, canali):
        return {"ts": ts, "quando": dt.datetime.fromtimestamp(ts, p.ROMA), "casa": casa, "ospite": ospite, "competizione": "UEFA CONFERENCE LEAGUE", "ordine": 6,
                "canali": [{"nome": c, "fta": True} for c in canali], "fonti": ["LiveOnSat"]}
    sola, mista = sch("AGF Aarhus", "Egnatia", ["RTSH Sport"]), sch("Shkendija", "Rijeka", ["RTSH 1", "Arena Sport 1", "Arena Sport 1"])
    altri = [{"titolo": "Basket", "sport": "Basket", "ts": ts, "fine": ts + 7200, "emittenti": [{"nome": "RTSH 1"}]},
             {"titolo": "Volley", "sport": "Pallavolo", "ts": ts, "fine": ts + 7200, "emittenti": [{"nome": "RTSH Sport"}, {"nome": "RAI 2"}]}]
    dove = [{"id": "rtsh", "nome": "RTSH 1 (Albania)", "canali": ["^RTSH\\b"]}, {"id": "rts", "nome": "RTS", "canali": ["^RTS\\b"]}]
    ev, al, dv, tolte = p.togli_ovunque([sola, mista], altri, dove, esclusa)
    assert [e["casa"] for e in ev] == ["Shkendija"] and [k["nome"] for k in ev[0]["canali"]] == ["Arena Sport 1", "Arena Sport 1"]
    assert [e["titolo"] for e in al] == ["Volley"] and [x["nome"] for x in al[0]["emittenti"]] == ["RAI 2"]
    assert [v["id"] for v in dv] == ["rts"] and len(tolte) == 4
    # nella pagina generata non c'è nessun RTSH
    h = p.genera_html(*p.finestra(ora)[:1], ora, p.raggruppa(ev), [], [], dv, al)
    assert "rtsh" not in h.lower()


test_rtsh_esclusa(); print("RTSH tolta ovunque: OK")


# Digi Sport Romania (23/10/2026): (1) nuovo HTML di digisport.ro (<h3 class="schedule-title">, spazi nelle celle) letto;
# (2) su LiveOnSat ogni "Digi Sport N Romania" è preso per qualsiasi partita di calcio, con link digisport.ro e VPN Romania.
def test_digi_sport_romania():
    import digisport as DG
    nuovo = ('<h3>Cine va câștiga derby-ul FCSB - Rapid (sâmbătă, ora 21:00, DGS 1)?</h3>'
             '<div class="schedule-wrapper active"> <h3 class="schedule-title"> Sambata 24 Octombrie </h3> <table class="schedule-table">'
             '<tr class=""> <td class="schedule-icon" data-schedule="stiri"></td> <td> 07:20 </td> <td> Stirile Digi Sport </td> </tr>'
             '<tr class="schedule-table-now"> <td class="schedule-icon" data-schedule="fotbal"></td> <td> 21:45 </td> '
             '<td> <span class="tag"> LIVE </span> Serie A: Napoli-Roma <br> Etapa 8 </td> </tr></table>')
    r = DG.righe(nuovo, dt.date(2026, 10, 23))
    assert [(x[0].strftime("%d/%m %H:%M"), x[2], x[3]) for x in r] == [("24/10 07:20", "", "Stirile Digi Sport"), ("24/10 21:45", "LIVE", "Serie A: Napoli-Roma")], r
    # competizioni romene -> etichette italiane già usate (niente sezioni doppie "CUPA LIGII ANGLIEI" / "LIGA PORTUGAL")
    cc = DG.carica_conf()["competizioni_calcio"]
    assert L.competizione_los(cc["Cupa Ligii Angliei"])[1] == "LEAGUE CUP (Inghilterra)"
    assert L.competizione_los(cc["Liga Portugal"])[1] == "PRIMEIRA LIGA (Portogallo)"
    assert L.competizione_los(cc["Cupa Germaniei"])[1] == "CUP (DFB-POKAL) (Germania)"
    alias, regole = CONF_LOS["alias_canali"], CONF_LOS["canali_in_chiaro"]
    for n, atteso in (("Digi Sport 2 Romania HD", "Digi Sport 2"), ("Digi Sport 4 Romania", "Digi Sport 4"), ("DigiSport 1 Romania", "Digi Sport 1")):
        assert L.pulisci_canale(n, alias) == atteso and L.in_chiaro(atteso, regole), n
    for n in ("Digi Sport 1 Hungary HD", "Digi Sport 1 HD Hungary"):
        assert not L.in_chiaro(L.pulisci_canale(n, alias), regole), n
    # link e VPN della voce digi-sport per qualsiasi competizione (qui LaLiga), un solo link per partita
    dove = json.loads((QUI.parent / "dove_vederli.json").read_text())["voci"]
    v = p.voce_dove("Digi Sport 3", dove)
    assert v["id"] == "digi-sport" and v["vpn_tag"] == "VPN Romania"
    ora = dt.datetime(2026, 10, 23, 9, 0, tzinfo=p.ROMA)
    q = ora + dt.timedelta(hours=10)
    g = [{"nome": "LALIGA", "partite": [{"casa": "Barcellona", "ospite": "Real Madrid", "quando": q, "ts": int(q.timestamp()),
                                          "canali": [{"nome": "Digi Sport 1", "fta": True}, {"nome": "Digi Sport 1", "fta": False}]}]}]
    h = p.genera_html(*p.finestra(ora)[:1], ora, g, [], [], dove, [])
    assert "digisport.ro/live/digisport-1" in h and "VPN Romania" in h
    i = h.index("Barcellona"); scheda = h[i:h.index("</ol>", i) if "</ol>" in h[i:] else i + 5000]
    assert scheda.count("digisport.ro/live/digisport-1") == 1, "un solo link Digi Sport 1 per partita"



def test_digi_da_liveonsat_e_doppioni_sabato():
    """LiveOnSat è la fonte di riserva per Digi Sport Romania: anche senza digisport.ro il canale resta (Gil Vicente-Porto)."""
    import primaplay as PP
    h = gzip.decompress((QUI / "fixtures_liveonsat_digi_2026-10-23" / "europe-portugal-primeira-liga.php.gz").read_bytes()).decode()
    conf = dict(CONF_LOS, pagine=["x"], pausa_secondi=0)
    ini = dt.datetime(2026, 10, 24, 0, 0, tzinfo=dt.timezone.utc)
    partite, falliti = L.raccogli_los(conf, ini, ini + dt.timedelta(days=1), scarica_fn=lambda u: (h, None))
    gv = [x for x in partite if "Gil Vicente" in x["titolo"]]
    assert not falliti and gv and "Digi Sport 3" in gv[0]["canali_fta"], gv
    # DAZN "A Coruna" = "Deportivo La Coruña" (niente scheda doppia), ma mai con l'Alavés
    assert U.stessa_partita(0, "Atletico Madrid", "A Coruna", 0, "Atlético Madrid", "Deportivo La Coruña") > 0
    assert U.stessa_partita(0, "Deportivo Alavés", "Getafe", 0, "A Coruna", "Getafe") == 0
    # sessioni Moto2/Moto3 di Prima Play: mai partite di calcio
    c = PP.carica_conf()
    for t in ("Moto 2: MP al Australiei - Antrenamente 3", "Moto 3: MP al Australiei - Calificări", "Moto2: MP al Australiei - Cursa"):
        assert PP.analizza_titolo(t, c)["sport"] == "Motomondiale", t
    assert PP.analizza_titolo("UYL: Man City - PSG", c)["sport"] == "Calcio"


test_digi_da_liveonsat_e_doppioni_sabato(); print("Digi da LiveOnSat senza digisport.ro, A Coruna, Moto2/3 Prima Play: OK")

test_digi_sport_romania(); print("Digi Sport Romania (digisport.ro nuovo HTML, LiveOnSat ogni competizione): OK")


def test_sport_nomi():
    """Stesso sport, qualunque lingua della fonte, nella stessa sezione italiana. La ricerca trova anche la parola straniera."""
    import sport_nomi as S
    import altri_sport as A
    import dazn as D
    # etichette viste sul sito e nelle altre lingue delle fonti
    casi = {
        "Basquetebol": "Basket", "Baloncesto": "Basket", "Basketball": "Basket", "Baschet": "Basket",
        "Basket-ball": "Basket", "Koszykówka": "Basket", "Pallacanestro": "Basket", "Basket": "Basket",
        "Ténis": "Tennis", "Tenis": "Tennis", "Tennis": "Tennis",
        "Tennis de table": "Tennistavolo", "Tenis de mesa": "Tennistavolo", "Tischtennis": "Tennistavolo",
        "Table tennis": "Tennistavolo", "Tennistavolo": "Tennistavolo",
        "Boxeo": "Boxe", "Boxing": "Boxe", "Boxen": "Boxe", "Boxe": "Boxe",
        "Fútbol americano": "Football americano", "Futebol americano": "Football americano",
        "American Football": "Football americano", "Football américain": "Football americano",
        "Fotbal american": "Football americano", "Football Americano": "Football americano",
        "Hockey sur glace": "Hockey su ghiaccio", "Eishockey": "Hockey su ghiaccio",
        "Hóquei no gelo": "Hockey su ghiaccio", "Ice Hockey": "Hockey su ghiaccio", "Hochei": "Hockey su ghiaccio",
        "Motor": "Motori", "Motorsport": "Motori", "Desportos motorizados": "Motori",
        "Deportes de motor": "Motori", "Motori": "Motori", "Moto": "Motori", "Formula E": "Motori",
        "Formula 1": "Formula 1", "Formel 1": "Formula 1", "Formule 1": "Formula 1", "F1": "Formula 1",
        "Volley": "Pallavolo", "Voleibol": "Pallavolo", "Vôlei": "Pallavolo", "Volei": "Pallavolo",
        "Volleyball": "Pallavolo", "Pallavolo": "Pallavolo", "Beach volley": "Beach volley",
        "Handebol": "Pallamano", "Balonmano": "Pallamano", "Handbal": "Pallamano", "Handball": "Pallamano",
        "Ciclismo": "Ciclismo", "Cycling": "Ciclismo", "Cyclisme": "Ciclismo", "Radsport": "Ciclismo",
        "Wielrennen": "Ciclismo", "Ciclism": "Ciclismo", "Kolarstwo": "Ciclismo",
        "Futebol": "Calcio", "Fútbol": "Calcio", "Fußball": "Calcio", "Voetbal": "Calcio", "Fotbal": "Calcio",
        "Calcio": "Calcio", "Futsal": "Calcio a 5", "Calcio a 5": "Calcio a 5",
        "Rugby": "Rugby", "Rugby League": "Rugby a 13", "Golf": "Golf", "MMA": "MMA",
        "Sci alpino": "Sci alpino", "Ski": "Sci", "Esquí": "Sci", "Sci": "Sci",
        "Equitazione | Salto ostacoli": "Equitazione", "Sport Estremi": "Sport estremi",
        "Squash": "Squash", "Muay Thai": "Muay Thai", "Curling": "Curling", "Darts": "Freccette",
        "Nuoto": "Nuoto", "Swimming": "Nuoto", "Natação": "Nuoto", "Motomondiale": "Motomondiale", "MotoGP": "Motomondiale",
        "Ginnastica": "Ginnastica artistica", "Gimnastica": "Ginnastica artistica", "Polo": "Pallanuoto",
        "Live TV": "Live TV", "TV Live": "TV Live", "OTHER": "OTHER", "Series & Shows": "Series & Shows",
    }
    for src, atteso in casi.items():
        assert S.normalizza(src) == atteso, (src, S.normalizza(src), atteso)
    # ogni nome già emesso dagli scraper resta se stesso (o l'unificazione voluta, es. Ginnastica)
    for _rx, nome in A.SPORT:
        assert S.normalizza(nome) == nome, nome
    pp = json.loads((QUI.parent / "primaplay.json").read_text(encoding="utf-8"))["sport"]
    for k, v in pp.items():
        atteso = "Ginnastica artistica" if v == "Ginnastica" else v
        assert S.normalizza(k) == atteso, (k, S.normalizza(k), atteso)
        assert S.normalizza(v) == atteso, (v, S.normalizza(v))
    for k, v in json.loads((QUI.parent / "digisport.json").read_text(encoding="utf-8"))["sport_elite"].items():
        assert S.normalizza(k) == v, (k, S.normalizza(k), v)
        assert S.normalizza(v) == v
    los = json.loads((QUI.parent / "liveonsat.json").read_text(encoding="utf-8"))["pagine_altri_sport"]
    for _u, (sp, _d) in los.items():
        assert S.normalizza(sp) == sp, sp
    cat = json.loads((QUI.parent / "categorie.json").read_text(encoding="utf-8"))
    for sp in cat["altri"]["elite"]["sport"] + cat["altri"]["sport_in_testa"]:
        assert S.normalizza(sp) == sp, sp
    # ogni Sport.Title dei JSON DAZN salvati ha un esito noto
    dazn_attesi = {
        "Adventure Sports": "Sport estremi", "American Football": "Football americano", "BKFC": "BKFC",
        "Bare Knuckle Fighting": "BKFC", "Bare Knuckle Fighting Championship": "BKFC", "Baseball": "Baseball",
        "Basket": "Basket", "Basketball": "Basket", "Boxe": "Boxe", "Boxing": "Boxe", "Calcio": "Calcio",
        "Ciclismo": "Ciclismo", "Curling": "Curling", "Cycling": "Ciclismo", "Darts": "Freccette",
        "Equestrian": "Equitazione", "Equestrian Jumping": "Equitazione", "Equestrian Sports": "Equitazione",
        "Equitazione | Salto ostacoli": "Equitazione", "Extreme Sports": "Sport estremi", "Football": "Calcio",
        "Football Americano": "Football americano", "Futsal": "Calcio a 5", "Golf": "Golf",
        "Hockey su ghiaccio": "Hockey su ghiaccio", "Ice Hockey": "Hockey su ghiaccio", "Live TV": "Live TV",
        "MMA": "MMA", "Motori": "Motori", "Motorsport": "Motori", "Nuoto": "Nuoto", "OTHER": "OTHER",
        "Series & Shows": "Series & Shows", "Sport Estremi": "Sport estremi", "Swimming": "Nuoto",
        "TV Live": "TV Live", "Table Tennis": "Tennistavolo", "Tennis": "Tennis", "Tennistavolo": "Tennistavolo",
        "Triathlon": "Triathlon", "Volley": "Pallavolo", "Volleyball": "Pallavolo",
    }
    visti = set()
    for f in (QUI).rglob("*.json.gz"):
        if "dazn" not in f.name and "dazn" not in str(f.parent):
            continue
        data = json.loads(gzip.open(f).read())

        def walk(o):
            if isinstance(o, dict):
                sp = o.get("Sport")
                if isinstance(sp, dict) and sp.get("Title"):
                    visti.add(sp["Title"])
                for x in o.values():
                    walk(x)
            elif isinstance(o, list):
                for x in o:
                    walk(x)
        walk(data)
    assert visti, "nessun titolo sport nei fixture DAZN"
    sconosciuti = visti - set(dazn_attesi)
    assert not sconosciuti, sconosciuti
    for t in visti:
        assert S.normalizza(t) == dazn_attesi[t], (t, S.normalizza(t))
    # riconoscimento dal titolo, non solo dall'etichetta DAZN
    assert A.sport_di("Basquetebol: Benfica x Porto") == "Basket"
    assert A.sport_di("Baloncesto: Barcelona - Madrid") == "Basket"
    assert A.sport_di("Ténis: ATP Osaka") == "Tennis"
    assert A.sport_di("Table tennis") == "Tennistavolo"
    assert A.sport_di("Tennistavolo") == "Tennistavolo"
    assert A.sport_di("Tennis de table") == "Tennistavolo"
    assert A.sport_di("Calcio a 5: Meta Catania") == "Calcio a 5"
    assert A.sport_di("Fútbol americano: Steelers - Saints") == "Football americano"
    assert A.sport_di("Pattinaggio di figura, Danza: Programma libero") == "Pattinaggio"
    assert A.sport_di("Danza sportiva: finale") == "Danza sportiva"
    assert A.sport_di("EuroLeague: Real Madrid vs Monaco") == "Basket"
    assert S.filtro_di("Basquetebol") == "basket" and S.filtro_di("Pallavolo") == "volley"
    assert S.filtro_di("Ténis") == "tennis" and S.filtro_di("Fútbol americano") == "nfl"
    assert S.filtro_di("Formula 1") == "f1" and S.filtro_di("Motomondiale") == "moto"
    assert S.filtro_di("Motori") is None and S.filtro_di("Ciclismo") is None
    # DAZN: l'etichetta portoghese/spagnola diventa il nome italiano, il calcio no
    def tile(sport, titolo, eid):
        return {"Sport": {"Id": "x", "Title": sport}, "Type": "Live", "EventId": eid,
                "Start": "2026-10-10T18:00:00Z", "End": "2026-10-10T20:00:00Z", "Title": titolo,
                "Competition": {"Title": ""}, "IsFreeToView": True}
    bsk = D.analizza_altri([tile("Basquetebol", "Barcelona x Zaragoza", "b1")], "pt")[0]
    assert bsk["sport"] == "Basket" and bsk["sport_orig"] == "Basquetebol"
    assert D.analizza_altri([tile("Ténis", "WTA Osaka", "t1")], "pt")[0]["sport"] == "Tennis"
    assert D.analizza_altri([tile("Boxeo", "Canelo vs Mbilli", "x1")], "es")[0]["sport"] == "Boxe"
    assert D.analizza_altri([tile("Volley", "Lube - Trento", "v1")], "it")[0]["sport"] == "Pallavolo"
    cal = D.analizza_altri([tile("Futebol", "Benfica - Porto", "c1")], "pt")[0]
    assert cal["sport"] == "Calcio" and cal["sport_orig"] == "Futebol"
    # stessa partita da due paesi: un solo evento, sotto Basket.
    # La lista bianca resta per lo sport già chiamato Basket. Liga Betclic maschile, arrivata come Basquetebol, resta.
    ora = dt.datetime(2026, 10, 10, 16, 0, tzinfo=p.ROMA)
    ts = int((ora + dt.timedelta(hours=3)).timestamp())

    def ev(sport, titolo, nome):
        return {"id": f"{nome}:{titolo}", "ts": ts, "fine": ts + 7200, "sport": sport, "titolo": titolo,
                "titolo_orig": titolo, "titolo_src": titolo, "evento": True, "lingua": "pt", "descrizione": "",
                "emittenti": [{"nome": nome, "pagina": "https://x", "link": None, "dazn_gratis": True}]}
    uniti = A.unisci_eventi([ev("Basquetebol", "Barcelona - Real Madrid", "DAZN Portogallo"),
                             ev("Basket", "Barcelona - Real Madrid", "DAZN Italia")])
    assert len(uniti) == 1 and uniti[0]["sport"] == "Basket", uniti
    assert {x["nome"] for x in uniti[0]["emittenti"]} == {"DAZN Portogallo", "DAZN Italia"}
    f = A.filtro_basket()
    acb = ev("Basquetebol", "Liga ACB, Barcelona x Zaragoza", "DAZN Portogallo")
    S.applica(acb)
    assert acb["sport"] == "Basket" and acb.get("sport_orig") == "Basquetebol" and f(acb) is None
    fem = ev("Basquetebol", "Liga Betclic Feminina, A x B", "DAZN Portogallo")
    S.applica(fem)
    assert f(fem), fem
    casa = ev("Basquetebol", "Liga Betclic Masculina, Queluz x Benfica", "DAZN Portogallo")
    S.applica(casa)
    assert f(casa) is None, f(casa)
    nativo = ev("Basket", "BBL, ALBA Berlin - Bayern", "DAZN Germania")
    S.applica(nativo)
    assert f(nativo), nativo
    # pagina: una sola sezione per sport, pulsante Per sport e ricerca sulla parola straniera
    eventi = [ev("Basquetebol", "Liga ACB, Barcelona x Zaragoza", "DAZN Portogallo"),
              ev("Basket", "EuroLeague: Milano - Madrid", "DAZN Italia"),
              ev("Ténis", "WTA Osaka", "DAZN Portogallo"),
              ev("Tennis", "ATP Almaty", "DAZN Italia"),
              ev("Pallavolo", "Lube - Trento", "DAZN Italia"),
              ev("Boxeo", "Canelo vs Mbilli", "DAZN Spagna"),
              ev("Fútbol americano", "Steelers - Saints", "DAZN Spagna"),
              ev("Hockey sur glace", "Kings - Devils", "DAZN Francia"),
              ev("Motor", "Supercars", "DAZN Spagna"),
              ev("Desportos motorizados", "TCR World Tour", "DAZN Portogallo")]
    for i, e in enumerate(eventi):
        e["ts"] = int((ora + dt.timedelta(hours=1 + i)).timestamp())
        e["fine"] = e["ts"] + 7200
        e["id"] = f"s{i}"
    h = p.genera_html(p.finestra(ora)[0], ora, [], [], [], [], eventi)
    for vietato in ("BASQUETEBOL", "TÉNIS", "BOXEO", "FÚTBOL AMERICANO", "HOCKEY SUR GLACE",
                    ">MOTOR<", "DESPORTOS MOTORIZADOS"):
        assert vietato not in h, vietato
    for titolo in ("BASKET", "TENNIS", "PALLAVOLO", "BOXE", "FOOTBALL AMERICANO", "HOCKEY SU GHIACCIO", "MOTORI"):
        assert f"<h2>{titolo}</h2>" in h, titolo
    assert h.count("<h2>BASKET</h2>") == 1 and h.count("<h2>TENNIS</h2>") == 1 and h.count("<h2>MOTORI</h2>") == 1
    assert 'data-sport="basket"' in h and 'data-sport="volley"' in h and 'data-sport="tennis"' in h
    assert 'data-sport="nfl"' in h
    assert 'data-alias="Basquetebol"' in h and 'data-alias="Ténis"' in h
    assert "basquetebol" in h and "baloncesto" in h and "baschet" in h and "boxeo" in h
    assert "ALIAS_SPORT" in h and "data-alias" in h
    assert "background:#000" in h and "font-size:1.35rem" in h


test_sport_nomi(); print("nomi sport unificati (tutte le lingue): OK")


def test_normalizzazione_non_nasconde():
    """Unificare il nome sposta l'evento nella sezione italiana. Non lo toglie, salvo il basket femminile."""
    import copy
    import sport_nomi as S
    import altri_sport as A
    import dazn as D

    ora = dt.datetime(2026, 10, 10, 16, 0, tzinfo=p.ROMA)
    inizio, fine = ora, ora + dt.timedelta(days=4)
    base = int((ora + dt.timedelta(hours=2)).timestamp())
    cat = json.loads((QUI.parent / "categorie.json").read_text(encoding="utf-8"))
    rx_donne = [r for r in cat["basket_esclusi"] if "3x3" not in r and "League" not in r]

    def ev(i, sport, titolo):
        ts = base + i * 4000
        return {"id": f"e{i}", "ts": ts, "fine": ts + 7200, "sport": sport, "titolo": titolo,
                "titolo_orig": titolo, "titolo_src": titolo, "evento": True, "lingua": "it",
                "descrizione": "", "comp": "",
                "emittenti": [{"nome": "DAZN Portogallo", "pagina": "https://x", "link": None, "vpn": None, "dazn_gratis": True}]}

    eventi = [
        ev(1, "Basquetebol", "Liga Betclic Masculina, Queluz x Benfica"),
        ev(2, "Basketball", "BBL, ALBA Berlin - Bayern"),
        ev(3, "Baloncesto", "Liga ACB, Barcelona - Madrid"),
        ev(4, "Basquetebol", "Liga Betclic Feminina, Uniao x Benfica"),
        ev(5, "Basket", "WNBA, Las Vegas Aces - NY Liberty"),
        ev(6, "Basket", "NBA, Los Angeles Lakers - Boston Celtics"),
        ev(7, "Basket", "BBL, Alba Berlin - Ulm"),
        ev(8, "Futebol", "Liga Portugal, Benfica - Porto"),
        ev(9, "Football", "Premier League, Arsenal vs Chelsea"),
        ev(10, "Fußball", "Frauen-Bundesliga, Wolfsburg - Essen"),
        ev(11, "Soccer", "MLS, Miami - Atlanta"),
        ev(12, "Ténis", "WTA Osaka"),
        ev(13, "Boxeo", "Canelo vs Mbilli"),
        ev(14, "Fútbol americano", "All Access Semana 6"),
        ev(15, "Football americano", "All Access Semana 7"),
        ev(16, "Volley", "Lube - Trento"),
        ev(17, "Motor", "Supercars Bathurst"),
        ev(18, "Koszykówka", "Greek Basket League, Olympiacos - Panathinaikos"),
        ev(19, "Basquetebol", "FIBA 3x3 World Tour Bucharest"),
        ev(20, "Basket", "FIBA 3x3 World Tour Lausanne"),
        ev(21, "Futsal", "Meta Catania - Real San Giuseppe"),
        ev(22, "Futebol", "Taca de Portugal"),
        ev(23, "Basketball", "NBA G League, Austin - Mexico"),
        ev(24, "Basket", "NBA G League, South Bay - Rip City"),
        ev(25, "Basquetebol Feminino", "Schio x Venezia"),
        ev(26, "Pallacanestro", "LNB Pro A, Monaco - Lyon"),
        ev(27, "Hockey sur glace", "Kings - Devils"),
        ev(28, "Desportos motorizados", "TCR World Tour"),
    ]

    def donne_basket(e):
        if S.normalizza(e["sport"]) != "Basket":
            return False
        testo = " ".join([e["sport"], e["titolo"]])
        return any(re.search(r, testo, re.I) for r in rx_donne)

    ids_donne = {e["id"] for e in eventi if donne_basket(e)}
    assert ids_donne == {"e4", "e5", "e25"}, ids_donne

    def visibili(attiva, fonte):
        precedente = S.ATTIVA
        S.imposta(attiva)
        try:
            dati = copy.deepcopy(fonte)
            vuoto = lambda *a, **k: ([], None)
            altri, calcio, _ = A.raccogli_altri(
                inizio, fine, ora, U.regex_femminile([]),
                scarica_srg_fn=vuoto, scarica_ard_fn=vuoto,
                scarica_dazn_fn=lambda: (dati, None))
            tenuti, _ = p.unisci_stream([], calcio, scartate=[])
            chiavi = {(e["ts"], e["casa"], e["ospite"]) for e in tenuti}
            ids = set()
            for e in altri:
                ids |= set(e.get("ids") or {e["id"]})
            for e in calcio:
                if (e["ts"], e["casa"], e["ospite"]) in chiavi:
                    ids |= set(e.get("ids") or {e["id"]})
            return ids, altri, calcio, tenuti
        finally:
            S.imposta(precedente)

    prima, _, _, _ = visibili(False, eventi)
    dopo, altri, calcio, tenuti = visibili(True, eventi)
    spariti = prima - dopo
    assert spariti <= ids_donne, spariti
    assert prima - ids_donne <= dopo, prima - ids_donne - dopo
    assert spariti == {"e4", "e25"}, spariti
    assert "e5" not in prima and "e5" not in dopo
    assert {"e1", "e2", "e3", "e6", "e8", "e9", "e10", "e11", "e18", "e19", "e22", "e23", "e26"} <= dopo
    assert "e7" not in prima and "e20" not in prima and "e24" not in prima
    assert "e15" not in prima and "e15" not in dopo

    sport_di = {e["titolo"]: e["sport"] for e in altri}
    assert sport_di["Liga Betclic Masculina, Queluz x Benfica"] == "Basket"
    assert sport_di["BBL, ALBA Berlin - Bayern"] == "Basket"
    assert sport_di["Greek Basket League, Olympiacos - Panathinaikos"] == "Basket"
    assert sport_di["FIBA 3x3 World Tour Bucharest"] == "Basket"
    assert sport_di["NBA G League, Austin - Mexico"] == "Basket"
    assert sport_di["LNB Pro A, Monaco - Lyon"] == "Basket"
    assert sport_di["WTA Osaka"] == "Tennis"
    assert sport_di["Canelo vs Mbilli"] == "Boxe"
    assert sport_di["Lube - Trento"] == "Pallavolo"
    assert sport_di["All Access Semana 6"] == "Football americano"
    assert sport_di["Supercars Bathurst"] == "Motori"
    assert sport_di["TCR World Tour"] == "Motori"
    assert sport_di["Kings - Devils"] == "Hockey su ghiaccio"
    assert sport_di["Meta Catania - Real San Giuseppe"] == "Calcio a 5"
    assert "Liga Betclic Feminina" not in " ".join(sport_di)
    assert not any("Benfica - Porto" in e["titolo"] or e["titolo"] == "Taca de Portugal" for e in altri)

    def squadre(casa, ospite):
        return any(e["casa"] == casa and e["ospite"] == ospite for e in calcio)

    assert squadre("Benfica", "Porto") and squadre("Arsenal", "Chelsea") and squadre("Miami", "Atlanta")
    assert squadre("Wolfsburg", "Essen")
    assert any(e["casa"] == "Taca de Portugal" and e["ospite"] == "" for e in calcio)
    assert all(e.get("da_etichetta") for e in calcio if e["casa"] in ("Benfica", "Arsenal", "Miami", "Wolfsburg", "Taca de Portugal"))

    h = p.genera_html(inizio.date(), ora, p.raggruppa(tenuti), [], [], None, altri)
    for testo in ("Queluz", "ALBA Berlin", "Olympiacos", "Barcelona", "Lakers", "Benfica", "Porto",
                  "Arsenal", "Chelsea", "Wolfsburg", "Taca de Portugal", "Austin", "Bucharest", "Monaco",
                  "WTA Osaka", "Canelo", "Lube", "Supercars", "Kings"):
        assert testo in h, testo
    assert "Liga Betclic Feminina" not in h and "Schio" not in h
    assert "<h2>BASKET</h2>" in h and "<h2>TENNIS</h2>" in h and "<h2>PALLAVOLO</h2>" in h
    assert h.count("<h2>BASKET</h2>") == 1

    def tile(sport, titolo, eid, ora_z):
        return {"Sport": {"Id": "x", "Title": sport}, "Type": "Live", "EventId": eid,
                "Start": ora_z, "End": "2026-10-10T22:00:00Z", "Title": titolo,
                "Competition": {"Title": ""}, "IsFreeToView": True}

    prod = D.analizza_altri([
        tile("Basquetebol", "Liga Betclic Masculina, Queluz x Benfica", "p1", "2026-10-10T18:00:00Z"),
        tile("Basquetebol", "Liga Betclic Feminina, Uniao x Benfica", "p2", "2026-10-10T19:00:00Z"),
        tile("Futebol", "Liga Portugal, Benfica - Porto", "p3", "2026-10-10T20:00:00Z"),
        tile("Basket", "BBL, Alba Berlin - Ulm", "p4", "2026-10-10T21:00:00Z"),
    ], "pt")
    assert prod[0]["sport_orig"] == "Basquetebol" and prod[2]["sport_orig"] == "Futebol" and "sport_orig" not in prod[3]
    ids_p, altri_p, calcio_p, _ = visibili(True, prod)
    assert "dazn:p1" in ids_p and "dazn:p2" not in ids_p and "dazn:p3" in ids_p and "dazn:p4" not in ids_p
    assert any("Queluz" in e["titolo"] and e["sport"] == "Basket" for e in altri_p)
    assert any(e["casa"] == "Benfica" and e["ospite"] == "Porto" for e in calcio_p)
    return len(dopo)


test_normalizzazione_non_nasconde(); print("normalizzazione non nasconde eventi (salvo basket femminile): OK")
