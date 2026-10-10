# ⚽ Calcio in TV – oggi e i prossimi 3 giorni

Pagina web (sfondo nero, caratteri grandi) con le partite trasmesse oggi e nei 3 giorni successivi sui canali scelti, con **orari italiani**. Si aggiorna da sola su GitHub Pages.

- **Periodo**: 4 giorni di calendario, da oggi alle 00:00 (ora italiana) fino alla fine del 3° giorno successivo (es. sabato 10 → *Sab 10 – Mar 13 ottobre*). Le partite finite (iniziate da più di 2h15m) vengono tolte a ogni aggiornamento e spariscono anche dalla pagina aperta; quelle in corso restano con l'etichetta *IN CORSO*.
- **Fonti**:
  - pagine canale di [LiveSoccerTV](https://www.livesoccertv.com/) (i canali di `canali.json`);
  - [LiveOnSat](https://liveonsat.com/): tutte le partite con almeno un canale **in chiaro** (gratuito), mostrando solo quei canali.
- **In chiaro** = canale segnato in rosso da LiveOnSat, oppure presente nell'elenco `canali_in_chiaro` di `liveonsat.json` (Rai, BBC, ITV, TF1, ZDF, RSI, RTÉ, ...). Sulla pagina questi canali sono **verdi** con l'etichetta *IN CHIARO*.
- La stessa partita trovata su entrambi i siti compare una sola volta, con i canali uniti.
- **Aggiornamento**: ogni ora (al minuto 17). La pagina aperta si ricarica da sola ogni 30 minuti. Si può avviare anche a mano.

## Pubblicazione (una volta sola)

1. Crea un account su https://github.com e installa GitHub CLI (https://cli.github.com).
2. Esegui `gh auth login`.
3. Da questa cartella esegui `./pubblica.sh`. Alla fine stampa l'indirizzo della pagina, del tipo `https://<utente>.github.io/palinsesto-calcio/`.
4. Sul telefono apri l'indirizzo e aggiungilo alla schermata Home:
   - **Android (Chrome)**: menu ⋮ > *Aggiungi a schermata Home*.
   - **iPhone (Safari)**: Condividi > *Aggiungi alla schermata Home*.

## Modificare i canali

Modifica `canali.json`: ogni voce ha un nome e l'URL della pagina canale di LiveSoccerTV. Le voci con lo stesso nome vengono unite in un solo canale. I canali DAZN vengono ignorati. Dopo il push, la pagina si rigenera da sola.

## Dove vederli

In fondo alla pagina c'è la sezione **Dove vederli** (link ufficiali, VPN necessaria, note). Toccando il nome di un canale in una partita si salta alla sua voce. I dati sono in `dove_vederli.json`:
- `canali`: espressioni regolari sui nomi dei canali che portano a quella voce;
- `fonte`: `utente` (voci indicate da te, sempre mostrate) o `ricerca` (link ufficiali trovati e controllati, mostrati solo se il canale compare in qualche partita);
- `verificato: false` mostra l'avviso *link da verificare*.

## Modificare LiveOnSat

In `liveonsat.json`:
- `pagine`: pagine di LiveOnSat da leggere (una per campionato/nazione; `2day.php` = tutte le partite di oggi);
- `canali_in_chiaro`: canali considerati gratuiti anche se LiveOnSat non li segna in rosso (espressioni regolari sul nome del canale);
- `alias_canali`: per unire più nomi dello stesso canale (es. tutte le varianti di TV5 Monde).
- `escludi_canali`: canali da non mostrare mai, per entrambe le fonti (basta una parola del nome: oggi `megogo`, `gem sport`, `persiana`, `irib`, `varzish`/`varzesh`, `meraj`). I canali DAZN che arrivano da LiveSoccerTV/LiveOnSat sono sempre esclusi (vedi sotto per le partite DAZN gratis). Se una partita resta senza canali, sparisce.

Per usare solo LiveSoccerTV: `python3 scraper/palinsesto.py --senza-liveonsat`.

## Aggiornare subito

Su GitHub apri **Actions > Aggiorna palinsesto > Run workflow**.

## Uso in locale

```bash
python3 scraper/palinsesto.py      # genera site/index.html
python3 tests/test_logica.py       # test offline
```

Serve solo Python 3.9 o successivo, senza librerie esterne. Pillow serve solo per rigenerare le icone con `scraper/genera_icone.py`.

## Note

- Se un canale o una pagina LiveOnSat non si scarica, in fondo alla pagina compare l'avviso **"Canali o pagine non scaricati"**.
- Se non si scarica niente da nessuno dei due siti, l'aggiornamento si ferma e resta online l'ultima versione buona.
- LiveOnSat a volte risponde "errore 502": lo script riprova da solo fino a 4 volte.
- **Copertura**: le pagine canale di LiveSoccerTV non hanno pagine successive; di solito elencano circa una settimana, quindi i 4 giorni sono coperti (se una pagina sembra piena, nel log compare una NOTA). LiveOnSat non ha pagine per giorno: `2day.php` copre solo oggi, i giorni successivi arrivano dalle pagine dei campionati in `liveonsat.json`; le partite di campionati non in elenco compaiono solo nel giorno stesso.
- **Attenzione**: anche con l'aggiornamento ogni ora, GitHub sospende le esecuzioni programmate dopo **60 giorni senza commit** nel repository (le esecuzioni automatiche non contano). Se la pagina smette di aggiornarsi, riattivale da **Actions** con *Enable workflow*, oppure fai un piccolo commit (anche solo modificare questo file) almeno ogni due mesi.

## Teleboy

`teleboy_canali.json` contiene l'elenco dei canali di [Teleboy](https://www.teleboy.ch/it/live) (TV via internet svizzera, serve la VPN Svizzera, registrazione gratuita). A ogni aggiornamento lo script rilegge la pagina pubblica dei canali (https://www.teleboy.ch/tv/sender) con Chrome headless; se non ci riesce usa la copia salvata. I pacchetti a pagamento (mySports) non contano.

Un canale di una partita che è anche su Teleboy viene mostrato (anche se LiveOnSat non lo segna in chiaro) con l'etichetta **TELEBOY**, e il suo link porta alla voce Teleboy in "Dove vederli"; accanto c'è "▶ Teleboy", il link diretto al canale nel player Teleboy (es. ITV: https://tv.teleboy.ch/live(player:live/346)). Il confronto dei nomi è prudente: ignora HD/numeri scritti in lettere/nome del paese solo se il paese coincide (es. "SRF Zwei Schweiz" = "SRF zwei", "ITV1 UK" = "ITV", ma "ITV X", "RTL Österreich", "TV8 Türkiye" no). Per aggiungere un'equivalenza usa `alias` nel file. Le esclusioni (`escludi_canali`) valgono sempre.

## DAZN gratis

Terza fonte: DAZN (Italia, Spagna, Francia, Germania, Portogallo, Belgio), senza login: prima le file pubbliche "Live" e "In arrivo" della pagina Calcio (`rail-router.discovery.indazn.com`, raggiungibile anche dai server GitHub), poi la guida EPG come riserva, poi `dati/dazn.json` se fresco. Anche qui il calcio femminile è escluso. Si prendono solo le partite di calcio **senza lucchetto** (gratis con l'account DAZN gratuito), con il canale "DAZN <Paese>" e l'etichetta **DAZN GRATIS**. Se la stessa partita c'è già (stessa logica: orario ±15 min + nomi simili) si aggiunge solo il canale. Le partite già finite (DAZN le segna ancora "Live") spariscono con la solita regola: inizio + 2h15. Se un paese non risponde, compare un avviso nel riquadro delle fonti non lette, senza bloccare l'aggiornamento. I paesi sono in `scraper/dazn.py` (`PAESI`). Prova senza DAZN: `python3 scraper/palinsesto.py --senza-dazn`.

La voce DAZN in "Dove vederli" contiene i link alle versioni dei vari paesi e la nota sulla VPN (serve solo per registrarsi).

### DAZN da un'altra macchina (pronto, non ancora attivo)

Dai server di GitHub la guida DAZN risponde 403 (bloccata): in quel caso la pagina mostra una sola riga "DAZN non raggiungibile in questo aggiornamento" (o l'elenco dei paesi falliti). Se nel repository c'è `dati/dazn.json` generato da meno di 3 ore, il build lo usa al posto dei paesi falliti (se manca o è vecchio, viene ignorato).

Per attivarlo, su un computer sempre acceso dove DAZN risponde (con `python3` e `gh` autenticato): `scripts/aggiorna_dazn.sh` legge DAZN, aggiorna via API solo `dati/dazn.json` e il commit fa ripartire il sito. Da mettere in cron ogni ora (es. `5 * * * *`). Prova senza toccare GitHub: `scripts/aggiorna_dazn.sh --prova`. Un commit all'ora tiene anche vivo il repository, così GitHub non sospende l'aggiornamento automatico dopo 60 giorni (ma riempie la cronologia di piccoli commit).

## Niente calcio femminile

Le partite femminili sono escluse da tutte le fonti (LiveSoccerTV, LiveOnSat, DAZN). Le parole che le riconoscono sono in `liveonsat.json` → `escludi_competizioni` (es. women, femminile, frauen, liga f, wsl…): basta che compaiano come parola intera nel nome della competizione o di una squadra. In più: "(W)" nel nome della competizione, oppure entrambe le squadre che finiscono con " W" o "(W)" (es. "Arsenal W - Chelsea W"; una sola squadra non basta). "Wolves", "Wanderers", "Western" ecc. non vengono toccate.

## Altri sport

Terzo bottone in alto: **ALTRI SPORT**. Dirette streaming gratuite di tutti gli altri sport da SRF, RTS e RSI (Svizzera, etichetta **VPN SVIZZERA**, o **SENZA VPN** se l'emittente le rende visibili anche all'estero) e da ARD Mediathek (Germania, etichetta **VPN GERMANIA**). Ogni evento ha giorno, ora di inizio e fine (orari italiani), sport, titolo ed emittenti; il nome dell'emittente apre direttamente la pagina della diretta. Lo stesso evento su più emittenti (es. GP di F1 su SRF, RTS e RSI) compare una volta sola. Gli eventi finiti spariscono (si usa l'ora di fine data dall'emittente). Le partite di calcio di queste fonti vanno nella sezione calcio (canale "SRF stream", "RSI stream", "ARD Das Erste stream"…); il calcio femminile è escluso anche qui.

Fonti: API pubbliche SRG (`il.srgssr.ch/integrationlayer/2.0/<srf|rts|rsi>/mediaList/video/scheduledLivestreams`) e ARD (`api.ardmediathek.de/page-gateway`, raccolta "Die Sport-Livestreams der ARD"). Codice in `scraper/altri_sport.py`. Teleboy non ha un palinsesto pubblico leggibile senza chiave, quindi i suoi canali non generano eventi qui. Prova senza: `python3 scraper/palinsesto.py --senza-altri-sport`.

### Solo dirette di gare, niente programmi
In ALTRI SPORT (e per le partite di calcio prese da SRF/RTS/RSI/ARD) restano solo le dirette di gare e partite: magazine, studio, highlights, sintesi, repliche e simili (Sportpanorama, Sportschau, Sport aktuell, Telegiornale sportivo…) vengono tolti. Regole e parole sono in `altri_sport.json`: `escludi_programmi` (se una di queste parole è nel titolo, l'elemento è tolto) e `parole_evento` (indizi di gara, usati quando la fonte non lo dice da sola, es. ARD). Il log della build elenca ogni programma tolto.
