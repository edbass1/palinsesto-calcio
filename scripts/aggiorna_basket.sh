#!/usr/bin/env bash
# Legge le pagine «TV Listings» di EuroLeague ed EuroCup da QUESTA macchina (con Chrome headless, perché il sito
# blocca le richieste semplici e i server di GitHub) e aggiorna solo il file dati/basket_tv.json del repository
# su GitHub (API "contents": un commit, nient'altro). Il commit su main fa partire da solo il workflow.
#
# Uso:   scripts/aggiorna_basket.sh [--prova] [--dispatch]
#   --prova     scrive solo il file locale dati/basket_tv.json, non tocca GitHub
#   --dispatch  dopo il commit avvia anche "Aggiorna palinsesto"
# Richiede: python3, google-chrome (o chromium), gh autenticato. Repository: variabile REPO.
# Le pagine cambiano circa una volta a settimana: basta un cron giornaliero, es.  0 9 * * *  /percorso/scripts/aggiorna_basket.sh
set -euo pipefail
REPO="${REPO:-edbass1/palinsesto-calcio}"
RAMO="${RAMO:-main}"
PERCORSO="dati/basket_tv.json"
cd "$(dirname "$0")/.."

PROVA=0; DISPATCH=0
for a in "$@"; do
  case "$a" in
    --prova) PROVA=1 ;;
    --dispatch) DISPATCH=1 ;;
    *) echo "opzione sconosciuta: $a" >&2; exit 2 ;;
  esac
done

if ! python3 scraper/euroleague_tv.py --esporta "$PERCORSO"; then
  echo "Nessuna pagina TV Listings letta: non aggiorno GitHub." >&2
  exit 1
fi
if [ "$PROVA" = 1 ]; then
  echo "Prova: scritto $PERCORSO, GitHub non toccato."
  exit 0
fi

SHA="$(gh api "repos/$REPO/contents/$PERCORSO?ref=$RAMO" --jq .sha 2>/dev/null || true)"
ARGS=(-X PUT "repos/$REPO/contents/$PERCORSO" -f message="Basket TV: dati aggiornati ($(date -u +%H:%MZ))"
      -f branch="$RAMO" -f content="$(base64 -w0 "$PERCORSO")")
[ -n "$SHA" ] && ARGS+=(-f sha="$SHA")
gh api "${ARGS[@]}" --jq '.commit.sha' | sed 's/^/commit: /'

if [ "$DISPATCH" = 1 ]; then
  gh workflow run aggiorna.yml -R "$REPO" --ref "$RAMO" && echo "workflow avviato"
fi
