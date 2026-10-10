#!/usr/bin/env bash
# Legge le partite DAZN gratis da QUESTA macchina (dove la guida DAZN risponde) e aggiorna
# solo il file dati/dazn.json del repository su GitHub (API "contents": un commit, nient'altro).
# Il commit su main fa partire da solo il workflow (evento push); con --dispatch lo avvia anche a mano.
#
# Uso:   scripts/aggiorna_dazn.sh [--prova] [--dispatch]
#   --prova     scrive solo il file locale dati/dazn.json, non tocca GitHub
#   --dispatch  dopo il commit avvia anche "Aggiorna palinsesto" (utile se si toglie il trigger push)
# Richiede: python3, gh autenticato (permessi repo). Repository: variabile REPO (predefinito sotto).
# Esempio cron (ogni ora al minuto 5):  5 * * * *  /percorso/palinsesto-calcio/scripts/aggiorna_dazn.sh >>/tmp/dazn.log 2>&1
set -euo pipefail
REPO="${REPO:-edbass1/palinsesto-calcio}"
RAMO="${RAMO:-main}"
PERCORSO="dati/dazn.json"
cd "$(dirname "$0")/.."

PROVA=0; DISPATCH=0
for a in "$@"; do
  case "$a" in
    --prova) PROVA=1 ;;
    --dispatch) DISPATCH=1 ;;
    *) echo "opzione sconosciuta: $a" >&2; exit 2 ;;
  esac
done

if ! python3 scraper/dazn.py --esporta "$PERCORSO"; then
  echo "Nessun paese DAZN letto: non aggiorno GitHub." >&2
  exit 1
fi
if [ "$PROVA" = 1 ]; then
  echo "Prova: scritto $PERCORSO, GitHub non toccato."
  exit 0
fi

SHA="$(gh api "repos/$REPO/contents/$PERCORSO?ref=$RAMO" --jq .sha 2>/dev/null || true)"
ARGS=(-X PUT "repos/$REPO/contents/$PERCORSO" -f message="DAZN: dati aggiornati ($(date -u +%H:%MZ))"
      -f branch="$RAMO" -f content="$(base64 -w0 "$PERCORSO")")
[ -n "$SHA" ] && ARGS+=(-f sha="$SHA")
gh api "${ARGS[@]}" --jq '.commit.sha' | sed 's/^/commit: /'

if [ "$DISPATCH" = 1 ]; then
  gh workflow run aggiorna.yml -R "$REPO" --ref "$RAMO" && echo "workflow avviato"
fi
