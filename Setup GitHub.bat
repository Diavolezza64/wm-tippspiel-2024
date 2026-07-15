@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ╔══════════════════════════════════════════════════════════╗
echo ║  GitHub einrichten – vollautomatisch                    ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: Git prüfen
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: Git ist nicht installiert.
    echo Bitte von https://git-scm.com herunterladen und installieren.
    pause & exit /b 1
)

:: Token prüfen
if not exist "config\github_token.txt" (
    echo FEHLER: config\github_token.txt nicht gefunden.
    echo Bitte GitHub-Token dort eintragen.
    pause & exit /b 1
)
set /p GH_TOKEN=<"config\github_token.txt"

:: Python für API-Abfragen
set PYTHON_CMD=
where py >nul 2>&1 && set PYTHON_CMD=py -3
if "!PYTHON_CMD!"=="" where python3 >nul 2>&1 && set PYTHON_CMD=python3
if "!PYTHON_CMD!"=="" where python >nul 2>&1 && set PYTHON_CMD=python

if "!PYTHON_CMD!"=="" (
    echo FEHLER: Python nicht gefunden.
    pause & exit /b 1
)

:: GitHub Username + Email vom Token holen, Repo-Name aus turnier.json
echo Lese GitHub-Konto und Turnier-Infos ...
!PYTHON_CMD! -c "
import urllib.request, json, os, sys
token = open('config/github_token.txt').read().strip()
req = urllib.request.Request('https://api.github.com/user',
    headers={'Authorization': f'token {token}', 'User-Agent': 'tippspiel'})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    user = json.loads(resp.read())
    login = user.get('login','')
    name  = user.get('name', login)
    email = user.get('email','') or f'{login}@github.com'
    print(f'LOGIN={login}')
    print(f'NAME={name}')
    print(f'EMAIL={email}')
except Exception as e:
    print(f'FEHLER={e}', file=sys.stderr)
    sys.exit(1)

# Turnier-Info
try:
    t = json.load(open('config/turnier.json', encoding='utf-8'))
    kuerzel = t.get('kuerzel','WM')
    jahr    = t.get('jahr','2026')
    tname   = t.get('name', f'{kuerzel} {jahr}')
    repo    = f'Fussball-Tippspiel-{kuerzel}{jahr}'
    print(f'REPO={repo}')
    print(f'TNAME={tname}')
except:
    print('REPO=Fussball-Tippspiel')
    print('TNAME=Fussball Tippspiel')
" > "%TEMP%\gh_info.txt" 2>&1
if %errorlevel% neq 0 (
    echo FEHLER beim Abrufen der GitHub-Infos:
    type "%TEMP%\gh_info.txt"
    pause & exit /b 1
)

for /f "tokens=1,* delims==" %%a in (%TEMP%\gh_info.txt) do set %%a=%%b
echo   Benutzer : %LOGIN% ^(%NAME%^)
echo   Turnier  : %TNAME%
echo   Repo     : %REPO%
echo.

:: Repo auf GitHub erstellen (falls nicht vorhanden)
echo Erstelle GitHub-Repository (falls nötig) ...
!PYTHON_CMD! -c "
import urllib.request, json, sys
token = open('config/github_token.txt').read().strip()
repo  = '%REPO%'
# Check if exists
req = urllib.request.Request(f'https://api.github.com/repos/%LOGIN%/{repo}',
    headers={'Authorization': f'token {token}', 'User-Agent': 'tippspiel'})
try:
    urllib.request.urlopen(req, timeout=10)
    print('EXISTS')
except urllib.error.HTTPError as e:
    if e.code == 404:
        # Create
        data = json.dumps({'name': repo, 'private': False, 'description': '%TNAME% Tippspiel'}).encode()
        req2 = urllib.request.Request('https://api.github.com/user/repos',
            data=data, headers={'Authorization': f'token {token}',
            'Content-Type': 'application/json', 'User-Agent': 'tippspiel'})
        urllib.request.urlopen(req2, timeout=15)
        print('CREATED')
    else:
        print(f'FEHLER: {e}', file=sys.stderr); sys.exit(1)
" 2>&1
if %errorlevel% neq 0 ( pause & exit /b 1 )

:: Repo-Info speichern
echo %LOGIN%/%REPO%> config\github_repo.txt

:: Git initialisieren
if not exist ".git" (
    git init -b main >nul 2>&1
    echo   ✓ Git Repository initialisiert
)

:: Remote setzen mit Token
git remote remove origin >nul 2>&1
git remote add origin https://%GH_TOKEN%@github.com/%LOGIN%/%REPO%.git

:: Git-Identität
git config user.email "%EMAIL%" >nul 2>&1
git config user.name "%NAME%" >nul 2>&1

:: Push
echo Lade Dateien auf GitHub ...
git add . >nul 2>&1
git commit -m "Ersteinrichtung %TNAME%" >nul 2>&1
git push -u origin main >nul 2>&1
if %errorlevel%==0 (
    echo.
    echo ╔══════════════════════════════════════════════════════════════════╗
    echo ║  Erfolgreich eingerichtet!                                      ║
    echo ╠══════════════════════════════════════════════════════════════════╣
    echo ║  GitHub Pages aktivieren:                                       ║
    echo ║  → github.com/%LOGIN%/%REPO%
    echo ║  → Settings → Pages → Branch: main → Save                      ║
    echo ║                                                                 ║
    echo ║  Dashboard: https://%LOGIN%.github.io/%REPO%/web/WM_Rangverlauf.html
    echo ╚══════════════════════════════════════════════════════════════════╝
) else (
    echo FEHLER beim Push. Bitte Token und Internet prüfen.
)
echo.
pause
