# ⚽ Calcio in TV – palinsesto del weekend

Pagina web (sfondo nero, caratteri grandi) con le partite trasmesse nel weekend sui canali scelti, con **orari italiani**. Si aggiorna da sola su GitHub Pages.

- **Periodo**: da venerdì 18:00 a lunedì 23:59. Da martedì a giovedì mostra il weekend successivo.
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

## Modificare LiveOnSat

In `liveonsat.json`:
- `pagine`: pagine di LiveOnSat da leggere (una per campionato/nazione; `2day.php` = tutte le partite di oggi);
- `canali_in_chiaro`: canali considerati gratuiti anche se LiveOnSat non li segna in rosso (espressioni regolari sul nome del canale);
- `alias_canali`: per unire più nomi dello stesso canale (es. tutte le varianti di TV5 Monde).

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
- **Attenzione**: anche con l'aggiornamento ogni ora, GitHub sospende le esecuzioni programmate dopo **60 giorni senza commit** nel repository (le esecuzioni automatiche non contano). Se la pagina smette di aggiornarsi, riattivale da **Actions** con *Enable workflow*, oppure fai un piccolo commit (anche solo modificare questo file) almeno ogni due mesi.
