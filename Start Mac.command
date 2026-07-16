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

# Auto-Update: neueste Code-Version laden
FALLBACK_BASE="https://raw.githubusercontent.com/Diavolezza64/Fussball-Tippspiel-Beat/main"
UPDATE_SRC="$DIR/config/update_source.txt"
# URL validieren und reparieren falls nötig
if [ -f "$UPDATE_SRC" ]; then
    BASE=$(tr -d '[:space:]' < "$UPDATE_SRC")
    if [[ "$BASE" != https://* ]]; then
        echo "   (update_source.txt ungültig – setze Standard-URL)"
        echo "$FALLBACK_BASE" > "$UPDATE_SRC"
        BASE="$FALLBACK_BASE"
    fi
else
    BASE="$FALLBACK_BASE"
fi
if [ -n "$BASE" ]; then
    echo "→ Code-Update von GitHub …"
    TOOLS="wm_auto.py wm_chart.py gen_rangliste.py debug_zusatz.py fetch_em_archiv.py fetch_wm_archiv.py wm2026_squads.py tippspiel_server.py"
    UPDATED=0
    for f in $TOOLS; do
        if curl -sf --max-time 15 "$BASE/tools/$f" -o "$DIR/tools/$f.tmp" 2>/dev/null; then
            mv "$DIR/tools/$f.tmp" "$DIR/tools/$f"
            UPDATED=$((UPDATED + 1))
        else
            rm -f "$DIR/tools/$f.tmp"
        fi
    done
    if curl -sf --max-time 30 "$BASE/web/WM_Rangverlauf.html" -o "$DIR/web/WM_Rangverlauf.html.tmp" 2>/dev/null; then
        mv "$DIR/web/WM_Rangverlauf.html.tmp" "$DIR/web/WM_Rangverlauf.html"
        UPDATED=$((UPDATED + 1))
    else
        rm -f "$DIR/web/WM_Rangverlauf.html.tmp"
    fi
    if curl -sf --max-time 15 "$BASE/web/index.html" -o "$DIR/web/index.html.tmp" 2>/dev/null; then
        mv "$DIR/web/index.html.tmp" "$DIR/web/index.html"
        UPDATED=$((UPDATED + 1))
    else
        rm -f "$DIR/web/index.html.tmp"
    fi
    if [ $UPDATED -gt 0 ]; then
        echo "   ✓ $UPDATED Dateien aktualisiert"
    else
        echo "   (offline oder keine Änderungen)"
    fi
    echo ""
fi

# ── Update-Server starten (falls noch nicht aktiv) ─────────────
SERVER_PY="$DIR/tools/tippspiel_server.py"
if [ -f "$SERVER_PY" ] && ! curl -sf --max-time 1 http://localhost:7373/status >/dev/null 2>&1; then
    nohup python3 "$SERVER_PY" > /tmp/tippspiel_server.log 2>&1 &
    disown
    sleep 2
fi

# Mitgliederliste neu laden falls gruppen.txt oder zusatz_spieler.csv neuer als teilnehmer.json
GRUPPEN="$DIR/config/gruppen.txt"
TEILNEHMER="$DIR/config/teilnehmer.json"
ZUSATZ="$DIR/data/zusatz_spieler.csv"
RELOAD_MEMBERS=0
if [ -f "$GRUPPEN" ] && { [ ! -f "$TEILNEHMER" ] || [ "$GRUPPEN" -nt "$TEILNEHMER" ]; }; then
    RELOAD_MEMBERS=1
fi
if [ -f "$ZUSATZ" ] && [ -f "$TEILNEHMER" ] && [ "$ZUSATZ" -nt "$TEILNEHMER" ]; then
    RELOAD_MEMBERS=1
fi
if [ $RELOAD_MEMBERS -eq 1 ]; then
    echo "→ Mitgliederliste aktualisieren …"
    python3 "$DIR/config/find_gruppe.py"
    echo ""
fi

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

echo "   (Fenster schliesst in 5 Sekunden …)"
sleep 5
osascript -e 'tell application "Terminal" to close front window' 2>/dev/null || true
