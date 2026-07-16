#!/usr/bin/env python3
"""
Fussball Tippspiel – Teilnehmer automatisch aus SRF auslesen
=======================================================
Aufruf:  python3 config/find_gruppe.py

Liest die Gruppennamen aus config/gruppen.txt, sucht alle Mitglieder
auf wmtippspiel.srf.ch und schreibt sie in config/teilnehmer.json.

Browser: Safari oder Chrome – welcher eine aktive Session hat, wird genutzt.
Voraussetzung: Im jeweiligen Browser auf wmtippspiel.srf.ch eingeloggt sein.
"""

import sys, os, json, re, time, subprocess
from datetime import datetime

# ── Pfade (alle relativ zu diesem Script) ───────────────────────
CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
GRUPPEN_TXT = os.path.join(CONFIG_DIR, 'gruppen.txt')
OUT_FILE    = os.path.join(CONFIG_DIR, 'teilnehmer.json')
BASE_URL    = 'https://wmtippspiel.srf.ch'

# ── Abhängigkeiten sicherstellen ────────────────────────────────
def ensure_deps():
    needed = []
    try: import requests
    except ImportError: needed.append('requests')
    try: import browser_cookie3
    except ImportError: needed.append('browser-cookie3')
    try: from bs4 import BeautifulSoup
    except ImportError: needed.append('beautifulsoup4')
    if needed:
        print(f'Installiere: {" ".join(needed)}')
        # --break-system-packages nur auf Linux/Mac nötig, nicht auf Windows
        flags = ['--break-system-packages'] if sys.platform != 'win32' else []
        r = subprocess.run([sys.executable, '-m', 'pip', 'install', *needed, '-q', *flags])
        if r.returncode != 0:
            subprocess.run([sys.executable, '-m', 'pip', 'install', *needed, '-q'], check=True)

ensure_deps()

import requests
import browser_cookie3
from bs4 import BeautifulSoup

# ── Browser-Session aufbauen ─────────────────────────────────────
_UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
       'AppleWebKit/605.1.15 (KHTML, like Gecko) '
       'Version/17.0 Safari/605.1.15')

def _make_session(cookie_jar):
    s = requests.Session()
    s.cookies = cookie_jar
    s.headers.update({
        'User-Agent': _UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'de-CH,de;q=0.9,en;q=0.8',
        'Referer': BASE_URL + '/',
    })
    return s

def _is_logged_in(session):
    """Gibt True zurück wenn die Session eingeloggt ist."""
    try:
        resp = session.get(BASE_URL + '/', timeout=15)
        # Eingeloggt: kein Login-Formular, aber ein Profil-Link
        return bool(re.search(r'/users/[^/"]{3,}', resp.text))
    except Exception:
        return False

def get_session():
    """
    Probiert Safari, Chrome, Edge und Firefox.
    Gibt (session, browser_name) zurück.
    Beendet das Script falls keiner eingeloggt ist.
    """
    import platform
    is_windows = platform.system() == 'Windows'

    # Reihenfolge: auf Windows Edge zuerst (vorinstalliert), dann Chrome
    if is_windows:
        browsers = [
            ('Edge',    lambda: browser_cookie3.edge(domain_name='.srf.ch')),
            ('Chrome',  lambda: browser_cookie3.chrome(domain_name='.srf.ch')),
            ('Firefox', lambda: browser_cookie3.firefox(domain_name='.srf.ch')),
        ]
    else:
        browsers = [
            ('Safari',  lambda: browser_cookie3.safari(domain_name='.srf.ch')),
            ('Chrome',  lambda: browser_cookie3.chrome(domain_name='.srf.ch')),
            ('Edge',    lambda: browser_cookie3.edge(domain_name='.srf.ch')),
            ('Firefox', lambda: browser_cookie3.firefox(domain_name='.srf.ch')),
        ]

    for name, load_cookies in browsers:
        try:
            cj = load_cookies()
            session = _make_session(cj)
            if _is_logged_in(session):
                print(f'   ✅ Browser: {name} (eingeloggt)')
                return session, name
            else:
                print(f'   ○  {name}: nicht eingeloggt – übersprungen')
        except Exception as e:
            print(f'   ○  {name}: {e}')

    print('\n❌  Kein Browser mit aktiver Session gefunden.')
    print('   Bitte auf wmtippspiel.srf.ch einloggen in:')
    print('   Windows: Edge (empfohlen) oder Chrome')
    print('   Mac:     Safari oder Chrome')
    print('   Tipp: Start PC.bat mit Rechtsklick → Als Administrator ausfuehren')
    sys.exit(1)

# ── Gruppennamen aus gruppen.txt laden ──────────────────────────
def load_group_names():
    if not os.path.exists(GRUPPEN_TXT):
        print(f'❌  {GRUPPEN_TXT} nicht gefunden.')
        print('   Bitte config/gruppen.txt mit Gruppennamen erstellen.')
        sys.exit(1)
    names = []
    with open(GRUPPEN_TXT, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                names.append(line)
    if not names:
        print('❌  Keine Gruppen in config/gruppen.txt gefunden (alle Zeilen leer oder #).')
        sys.exit(1)
    return names

# ── React-Props parsen ───────────────────────────────────────────
def get_react_props(doc, class_name=None):
    """Gibt Liste aller geparsten data-react-props zurück."""
    sel = {'data-react-class': class_name} if class_name else None
    els = doc.find_all(attrs={'data-react-class': True}) if not sel \
          else doc.find_all(attrs=sel)
    result = []
    for el in els:
        try:
            result.append((el.get('data-react-class', ''),
                           json.loads(el['data-react-props'])))
        except Exception:
            pass
    return result

def react_classes(doc):
    return sorted({el['data-react-class']
                   for el in doc.find_all(attrs={'data-react-class': True})})

# ── Gruppe suchen ────────────────────────────────────────────────
def search_group(session, group_name):
    """
    Sucht eine Gruppe nach Name oder direktem URL-Pfad.
    Gibt (group_id, group_url) oder (None, None).

    gruppen.txt kann enthalten:
      UZH_physik              → Name wird gesucht
      /leagues/UZH_physik     → Direkter Pfad (kein Suchen nötig)
      /leagues/46532          → Direkter Pfad mit numerischer ID
    """
    # 0a) Direkte URL/Pfad-Eingabe (beginnt mit /)
    if group_name.startswith('/'):
        gid = group_name.rstrip('/').split('/')[-1]
        print(f'   Direkter Pfad: {group_name}  (id={gid})')
        return gid, group_name

    # 0b) Direkt via Slug versuchen (schnellster Weg)
    slug        = group_name.strip().replace(' ', '-')
    slug_lower  = slug.lower()
    direct_urls = []
    for prefix in ('leagues', 'ligen', 'communities', 'groups'):
        for s in (slug, slug_lower):
            direct_urls.append(f'/{prefix}/{s}')

    for url in direct_urls:
        try:
            resp = session.get(BASE_URL + url, timeout=15)
            if resp.status_code != 200:
                continue
            doc = BeautifulSoup(resp.text, 'html.parser')
            # Valide Gruppen-Seite: hat React-Komponenten oder Mitglieder-Links
            if doc.find(attrs={'data-react-class': True}):
                # Gruppen-ID aus URL ableiten (letztes Segment)
                gid = url.rstrip('/').split('/')[-1]
                print(f'   ✅ Direkte URL gefunden: {url}  (id={gid})')
                return gid, url
        except Exception as e:
            print(f'   ○  {url}: {e}')

    q = requests.utils.quote(group_name)

    search_paths = [
        f'/search?q={q}',
        f'/leagues?q={q}',
        f'/communities?q={q}',
        '/leagues',
        '/communities',
        '/ligen',
    ]

    for path in search_paths:
        try:
            resp = session.get(BASE_URL + path, timeout=15)
            if resp.status_code != 200:
                continue
            doc = BeautifulSoup(resp.text, 'html.parser')

            # 1) React-Props nach Gruppen-Einträgen durchsuchen
            for cls, props in get_react_props(doc):
                hit = _find_group_in_props(props, group_name)
                if hit:
                    print(f'   Gefunden via {path} [{cls}]: {hit}')
                    return hit['id'], hit['url']

            # 2) Direkte Links auf Gruppen-Seiten
            pattern = re.compile(r'/(leagues|communities|groups|ligen)/([^/?#"]+)')
            for a in doc.find_all('a', href=pattern):
                text = a.get_text(strip=True)
                if group_name.lower() in text.lower():
                    m = pattern.search(a['href'])
                    if m:
                        gid = m.group(2)
                        url = f'/{m.group(1)}/{gid}'
                        print(f'   Gefunden via Link auf {path}: {text!r} → {url}')
                        return gid, url

            time.sleep(0.2)
        except Exception as e:
            print(f'   ⚠️  {path}: {e}')

    return None, None

def _find_group_in_props(props, name, depth=0):
    """Durchsucht Props rekursiv nach einem Gruppen-Eintrag mit passendem Namen."""
    if depth > 6:
        return None
    if isinstance(props, dict):
        # Typische Felder für Gruppen-Listen
        for key in ('leagues', 'communities', 'groups', 'ligen',
                    'items', 'results', 'data', 'leagueList'):
            val = props.get(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        item_name = item.get('name', item.get('title', ''))
                        if name.lower() in item_name.lower():
                            gid = str(item.get('id') or item.get('slug') or '')
                            url = item.get('url') or item.get('path') or ''
                            if gid:
                                return {'id': gid, 'name': item_name, 'url': url}
        for v in props.values():
            if isinstance(v, (dict, list)):
                hit = _find_group_in_props(v, name, depth + 1)
                if hit:
                    return hit
    elif isinstance(props, list):
        for item in props:
            hit = _find_group_in_props(item, name, depth + 1)
            if hit:
                return hit
    return None

# ── Mitglieder einer Gruppe laden ───────────────────────────────
_MEMBER_KEYS = ('bets', 'users', 'members', 'participants', 'rankings',
                'leaderboard', 'entries', 'rankers', 'items', 'results', 'data')

def fetch_members(session, group_id, group_url):
    """
    Lädt alle Mitglieder einer Gruppe inkl. Pagination.
    Gibt Liste von {'id', 'name'} zurück.
    """
    base_path = group_url if group_url else f'/communities/{group_id}'
    base_full = BASE_URL + base_path if not base_path.startswith('http') else base_path

    all_members = []
    seen_ids   = set()
    page       = 1

    while True:
        url = f'{base_full}?page={page}' if page > 1 else base_full
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                print(f'   ⚠️  {url}: HTTP {resp.status_code}')
                break
            doc = BeautifulSoup(resp.text, 'html.parser')

            # ── 1) Direkt aus HTML: <a href="/users/ID">Name</a> ──
            found_on_page = _extract_members_html(doc)

            # ── 2) Fallback: React-Props ───────────────────────────
            if not found_on_page:
                for cls, props in get_react_props(doc):
                    found_on_page.extend(_extract_members(props))

            if found_on_page:
                new = 0
                for m in found_on_page:
                    if m['id'] not in seen_ids:
                        seen_ids.add(m['id'])
                        all_members.append(m)
                        new += 1
                print(f'   Seite {page}: {new} neue Mitglieder')
                if new == 0:
                    break   # keine neuen → fertig
            else:
                break       # keine Mitglieder auf dieser Seite

            # Nächste Seite prüfen
            has_next = bool(doc.find('a', href=re.compile(r'\?page=' + str(page + 1))))
            if not has_next:
                break
            page += 1
            time.sleep(0.3)

        except Exception as e:
            print(f'   ⚠️  {url}: {e}')
            break

    return all_members


def _extract_members_html(doc):
    """
    Extrahiert Mitglieder direkt aus dem gerenderten HTML.
    Sucht <a href="/users/ID">Name</a> Links auf der Seite.
    """
    members = []
    user_pattern = re.compile(r'^/users/([^/?#]+)$')
    seen = set()
    for a in doc.find_all('a', href=user_pattern):
        m = user_pattern.match(a['href'])
        if not m:
            continue
        uid  = m.group(1)
        name = a.get_text(strip=True)
        # Rollen-Labels wie "admin", "moderator" rausfiltern
        for role in ('admin', 'moderator', 'Inaktive:r Nutzer:in'):
            name = name.replace(role, '').strip()
        if uid and name and len(name) >= 2 and uid not in seen:
            seen.add(uid)
            members.append({'id': uid, 'name': name})
    return members

def _extract_members(props, depth=0):
    if depth > 8:
        return []
    members = []
    if isinstance(props, dict):
        for key in _MEMBER_KEYS:
            val = props.get(key)
            if isinstance(val, list):
                for item in val:
                    m = _parse_user(item)
                    if m:
                        members.append(m)
        if not members:
            for v in props.values():
                if isinstance(v, (dict, list)):
                    members.extend(_extract_members(v, depth + 1))
    elif isinstance(props, list):
        for item in props:
            m = _parse_user(item)
            if m:
                members.append(m)
            elif isinstance(item, (dict, list)):
                members.extend(_extract_members(item, depth + 1))
    return members

def _parse_user(item):
    if not isinstance(item, dict):
        return None
    user = item.get('user') or item.get('bettor') or {}
    if not isinstance(user, dict):
        user = {}
    uid = str(
        user.get('public_id') or user.get('id') or
        item.get('user_id')   or item.get('public_id') or
        item.get('id')        or ''
    )
    name = (
        user.get('nickname') or user.get('username') or user.get('name') or
        item.get('nickname') or item.get('username') or item.get('name') or ''
    )
    # User-URL als Fallback für ID
    url = user.get('url') or item.get('url') or ''
    if url and not uid:
        m = re.search(r'/users/([^/?#]+)', url)
        if m:
            uid = m.group(1)
    if uid and name and len(uid) >= 3 and len(name) >= 2:
        return {'id': str(uid), 'name': str(name)}
    return None

# ── Debug: alle React-Klassen einer URL ausgeben ─────────────────
def debug_url(session, url):
    full = BASE_URL + url if not url.startswith('http') else url
    resp = session.get(full, timeout=20)
    doc  = BeautifulSoup(resp.text, 'html.parser')
    print(f'\n── DEBUG {url} ───────────────────────────')
    print(f'Status: {resp.status_code}')
    cls = react_classes(doc)
    print(f'React-Klassen: {cls}')
    for c, p in get_react_props(doc):
        print(f'\n[{c}] keys: {list(p.keys()) if isinstance(p, dict) else type(p).__name__}')
    # Alle Leagues/Gruppen-Links auf der Seite
    pattern = re.compile(r'/(leagues|communities|groups|ligen)/([^/?#"\']+)')
    links = {}
    for a in doc.find_all('a', href=pattern):
        m = pattern.search(a['href'])
        if m:
            links[m.group(0)] = a.get_text(strip=True)
    if links:
        print('\nGefundene Gruppen-Links:')
        for path, name in sorted(links.items()):
            print(f'  {path}  →  {name!r}')
    else:
        print('\n(Keine Gruppen-Links auf dieser Seite gefunden)')

# ── Zusatzfragen-Antworten von SRF holen ─────────────────────────
_ZUSATZ_FIELD_KEYS = ['wm', 'ch', 't_ch', 't_k', 'nullnull']

def _parse_zusatz_from_html(html_text):
    """Parst TextSelection-Antworten aus HTML. Gibt {key: answer} oder None zurück."""
    from bs4 import BeautifulSoup as _BS
    doc = _BS(html_text, 'html.parser')
    bets = doc.find_all(attrs={'data-react-class': 'TextSelection'})
    if not bets:
        return None
    answers = {}
    for i, el in enumerate(bets):
        bet = json.loads(el.get('data-react-props', '{}')).get('bet', {})
        picks = bet.get('picks', [])
        ans_map = {a['id']: a['name'] for a in bet.get('answers', [])}
        answer = ans_map.get(picks[0]) if picks else None
        key = _ZUSATZ_FIELD_KEYS[i] if i < len(_ZUSATZ_FIELD_KEYS) else f'q{i}'
        answers[key] = answer
    return answers if answers else None


def fetch_zusatz_antworten(session, members):
    """Holt Zusatzfragen-Antworten von SRF (Runde 40) für alle Member.
    Gibt {id: {wm, ch, t_ch, t_k, nullnull}} zurück.

    Sonderfall: wenn der eingeloggte User seine eigene Profilseite aufruft,
    leitet SRF um (z.B. /mein-profil). In dem Fall wird /round/40 an die
    Redirect-URL angehängt und ein zweiter Versuch gestartet.
    """
    print('→ Zusatzfragen-Antworten von SRF laden …')
    result = {}
    for m in members:
        try:
            url = f'{BASE_URL}/users/{m["id"]}/round/40'
            resp = session.get(url, timeout=20, allow_redirects=True)

            if resp.status_code != 200:
                print(f'   ⚠️  {m["name"]}: HTTP {resp.status_code}')
                continue

            answers = _parse_zusatz_from_html(resp.text)

            # Redirect erkannt und keine Antworten → /round/40 an Redirect-URL hängen
            if answers is None and resp.url != url:
                redirect_base = resp.url.split('?')[0].rstrip('/')
                if '/round/' not in redirect_base:
                    alt_url = redirect_base + '/round/40'
                    alt_resp = session.get(alt_url, timeout=20)
                    if alt_resp.status_code == 200:
                        answers = _parse_zusatz_from_html(alt_resp.text)

            if answers is not None:
                result[m['id']] = answers
            else:
                print(f'   ⚠️  {m["name"]}: Zusatzfragen nicht gefunden (URL: {resp.url})')

        except Exception as e:
            print(f'   ⚠️  {m["name"]}: {e}')
        time.sleep(0.1)
    print(f'   ✅ Zusatzfragen: {len(result)}/{len(members)} Antworten gespeichert')
    return result

# ── teilnehmer.json schreiben ────────────────────────────────────
def save(members, session=None):
    out = [{'id': m['id'], 'name': m['name'], 'rank': i}
           for i, m in enumerate(members, 1)]

    # Zusatzspieler aus data/zusatz_spieler.csv ZUERST hinzufügen
    # (damit ihre Zusatzfragen im nächsten Schritt mit geholt werden)
    zusatz_path = os.path.join(os.path.dirname(CONFIG_DIR), 'data', 'zusatz_spieler.csv')
    existing_ids = {m['id'] for m in out}
    zusatz_count = 0
    if os.path.exists(zusatz_path):
        import csv as _csv
        with open(zusatz_path, encoding='utf-8') as f:
            for row in _csv.DictReader(f):
                eid   = row.get('id',   '').strip()
                ename = row.get('name', '').strip()
                if eid and ename and eid not in existing_ids:
                    out.append({'id': eid, 'name': ename, 'rank': len(out) + 1})
                    existing_ids.add(eid)
                    zusatz_count += 1
        if zusatz_count:
            print(f'   + {zusatz_count} Zusatzspieler aus data/zusatz_spieler.csv hinzugefügt')

    # Zusatzfragen-Antworten von SRF holen – jetzt für ALLE (inkl. Zusatzspieler)
    if session:
        zusatz_by_id = fetch_zusatz_antworten(session, out)
        for entry in out:
            if entry['id'] in zusatz_by_id:
                entry['zusatz'] = zusatz_by_id[entry['id']]

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'✅  {len(out)} Teilnehmer → config/teilnehmer.json')
    print('   Tipp: "rank"-Felder können manuell angepasst werden.')

# ── Hauptprogramm ────────────────────────────────────────────────
def main():
    # --debug URL für Fehleranalyse
    if '--debug' in sys.argv:
        idx = sys.argv.index('--debug')
        url = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else '/'
        session, _ = get_session()
        debug_url(session, url)
        return

    group_names = load_group_names()
    print(f'   Gruppen in gruppen.txt: {group_names}')

    print('\n→ Browser-Session aufbauen …')
    session, browser = get_session()

    all_members = {}   # id → member, über alle Gruppen

    for group_name in group_names:
        print(f'\n→ Suche Gruppe "{group_name}" …')
        group_id, group_url = search_group(session, group_name)

        if not group_id:
            print(f'   ⚠️  Gruppe "{group_name}" nicht gefunden.')
            print('   Tipp: Starte mit --debug /leagues für Fehleranalyse.')
            continue

        print(f'→ Lade Mitglieder von "{group_name}" (id={group_id}) …')
        members = fetch_members(session, group_id, group_url)

        if not members:
            print(f'   ⚠️  Keine Mitglieder für "{group_name}" gefunden.')
            print(f'   Tipp: python3 config/find_gruppe.py --debug /leagues/{group_id}')
        else:
            for m in members:
                all_members[m['id']] = m   # Duplikate über Gruppen deduplicieren

    if not all_members:
        print('\n❌  Keine Teilnehmer gefunden. Mögliche Gründe:')
        print('   • Gruppenname in gruppen.txt stimmt nicht exakt überein')
        print('   • SRF verwendet andere URL-Strukturen → --debug nutzen')
        print('   Beispiel: python3 config/find_gruppe.py --debug /')
        sys.exit(1)

    members_list = sorted(all_members.values(), key=lambda m: m['name'].lower())

    print(f'\nGefundene Teilnehmer ({len(members_list)}):')
    for m in members_list:
        print(f'  {m["name"]:<32} id: {m["id"]}')

    save(members_list, session=session)

if __name__ == '__main__':
    main()
