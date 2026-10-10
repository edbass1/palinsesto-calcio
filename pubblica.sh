#!/usr/bin/env bash
# Pubblica il progetto su GitHub Pages. Richiede il comando "gh" già autenticato (gh auth login).
set -euo pipefail
cd "$(dirname "$0")"
REPO="${1:-palinsesto-calcio}"

gh auth status >/dev/null || { echo "Prima esegui: gh auth login"; exit 1; }
UTENTE="$(gh api user --jq .login)"
echo "Account GitHub: $UTENTE  –  repository: $REPO"

# identità git locale se non configurata
git config user.email >/dev/null || git config user.email "$(gh api user --jq .id)+$UTENTE@users.noreply.github.com"
git config user.name  >/dev/null || git config user.name "$UTENTE"

# commit iniziale se manca
git add -A
git diff --cached --quiet || git commit -q -m "Palinsesto calcio in TV"
git branch -M main

# crea il repository pubblico (se non esiste) e fa il push
if gh repo view "$UTENTE/$REPO" >/dev/null 2>&1; then
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$UTENTE/$REPO.git"
  git push -u origin main
else
  gh repo create "$REPO" --public --source=. --remote=origin --push \
    --description "Palinsesto calcio in TV del weekend (orari italiani)"
fi

# abilita GitHub Pages con pubblicazione tramite GitHub Actions
if gh api "repos/$UTENTE/$REPO/pages" >/dev/null 2>&1; then
  gh api -X PUT "repos/$UTENTE/$REPO/pages" -f build_type=workflow >/dev/null
else
  gh api -X POST "repos/$UTENTE/$REPO/pages" -f build_type=workflow >/dev/null
fi

# avvia il workflow (il push l'ha probabilmente già avviato; questo lo garantisce)
sleep 5
gh workflow run aggiorna.yml --repo "$UTENTE/$REPO" --ref main || true

URL="$(gh api "repos/$UTENTE/$REPO/pages" --jq .html_url)"
echo
echo "Fatto. La pagina sarà online tra 1-2 minuti a questo indirizzo:"
echo "  $URL"
echo "Avanzamento: https://github.com/$UTENTE/$REPO/actions"
