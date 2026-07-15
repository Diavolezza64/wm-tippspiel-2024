# 🏆 Fussball Tippspiel

Automatische Auswertung deiner SRF Fussball-Tippspiel-Gruppe.  
Das Script holt die aktuellen Daten vom SRF-Server und erstellt ein lokales HTML-Dashboard.

---

## 📥 Installation (einmalig)

1. Oben rechts auf **Code → Download ZIP** klicken
2. ZIP entpacken (z.B. in den Downloads-Ordner)
3. Ordner öffnen
4. Datei `config/gruppen.txt.example` kopieren und umbenennen zu `config/gruppen.txt`
5. `config/gruppen.txt` öffnen und deine **Gruppen-ID** eintragen  
   *(Zahl aus der SRF-URL: `wmtippspiel.srf.ch/gruppe/`**12345**)*

---

## ▶️ Starten

| Betriebssystem | Datei |
|---|---|
| Mac | `Start Mac.command` doppelklicken |
| Windows | `Start PC.bat` doppelklicken |

Das Script:
- Holt die aktuellen Tipps und Resultate von SRF
- Erstellt das Dashboard (`web/WM_Rangverlauf.html`)
- Öffnet das Dashboard automatisch im Browser

---

## 5️⃣ GitHub einrichten (optional, für Smartphone-Zugriff)

Damit das Dashboard auch auf dem Handy abrufbar ist, einmalig:

1. GitHub-Konto erstellen auf [github.com](https://github.com) (falls noch nicht vorhanden)
2. Persönlichen Token erstellen:  
   → github.com → Profilbild → Settings → Developer Settings  
   → Personal access tokens → Tokens (classic) → **Generate new token**  
   → Berechtigungen: **repo** (alle ankreuzen) → Token kopieren
3. Token in die Datei `config/github_token.txt` eintragen
4. **`Setup GitHub.bat`** doppelklicken → richtet alles vollautomatisch ein
5. GitHub Pages aktivieren: link wird am Ende von Schritt 4 angezeigt

Ab dann lädt `Start PC.bat` das Dashboard täglich automatisch auf GitHub hoch.

---

## 🔑 Voraussetzungen

**Eingeloggt sein beim SRF Tippspiel**  
Das Script liest die Login-Cookies aus dem Browser.

- **Mac:** Safari, Chrome oder Edge
- **Windows:** unbedingt **Microsoft Edge** verwenden  
  *(Chrome auf Windows benötigt Admin-Rechte für den Cookie-Zugriff)*

**Python 3** muss installiert sein:
- Mac: meist vorinstalliert, sonst [python.org](https://python.org)
- Windows: `Start PC.bat` installiert Python automatisch via Winget, falls es fehlt

---

## 📊 Dashboard

Nach dem Start öffnet sich `web/index.html` im Browser mit:

| Ansicht | Inhalt |
|---|---|
| Rangliste | Punkte aller Teilnehmer im Vergleich |
| Verlauf | Rangentwicklung über alle Spieltage |
| Details | Einzelne Tipps pro Spieler |

---

## ℹ️ Hinweise

- Die `data/` und `output/` Ordner werden beim Start automatisch neu erstellt
- Auf dem **Smartphone** ist das Dashboard über [GitHub Pages](https://diavolezza64.github.io/Fussball-Tippspiel-Beat/) abrufbar
- ZIP-Downloads können **keine Daten auf GitHub zurückschreiben** — nur der Original-Ordner mit Git-Einrichtung kann pushen
