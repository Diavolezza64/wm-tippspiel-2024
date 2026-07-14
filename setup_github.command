#!/bin/bash
# GitHub-Setup fuer Fussball Tippspiel Beat
# Doppelklick zum Ausfuehren

cd "$(dirname "$0")"
echo "================================================"
echo " GitHub-Setup - Fussball Tippspiel Beat"
echo "================================================"
echo ""

# gh CLI pruefen / installieren
if ! command -v gh &>/dev/null; then
    echo "GitHub CLI (gh) wird installiert..."
    if command -v brew &>/dev/null; then
        brew install gh
    else
        echo "Homebrew fehlt. Bitte von https://brew.sh installieren."
        read
        exit 1
    fi
fi

# GitHub-Login
gh auth status &>/dev/null || (
    echo "Bitte bei GitHub einloggen (Browser oeffnet sich):"
    gh auth login --web --git-protocol https
)

# GitHub-Username ermitteln
GH_USER=$(gh api user --jq .login)
echo "GitHub-User: $GH_USER"
echo ""

# Bestehendes Repo umbenennen
OLD_REPO="wm-tippspiel-2024"
NEW_REPO="Fussball-Tippspiel-Beat"

echo "Benenne $OLD_REPO um zu $NEW_REPO ..."
gh repo rename "$NEW_REPO" --repo "$GH_USER/$OLD_REPO" --yes 2>/dev/null && \
    echo "Repo umbenannt." || \
    echo "Umbenennung uebersprungen (existiert bereits oder anderer Fehler)."

REMOTE_URL="https://github.com/$GH_USER/$NEW_REPO.git"
echo ""
echo "Remote-URL: $REMOTE_URL"

# Lokales Git initialisieren
if [ ! -d ".git" ]; then
    git init
    git branch -m main
    git config user.name "Beat Nauer"
    git config user.email "b.nauer@bluewin.ch"
    echo "Git initialisiert."
fi

# Remote setzen
git remote remove origin 2>/dev/null
git remote add origin "$REMOTE_URL"

# Alle Dateien committen und pushen
git add .
git commit -m "Fussball Tippspiel Beat - aktueller Stand" 2>/dev/null || true
echo ""
echo "Push zu GitHub..."
git push -u origin main --force

echo ""
echo "================================================"
echo "Fertig! Repo: https://github.com/$GH_USER/$NEW_REPO"
echo "================================================"
echo "Druecke Enter zum Schliessen..."
read
