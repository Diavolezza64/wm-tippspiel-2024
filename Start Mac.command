#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Fussball Tippspiel – Daten aktualisieren (Mac)
# Doppelklick im Finder startet dieses Script im Terminal.
#
# Einmalig ausführbar machen (einmal im Terminal eingeben):
#   chmod +x "Start Mac.command"
# ──────────────────────────────────────────────────────────────

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "🏆 Fussball Tippspiel – Daten werden aktualisiert …"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Python 3 suchen
if command -v python3 &>/dev/null; then
    python3 tools/wm_auto.py
elif command -v python &>/dev/null; then
    python tools/wm_auto.py
else
    echo "❌  Python 3 nicht gefunden."
    echo "    Bitte von https://python.org installieren."
fi

echo ""

# GitHub: Änderungen automatisch pushen (nur wenn Git eingerichtet ist)
if [ -d ".git" ] && command -v git &>/dev/null; then
    git add . &>/dev/null
    if ! git diff --cached --quiet; then
        DATUM=$(date '+%Y-%m-%d %H:%M')
        git commit -m "Auto-Update $DATUM" &>/dev/null && \
        git push &>/dev/null && \
        echo "✅ GitHub aktualisiert" || \
        echo "⚠️  GitHub-Push fehlgeschlagen (kein Internet?)"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Dashboard im Browser öffnen
if [ -f "web/index.html" ]; then
    open "web/index.html"
fi

echo "Drücke Enter zum Schliessen …"
read -r
