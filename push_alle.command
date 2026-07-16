#!/bin/bash
# ──────────────────────────────────────────────────────────────
# push_alle.command
# Beat's Master-Repo pushen + allgemeine Files an alle Satellites verteilen
# ──────────────────────────────────────────────────────────────

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

echo "🚀 Master-Push + Satellite-Update"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1) Beat's Repo pushen ─────────────────────────────────────
echo "→ Beat's Master-Repo wird gepusht …"
git add -A
if git diff --cached --quiet; then
    echo "   (keine lokalen Änderungen zum Committen)"
else
    git commit -m "Update $(date '+%Y-%m-%d %H:%M')"
fi
if git push; then
    echo "   ✅ Beat's GitHub aktualisiert"
else
    echo "   ❌ Push fehlgeschlagen"
    echo ""; echo "Drücke Enter zum Schliessen …"; read -r; exit 1
fi
echo ""

# ── 2) Satellites aktualisieren ───────────────────────────────
SATELLITES_FILE="$DIR/config/satellites.txt"
if [ ! -f "$SATELLITES_FILE" ]; then
    echo "⚠️  config/satellites.txt nicht gefunden – keine Satellites"
    echo ""; echo "Drücke Enter zum Schliessen …"; read -r; exit 0
fi

# Allgemeine Files – KEIN wm_auto.py (bleibt satellite-spezifisch)
# Keine Config-Files (teilnehmer.json, gruppen.txt etc.)
TOOL_FILES="wm_chart.py gen_rangliste.py debug_zusatz.py fetch_em_archiv.py fetch_wm_archiv.py wm2026_squads.py find_gruppe.py"

TOTAL=0
FAILED=0

while IFS= read -r REPO || [ -n "$REPO" ]; do
    # Leere Zeilen und Kommentare überspringen
    [[ -z "$REPO" || "$REPO" == \#* ]] && continue

    TOTAL=$((TOTAL + 1))
    REPO_NAME=$(basename "$REPO")
    echo "→ Satellite: $REPO"

    TMP=$(mktemp -d)

    if ! git clone "https://github.com/$REPO.git" "$TMP/$REPO_NAME" 2>/dev/null; then
        echo "   ❌ Klonen fehlgeschlagen"
        rm -rf "$TMP"
        FAILED=$((FAILED + 1))
        echo ""
        continue
    fi

    cd "$TMP/$REPO_NAME" || { rm -rf "$TMP"; continue; }

    # Tools kopieren
    UPDATED=0
    for f in $TOOL_FILES; do
        if [ -f "$DIR/tools/$f" ]; then
            cp "$DIR/tools/$f" "tools/$f" 2>/dev/null && UPDATED=$((UPDATED + 1))
        fi
    done

    # WM_Rangverlauf.html (Template mit aktuellem Layout)
    if [ -f "$DIR/web/WM_Rangverlauf.html" ]; then
        cp "$DIR/web/WM_Rangverlauf.html" "web/WM_Rangverlauf.html" 2>/dev/null && UPDATED=$((UPDATED + 1))
    fi

    git config user.email "b.nauer@bluewin.ch"
    git config user.name "Beat Nauer"
    git add -A

    if git diff --cached --quiet; then
        echo "   (keine Änderungen – alles aktuell)"
    else
        git commit -m "Master-Update $(date '+%Y-%m-%d %H:%M')" 2>/dev/null
        if git push 2>/dev/null; then
            echo "   ✅ $UPDATED Dateien aktualisiert und gepusht"
        else
            echo "   ❌ Push fehlgeschlagen"
            FAILED=$((FAILED + 1))
        fi
    fi

    rm -rf "$TMP"
    cd "$DIR" || exit 1
    echo ""
done < "$SATELLITES_FILE"

# ── Zusammenfassung ───────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $FAILED -eq 0 ]; then
    echo "✅ Fertig – $TOTAL Satellite(s) aktualisiert"
else
    echo "⚠️  $FAILED von $TOTAL Satellite(s) fehlgeschlagen"
fi
echo ""
echo "Drücke Enter zum Schliessen …"
read -r
