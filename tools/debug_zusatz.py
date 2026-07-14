#!/usr/bin/env python3
"""Debug: Zeigt Zusatzfragen-Antworten von Roger K und Beat N direkt."""

import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Abhängigkeiten prüfen
try:
    import requests, browser_cookie3
    from bs4 import BeautifulSoup
except ImportError:
    print("Fehlende Pakete – bitte installieren:")
    print("  pip install requests browser-cookie3 beautifulsoup4 --break-system-packages")
    sys.exit(1)

BASE_URL = 'https://wmtippspiel.srf.ch'
TARGETS = [
    ('Roger K',  'a3nm'),
    ('Beat N',   'XbPvY'),
    ('Röle A',   'oj5kA'),
]

def get_session():
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0'})
    for fn in (browser_cookie3.safari, browser_cookie3.chrome):
        try:
            jar = fn(domain_name='.wmtippspiel.srf.ch')
            s.cookies.update(jar)
            break
        except Exception:
            pass
    return s

def fetch_round40(session, name, uid):
    url = f'{BASE_URL}/users/{uid}/round/40'
    print(f'\n{"="*60}')
    print(f'  {name}  ({uid})')
    print(f'  {url}')
    print('='*60)
    resp = session.get(url, timeout=20)
    doc  = BeautifulSoup(resp.text, 'html.parser')

    els = doc.find_all(attrs={'data-react-class': True})
    if not els:
        print('  ❌ Keine React-Komponenten gefunden (Login-Problem?)')
        return

    for el in els:
        cls = el.get('data-react-class', '')
        try:
            props = json.loads(el.get('data-react-props', '{}'))
        except Exception:
            props = {}

        print(f'\n  ── Komponente: {cls} ──')
        # Vollständige Props ausgeben
        print(json.dumps(props, ensure_ascii=False, indent=4))

session = get_session()
for name, uid in TARGETS:
    fetch_round40(session, name, uid)

print('\n✅ Fertig.')
