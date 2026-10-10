#!/usr/bin/env python3
"""Test offline: finestra del weekend, LiveSoccerTV (pagine salvate il 9/10/2026, 62 partite attese),
LiveOnSat (pagine salvate il 10/10/2026): canali in chiaro, orari, unione dei doppioni."""
import datetime as dt, gzip, json, sys
from pathlib import Path
QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI.parent / "scraper"))
import palinsesto as p
import liveonsat as L
import unisci as U

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
    casi = {  # ora italiana -> venerdì atteso
        "2026-10-09T10:00": "2026-10-09", "2026-10-10T18:00": "2026-10-09", "2026-10-12T23:59": "2026-10-09",
        "2026-10-13T00:00": "2026-10-16", "2026-10-15T23:00": "2026-10-16", "2026-10-26T12:00": "2026-10-23",
    }
    for ora, ven in casi.items():
        v, ini, fine = p.finestra_weekend(dt.datetime.fromisoformat(ora).replace(tzinfo=p.ROMA))
        assert str(v) == ven, (ora, v)
        assert ini.hour == 18 and (fine - ini) == dt.timedelta(days=3, hours=6), (ini, fine)
    # cambio d'ora: weekend 23-26 ottobre 2026 (fine ora legale domenica 25)
    v, ini, fine = p.finestra_weekend(dt.datetime(2026, 10, 24, 12, tzinfo=p.ROMA))
    assert ini.utcoffset() == dt.timedelta(hours=2) and fine.utcoffset() == dt.timedelta(hours=1)


def test_fixture():
    """Solo LiveSoccerTV: deve dare lo stesso risultato di prima (62 partite)."""
    canali = json.loads((QUI.parent / "canali.json").read_text())["canali"]
    p.scarica = finto_lstv
    v, ini, fine = p.finestra_weekend(dt.datetime(2026, 10, 9, 12, tzinfo=p.ROMA))
    gruppi, falliti, senza = p.raccogli(canali, ini, fine)
    n = sum(len(g["partite"]) for g in gruppi)
    assert n == 62 and not falliti and not senza, (n, falliti, senza)
    nomi = [g["nome"] for g in gruppi]
    assert nomi[:6] == ["SERIE A", "SERIE B", "PREMIER LEAGUE", "LALIGA", "BUNDESLIGA", "LIGUE 1"], nomi
    serie_a = [(e["quando"].strftime("%a %H:%M"), f'{e["casa"]} - {e["ospite"]}', [c["nome"] for c in e["canali"]])
               for e in gruppi[0]["partite"]]
    assert serie_a[1] == ("Sat 18:00", "Inter - Parma", ["Prima Sport 2", "Golazo Network"]), serie_a[1]
    psg = [e for g in gruppi for e in g["partite"] if "PSG" in e["titolo"]][0]
    assert [c["nome"] for c in psg["canali"]] == ["TV5 Monde"]
    html = p.genera_html(v, dt.datetime(2026, 10, 9, 12, 47, tzinfo=p.ROMA), gruppi, ["Canale X (HTTP 404)"], [])
    assert "non scaricati" in html and "Canale X" in html and html.count('class="partita"') == 62
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


def test_unione():
    """LiveSoccerTV (9/10) + LiveOnSat (10/10), weekend 9-12 ottobre."""
    canali = json.loads((QUI.parent / "canali.json").read_text())["canali"]
    p.scarica = finto_lstv
    L.scarica = finto_los
    conf = dict(CONF_LOS, pausa_secondi=0)
    v, ini, fine = p.finestra_weekend(dt.datetime(2026, 10, 10, 18, 30, tzinfo=p.ROMA))
    st = {}
    gruppi, falliti, senza = p.raccogli(canali, ini, fine, conf, st)
    tutte = {f'{e["casa"]} - {e["ospite"]}': e for g in gruppi for e in g["partite"]}
    # pagine non salvate nei fixture -> segnalate, senza bloccare
    assert len(falliti) == len(conf["pagine"]) - 7 and all(f.startswith("LiveOnSat") for f in falliti), falliti
    assert st["livesoccertv"] == 62 and st["liveonsat"] > 0 and st["uniti"] and st["solo_liveonsat"] > 0, st
    assert st["totale"] == 62 + st["liveonsat"] - len(st["uniti"]), st
    # doppioni uniti: canali LiveSoccerTV + canali in chiaro LiveOnSat, una sola riga
    psg = tutte["PSG - Le Mans"]
    assert [(c["nome"], c["fta"]) for c in psg["canali"]] == [("TV5 Monde", True), ("Persiana Sports 2", True)], psg["canali"]
    assert psg["fonti"] == ["LiveSoccerTV", "LiveOnSat"]
    como = tutte["Como - Roma"]
    assert [c["nome"] for c in como["canali"]] == ["Prima Sport 1", "Sporty TV Africa"], como["canali"]
    sot = tutte["Southampton - Portsmouth"]
    assert sot["canali"][:2] == [{"nome": "Golazo Network", "fta": False}, {"nome": "ITV1 UK", "fta": True}], sot["canali"]
    assert not any(k.startswith("Paris St Germain") or k.startswith("Como 1907") for k in tutte)
    # partite solo LiveOnSat, nelle competizioni giuste
    lu = tutte["Lugano - Luzern"]
    assert lu["competizione"] == "SUPER LEAGUE (Svizzera)" and lu["fonti"] == ["LiveOnSat"]
    assert tutte["Galway United - Derry City"]["competizione"] == "FAI CUP (Irlanda)"
    nomi = [g["nome"] for g in gruppi]
    assert nomi.index("SERIE A") == 0 and nomi.count("PREMIER LEAGUE") == 1 and nomi.count("SERIE A") == 1
    assert not any("dazn" in c["nome"].lower() for e in tutte.values() for c in e["canali"])
    html = p.genera_html(v, dt.datetime(2026, 10, 10, 18, 30, tzinfo=p.ROMA), gruppi, falliti, senza)
    assert html.count('class="partita"') == st["totale"] and html.count('<li class="fta">') > 50
    return st


if __name__ == "__main__":
    test_finestra(); print("finestra: OK")
    print("LiveSoccerTV 9/10/2026:", test_fixture(), "partite – OK")
    test_fta(); print("LiveOnSat canali in chiaro: OK")
    test_orari(); print("LiveOnSat orari/fuso: OK")
    test_dedup(); print("doppioni (nomi/orari): OK")
    st = test_unione()
    print(f"unione: LiveSoccerTV {st['livesoccertv']} + LiveOnSat {st['liveonsat']} - uniti {len(st['uniti'])}"
          f" = {st['totale']} – OK")
