#!/usr/bin/env python3
"""
Tippspiel – Tägliche Automatisierung
Liest Browser-Cookies, ruft Daten von SRF ab,
erstellt Tipps-CSV, Rangverlauf-CSV, PDF-Chart und Rangliste-PDF.

Das aktive Turnier wird aus config/turnier.json gelesen.
Alle Dateien liegen im selben Ordner wie dieses Script (iCloud-Ordner).

Voraussetzungen (einmalig):
    pip install requests browser-cookie3 beautifulsoup4 matplotlib reportlab --break-system-packages

Aufruf:
    python3 "/Users/nauer.beat/Library/Mobile Documents/com~apple~CloudDocs/2 Freizeit/Fussball Tippspiel/tools/wm_auto.py"
"""

import sys, os, json, csv, time, subprocess, glob, re, struct, shutil
from datetime import datetime

# Alle Pfade relativ zum Projekt-Stammverzeichnis
# wm_auto.py liegt in tools/ → Stammverzeichnis = eine Ebene höher
TOOLS_DIR  = os.path.dirname(os.path.abspath(__file__))
SCRIPT_DIR = os.path.dirname(TOOLS_DIR)          # Projekt-Root
BASE_DIR   = SCRIPT_DIR
WEB_DIR    = os.path.join(SCRIPT_DIR, 'web')     # HTML-Dateien
CONFIG_DIR = os.path.join(SCRIPT_DIR, 'config')
DATA_DIR   = os.path.join(SCRIPT_DIR, 'data')
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'output')
for _d in (CONFIG_DIR, DATA_DIR, OUTPUT_DIR):
    os.makedirs(_d, exist_ok=True)

# ── Turnierkonfiguration ──────────────────────────────────────
def _load_turnier():
    """Liest das aktive Turnier aus config/turnier.json."""
    path = os.path.join(CONFIG_DIR, 'turnier.json')
    if not os.path.exists(path):
        # Rückwärtskompatibilität: Defaults für WM 2026
        return {
            'name': 'WM 2026', 'kuerzel': 'WM', 'jahr': '2026',
            'srf_host': 'wmtippspiel.srf.ch',
            'torschuetzen_url': 'https://www.fussballdaten.de/wm/tore/',
            'smb_subfolder': 'Fussball Tippspiel 2026',
            'html_datei': 'WM_Rangverlauf.html',
        }
    with open(path, encoding='utf-8') as f:
        t = json.load(f)
    print(f'   Turnier: {t["name"]}  |  SRF: {t["srf_host"]}')
    return t

TURNIER  = _load_turnier()
BASE_URL = f'https://{TURNIER["srf_host"]}'
KUERZEL  = TURNIER.get('kuerzel', 'WM')

# ── Aufräumen: pro Datei-Gruppe nur die neueste Version behalten ──────────────
def cleanup_old_files():
    """Löscht veraltete datierte Dateien – behält nur die jeweils neueste."""
    k = KUERZEL
    DATED_GROUPS = [
        (DATA_DIR,   f'{k}_Rangverlauf_????-??-??.csv'),
        (DATA_DIR,   f'{k}_Tipps_????-??-??.csv'),
        (OUTPUT_DIR, f'{k}_Rangliste_????-??-??.pdf'),
        (OUTPUT_DIR, f'{k}_RangverlaufChart_????-??-??.pdf'),
        (OUTPUT_DIR, f'{k}_Rangverlauf_????-??-??.pdf'),
    ]
    deleted = []
    for search_dir, pattern in DATED_GROUPS:
        files = sorted(glob.glob(os.path.join(search_dir, pattern)))
        for old in files[:-1]:   # alle ausser dem neuesten löschen
            try:
                os.remove(old)
                deleted.append(os.path.basename(old))
            except Exception as e:
                print(f'   ⚠️  Konnte nicht löschen: {os.path.basename(old)} ({e})')
    # __pycache__ entfernen
    for d in (SCRIPT_DIR, os.path.join(SCRIPT_DIR, 'tools')):
        pycache = os.path.join(d, '__pycache__')
        if os.path.isdir(pycache):
            shutil.rmtree(pycache, ignore_errors=True)
            deleted.append('__pycache__/')
    if deleted:
        print(f'   🗑️  Gelöscht: {", ".join(deleted)}')
    else:
        print('   Keine alten Dateien zum Aufräumen.')

def _auto_update_members():
    """
    Prüft ob gruppen.txt existiert und ob sie neuer ist als teilnehmer.json.
    Falls gruppen.txt fehlt → Ersteinrichtung anleiten.
    Falls gruppen.txt neuer → find_gruppe.py automatisch ausführen.
    """
    gruppen_txt   = os.path.join(CONFIG_DIR, 'gruppen.txt')
    example_txt   = os.path.join(CONFIG_DIR, 'gruppen.txt.example')
    teilnehmer    = os.path.join(CONFIG_DIR, 'teilnehmer.json')
    find_script   = os.path.join(CONFIG_DIR, 'find_gruppe.py')

    # Ersteinrichtung: gruppen.txt fehlt
    if not os.path.exists(gruppen_txt):
        print()
        print('╔══════════════════════════════════════════════════════════╗')
        print('║  ERSTEINRICHTUNG – Gruppen-ID fehlt                     ║')
        print('╠══════════════════════════════════════════════════════════╣')
        print('║  1. Datei öffnen:  config/gruppen.txt.example           ║')
        print('║  2. Kopieren als:  config/gruppen.txt                   ║')
        print('║  3. Deine Gruppen-ID eintragen (Zahl aus der SRF-URL)   ║')
        print('║  4. Dieses Script erneut starten                        ║')
        print('╚══════════════════════════════════════════════════════════╝')
        print()
        sys.exit(0)

    # Gruppen-ID prüfen (darf nicht Platzhalter sein)
    with open(gruppen_txt, 'r', encoding='utf-8') as f:
        ids = [l.strip() for l in f if l.strip() and not l.startswith('#')]
    if not ids or ids[0] == 'XXXXX':
        print()
        print('╔══════════════════════════════════════════════════════════╗')
        print('║  EINRICHTUNG – Bitte Gruppen-ID eintragen               ║')
        print('║  Datei:  config/gruppen.txt                             ║')
        print('║  Inhalt: Deine Gruppen-ID (Zahl aus der SRF-URL)        ║')
        print('╚══════════════════════════════════════════════════════════╝')
        print()
        sys.exit(0)

    if not os.path.exists(find_script):
        return

    gruppen_mtime    = os.path.getmtime(gruppen_txt)
    find_mtime       = os.path.getmtime(find_script) if os.path.exists(find_script) else 0
    teilnehmer_mtime = os.path.getmtime(teilnehmer) if os.path.exists(teilnehmer) else 0

    if gruppen_mtime <= teilnehmer_mtime and find_mtime <= teilnehmer_mtime:
        return  # teilnehmer.json ist aktuell

    if find_mtime > teilnehmer_mtime:
        print('⚠️  find_gruppe.py wurde aktualisiert → Mitglieder + Zusatzfragen werden neu geladen …')
    else:
        print('⚠️  gruppen.txt wurde geändert → Mitglieder werden neu geladen …')
    result = subprocess.run(
        [sys.executable, find_script],
        capture_output=False
    )
    if result.returncode != 0:
        print('❌  find_gruppe.py fehlgeschlagen – bitte manuell ausführen.')
        sys.exit(1)
    print('✅  Mitglieder aktualisiert.')

ZUSATZ_ANTWORTEN = {}  # {name: {wm, ch, t_ch, t_k, nullnull}} – aus teilnehmer.json

def _parse_ausschluss():
    """Liest config/ausschluss.txt. Unterstützt 'ID;Name' und 'Name'-Format.
    Gibt (excluded_ids: set, excluded_names: set) zurück."""
    ausschluss_path = os.path.join(CONFIG_DIR, 'ausschluss.txt')
    excl_ids, excl_names = set(), set()
    if os.path.exists(ausschluss_path):
        with open(ausschluss_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ';' in line:
                    parts = line.split(';', 1)
                    excl_ids.add(parts[0].strip())
                    excl_names.add(parts[1].strip().lower())
                else:
                    excl_names.add(line.lower())
    return excl_ids, excl_names

def _load_members():
    """Lädt Teilnehmerliste aus config/teilnehmer.json + data/zusatz_spieler.csv.
    Ausschluss per ID (primär) oder Name (Fallback) via config/ausschluss.txt.
    Zusatzfragen-Antworten werden aus 'zusatz'-Feld in JSON in ZUSATZ_ANTWORTEN gespeichert."""
    global ZUSATZ_ANTWORTEN
    path = os.path.join(CONFIG_DIR, 'teilnehmer.json')
    if not os.path.exists(path):
        _auto_update_members()   # find_gruppe.py automatisch ausführen
    if not os.path.exists(path):
        raise FileNotFoundError(
            f'Teilnehmerliste fehlt: {path}\n'
            f'Bitte config/find_gruppe.py ausführen um die Teilnehmer zu laden.'
        )
    with open(path, encoding='utf-8') as f:
        members = json.load(f)

    # Zusatzfragen-Antworten aus JSON extrahieren
    for m in members:
        if m.get('zusatz'):
            ZUSATZ_ANTWORTEN[m['name']] = dict(m['zusatz'])
        m.pop('zusatz', None)  # nicht in MEMBERS-Liste behalten

    # Ausschluss per ID (primär) oder Name (Fallback)
    excl_ids, excl_names = _parse_ausschluss()
    def is_excluded(m):
        return m['id'] in excl_ids or m['name'].lower() in excl_names
    members = [m for m in members if not is_excluded(m)]

    # Zusätzliche Spieler aus data/zusatz_spieler.csv hinzufügen
    extra_path = os.path.join(BASE_DIR, 'data', 'zusatz_spieler.csv')
    if os.path.exists(extra_path):
        existing_ids = {m['id'] for m in members}
        with open(extra_path, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                eid  = row.get('id',   '').strip()
                ename = row.get('name', '').strip()
                if eid and ename and eid not in existing_ids:
                    if eid not in excl_ids and ename.lower() not in excl_names:
                        members.append({'id': eid, 'name': ename, 'rank': len(members) + 1})
                        existing_ids.add(eid)

    if excl_ids or excl_names:
        all_excl = sorted(excl_names | excl_ids)
        print(f'   Ausgeschlossen: {", ".join(all_excl)}')
    if ZUSATZ_ANTWORTEN:
        print(f'   Zusatzfragen-Antworten geladen: {len(ZUSATZ_ANTWORTEN)} Einträge')
    print(f'   Teilnehmer geladen: {len(members)} (inkl. Zusatzspieler)')
    return members

_auto_update_members()
MEMBERS = _load_members()

# ── Abhängigkeiten installieren ───────────────────────────────
def ensure_deps():
    needed = []
    try: import requests
    except ImportError: needed.append('requests')
    try: import browser_cookie3
    except ImportError: needed.append('browser-cookie3')
    try: from bs4 import BeautifulSoup
    except ImportError: needed.append('beautifulsoup4')

    if needed:
        print('Installiere:', ' '.join(needed))
        subprocess.run([sys.executable, '-m', 'pip', 'install',
                        *needed, '-q'], check=True)

ensure_deps()

import requests
import browser_cookie3
from bs4 import BeautifulSoup

# ── Browser-Session aufbauen (Mac: Safari/Chrome, Windows: Chrome/Edge/Firefox) ──
def make_session():
    import platform
    _UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
           'AppleWebKit/605.1.15 (KHTML, like Gecko) '
           'Version/17.0 Safari/605.1.15')

    is_mac = platform.system() == 'Darwin'
    if is_mac:
        browsers = [
            ('Safari', lambda: browser_cookie3.safari(domain_name='.srf.ch')),
            ('Chrome', lambda: browser_cookie3.chrome(domain_name='.srf.ch')),
        ]
    else:
        browsers = [
            ('Chrome',  lambda: browser_cookie3.chrome(domain_name='.srf.ch')),
            ('Edge',    lambda: browser_cookie3.edge(domain_name='.srf.ch')),
            ('Firefox', lambda: browser_cookie3.firefox(domain_name='.srf.ch')),
        ]

    for browser_name, load_cookies in browsers:
        try:
            cj = load_cookies()
            s  = requests.Session()
            s.cookies = cj
            s.headers.update({
                'User-Agent': _UA,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'de-CH,de;q=0.9,en;q=0.8',
                'Referer': BASE_URL + '/',
            })
            # Login-Check: eingeloggte User haben einen /users/-Link auf der Startseite
            resp = s.get(BASE_URL + '/', timeout=15)
            if re.search(r'/users/[^/"]{3,}', resp.text):
                print(f'   Browser: {browser_name} ✓')
                return s
            print(f'   {browser_name}: Cookies gefunden, aber nicht eingeloggt – übersprungen')
        except Exception as e:
            print(f'   {browser_name}: {e}')

    print('\n⚠️  Kein Browser mit aktiver Session auf wmtippspiel.srf.ch gefunden.')
    print('   Bitte in Safari oder Chrome auf wmtippspiel.srf.ch einloggen.')
    sys.exit(1)

# ── Runden ermitteln ─────────────────────────────────────────
def get_rounds(session):
    for path in ['/users/a3nm', '/']:
        try:
            resp = session.get(BASE_URL + path, timeout=20)
            doc  = BeautifulSoup(resp.text, 'html.parser')
            el   = doc.find(attrs={'data-react-class': 'SelectRaceweek/index'})
            if not el:
                continue
            opts = json.loads(el['data-react-props']).get('options', [])
            rounds = []
            for o in opts:
                if o.get('cancelled'):
                    continue
                m = re.search(r'/round/(\d+)', o.get('url', ''))
                if m:
                    rounds.append({'id': m.group(1), 'name': o['name']})
            if rounds:
                return rounds
        except Exception as e:
            print(f'  Runden-Fehler bei {path}: {e}')
    print('⚠️  Keine Runden gefunden. Login überprüfen.')
    sys.exit(1)

# ── Daten abrufen ─────────────────────────────────────────────
def fetch_all(session, rounds):
    games_meta  = {}
    player_data = {m['id']: {} for m in MEMBERS}
    total = len(MEMBERS) * len(rounds)
    done  = 0

    for m in MEMBERS:
        for r in rounds:
            url = f'/round/{r["id"]}' if m['id'] == 'XbPvY' \
                  else f'/users/{m["id"]}/round/{r["id"]}'
            try:
                resp = session.get(BASE_URL + url, timeout=20)
                doc  = BeautifulSoup(resp.text, 'html.parser')
                for el in doc.find_all(attrs={'data-react-class': 'ScoreBet'}):
                    b      = json.loads(el['data-react-props'])['bet']
                    bet_id = b['bet_id']
                    if bet_id not in games_meta:
                        teams = b.get('teams') or []
                        games_meta[bet_id] = {
                            'bet_id':       bet_id,
                            'event_date':   b['event_date'],
                            'roundName':    r['name'],
                            'match':        f"{teams[0]['name'] if teams else '?'} vs "
                                            f"{teams[1]['name'] if len(teams) > 1 else '?'}",
                            'final_results': b.get('final_results'),
                            'meta_location': b.get('meta_location') or '',
                        }
                    picks = b.get('picks') or []
                    player_data[m['id']][bet_id] = {
                        'picks': picks if len(picks) >= 2 else None,
                        'score': b.get('total_score'),
                    }
            except Exception as e:
                print(f'  ⚠️  {m["name"]} Runde {r["id"]}: {e}')
            done += 1
            if done % 8 == 0:
                print(f'  {done}/{total}  {m["name"]}  Runde {r["id"]}')
            time.sleep(0.2)

    return games_meta, player_data

# ── CSVs schreiben ────────────────────────────────────────────
def write_csvs(games_meta, player_data, today, zusatz_data=None):
    sorted_games = sorted(games_meta.values(),
                          key=lambda g: g['event_date'])
    played_games = [g for g in sorted_games
                    if g.get('final_results') and len(g['final_results']) >= 2]

    # Tabelle 1: Tipps
    rows1 = [['Rang','Name','Runde','Datum','Uhrzeit','Stadion','Spiel','Tipp','Resultat','Punkte']]
    for m in MEMBERS:
        for g in sorted_games:
            pd = player_data[m['id']].get(g['bet_id'])
            if not pd or not pd['picks']:
                continue
            d = datetime.fromisoformat(g['event_date'].replace('Z','+00:00'))
            rows1.append([
                m['rank'], m['name'], g['roundName'],
                d.strftime('%d.%m.%Y'), d.strftime('%H:%M'),
                g['meta_location'], g['match'],
                ':'.join(str(x) for x in pd['picks']),
                ':'.join(str(x) for x in g['final_results']) if g['final_results'] else '',
                pd['score'] if pd['score'] is not None else '',
            ])

    # Tabelle 2: Rangverlauf
    hdr2 = ['Spiel', 'Datum', 'Match']
    for m in MEMBERS:
        hdr2 += [m['name'] + ' Rang', m['name'] + ' Punkte kum.']
    rows2 = [hdr2]

    cum_pts    = {m['id']: 0 for m in MEMBERS}
    id_to_name = {m['id']: m['name'] for m in MEMBERS}

    # Bonus-Entscheidungs-Indizes: CH nach Schweiz-Ausscheidung, WM/etc. nach Finale
    _CH_NAMES_LW = ['schweiz', 'switzerland', 'suisse', 'svizzera']
    _finale_idx  = None
    _ch_last_idx = None
    for _idx, _g in enumerate(played_games):
        if _normalize_runde(_g.get('roundName', '')) == 'finale':
            _finale_idx = _idx
        if any(n in _g['match'].lower() for n in _CH_NAMES_LW):
            _ch_last_idx = _idx

    def get_bonus_at_game(m_id, game_idx):
        """Gestaffelter Bonus: CH-Bonus ab Schweiz' letztem Spiel, WM/Torsch./0:0 ab Finale."""
        name = id_to_name[m_id]
        zd   = (zusatz_data or {}).get(name, {})
        b    = 0
        if _ch_last_idx is not None and game_idx >= _ch_last_idx:
            b += zd.get('p_ch', 0) + zd.get('p_t_ch', 0)
        if _finale_idx is not None and game_idx >= _finale_idx:
            b += zd.get('p_wm', 0) + zd.get('p_t_k', 0) + zd.get('p_nullnull', 0)
        return b

    game_num = 0
    for game_idx, g in enumerate(played_games):
        for m in MEMBERS:
            pd = player_data[m['id']].get(g['bet_id'])
            cum_pts[m['id']] += (pd['score'] if pd and pd['score'] is not None else 0)

        sorted_m = sorted(MEMBERS, key=lambda m: cum_pts[m['id']] + get_bonus_at_game(m['id'], game_idx), reverse=True)
        ranks, prev_pts, prev_rank = {}, None, 0
        for i, m in enumerate(sorted_m):
            total = cum_pts[m['id']] + get_bonus_at_game(m['id'], game_idx)
            if total != prev_pts:
                prev_rank = i + 1
                prev_pts  = total
            ranks[m['id']] = prev_rank

        game_num += 1
        d   = datetime.fromisoformat(g['event_date'].replace('Z','+00:00'))
        row = [game_num, d.strftime('%d.%m.%Y'), g['match']]
        for m in MEMBERS:
            row += [ranks[m['id']], cum_pts[m['id']] + get_bonus_at_game(m['id'], game_idx)]
        rows2.append(row)

    def save_csv(rows, path):
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f, delimiter=';', quoting=csv.QUOTE_ALL)
            w.writerows(rows)

    p1 = os.path.join(DATA_DIR, f'{KUERZEL}_Tipps_{today}.csv')
    p2 = os.path.join(DATA_DIR, f'{KUERZEL}_Rangverlauf_{today}.csv')
    save_csv(rows1, p1)
    save_csv(rows2, p2)
    print(f'   ✅ {os.path.basename(p1)}  ({len(rows1)-1} Zeilen)')
    print(f'   ✅ {os.path.basename(p2)}  ({len(rows2)-1} Spiele)')
    return p2

# ── Finalspiele-Daten aufbereiten ────────────────────────────
# Mapping: (Datums-Präfix, Ortsschlüssel) → Bracket-Position
# Hardcoded R32-Teams (Reihenfolge = Bracket-Positionen 0–15)
# Fallback falls SRF-API-Matching via Datum+Venue fehlschlägt
_R32_HARDCODED = [
    ('Deutschland',     'Paraguay'),        # 0  Boston/Foxborough,   29.06
    ('Frankreich',      'Schweden'),        # 1  New York/MetLife,    30.06
    ('Südafrika',       'Kanada'),          # 2  Los Angeles/SoFi,    28.06
    ('Niederlande',     'Marokko'),         # 3  Monterrey,           29.06
    ('Portugal',        'Kroatien'),        # 4  Toronto,             02.07
    ('Spanien',         'Österreich'),      # 5  Los Angeles,         02.07
    ('USA',             'Bosnien-Herzeg.'), # 6  San Francisco/Levi,  01.07
    ('Belgien',         'Senegal'),         # 7  Seattle,             01.07
    ('Brasilien',       'Japan'),           # 8  Houston,             29.06
    ('Elfenbeinküste',  'Norwegen'),        # 9  Dallas,              30.06
    ('Mexiko',          'Ecuador'),         # 10 Mexiko-Stadt,        30.06
    ('England',         'DR Kongo'),        # 11 Atlanta,             01.07
    ('Argentinien',     'Kap Verde'),       # 12 Miami,               03.07
    ('Australien',      'Ägypten'),         # 13 Dallas,              03.07
    ('Schweiz',         'Algerien'),        # 14 Vancouver,           02.07
    ('Kolumbien',       'Ghana'),           # 15 Kansas City,         03.07
]

_FINALS_POS = {
    'r32': [
        ('2026-06-29', 'foxborough'),   # 0  Deutschland vs Paraguay
        ('2026-06-30', 'new york'),     # 1  Frankreich vs Schweden
        ('2026-06-28', 'los angeles'),  # 2  Südafrika vs Kanada
        ('2026-06-29', 'monterrey'),    # 3  Niederlande vs Marokko
        ('2026-07-02', 'toronto'),      # 4  Portugal vs Kroatien
        ('2026-07-02', 'los angeles'),  # 5  Spanien vs Österreich
        ('2026-07-01', 'santa clara'),  # 6  USA vs Bosnien (Levi's)
        ('2026-07-01', 'seattle'),      # 7  Belgien vs Senegal
        ('2026-06-29', 'houston'),      # 8  Brasilien vs Japan
        ('2026-06-30', 'dallas'),       # 9  Elfenbeinküste vs Norwegen
        ('2026-06-30', 'mexico'),       # 10 Mexiko vs Ecuador
        ('2026-07-01', 'atlanta'),      # 11 England vs DR Kongo
        ('2026-07-03', 'miami'),        # 12 Argentinien vs Kap Verde
        ('2026-07-03', 'dallas'),       # 13 Australien vs Ägypten
        ('2026-07-02', 'vancouver'),    # 14 Schweiz vs Algerien
        ('2026-07-03', 'kansas'),       # 15 Kolumbien vs Ghana
    ],
    'r16': [
        ('2026-07-04', 'philadelphia'),
        ('2026-07-04', 'houston'),
        ('2026-07-06', 'dallas'),
        ('2026-07-07', 'seattle'),
        ('2026-07-05', 'new york'),
        ('2026-07-08', 'mexico'),
        ('2026-07-07', 'atlanta'),
        ('2026-07-07', 'vancouver'),
    ],
    'qf': [
        ('2026-07-09', 'boston'),
        ('2026-07-10', 'los angeles'),
        ('2026-07-11', 'miami'),
        ('2026-07-12', 'kansas'),
    ],
    'sf': [
        ('2026-07-14', 'dallas'),
        ('2026-07-15', 'atlanta'),
    ],
    'f': [
        ('2026-07-19', 'new york'),
    ],
}

# Zusatzfragen-Punkte werden lokal aus Spieldaten berechnet (kein CSV mehr)
ZUSATZ_KEYS = ['wm', 'ch', 't_ch', 't_k', 'nullnull']
ZUSATZ_PTS_KEYS = ['p_wm', 'p_ch', 'p_t_ch', 'p_t_k', 'p_nullnull']

def _normalize_runde(runde):
    """Normalisiert Runden-Bezeichnungen für Vergleich (verschiedene Formate)."""
    if not runde:
        return ''
    r = str(runde).lower().strip().replace('-', '').replace(' ', '')
    if any(x in r for x in ['halbfinal', '1/2', 'semifinal']):  return 'halbfinale'
    if any(x in r for x in ['viertelfinal', '1/4', 'quarterfinal']): return 'viertelfinale'
    if any(x in r for x in ['achtelfinal', '1/8', 'roundof16']): return 'achtelfinale'
    if any(x in r for x in ['sechzehntel', '1/16', 'roundof32']): return 'sechzehntelfinale'
    if any(x in r for x in ['zweiunddrei', '1/32', 'roundof64']): return 'zweiunddreissigstefinale'
    if r in ('final', 'finale', 'f', '1/1'):                    return 'finale'
    if any(x in r for x in ['gruppe', 'vorrunde', 'group']):    return 'gruppenphase'
    return r

def calc_zusatz_punkte(games_meta):
    """Berechnet Bonus-Punkte für alle Spieler aus ZUSATZ_ANTWORTEN (teilnehmer.json).
    Richtige Antworten werden aus games_meta + Torschützenliste abgeleitet.
    Punkte: wm=50, ch/t_ch/t_k/nullnull=20 je."""
    if not ZUSATZ_ANTWORTEN:
        print('   (keine Zusatzantworten in teilnehmer.json – übersprungen)')
        return {}

    PUNKTE = {'wm': 50, 'ch': 20, 't_ch': 20, 't_k': 20, 'nullnull': 20}
    CH_NAMES = ['schweiz', 'switzerland', 'suisse', 'svizzera']
    RUNDEN_ORDER = ['gruppenphase', 'zweiunddreissigstefinale', 'sechzehntelfinale',
                    'achtelfinale', 'viertelfinale', 'halbfinale', 'finale']

    sorted_games = sorted(games_meta.values(), key=lambda g: g['event_date'])

    # Weltmeister: Sieger des Finales
    weltmeister = None
    for g in sorted_games:
        if _normalize_runde(g.get('roundName','')) == 'finale':
            fr = g.get('final_results')
            if fr and len(fr) >= 2:
                teams = g['match'].split(' vs ')
                if len(teams) == 2:
                    if fr[0] > fr[1]: weltmeister = teams[0].strip()
                    elif fr[1] > fr[0]: weltmeister = teams[1].strip()

    # Schweiz: höchste erreichte Runde
    ch_runde = 'gruppenphase'
    for g in sorted_games:
        if any(n in g['match'].lower() for n in CH_NAMES):
            rn = _normalize_runde(g.get('roundName', ''))
            if rn in RUNDEN_ORDER and RUNDEN_ORDER.index(rn) > RUNDEN_ORDER.index(ch_runde):
                ch_runde = rn

    # Tore Schweiz: alle Tore in allen Spielen
    ch_goals = 0
    for g in sorted_games:
        fr = g.get('final_results')
        if not fr or len(fr) < 2: continue
        parts = g['match'].split(' vs ')
        if len(parts) != 2: continue
        t1, t2 = parts[0].strip().lower(), parts[1].strip().lower()
        if any(n in t1 for n in CH_NAMES): ch_goals += fr[0]
        elif any(n in t2 for n in CH_NAMES): ch_goals += fr[1]

    # 0:0 Spiele
    nullnull = sum(1 for g in sorted_games
                   if g.get('final_results') and g['final_results'] == [0, 0])

    # Torschützenkönig: Tore des Führenden
    scorers, _ = fetch_torschuetzen()
    t_k = scorers[0]['tore'] if scorers else None

    # Finale gespielt? Nur dann WM, Torschützenkönig und 0:0 auswerten
    final_played = weltmeister is not None

    print(f'   Richtige Antworten: WM={weltmeister or "offen (Finale ausstehend)"}, '
          f'CH={ch_runde}, Tore CH={ch_goals}, '
          f'Torschützenkönig={t_k or "offen"} ({"final" if final_played else "offen"}), '
          f'0:0={nullnull} ({"final" if final_played else "offen"})')

    # Punkte pro Spieler berechnen
    zusatz = {}
    for name, ant in ZUSATZ_ANTWORTEN.items():
        entry = dict(ant)
        total = 0

        # Weltmeister (50 Punkte) – nur nach Finale
        p = 0
        if final_played and weltmeister and ant.get('wm'):
            if str(ant['wm']).strip().lower() == weltmeister.strip().lower():
                p = PUNKTE['wm']
        entry['p_wm'] = p; total += p

        # Schweiz Runde (20 Punkte) – sofort auswertbar
        p = 0
        if ant.get('ch') and _normalize_runde(ant['ch']) == ch_runde:
            p = PUNKTE['ch']
        entry['p_ch'] = p; total += p

        # Tore Schweiz (20 Punkte) – sofort auswertbar
        p = 0
        try:
            if ant.get('t_ch') is not None and int(ant['t_ch']) == ch_goals:
                p = PUNKTE['t_ch']
        except (ValueError, TypeError): pass
        entry['p_t_ch'] = p; total += p

        # Tore Torschützenkönig (20 Punkte) – nur nach Finale
        p = 0
        if final_played:
            try:
                if t_k is not None and ant.get('t_k') is not None and int(ant['t_k']) == t_k:
                    p = PUNKTE['t_k']
            except (ValueError, TypeError): pass
        entry['p_t_k'] = p; total += p

        # Anzahl 0:0 (20 Punkte) – nur nach Finale
        p = 0
        if final_played:
            try:
                if ant.get('nullnull') is not None and int(ant['nullnull']) == nullnull:
                    p = PUNKTE['nullnull']
            except (ValueError, TypeError): pass
        entry['p_nullnull'] = p; total += p

        entry['punkte'] = total
        zusatz[name] = entry

    print(f'   ✅ Zusatzpunkte berechnet: {len(zusatz)} Spieler')
    return zusatz


def build_finals_data(games_meta):
    """Ordnet KO-Spiele aus games_meta den Bracket-Positionen zu.
    Matching nur über Datum + Ort – unabhängig vom Rundennamen der API."""
    result = {key: [None] * len(pos) for key, pos in _FINALS_POS.items()}

    # Flaches Lookup: (datum, orts-schlüssel) → (rkey, pos-index)
    pos_lookup = {}
    for rkey, positions in _FINALS_POS.items():
        for idx, (d, v) in enumerate(positions):
            pos_lookup[(d, v)] = (rkey, idx)

    unmatched_ko = []
    for g in games_meta.values():
        date_pfx = g['event_date'][:10]
        venue_lc = (g.get('meta_location') or '').lower()
        # Suche den passenden Eintrag in pos_lookup
        match_key = None
        for (d, v), val in pos_lookup.items():
            if d == date_pfx and v in venue_lc:
                match_key = (d, v)
                break
        if not match_key:
            # KO-Spiel (nach Gruppenphase) aber kein Match → für Debug merken
            if date_pfx >= '2026-06-29':
                unmatched_ko.append(f'{date_pfx} | venue="{g.get("meta_location","")}" | {g["match"]}')
            continue
        rkey, idx = pos_lookup[match_key]
        teams = g['match'].split(' vs ')
        t1 = teams[0].strip() if teams else '?'
        t2 = teams[1].strip() if len(teams) > 1 else '?'
        fr  = g.get('final_results')
        res = ':'.join(str(x) for x in fr) if fr and len(fr) >= 2 else ''
        # Datum + Uhrzeit aus event_date extrahieren (in CEST = UTC+2)
        try:
            from datetime import timezone, timedelta
            CEST = timezone(timedelta(hours=2))
            dt = datetime.fromisoformat(g['event_date'].replace('Z','+00:00')).astimezone(CEST)
            h  = dt.strftime('%H:%M')
            DAYS_DE2 = ['Mo','Di','Mi','Do','Fr','Sa','So']
            d_str = f"{DAYS_DE2[dt.weekday()]} {dt.strftime('%d.%m')}"
        except Exception:
            h = ''
            d_str = ''
        result[rkey][idx] = {'t1': t1, 't2': t2, 'r': res, 'h': h, 'd': d_str}

    if unmatched_ko:
        print('   ⚠️  Ungematchte KO-Spiele (Venue-Namen für _FINALS_POS):')
        for line in sorted(set(unmatched_ko)):
            print(f'      {line}')

    # Fallback R32: Positionen die vom API-Matching nicht gefüllt wurden
    # → Teamname-Suche in games_meta für Resultat
    DAYS_DE = ['Mo','Di','Mi','Do','Fr','Sa','So']

    # Alias-Mapping: deutsche Namen → mögliche englische API-Namen
    _ALIASES = {
        'Mexiko': ['Mexico'], 'Brasilien': ['Brazil'], 'Ägypten': ['Egypt'],
        'Norwegen': ['Norway'], 'Schweiz': ['Switzerland'], 'Österreich': ['Austria'],
        'Spanien': ['Spain'], 'Schweden': ['Sweden'], 'Türkei': ['Turkey'],
        'Kolumbien': ['Colombia'], 'Südkorea': ['South Korea'], 'Südafrika': ['South Africa'],
        'Elfenbeinküste': ["Côte d'Ivoire", 'Ivory Coast'],
        'DR Kongo': ['Congo DR', 'DR Congo'], 'Kap Verde': ['Cape Verde'],
        'Neuseeland': ['New Zealand'], 'Schottland': ['Scotland'],
    }

    def find_game_by_teams(t1, t2):
        """Sucht in games_meta nach t1 vs t2 (inkl. Alias-Namen), gibt (res, h, d_str) zurück."""
        t1v = [t1] + _ALIASES.get(t1, [])
        t2v = [t2] + _ALIASES.get(t2, [])
        for g in games_meta.values():
            parts = g['match'].split(' vs ')
            if len(parts) < 2:
                continue
            g1, g2 = parts[0].strip(), parts[1].strip()
            m1 = any(v.lower() in g1.lower() or g1.lower() in v.lower() for v in t1v)
            m2 = any(v.lower() in g2.lower() or g2.lower() in v.lower() for v in t2v)
            if m1 and m2:
                fr = g.get('final_results')
                res = ':'.join(str(x) for x in fr) if fr and len(fr) >= 2 else ''
                try:
                    from datetime import timezone, timedelta
                    CEST = timezone(timedelta(hours=2))
                    dt = datetime.fromisoformat(g['event_date'].replace('Z','+00:00')).astimezone(CEST)
                    h = dt.strftime('%H:%M')
                    DAYS_DE = ['Mo','Di','Mi','Do','Fr','Sa','So']
                    d_str = f"{DAYS_DE[dt.weekday()]} {dt.strftime('%d.%m')}"
                except Exception:
                    h, d_str = '', ''
                return res, h, d_str
        return '', '', ''

    for idx, (t1, t2) in enumerate(_R32_HARDCODED):
        if result['r32'][idx] is None:
            res, h, d_str = find_game_by_teams(t1, t2)
            result['r32'][idx] = {'t1': t1, 't2': t2, 'r': res, 'h': h, 'd': d_str}
            if res:
                print(f'   ✅ R32[{idx}] {t1} vs {t2}: {res}')
    filled = sum(1 for x in result['r32'] if x)
    print(f'   R32-Bracket: {filled}/16 Positionen gefüllt (inkl. Hardcode-Fallback)')

    # ── Sieger-Propagation: r32→r16→qf→sf→f ─────────────────

    # ── Sieger-Propagation: r32→r16→qf→sf→f ─────────────────
    # NOTE: This runs BEFORE team-name fallback so propagation uses fresh r32 results.

    def get_winner(game):
        """Gibt den Sieger eines KO-Spiels zurück (None wenn noch kein Resultat)."""
        if not game or not game.get('r'):
            return None
        parts = game['r'].split(':')
        if len(parts) < 2:
            return None
        try:
            g1, g2 = int(parts[0]), int(parts[1])
        except ValueError:
            return None
        if g1 > g2:
            return game['t1']
        elif g2 > g1:
            return game['t2']
        return None  # Unentschieden (sollte in KO nicht vorkommen)

    propagation = [
        ('r32', 'r16'),
        ('r16', 'qf'),
        ('qf',  'sf'),
        ('sf',  'f'),
    ]
    for src_key, dst_key in propagation:
        src = result[src_key]
        dst = result[dst_key]
        for i in range(len(dst)):
            idx1, idx2 = 2*i, 2*i+1
            if idx1 >= len(src) or idx2 >= len(src):
                break
            w1 = get_winner(src[idx1])
            w2 = get_winner(src[idx2])
            if w1 or w2:
                existing = dst[i] or {}
                dst[i] = {
                    't1': w1 or existing.get('t1', ''),
                    't2': w2 or existing.get('t2', ''),
                    'r':  existing.get('r', ''),
                    'h':  existing.get('h', ''),
                    'd':  existing.get('d', ''),
                }
    prop_filled = sum(1 for key in ['r16','qf','sf','f'] for x in result[key] if x and (x.get('t1') or x.get('t2')))
    print(f'   Bracket-Propagation: {prop_filled} Slots mit Sieger-Teams gefüllt')

    # ── Team-Name-Fallback für alle KO-Runden (r16, qf, sf, f) ──
    # Falls Venue-Matching fehlt: Resultat aus games_meta via Team-Namen holen
    for ko_key in ['r16', 'qf', 'sf', 'f']:
        for idx, slot in enumerate(result[ko_key]):
            if slot is None:
                continue
            t1 = slot.get('t1', '')
            t2 = slot.get('t2', '')
            if not t1 or not t2:
                continue
            # Only fill if result or date/time is missing
            if slot.get('r') and slot.get('h') and slot.get('d'):
                continue
            res, h, d_str = find_game_by_teams(t1, t2)
            if res or h or d_str:
                updated = {
                    't1': t1,
                    't2': t2,
                    'r':  res if res else slot.get('r', ''),
                    'h':  h if h else slot.get('h', ''),
                    'd':  d_str if d_str else slot.get('d', ''),
                }
                result[ko_key][idx] = updated
                if res:
                    print(f'   ✅ {ko_key.upper()}[{idx}] {t1} vs {t2}: {res}')
    ko_results = sum(1 for key in ['r16','qf','sf','f'] for x in result[key] if x and x.get('r'))
    print(f'   KO-Resultate nach Fallback: {ko_results} Spiele mit Ergebnis')

    return result

# ── Torschützenliste von fussballdaten.de ────────────────────
def fetch_torschuetzen():
    """Scrapt die Top-Torschützen der WM von fussballdaten.de/wm/tore/.
    Tabellenstruktur: # | Spieler (img+Name+Verein) | Einsatzzeit | Min/Tor | Elfer | Tore
    Name wird aus dem Person-Link extrahiert, Land aus der Verein-Link-URL.
    Gibt (list[dict], str) zurück: Liste der Torschützen + Datum-String."""
    try:
        import urllib.request, re as _re, datetime as _dt
        url = TURNIER.get('torschuetzen_url', 'https://www.fussballdaten.de/wm/tore/')
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')

        rows = _re.findall(r'<tr[^>]*>.*?</tr>', html, _re.DOTALL)
        scorers = []
        for row in rows:
            cells_raw = _re.findall(r'<td[^>]*>(.*?)</td>', row, _re.DOTALL)
            if len(cells_raw) < 6:
                continue
            # Rang prüfen (erste Zelle, Text ohne Tags)
            rank_txt = _re.sub(r'<[^>]+>', '', cells_raw[0]).strip()
            try:
                rank = int(rank_txt)
            except ValueError:
                continue
            if rank < 1 or rank > 25:
                continue

            # Spieler-Zelle (cells_raw[1]): Name aus Person-Link, Land aus Verein-Link-URL
            spieler = cells_raw[1]
            name_m = _re.search(r'<a\s[^>]*href="[^"]*/person/[^"]*"[^>]*>([^<]+)</a>', spieler)
            name = name_m.group(1).strip() if name_m else _re.sub(r'<[^>]+>', ' ', spieler).strip()
            # Land aus Verein-URL: /vereine/argentinien/ → "Argentinien"
            land_m = _re.search(r'href="[^"]*/vereine/([^/?#"]+)', spieler)
            land = land_m.group(1).replace('-', ' ').title() if land_m else ''

            # Spalten: [0]=Rang, [1]=Spieler, [2]=Einsatzzeit(Min), [3]=Min/Tor, [4]=Elfer, [5]=Tore
            try:
                tore = int(_re.sub(r'[^\d]', '', cells_raw[5].strip()) or '0')
            except (ValueError, IndexError):
                continue
            try:
                einsatz = int(_re.sub(r'[^\d]', '', cells_raw[2].strip()) or '0')
            except (ValueError, IndexError):
                einsatz = 0

            if not name or tore < 1:
                continue
            scorers.append({
                'name': name,
                'land': land,
                'tore': tore,
                'spiele': einsatz,   # Einsatzzeit in Minuten (wird als "Min." angezeigt)
            })
            if len(scorers) >= 20:
                break

        if scorers:
            today = _dt.date.today().strftime('%d.%m.%Y')
            return scorers, today
        return [], ''
    except Exception as e:
        print(f'   ⚠️  fetch_torschuetzen Fehler: {e}')
        return [], ''

# ── SRF-Gruppenleaderboard laden ─────────────────────────────
def _parse_srf_user_entry(item):
    """Extrahiert Name, Score und Rang aus einem SRF-Leaderboard-Eintrag."""
    if not isinstance(item, dict):
        return None
    user = item.get('user') or item.get('bettor') or {}
    if not isinstance(user, dict):
        user = {}
    name = (user.get('nickname') or user.get('username') or user.get('name') or
            item.get('nickname') or item.get('username') or item.get('name') or '')
    if not name or len(name) < 2:
        return None
    score = None
    for k in ('total_score', 'score', 'points', 'totalScore', 'total'):
        v = item.get(k)
        if v is None:
            v = user.get(k)
        if isinstance(v, (int, float)):
            score = int(v); break
    rang = None
    for k in ('rank', 'position', 'ranking', 'place', 'pos'):
        v = item.get(k)
        if isinstance(v, int):
            rang = v; break
    if name and score is not None:
        return {'name': name, 'score': score, 'rank': rang}
    return None

def _parse_srf_lb_props(props, depth=0):
    """Rekursiv Leaderboard-Einträge aus React-Props extrahieren."""
    if depth > 6 or not isinstance(props, (dict, list)):
        return []
    if isinstance(props, dict):
        for key in ('leaderboard', 'entries', 'rankers', 'rankings',
                    'members', 'bettors', 'items', 'results', 'data'):
            val = props.get(key)
            if isinstance(val, list) and len(val) >= 3:
                entries = [e for e in (_parse_srf_user_entry(x) for x in val) if e]
                if len(entries) >= 3:
                    return entries
        for v in props.values():
            if isinstance(v, (dict, list)):
                r = _parse_srf_lb_props(v, depth+1)
                if len(r) >= 3:
                    return r
    elif isinstance(props, list) and len(props) >= 3:
        entries = [e for e in (_parse_srf_user_entry(x) for x in props) if e]
        if len(entries) >= 3:
            return entries
        for item in props:
            r = _parse_srf_lb_props(item, depth+1)
            if len(r) >= 3:
                return r
    return []

def fetch_srf_leaderboard(session):
    """
    Lädt das offizielle SRF-Gruppenleaderboard.
    Gibt dict {name → {srf_punkte, srf_rang}} zurück.
    """
    from bs4 import BeautifulSoup
    gruppen_txt = os.path.join(CONFIG_DIR, 'gruppen.txt')
    group_ids = []
    if os.path.exists(gruppen_txt):
        with open(gruppen_txt, encoding='utf-8') as f:
            for line in f:
                line = line.split('#')[0].strip()
                if line:
                    group_ids.append(line)
    if not group_ids:
        print('   ⚠️  SRF-Leaderboard: keine Gruppen-IDs in gruppen.txt')
        return {}
    base_url = f'https://{TURNIER["srf_host"]}'
    result = {}
    for group_id in group_ids:
        for prefix in ('leagues', 'ligen', 'communities', 'groups'):
            url = f'{base_url}/{prefix}/{group_id}'
            try:
                resp = session.get(url, timeout=20)
                if resp.status_code != 200:
                    continue
                doc = BeautifulSoup(resp.text, 'html.parser')
                for el in doc.find_all(attrs={'data-react-class': True}):
                    try:
                        props = json.loads(el['data-react-props'])
                        entries = _parse_srf_lb_props(props)
                        if len(entries) >= 3:
                            for pos, e in enumerate(entries, 1):
                                result[e['name']] = {
                                    'srf_punkte': e['score'],
                                    'srf_rang':   e['rank'] if e['rank'] is not None else pos
                                }
                            if result:
                                print(f'   ✅ SRF-Leaderboard: {len(result)} Einträge ({url})')
                                return result
                    except Exception:
                        pass
                time.sleep(0.2)
            except Exception as e:
                print(f'   ⚠️  SRF-Leaderboard {url}: {e}')
    print('   ⚠️  SRF-Leaderboard: Daten nicht gefunden')
    return {}

# ── Daten in HTML einbetten ───────────────────────────────────
def embed_in_html(rang_path, tipps_path, games_meta=None, zusatz_data=None, srf_lb=None):
    html_path = os.path.join(WEB_DIR, TURNIER.get('html_datei', 'WM_Rangverlauf.html'))
    if not os.path.exists(html_path):
        print(f'⚠️  {os.path.basename(html_path)} nicht gefunden – HTML wird nicht aktualisiert.')
        return

    # Rangverlauf-Daten parsen
    with open(rang_path, encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=';')
        header = next(reader)
        rows = [r for r in reader if r and r[0].strip()]

    members = [header[i].replace(' Rang', '').strip() for i in range(3, len(header), 2)]
    N = len(members)
    game_nums, game_dates, game_names = [], [], []
    ranks  = [[] for _ in range(N)]
    points = [[] for _ in range(N)]
    for row in rows:
        game_nums.append(int(row[0]))
        game_dates.append(row[1])
        game_names.append(row[2])
        for p in range(N):
            ranks [p].append(int(row[3 + p*2])     if row[3 + p*2].strip()     else 0)
            points[p].append(int(row[3 + p*2 + 1]) if row[3 + p*2 + 1].strip() else 0)

    # Spielresultate: primär aus games_meta (authoritative), Fallback aus Tipps-CSV Spalte I
    game_result_map = {}  # match-name → Resultat

    # 1) Aus games_meta (direkt von SRF-API, immer vollständig)
    if games_meta:
        for g in games_meta.values():
            if g.get('final_results') and len(g['final_results']) >= 2:
                game_result_map[g['match']] = ':'.join(str(x) for x in g['final_results'])

    # 2) Tipps-Daten parsen (Spalte I als Fallback für Resultate)
    tipps_data = '[]'
    if tipps_path and os.path.exists(tipps_path):
        with open(tipps_path, encoding='utf-8-sig') as f:
            reader = csv.reader(f, delimiter=';')
            next(reader)
            tipps = []
            for row in reader:
                if not row or not row[0].strip(): continue
                tipps.append({'name': row[1], 'datum': row[3], 'spiel': row[6],
                              'tipp': row[7], 'resultat': row[8],
                              'punkte': int(row[9]) if row[9].strip() else 0})
                # Fallback: Resultat aus Spalte I wenn noch nicht in game_result_map
                if len(row) > 8 and row[8].strip() and row[6] not in game_result_map:
                    game_result_map[row[6]] = row[8]
        tipps_data = json.dumps(tipps, ensure_ascii=False)

    # Spielresultate in Reihenfolge der Rangverlauf-Spiele
    game_results = [game_result_map.get(n, '') for n in game_names]
    found = sum(1 for r in game_results if r)
    print(f'   Spielresultate: {found}/{len(game_results)} eingebettet')

    # Bonus-Entscheidungs-Indizes + Aufschlüsselung für JS-seitige gestaffelte Berechnung
    _CH_NAMES_LW2 = ['schweiz', 'switzerland', 'suisse', 'svizzera']
    _sorted_played2 = sorted(
        [g for g in (games_meta or {}).values() if g.get('final_results') and len(g['final_results']) >= 2],
        key=lambda g: g['event_date']
    )
    _finale_game_idx2  = None
    _ch_last_game_idx2 = None
    for _idx2, _g2 in enumerate(_sorted_played2):
        if _normalize_runde(_g2.get('roundName', '')) == 'finale':
            _finale_game_idx2 = _idx2
        if any(n in _g2['match'].lower() for n in _CH_NAMES_LW2):
            _ch_last_game_idx2 = _idx2
    _bonus_breakdown = {
        name: {'ch': zd.get('p_ch', 0), 't_ch': zd.get('p_t_ch', 0),
               'wm': zd.get('p_wm', 0), 't_k': zd.get('p_t_k', 0),
               'nullnull': zd.get('p_nullnull', 0)}
        for name, zd in (zusatz_data or {}).items()
    }

    rang_data = json.dumps({
        'members': members, 'gameNums': game_nums,
        'gameDates': game_dates, 'gameNames': game_names,
        'gameResults': game_results,
        'ranks': ranks, 'points': points,
        'bonusDecision': {'chIdx': _ch_last_game_idx2, 'finaleIdx': _finale_game_idx2},
        'bonusBreakdown': _bonus_breakdown
    }, ensure_ascii=False)

    # In HTML einbetten
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    import re
    html = re.sub(r'/\*RANG_DATA\*/.*?/\*END_RANG\*/',
                  f'/*RANG_DATA*/{rang_data}/*END_RANG*/', html, flags=re.DOTALL)
    html = re.sub(r'/\*TIPPS_DATA\*/.*?/\*END_TIPPS\*/',
                  f'/*TIPPS_DATA*/{tipps_data}/*END_TIPPS*/', html, flags=re.DOTALL)


    # Config-Daten (hidden players + extra players) aus lokalen CSVs injizieren
    cfg_hidden, cfg_extra = load_config_csvs()
    html = re.sub(r'/\*CFG_HIDDEN\*/.*?/\*END_CFG_HIDDEN\*/',
                  f'/*CFG_HIDDEN*/{cfg_hidden}/*END_CFG_HIDDEN*/', html, flags=re.DOTALL)
    html = re.sub(r'/\*CFG_EXTRA\*/.*?/\*END_CFG_EXTRA\*/',
                  f'/*CFG_EXTRA*/{cfg_extra}/*END_CFG_EXTRA*/', html, flags=re.DOTALL)

    # Finalspiele-Daten (echte Teams + Resultate)
    finals_data = build_finals_data(games_meta) if games_meta else {}

    # Merge: bestehende WM_FINALS_DATA aus HTML beibehalten wenn API leer liefert
    existing_fd_m = re.search(
        r'/\*WM_FINALS_DATA_START\*/var WM_FINALS_DATA=(\{.*?\});/\*WM_FINALS_DATA_END\*/',
        html, re.DOTALL)
    if existing_fd_m:
        try:
            ex_fd = json.loads(existing_fd_m.group(1))
            for rnd_key in ['r32', 'r16', 'qf', 'sf', 'f']:
                ex_rnd = ex_fd.get(rnd_key) or []
                new_rnd = finals_data.get(rnd_key) or []
                for i, ex_slot in enumerate(ex_rnd):
                    if i >= len(new_rnd) or not ex_slot:
                        continue
                    new_slot = new_rnd[i]
                    if not new_slot:
                        finals_data[rnd_key][i] = ex_slot
                        continue
                    # Fehlende Felder aus HTML-Version ergänzen
                    for field in ('r', 'h', 'd'):
                        if not new_slot.get(field) and ex_slot.get(field):
                            finals_data[rnd_key][i][field] = ex_slot[field]
            print('   ✅ WM_FINALS_DATA: bestehende Werte als Fallback gemergt')
        except Exception as e:
            print(f'   ⚠️  Merge WM_FINALS_DATA Fehler: {e}')

    finals_js = json.dumps(finals_data, ensure_ascii=False)
    html = re.sub(r'/\*WM_FINALS_DATA_START\*/.*?/\*WM_FINALS_DATA_END\*/',
                  f'/*WM_FINALS_DATA_START*/var WM_FINALS_DATA={finals_js};/*WM_FINALS_DATA_END*/',
                  html, flags=re.DOTALL)
    n_live = sum(1 for rnd in finals_data.values() for m in rnd if m)
    print(f'   Finalspiele live: {n_live} Spiel(e) mit echten Daten')

    # Zusatzfragen einbetten
    zusatz_js = json.dumps(zusatz_data or {}, ensure_ascii=False)
    html = re.sub(r'/\*ZUSATZ_DATA_START\*/.*?/\*ZUSATZ_DATA_END\*/',
                  f'/*ZUSATZ_DATA_START*/var ZUSATZ_DATA={zusatz_js};/*ZUSATZ_DATA_END*/',
                  html, flags=re.DOTALL)
    print(f'   Zusatzfragen eingebettet: {len(zusatz_data or {})} Einträge')

    # SRF-Leaderboard einbetten
    srf_js = json.dumps(srf_lb or {}, ensure_ascii=False)
    html = re.sub(r'/\*SRF_LB_START\*/.*?/\*SRF_LB_END\*/',
                  f'/*SRF_LB_START*/var SRF_LEADERBOARD={srf_js};/*SRF_LB_END*/',
                  html, flags=re.DOTALL)
    print(f'   SRF-Leaderboard eingebettet: {len(srf_lb or {})} Einträge')

    # Torschützenliste einbetten (aus fussballdaten.de)
    # Sanity-Check: nur überschreiben wenn Top-Torschütze MEHR oder GLEICH Tore hat
    # → verhindert, dass veraltete Scrapdaten korrekte Werte überschreiben
    scorers, updated_date = fetch_torschuetzen()
    if scorers:
        existing_match = re.search(r'var WM_TORSCHUETZEN_DATA=(\[.*?\]);', html, re.DOTALL)
        new_max = max((s.get('tore', 0) for s in scorers), default=0)
        # Plausibilitäts-Check: mindestens 1 Tor und sinnvolle Einsatzzeit
        plausibel = new_max >= 1 and any(s.get('spiele', 0) > 0 for s in scorers)
        if plausibel:
            scorers_js  = json.dumps(scorers, ensure_ascii=False)
            updated_str = json.dumps(updated_date, ensure_ascii=False)
            html = re.sub(
                r'var WM_TORSCHUETZEN_DATA=\[.*?\];',
                f'var WM_TORSCHUETZEN_DATA={scorers_js};',
                html, flags=re.DOTALL
            )
            html = re.sub(
                r'var WM_TORSCHUETZEN_UPDATED=.*?;',
                f'var WM_TORSCHUETZEN_UPDATED={updated_str};',
                html
            )
            print(f'   Torschützen: {len(scorers)} Einträge aktualisiert (Stand: {updated_date}, Top: {new_max} Tore)')
        else:
            print(f'   ⚠️  Torschützen übersprungen: Scraper liefert unplausible Daten (Top: {new_max} Tore)')
    else:
        print('   ⚠️  Torschützen konnten nicht abgerufen werden – bestehende Daten bleiben')

    # Turnier-Metadaten einbetten (für dynamische Labels im Dashboard)
    turnier_meta = {
        'name':    TURNIER.get('name',    'WM 2026'),
        'kuerzel': TURNIER.get('kuerzel', 'WM'),
        'jahr':    TURNIER.get('jahr',    '2026'),
    }
    turnier_js = json.dumps(turnier_meta, ensure_ascii=False)
    html = re.sub(
        r'/\*TURNIER_META_START\*/.*?/\*TURNIER_META_END\*/',
        f'/*TURNIER_META_START*/var TURNIER_META={turnier_js};/*TURNIER_META_END*/',
        html, flags=re.DOTALL
    )

    # TURNIERE-Liste einbetten (für Turnier-Wechsler in der Sidebar)
    # Liest die Gesamtliste aus index.html und ergänzt das aktuelle Turnier falls nötig
    current_datei = TURNIER.get('html_datei', 'WM_Rangverlauf.html')
    turniere_list = []
    index_path = os.path.join(WEB_DIR, 'index.html')
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as _f:
            _idx = _f.read()
        _m = re.search(r'const TURNIERE = (\[.*?\]);', _idx, re.DOTALL)
        if _m:
            try:
                turniere_list = json.loads(_m.group(1))
            except Exception:
                pass
    # Aktuelles Turnier sicherstellen
    if not any(t.get('datei') == current_datei for t in turniere_list):
        turniere_list.append({
            'name': TURNIER['name'],
            'datei': current_datei,
            'sub': TURNIER.get('sub', ''),
            'aktiv': True,
        })
    # Aktiv-Flag korrekt setzen
    for t in turniere_list:
        t['aktiv'] = (t.get('datei') == current_datei)
    turniere_js = json.dumps(turniere_list, ensure_ascii=False)
    html = re.sub(
        r'/\*TURNIERE_START\*/.*?/\*TURNIERE_END\*/',
        f'/*TURNIERE_START*/const TURNIERE={turniere_js};/*TURNIERE_END*/',
        html, flags=re.DOTALL
    )

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'   ✅ HTML aktualisiert: {os.path.basename(html_path)}')

# ── PDF generieren ────────────────────────────────────────────
def generate_pdf():
    chart_script = os.path.join(SCRIPT_DIR, 'tools', 'wm_chart.py')
    if not os.path.exists(chart_script):
        print('   ⚠️  tools/wm_chart.py nicht gefunden – Rangverlauf-Chart wird übersprungen.')
        return
    result = subprocess.run([sys.executable, chart_script, DATA_DIR, OUTPUT_DIR],
                            capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print('⚠️  PDF-Fehler:', result.stderr[-500:])

# ── Hauptprogramm ─────────────────────────────────────────────
SMB_MOUNT  = '/Volumes/Transfer'
SMB_TARGET = f'/Volumes/Transfer/{TURNIER.get("smb_subfolder", "Fussball Tippspiel 2026")}'
SMB_URL    = 'smb://130.60.191.116/Transfer'

def copy_to_smb(today):
    """Mountet den SMB-Share (falls nötig) und kopiert die drei Files."""
    # Share mounten falls nicht vorhanden
    if not os.path.isdir(SMB_MOUNT):
        r = subprocess.run(
            ['osascript', '-e', f'mount volume "{SMB_URL}"'],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            print(f'   ⚠️  SMB mount fehlgeschlagen: {r.stderr.strip()}')
            return
        time.sleep(2)

    # Zielordner erstellen falls nötig
    try:
        os.makedirs(SMB_TARGET, exist_ok=True)
    except Exception as e:
        print(f'   ⚠️  SMB Zielordner nicht erreichbar: {e}')
        return

    files_to_copy = [
        os.path.join(OUTPUT_DIR, f'{KUERZEL}_Rangliste_{today}.pdf'),
        os.path.join(OUTPUT_DIR, f'{KUERZEL}_RangverlaufChart_{today}.pdf'),
        os.path.join(DATA_DIR,   f'{KUERZEL}_Tipps_{today}.csv'),
    ]
    for src in files_to_copy:
        if os.path.exists(src):
            dst = os.path.join(SMB_TARGET, os.path.basename(src))
            try:
                shutil.copy(src, dst)
                print(f'   ✅ {os.path.basename(src)} → SMB')
            except Exception as e:
                print(f'   ⚠️  Kopieren fehlgeschlagen ({os.path.basename(src)}): {e}')
        else:
            print(f'   ⚠️  Datei nicht gefunden: {os.path.basename(src)}')

# ── index.html aktualisieren ─────────────────────────────────
def update_index_html():
    """Stellt sicher, dass das aktive Turnier im index.html Dropdown erscheint.
    Wird ausgeführt wenn sich das Turnier ändert (neues Kürzel/html_datei)."""
    index_path = os.path.join(WEB_DIR, 'index.html')
    if not os.path.exists(index_path):
        print('   ℹ️  index.html nicht gefunden – übersprungen.')
        return
    with open(index_path, 'r', encoding='utf-8') as f:
        html = f.read()
    m = re.search(r'const TURNIERE = (\[.*?\]);', html, re.DOTALL)
    if not m:
        print('   ⚠️  TURNIERE-Array in index.html nicht gefunden.')
        return
    try:
        turniere = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        print(f'   ⚠️  TURNIERE-Parse-Fehler: {e}')
        return
    html_datei = TURNIER.get('html_datei', 'WM_Rangverlauf.html')
    if any(t.get('datei') == html_datei for t in turniere):
        return  # Bereits vorhanden – nichts zu tun
    # Neues Turnier ans Ende der Liste hinzufügen
    turniere.append({
        'name': TURNIER['name'],
        'datei': html_datei,
        'sub': TURNIER.get('sub', ''),
        'aktiv': True,
    })
    new_list = json.dumps(turniere, ensure_ascii=False, indent=2)
    html = html[:m.start(1)] + new_list + html[m.end(1):]
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'   ✅ index.html: "{TURNIER["name"]}" zur Turnierauswahl hinzugefügt')

# ── GitHub Pages Upload ───────────────────────────────────────
# Token + Repo aus config/-Dateien lesen (nie im Code speichern)
def _read_config(filename, default=""):
    path = os.path.join(CONFIG_DIR, filename)
    try:
        with open(path, encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return default

GITHUB_TOKEN = _read_config('github_token.txt')
GITHUB_REPO  = _read_config('github_repo.txt', 'Diavolezza64/Fussball-Tippspiel-Beat')


def load_config_csvs():
    """Liest config/ausschluss.txt (ehemalige) und data/zusatz_spieler.csv.
    Gibt JSON-Strings zurück, die in die HTML-Marker injiziert werden."""
    import json as _json

    # Ehemalige aus ausschluss.txt lesen (Format: 'ID;Name' oder 'Name')
    ausschluss_path = os.path.join(CONFIG_DIR, 'ausschluss.txt')
    hidden = []
    if os.path.exists(ausschluss_path):
        with open(ausschluss_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ';' in line:
                    # ID;Name → nur Name extrahieren
                    name = line.split(';', 1)[1].strip()
                else:
                    name = line
                if name:
                    hidden.append(name)

    # Zusatzspieler aus data/zusatz_spieler.csv
    extra_path = os.path.join(BASE_DIR, 'data', 'zusatz_spieler.csv')
    extra = []
    if os.path.exists(extra_path):
        with open(extra_path, encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
            extra = [{'name': r.get('name','').strip(), 'id': r.get('id','').strip()}
                     for r in rows if r.get('name','').strip()]

    return _json.dumps(hidden, ensure_ascii=False), _json.dumps(extra, ensure_ascii=False)


def strip_config_from_html(html):
    """Entfernt CFG-Daten aus HTML bevor es auf GitHub hochgeladen wird."""
    html = re.sub(r'/\*CFG_HIDDEN\*/.*?/\*END_CFG_HIDDEN\*/',
                  '/*CFG_HIDDEN*/null/*END_CFG_HIDDEN*/', html, flags=re.DOTALL)
    html = re.sub(r'/\*CFG_EXTRA\*/.*?/\*END_CFG_EXTRA\*/',
                  '/*CFG_EXTRA*/[]/*END_CFG_EXTRA*/', html, flags=re.DOTALL)
    return html

def upload_to_github():
    """Lädt WM_Rangverlauf.html als index.html auf GitHub hoch (erstellt oder aktualisiert)."""
    import base64, json, urllib.request, urllib.error
    html_path = os.path.join(WEB_DIR, TURNIER.get('html_datei', 'WM_Rangverlauf.html'))
    if not os.path.exists(html_path):
        print(f'   ⚠️  {os.path.basename(html_path)} nicht gefunden – GitHub-Upload übersprungen.')
        return
    if not GITHUB_TOKEN or GITHUB_TOKEN.startswith('ghp_DEIN'):
        print('   ⚠️  Kein GitHub-Token konfiguriert – Upload übersprungen.')
        return

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/index.html"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json"
    }

    # SHA der bestehenden Datei abrufen (nötig für Updates)
    sha = None
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            sha = json.loads(resp.read()).get('sha')
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f'   ⚠️  GitHub SHA-Abruf fehlgeschlagen: {e.code}')
            return

    with open(html_path, 'r', encoding='utf-8') as f:
        html_for_upload = strip_config_from_html(f.read())
    content_b64 = base64.b64encode(html_for_upload.encode('utf-8')).decode('ascii')

    payload = {"message": f"Update WM Rangliste {datetime.now().strftime('%Y-%m-%d')}", "content": content_b64}
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            json.loads(resp.read())
            print(f'   ✅ GitHub Pages aktualisiert: https://{GITHUB_REPO.split("/")[0].lower()}.github.io/{GITHUB_REPO.split("/")[1]}/')
    except urllib.error.HTTPError as e:
        msg = json.loads(e.read()).get('message', '')
        print(f'   ⚠️  GitHub-Upload fehlgeschlagen ({e.code}): {msg}')


def _self_update():
    """Aktualisiert wm_auto.py selbst von GitHub und startet neu falls geändert.
    Funktioniert unabhängig davon wo der Ordner liegt oder welches Start-Script verwendet wird."""
    import urllib.request as urlreq, sys
    src_file = os.path.join(CONFIG_DIR, 'update_source.txt')
    if not os.path.exists(src_file):
        return
    base = open(src_file, encoding='utf-8').read().strip()
    url  = f'{base}/tools/wm_auto.py'
    try:
        req  = urlreq.Request(url, headers={'User-Agent': 'tippspiel'})
        new  = urlreq.urlopen(req, timeout=15).read()
        self = os.path.abspath(__file__)
        if new != open(self, 'rb').read():
            with open(self, 'wb') as f:
                f.write(new)
            print('   ✅ wm_auto.py aktualisiert – starte neu …')
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception:
        pass  # offline oder kein Update nötig


def _update_html_template():
    """Lädt die neueste WM_Rangverlauf.html von GitHub falls update_source.txt vorhanden."""
    import urllib.request as urlreq
    html_datei = TURNIER.get('html_datei', 'WM_Rangverlauf.html')
    src_file  = os.path.join(CONFIG_DIR, 'update_source.txt')
    html_file = os.path.join(BASE_DIR, 'web', html_datei)
    if not os.path.exists(src_file):
        return
    base = open(src_file, encoding='utf-8').read().strip()
    url  = f'{base}/web/{html_datei}'
    try:
        req = urlreq.Request(url, headers={'User-Agent': 'tippspiel'})
        data = urlreq.urlopen(req, timeout=30).read()
        with open(html_file, 'wb') as f:
            f.write(data)
        print(f'   ✅ HTML-Template aktualisiert')
    except Exception as e:
        print(f'   ℹ️  HTML-Template Update übersprungen: {e}')


def _auto_github_setup():
    """
    Richtet Git + GitHub automatisch ein falls:
    - config/github_token.txt vorhanden
    - aber noch kein .git Verzeichnis existiert
    Repo-Name wird aus dem Ordnernamen abgeleitet.
    """
    import urllib.request as urlreq
    token_file = os.path.join(CONFIG_DIR, 'github_token.txt')
    repo_file  = os.path.join(CONFIG_DIR, 'github_repo.txt')
    git_dir    = os.path.join(BASE_DIR, '.git')

    if os.path.exists(git_dir) or not os.path.exists(token_file):
        return  # Bereits eingerichtet oder kein Token

    token = open(token_file, encoding='utf-8').read().strip()
    if not token:
        return

    print('→ GitHub Ersteinrichtung …')

    # Username via API
    try:
        req = urlreq.Request('https://api.github.com/user',
            headers={'Authorization': f'token {token}', 'User-Agent': 'tippspiel'})
        user = json.loads(urlreq.urlopen(req, timeout=10).read())
        gh_user = user.get('login', '')
        gh_name = user.get('name', gh_user)
        gh_email = user.get('email', '') or f'{gh_user}@github.com'
    except Exception as e:
        print(f'   ⚠️  GitHub-API nicht erreichbar: {e}')
        return

    # Repo-Name aus Ordnername ableiten (Fussball-Tippspiel-Daniel-main → Fussball-Tippspiel-Daniel)
    folder = os.path.basename(BASE_DIR)
    repo_name = folder.removesuffix('-main').removesuffix('-master')

    print(f'   Benutzer : {gh_user}')
    print(f'   Repo     : {repo_name}')

    # git init + remote
    os.system(f'git -C "{BASE_DIR}" init -b main')
    os.system(f'git -C "{BASE_DIR}" config user.email "{gh_email}"')
    os.system(f'git -C "{BASE_DIR}" config user.name "{gh_name}"')
    remote = f'https://{token}@github.com/{gh_user}/{repo_name}.git'
    os.system(f'git -C "{BASE_DIR}" remote remove origin 2>/dev/null || true')
    os.system(f'git -C "{BASE_DIR}" remote add origin "{remote}"')

    # Repo speichern
    with open(repo_file, 'w') as f:
        f.write(f'{gh_user}/{repo_name}')

    # Initialer Push (nach wm_auto.py Durchlauf, nicht jetzt)
    # Marker setzen damit upload_to_github() weiss dass git push nötig ist
    print(f'   ✅ Git eingerichtet → wird nach Datenupdate gepusht')


def _git_push_if_setup():
    """Pusht falls .git vorhanden. Token wird verwendet wenn vorhanden (andere User),
    sonst macOS Keychain (Beat).
    Schreibt ausserdem die bereinigte WM_Rangverlauf.html als index.html ins Root,
    damit GitHub Pages aktuell bleibt – ohne API-Token."""
    import subprocess
    git_dir    = os.path.join(BASE_DIR, '.git')
    token_file = os.path.join(CONFIG_DIR, 'github_token.txt')
    repo_file  = os.path.join(CONFIG_DIR, 'github_repo.txt')

    if not os.path.exists(git_dir):
        return  # Kein git-Repo → überspringen

    # Root index.html + web/WM_Rangverlauf.html ohne private Config-Daten erzeugen
    html_src  = os.path.join(WEB_DIR, TURNIER.get('html_datei', 'WM_Rangverlauf.html'))
    index_dst = os.path.join(BASE_DIR, 'index.html')
    html_full_backup = None  # lokale Version mit Config wiederherstellen nach Push
    if os.path.exists(html_src):
        try:
            with open(html_src, encoding='utf-8') as f:
                html_full_backup = f.read()
            html_stripped = strip_config_from_html(html_full_backup)
            # index.html (Root) – Config geleert
            with open(index_dst, 'w', encoding='utf-8') as f:
                f.write(html_stripped)
            # web/WM_Rangverlauf.html – für GitHub ebenfalls Config leeren
            with open(html_src, 'w', encoding='utf-8') as f:
                f.write(html_stripped)
        except Exception as e:
            print(f'   ⚠️  HTML konnte nicht bereinigt werden: {e}')
            html_full_backup = None

    # Token + Repo-URL setzen falls vorhanden (für Daniel/andere)
    if os.path.exists(token_file) and os.path.exists(repo_file):
        token   = open(token_file, encoding='utf-8').read().strip()
        gh_repo = open(repo_file,  encoding='utf-8').read().strip()
        if token and gh_repo:
            remote = f'https://{token}@github.com/{gh_repo}.git'
            subprocess.run(['git', '-C', BASE_DIR, 'remote', 'set-url', 'origin', remote],
                           capture_output=True)

    subprocess.run(['git', '-C', BASE_DIR, 'pull', '--rebase', '--autostash'],
                   capture_output=True)
    subprocess.run(['git', '-C', BASE_DIR, 'add', '.'], capture_output=True)
    result = subprocess.run(['git', '-C', BASE_DIR, 'diff', '--cached', '--quiet'],
                            capture_output=True)
    if result.returncode == 1:  # Änderungen vorhanden
        from datetime import datetime as dt
        msg = f'Auto-Update {dt.now().strftime("%Y-%m-%d %H:%M")}'
        subprocess.run(['git', '-C', BASE_DIR, 'commit', '-m', msg], capture_output=True)
        r = subprocess.run(['git', '-C', BASE_DIR, 'push', '-u', 'origin', 'main'],
                           capture_output=True)
        if r.returncode == 0:
            print('   ✅ GitHub aktualisiert')
        else:
            print('   ⚠️  GitHub-Push fehlgeschlagen')

    # Lokale web/WM_Rangverlauf.html mit Config wiederherstellen
    if html_full_backup is not None and os.path.exists(html_src):
        try:
            with open(html_src, 'w', encoding='utf-8') as f:
                f.write(html_full_backup)
        except Exception:
            pass


def main():
    today = datetime.now().strftime('%Y-%m-%d')
    print(f'\n🏆 {TURNIER["name"]} – Abruf {today}')

    _self_update()   # Aktualisiert sich selbst von GitHub, startet neu falls nötig

    _auto_github_setup()

    # HTML-Template aktualisieren falls update_source.txt vorhanden
    _update_html_template()

    print('→ Browser-Session aufbauen …')
    session = make_session()

    print('→ Runden ermitteln …')
    rounds = get_rounds(session)
    print(f'   {len(rounds)} Runden gefunden: {", ".join(r["name"] for r in rounds)}')

    print(f'→ Daten abrufen ({len(MEMBERS)} Spieler × {len(rounds)} Runden) …')
    games_meta, player_data = fetch_all(session, rounds)

    print('→ Zusatzfragen auswerten …')
    zusatz_data = calc_zusatz_punkte(games_meta)

    print('→ SRF-Leaderboard laden …')
    srf_lb = fetch_srf_leaderboard(session)

    print('→ CSVs schreiben …')
    rang_path  = os.path.join(DATA_DIR, f'{KUERZEL}_Rangverlauf_{today}.csv')
    tipps_path = os.path.join(DATA_DIR, f'{KUERZEL}_Tipps_{today}.csv')
    write_csvs(games_meta, player_data, today, zusatz_data=zusatz_data)

    print('→ PDF generieren …')
    generate_pdf()

    print('→ HTML aktualisieren …')
    embed_in_html(rang_path, tipps_path, games_meta, zusatz_data=zusatz_data, srf_lb=srf_lb)

    print('→ Rangliste PDF generieren …')
    gen_script = os.path.join(SCRIPT_DIR, 'tools', 'gen_rangliste.py')
    if os.path.exists(gen_script):
        try:
            import importlib.util, traceback
            spec = importlib.util.spec_from_file_location('gen_rangliste', gen_script)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            print(f'   gen_rangliste geladen, CSV: {rang_path}')
            members, cum, n = mod.load_csv(rang_path)
            print(f'   {len(members)} Teilnehmer, {n} Spiele geladen')
            pdf_out = os.path.join(OUTPUT_DIR, f'{KUERZEL}_Rangliste_{today}.pdf')
            mod.generate(pdf_out, members, cum, n, zusatz_data=zusatz_data)
        except Exception as e:
            print(f'   ⚠️  Rangliste PDF Fehler: {e}')
            traceback.print_exc()
    else:
        print('   tools/gen_rangliste.py nicht gefunden – übersprungen')

    print('→ Alte Dateien aufräumen …')
    cleanup_old_files()

    print('→ Files auf SMB-Share kopieren …')
    copy_to_smb(today)

    print('→ GitHub Pages aktualisieren …')
    upload_to_github()
    _git_push_if_setup()

    print('→ index.html aktualisieren …')
    update_index_html()

    print('\n✅ Fertig!')

if __name__ == '__main__':
    main()
