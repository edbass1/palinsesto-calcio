#!/usr/bin/env python3
"""Test offline: finestra di 4 giorni, LiveSoccerTV (pagine salvate il 9/10/2026, 62 partite attese),
LiveOnSat (pagine salvate il 10/10/2026): canali in chiaro, orari, unione dei doppioni."""
import datetime as dt, gzip, json, re, sys
from pathlib import Path
QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent / "scraper"))
import palinsesto as p
import liveonsat as L
import unisci as U
import teleboy as TB
import dazn as DZ

CONF_LOS = json.loads((QUI.parent / "liveonsat.json").read_text(encoding="utf-8"))
DIR_LOS = QUI / "fixtures_liveonsat_2026-10-10"


def finto_lstv(url, tentativi=3):
    f = QUI / "fixtures_2026-10-09" / (url.rstrip("/").split("/")[-1] + ".html.gz")
    return gzip.open(f, "rt", encoding="utf-8").read(), None


def finto_los(url, tentativi=4):
    f = DIR_LOS / (url.rsplit("/", 1)[-1].replace(".php", "") + ".html.gz")
    if not f.exists():
        return None, "HTTP 502"
    return gzip.open(f, "rt", encoding="utf-8").read(), None


def los_pagina(nome):
    return L.analizza(finto_los(nome + ".php")[0], CONF_LOS["canali_in_chiaro"], CONF_LOS["alias_canali"])


def test_finestra():
    """Finestra mobile: oggi 00:00 -> fine del 3° giorno successivo (4 giorni), ora italiana."""
    casi = {  # ora italiana -> (primo giorno, ultimo giorno, testo)
        "2026-10-10T18:30": ("2026-10-10", "2026-10-13", "Sab 10 – Mar 13 ottobre"),
        "2026-10-10T00:00": ("2026-10-10", "2026-10-13", "Sab 10 – Mar 13 ottobre"),
        "2026-10-09T23:59": ("2026-10-09", "2026-10-12", "Ven 9 – Lun 12 ottobre"),
        "2026-10-14T09:00": ("2026-10-14", "2026-10-17", "Mer 14 – Sab 17 ottobre"),
        "2026-10-30T12:00": ("2026-10-30", "2026-11-02", "Ven 30 ottobre – Lun 2 novembre"),
        "2026-12-30T12:00": ("2026-12-30", "2027-01-02", "Mer 30 dicembre – Sab 2 gennaio"),
    }
    for ora, (primo, ultimo, testo) in casi.items():
        g, ini, fine = p.finestra(dt.datetime.fromisoformat(ora).replace(tzinfo=p.ROMA))
        assert str(g) == primo and (ini.hour, ini.minute) == (0, 0) and ini.date() == g, (ora, g, ini)
        assert str((fine - dt.timedelta(seconds=1)).date()) == ultimo and (fine.hour, fine.minute) == (0, 0), (ora, fine)
        assert p.periodo(g) == testo, (ora, p.periodo(g))
    # un'ora UTC tarda è già "domani" in Italia
    g, _, _ = p.finestra(dt.datetime(2026, 10, 9, 22, 30, tzinfo=dt.timezone.utc))
    assert str(g) == "2026-10-10"
    # cambio d'ora (domenica 25/10/2026): la finestra 24-27 ottobre dura 97 ore
    g, ini, fine = p.finestra(dt.datetime(2026, 10, 24, 12, tzinfo=p.ROMA))
    assert ini.utcoffset() == dt.timedelta(hours=2) and fine.utcoffset() == dt.timedelta(hours=1)
    assert fine.timestamp() - ini.timestamp() == 97 * 3600
    # ora legale (domenica 28/3/2027): 95 ore
    g, ini, fine = p.finestra(dt.datetime(2027, 3, 27, 9, tzinfo=p.ROMA))
    assert fine.timestamp() - ini.timestamp() == 95 * 3600


def test_fixture():
    """Solo LiveSoccerTV, finestra ven 9 – lun 12: le 62 partite di prima (da ven 18:00) + 2 di venerdì pomeriggio."""
    canali = json.loads((QUI.parent / "canali.json").read_text())["canali"]
    p.scarica = finto_lstv
    v, ini, fine = p.finestra(dt.datetime(2026, 10, 9, 12, tzinfo=p.ROMA))
    gruppi, falliti, senza = p.raccogli(canali, ini, fine)
    n = sum(len(g["partite"]) for g in gruppi)
    assert n == 64 and not falliti and not senza, (n, falliti, senza)
    prima_18 = [e for g in gruppi for e in g["partite"] if e["quando"] < dt.datetime(2026, 10, 9, 18, tzinfo=p.ROMA)]
    assert sorted(e["casa"] for e in prima_18) == ["Al Fateh", "Corvinul Hunedoara"], prima_18
    nomi = [g["nome"] for g in gruppi]
    assert nomi[:6] == ["SERIE A", "SERIE B", "PREMIER LEAGUE", "LALIGA", "BUNDESLIGA", "LIGUE 1"], nomi
    serie_a = [(e["quando"].strftime("%a %H:%M"), f'{e["casa"]} - {e["ospite"]}', [c["nome"] for c in e["canali"]])
               for e in gruppi[0]["partite"]]
    assert serie_a[1] == ("Sat 18:00", "Inter - Parma", ["Prima Sport 2", "Golazo Network"]), serie_a[1]
    psg = [e for g in gruppi for e in g["partite"] if "PSG" in e["titolo"]][0]
    assert [c["nome"] for c in psg["canali"]] == ["TV5 Monde"]
    html = p.genera_html(v, dt.datetime(2026, 10, 9, 12, 47, tzinfo=p.ROMA), gruppi, ["Canale X (HTTP 404)"], [])
    assert "non scaricati" in html and "Canale X" in html and html.count('class="partita"') == 2 * 64
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
    assert r["canali_fta"] == ["Persiana Sports 3"], r
    # alias: varianti TV5 Monde unite, ITV 1 England -> ITV1 UK
    assert trova("2day", "Paris St Germain v Le Mans")["canali_fta"] == ["Persiana Sports 2", "TV5 Monde"]
    assert "ITV1 UK" in trova("uk-britain-ireland-all-football", "Southampton v Portsmouth")["canali_fta"]
    # Genoa-Fiorentina: nessun canale in chiaro
    assert trova("europe-italy-all-football", "Genoa v Fiorentina")["canali_fta"] == []
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
    assert titoli["Arsenal v Leeds United"]["canali_fta"] == ["Idman TV", "Solh TV"]
    # Rayo-Athletic aveva solo Persiana Sports 3 (+ DAZN): sparisce
    assert grezzo["Rayo Vallecano v Athletic Bilbao"]["canali_fta"] == ["DAZN España HD FTA", "Persiana Sports 3"]
    assert "Rayo Vallecano v Athletic Bilbao" not in titoli
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
        "prima-sport", "golazo", "itv1", "itvx", "bbc-alba", "bbc", "sportynet-brasil", "sportynet-plus", "tv5monde",
        "sporty-tv-africa", "rsi", None]
    assert "PPV" in next(v for v in dove if v["id"] == "sportynet-plus")["note"]
    e = {"ts": 1791648000, "quando": dt.datetime(2026, 10, 10, 18, tzinfo=p.ROMA), "casa": "A", "ospite": "B",
         "canali": [{"nome": "Prima Sport 2", "fta": False}, {"nome": "RSI La 2 Svizzera", "fta": True},
                    {"nome": "Persiana Sports 2", "fta": True}]}
    h = p.genera_html(dt.date(2026, 10, 10), dt.datetime(2026, 10, 10, 18, tzinfo=p.ROMA),
                      [{"nome": "X", "partite": [e]}], [], [], dove)
    assert '<a href="#dv-prima-sport"' in h and '<a href="#dv-rsi"' in h and "Persiana Sports 2</li>" in h
    assert 'id="dv-golazo"' in h and 'id="dv-dazn"' in h and 'id="dv-rsi"' in h  # utente sempre, ricerca se usata
    assert 'id="dv-zdf"' not in h and 'target="_blank" rel="noopener noreferrer"' in h
    assert "Calcio in TV · Sab 10 – Mar 13 ottobre" in h and h.count("data-filtro=") == 5 and "eekend" not in h


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
        "MDR Fernsehen": "MDR Sachsen", "ORF 1 Austria": "ORF 1", "ServusTV Österreich": "ServusTV", "Nitro Deutschland": "NITRO", "Prima Sport 1": None, "mySports 2": None, "Sport 1+": None,
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
    assert st["dazn"] == {"it": 2, "de": 2, "pt": 10, "be": 2}, st["dazn"]
    tutte = {f'{e["casa"]} - {e["ospite"]}': (g["nome"], e) for g in gruppi for e in g["partite"]}
    nomi = lambda k: [c["nome"] for c in tutte[k][1]["canali"]]  # noqa: E731
    assert nomi("Levante - Sevilla")[-2:] == ["DAZN Italia", "DAZN Portogallo"], nomi("Levante - Sevilla")
    assert "DAZN Belgio" in nomi("PSG - Le Mans") and "TV5 Monde" in nomi("PSG - Le Mans")
    assert tutte["Leipzig U19 - PSV U19"][0] == "UEFA YOUTH LEAGUE"
    assert nomi("Leipzig U19 - PSV U19") == ["DAZN Portogallo"]
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
          ("UEFA Youth League", ("Leipzig U19", "PSV U19")), ("Eredivisie", ("Willem II", "Go Ahead Eagles")),
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
                                    {"ora": ora2, "scarica_srg_fn": srg, "scarica_ard_fn": lambda i, f: ([], None)})
    tutte = {f'{e["casa"]} - {e["ospite"]}': (g["nome"], e) for g in gruppi for e in g["partite"]}
    nome, lug = tutte["Lugano - Luzern"]
    assert nome == "SUPER LEAGUE (Svizzera)" and [c["nome"] for c in lug["canali"]][-2:] == ["SRF stream", "RSI stream"], lug
    assert lug["quando"].strftime("%H:%M") == "18:00" and "Streaming" in lug["fonti"]  # unita alla partita LiveOnSat delle 18
    assert lug["canali"][-2]["url"] == "https://www.srf.ch/play/tv/-/video/-?urn=urn:swisstxt:video:srf:1830000"
    h = p.genera_html(v, ora, gruppi, falliti, [], [], altri)
    assert 'data-vista="altri"' in h and 'id="vista-altri"' in h and "VPN SVIZZERA" in h and "VPN GERMANIA" in h
    assert 'href="https://www.ardmediathek.de/video/' in h and 'data-fine="' in h and "ALTRI SPORT" in h
    assert 'href="https://www.srf.ch/play/tv/-/video/-?urn=urn:swisstxt:video:srf:1830000" target="_blank"' in h
    # un'emittente che non risponde: avviso, nessun errore
    A.json_url = lambda url, tentativi=3: (None, "HTTP Error 403") if "ardmediathek" in url else finto_json(url)
    _, _, avvisi = A.raccogli_altri(ini, fine, ora, rx)
    assert avvisi == ["Altri sport: non raggiungibile ARD"], avvisi
    A.json_url = finto_json
    return altri, calcio


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
    assert st["livesoccertv"] == 62 and st["liveonsat"] > 0 and st["uniti"] and st["solo_liveonsat"] > 0, st
    assert st["totale"] == 62 + st["liveonsat"] - len(st["uniti"]), st
    # doppioni uniti: canali LiveSoccerTV + canali in chiaro LiveOnSat, una sola riga
    psg = tutte["PSG - Le Mans"]
    assert [(c["nome"], c["fta"]) for c in psg["canali"]] == [("TV5 Monde", True)], psg["canali"]  # Persiana esclusa
    assert psg["fonti"] == ["LiveSoccerTV", "LiveOnSat"]
    como = tutte["Como - Roma"]
    assert [c["nome"] for c in como["canali"]] == ["Prima Sport 1", "Sporty TV Africa"], como["canali"]
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
    assert 'TELEBOY</span>' in h2 and 'id="dv-teleboy"' in h2 and 'href="https://tv.teleboy.ch"' in h2
    assert "Canali di questa pagina disponibili su Teleboy" in h2 and h2.count('href="#dv-teleboy"') > 0
    assert not any(x in h2.lower() for x in ("megogo", "persiana", "gem sport"))
    # vista "in ordine di orario": stesse partite, ordinate per ora, con separatori per giorno ed etichetta campionato
    import re as _re
    orario = html[html.index('id="vista-orario"'):html.index('</main>')]
    ts = [int(x) for x in _re.findall(r'data-ts="(\d+)"', orario)]
    assert len(ts) == st["totale"] and ts == sorted(ts)
    assert _re.findall(r'class="giorno-h">([^<]+)', orario) == ["VENERDÌ 9 OTTOBRE", "SABATO 10 OTTOBRE", "DOMENICA 11 OTTOBRE", "LUNEDÌ 12 OTTOBRE"]
    assert orario.count('class="comp-tag"') == st["totale"] and 'data-vista="orario"' in html and "localStorage" in html
    return st


if __name__ == "__main__":
    test_finestra(); print("finestra: OK")
    print("LiveSoccerTV 9/10/2026:", test_fixture(), "partite – OK")
    test_fta(); print("LiveOnSat canali in chiaro: OK")
    test_esclusi(); print("LiveOnSat canali esclusi (Megogo/DAZN): OK")
    test_orari(); print("LiveOnSat orari/fuso: OK")
    test_dedup(); print("doppioni (nomi/orari): OK")
    test_ordine(); print("ordine competizioni: OK")
    test_finite(); print("partite finite tolte: OK")
    test_dove(); print("dove vederli: OK")
    tb = test_teleboy(); print(f"Teleboy ({tb.n} canali): OK")
    sd = test_dazn(); print(f"DAZN: gratis {sd['dazn']}, unite {len(sd['uniti_dazn'])}, solo DAZN {sd['solo_dazn']} – OK")
    sf = test_femminile(); print(f"femminile: {len(sf['femminili_tolte'])} partite escluse nei dati salvati – OK")
    al, ca = test_altri_sport(); print(f"altri sport: {len(al)} eventi, calcio in streaming {len(ca)} – OK")
    st = test_unione()
    print(f"unione: LiveSoccerTV {st['livesoccertv']} + LiveOnSat {st['liveonsat']} - uniti {len(st['uniti'])}"
          f" = {st['totale']} – OK")
