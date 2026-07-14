#!/usr/bin/env python3
"""
fetch_wm_archiv.py – Generiert ein Archiv-Dashboard für WM 2022 (Katar).
Ausgabe: WM_2022_Archiv.html im Hauptverzeichnis des Projekts.
Aufruf:  python3 tools/fetch_wm_archiv.py
"""

import os, re, json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(SCRIPT_DIR)

# ═══════════════════════════════════════════════════════════════════════════
#  D A T E N
# ═══════════════════════════════════════════════════════════════════════════

META = {
    'name':        'WM 2022',
    'ort':         'Katar 🇶🇦',
    'datum':       '20. November – 18. Dezember 2022',
    'teams':       32,
    'spiele':      64,
    'weltmeister': '🇦🇷 Argentinien',
    'finalist':    '🇫🇷 Frankreich',
    'dritter':     '🇭🇷 Kroatien',
    'vierter':     '🇲🇦 Marokko',
}

# Tupel: (Heim, Gast, Tore_H, Tore_G, HT_H, HT_G, Datum_str)
GRUPPEN = [
    {
        'name': 'Gruppe A',
        'teams': ['🇶🇦 Katar', '🇪🇨 Ecuador', '🇸🇳 Senegal', '🇳🇱 Niederlande'],
        'spiele': [
            ('🇶🇦 Katar',       '🇪🇨 Ecuador',      0,2, 0,2, '20.11.'),
            ('🇸🇳 Senegal',     '🇳🇱 Niederlande',   0,2, 0,1, '21.11.'),
            ('🇶🇦 Katar',       '🇸🇳 Senegal',       1,3, 0,1, '25.11.'),
            ('🇳🇱 Niederlande', '🇪🇨 Ecuador',       1,1, 0,1, '25.11.'),
            ('🇪🇨 Ecuador',     '🇸🇳 Senegal',       1,2, 0,0, '29.11.'),
            ('🇳🇱 Niederlande', '🇶🇦 Katar',         2,0, 2,0, '29.11.'),
        ],
    },
    {
        'name': 'Gruppe B',
        'teams': ['🏴󠁧󠁢󠁥󠁮󠁧󠁿 England', '🇮🇷 Iran', '🇺🇸 USA', '🏴󠁧󠁢󠁷󠁬󠁳󠁿 Wales'],
        'spiele': [
            ('🏴󠁧󠁢󠁥󠁮󠁧󠁿 England', '🇮🇷 Iran',       6,2, 3,0, '21.11.'),
            ('🇺🇸 USA',         '🏴󠁧󠁢󠁷󠁬󠁳󠁿 Wales',     1,1, 1,0, '21.11.'),
            ('🏴󠁧󠁢󠁥󠁮󠁧󠁿 England', '🇺🇸 USA',         0,0, 0,0, '25.11.'),
            ('🏴󠁧󠁢󠁷󠁬󠁳󠁿 Wales',   '🇮🇷 Iran',       0,2, 0,1, '25.11.'),
            ('🏴󠁧󠁢󠁷󠁬󠁳󠁿 Wales',   '🏴󠁧󠁢󠁥󠁮󠁧󠁿 England', 0,3, 0,0, '29.11.'),
            ('🇮🇷 Iran',        '🇺🇸 USA',         0,1, 0,0, '29.11.'),
        ],
    },
    {
        'name': 'Gruppe C',
        'teams': ['🇦🇷 Argentinien', '🇸🇦 Saudi-Arabien', '🇲🇽 Mexiko', '🇵🇱 Polen'],
        'spiele': [
            ('🇦🇷 Argentinien',  '🇸🇦 Saudi-Arabien', 1,2, 1,0, '22.11.'),
            ('🇲🇽 Mexiko',       '🇵🇱 Polen',          0,0, 0,0, '22.11.'),
            ('🇵🇱 Polen',        '🇸🇦 Saudi-Arabien',  2,0, 0,0, '26.11.'),
            ('🇦🇷 Argentinien',  '🇲🇽 Mexiko',         2,0, 0,0, '26.11.'),
            ('🇵🇱 Polen',        '🇦🇷 Argentinien',    0,2, 0,0, '30.11.'),
            ('🇸🇦 Saudi-Arabien','🇲🇽 Mexiko',         1,2, 0,0, '30.11.'),
        ],
    },
    {
        'name': 'Gruppe D',
        'teams': ['🇫🇷 Frankreich', '🇦🇺 Australien', '🇩🇰 Dänemark', '🇹🇳 Tunesien'],
        'spiele': [
            ('🇫🇷 Frankreich', '🇦🇺 Australien', 4,1, 2,1, '22.11.'),
            ('🇩🇰 Dänemark',   '🇹🇳 Tunesien',   0,0, 0,0, '22.11.'),
            ('🇫🇷 Frankreich', '🇩🇰 Dänemark',   2,1, 1,0, '26.11.'),
            ('🇦🇺 Australien', '🇹🇳 Tunesien',   1,0, 0,0, '26.11.'),
            ('🇹🇳 Tunesien',   '🇫🇷 Frankreich', 1,0, 0,0, '30.11.'),
            ('🇦🇺 Australien', '🇩🇰 Dänemark',   1,0, 0,0, '30.11.'),
        ],
    },
    {
        'name': 'Gruppe E',
        'teams': ['🇯🇵 Japan', '🇪🇸 Spanien', '🇩🇪 Deutschland', '🇨🇷 Costa Rica'],
        'spiele': [
            ('🇪🇸 Spanien',     '🇨🇷 Costa Rica',  7,0, 3,0, '23.11.'),
            ('🇩🇪 Deutschland', '🇯🇵 Japan',        1,2, 1,0, '23.11.'),
            ('🇯🇵 Japan',       '🇨🇷 Costa Rica',  0,1, 0,0, '27.11.'),
            ('🇪🇸 Spanien',     '🇩🇪 Deutschland', 1,1, 0,0, '27.11.'),
            ('🇯🇵 Japan',       '🇪🇸 Spanien',     2,1, 0,0, '01.12.'),
            ('🇨🇷 Costa Rica',  '🇩🇪 Deutschland', 2,4, 0,2, '01.12.'),
        ],
    },
    {
        'name': 'Gruppe F',
        'teams': ['🇲🇦 Marokko', '🇭🇷 Kroatien', '🇧🇪 Belgien', '🇨🇦 Kanada'],
        'spiele': [
            ('🇲🇦 Marokko',  '🇭🇷 Kroatien', 0,0, 0,0, '23.11.'),
            ('🇧🇪 Belgien',  '🇨🇦 Kanada',   1,0, 0,0, '23.11.'),
            ('🇧🇪 Belgien',  '🇲🇦 Marokko',  0,2, 0,0, '27.11.'),
            ('🇭🇷 Kroatien', '🇨🇦 Kanada',   4,1, 1,1, '27.11.'),
            ('🇲🇦 Marokko',  '🇨🇦 Kanada',   2,1, 1,0, '01.12.'),
            ('🇭🇷 Kroatien', '🇧🇪 Belgien',  0,0, 0,0, '01.12.'),
        ],
    },
    {
        'name': 'Gruppe G',
        'teams': ['🇧🇷 Brasilien', '🇨🇭 Schweiz', '🇨🇲 Kamerun', '🇷🇸 Serbien'],
        'spiele': [
            ('🇧🇷 Brasilien', '🇷🇸 Serbien',  2,0, 0,0, '24.11.'),
            ('🇨🇭 Schweiz',   '🇨🇲 Kamerun',  1,0, 0,0, '24.11.'),
            ('🇧🇷 Brasilien', '🇨🇭 Schweiz',   1,0, 0,0, '28.11.'),
            ('🇨🇲 Kamerun',   '🇷🇸 Serbien',   3,3, 1,2, '28.11.'),
            ('🇨🇲 Kamerun',   '🇧🇷 Brasilien', 1,0, 0,0, '02.12.'),
            ('🇨🇭 Schweiz',   '🇷🇸 Serbien',   3,2, 1,0, '02.12.'),
        ],
    },
    {
        'name': 'Gruppe H',
        'teams': ['🇵🇹 Portugal', '🇰🇷 Südkorea', '🇺🇾 Uruguay', '🇬🇭 Ghana'],
        'spiele': [
            ('🇵🇹 Portugal',  '🇬🇭 Ghana',     3,2, 1,0, '24.11.'),
            ('🇺🇾 Uruguay',   '🇰🇷 Südkorea',  0,0, 0,0, '24.11.'),
            ('🇵🇹 Portugal',  '🇺🇾 Uruguay',   2,0, 0,0, '28.11.'),
            ('🇰🇷 Südkorea',  '🇬🇭 Ghana',     2,3, 1,2, '28.11.'),
            ('🇰🇷 Südkorea',  '🇵🇹 Portugal',  2,1, 1,1, '02.12.'),
            ('🇬🇭 Ghana',     '🇺🇾 Uruguay',   0,2, 0,2, '02.12.'),
        ],
    },
]

# Tupel: (Heim, Gast, Tore_H, Tore_G, VerlängerungOderElf, Notiz, Datum, Paarung)
KO = {
    'R16': [
        ('🇳🇱 Niederlande',  '🇺🇸 USA',          3,1, False, '',                      '03.12.', 'A1 – B2'),
        ('🇦🇷 Argentinien',  '🇦🇺 Australien',   2,1, False, '',                      '03.12.', 'C1 – D2'),
        ('🇫🇷 Frankreich',   '🇵🇱 Polen',         3,1, False, '',                      '04.12.', 'D1 – C2'),
        ('🏴󠁧󠁢󠁥󠁮󠁧󠁿 England',    '🇸🇳 Senegal',       3,0, False, '',                      '04.12.', 'B1 – A2'),
        ('🇯🇵 Japan',        '🇭🇷 Kroatien',      1,1, True,  'Kroatien 3:1 i.E.',     '05.12.', 'E1 – F2'),
        ('🇧🇷 Brasilien',    '🇰🇷 Südkorea',      4,1, False, '',                      '05.12.', 'G1 – H2'),
        ('🇲🇦 Marokko',      '🇪🇸 Spanien',       0,0, True,  'Marokko 3:0 i.E.',      '06.12.', 'F1 – E2'),
        ('🇵🇹 Portugal',     '🇨🇭 Schweiz',       6,1, False, '',                      '06.12.', 'H1 – G2'),
    ],
    'QF': [
        ('🇳🇱 Niederlande',  '🇦🇷 Argentinien',  2,2, True,  'Argentinien 4:3 i.E.',  '09.12.', ''),
        ('🇭🇷 Kroatien',     '🇧🇷 Brasilien',     1,1, True,  'Kroatien 4:2 i.E.',     '09.12.', ''),
        ('🇲🇦 Marokko',      '🇵🇹 Portugal',      1,0, False, '',                      '10.12.', ''),
        ('🏴󠁧󠁢󠁥󠁮󠁧󠁿 England',    '🇫🇷 Frankreich',    1,2, False, '',                      '10.12.', ''),
    ],
    'SF': [
        ('🇦🇷 Argentinien',  '🇭🇷 Kroatien',     3,0, False, '',                      '13.12.', ''),
        ('🇫🇷 Frankreich',   '🇲🇦 Marokko',      2,0, False, '',                      '14.12.', ''),
    ],
    'P3': [
        ('🇭🇷 Kroatien',     '🇲🇦 Marokko',      2,1, False, '',                      '17.12.', ''),
    ],
    'F': [
        ('🇦🇷 Argentinien',  '🇫🇷 Frankreich',   3,3, True,  'Argentinien 4:2 i.E.',  '18.12.', ''),
    ],
}

TORSCHUETZEN = [
    (8,  '🇫🇷 Kylian Mbappé',        'Frankreich'),
    (7,  '🇦🇷 Lionel Messi',          'Argentinien'),
    (4,  '🇦🇷 Julián Álvarez',        'Argentinien'),
    (4,  '🇫🇷 Olivier Giroud',         'Frankreich'),
    (3,  '🇵🇹 Gonçalo Ramos',          'Portugal'),
    (3,  '🇳🇱 Cody Gakpo',            'Niederlande'),
    (3,  '🏴󠁧󠁢󠁥󠁮󠁧󠁿 Marcus Rashford',     'England'),
    (3,  '🇧🇷 Richarlison',            'Brasilien'),
    (3,  '🇮🇷 Mehdi Taremi',           'Iran'),
    (3,  '🇪🇨 Enner Valencia',         'Ecuador'),
    (3,  '🇨🇲 Vincent Aboubakar',      'Kamerun'),
    (2,  '🏴󠁧󠁢󠁥󠁮󠁧󠁿 Bukayo Saka',         'England'),
    (2,  '🇵🇹 João Félix',             'Portugal'),
    (2,  '🇪🇸 Ferran Torres',          'Spanien'),
    (2,  '🇨🇭 Breel Embolo',           'Schweiz'),
    (2,  '🇵🇱 Robert Lewandowski',     'Polen'),
    (2,  '🇷🇸 Aleksandar Mitrović',    'Serbien'),
    (2,  '🇦🇺 Mitchell Duke',          'Australien'),
    (2,  '🇲🇦 Youssef En-Nesyri',      'Marokko'),
    (2,  '🇦🇷 Ángel Di María',         'Argentinien'),
]

# ═══════════════════════════════════════════════════════════════════════════
#  S T A N D I N G S
# ═══════════════════════════════════════════════════════════════════════════

def compute_standings(gruppe):
    teams = {}
    for t in gruppe['teams']:
        teams[t] = {'pts':0,'w':0,'d':0,'l':0,'gf':0,'ga':0}
    for (t1,t2,g1,g2,_ht1,_ht2,_d) in gruppe['spiele']:
        if t1 not in teams or t2 not in teams:
            continue
        teams[t1]['gf'] += g1; teams[t1]['ga'] += g2
        teams[t2]['gf'] += g2; teams[t2]['ga'] += g1
        if g1 > g2:
            teams[t1]['pts'] += 3; teams[t1]['w'] += 1; teams[t2]['l'] += 1
        elif g1 < g2:
            teams[t2]['pts'] += 3; teams[t2]['w'] += 1; teams[t1]['l'] += 1
        else:
            teams[t1]['pts'] += 1; teams[t1]['d'] += 1
            teams[t2]['pts'] += 1; teams[t2]['d'] += 1
    return sorted(teams.items(), key=lambda x: (-x[1]['pts'], -(x[1]['gf']-x[1]['ga']), -x[1]['gf']))

# ═══════════════════════════════════════════════════════════════════════════
#  H T M L - G E N E R A T O R E N
# ═══════════════════════════════════════════════════════════════════════════

def score_cell(g1, g2, ext, notiz):
    if ext:
        short = notiz.split(' ')[-1] if notiz else 'n.V./i.E.'
        return f'<span class="score ext">{g1}:{g2} n.V.</span><br><span class="pen">{short}</span>'
    return f'<span class="score">{g1}:{g2}</span>'

def winner(g1, g2, ext, notiz, t1, t2):
    if ext:
        # winner is in the notiz, e.g. "Argentinien 4:3 i.E."
        # crude: extract from notiz
        for t in [t1, t2]:
            short = t.split(' ', 1)[-1] if ' ' in t else t
            if short in notiz:
                return t
        return t1 if g1 > g2 else (t2 if g2 > g1 else '')
    return t1 if g1 > g2 else (t2 if g2 > g1 else '')

def render_gruppen():
    html = '<div class="gruppen-grid">'
    for g in GRUPPEN:
        st = compute_standings(g)
        html += f'<div class="gruppe-box"><h3>{g["name"]}</h3>'
        html += '<table class="ptable" data-export="1"><thead><tr><th>Team</th><th>Sp</th><th>S</th><th>U</th><th>N</th><th>T</th><th>Td</th><th>Pts</th></tr></thead><tbody>'
        for i,(t,s) in enumerate(st):
            cls = 'qf' if i < 2 else ''
            html += f'<tr class="{cls}"><td>{t}</td><td>{s["w"]+s["d"]+s["l"]}</td><td>{s["w"]}</td><td>{s["d"]}</td><td>{s["l"]}</td><td>{s["gf"]}:{s["ga"]}</td><td>{s["gf"]-s["ga"]:+d}</td><td><b>{s["pts"]}</b></td></tr>'
        html += '</tbody></table>'
        html += '<table class="stab" data-export="1"><thead><tr><th>Datum</th><th>Heim</th><th>Erg.</th><th>Gast</th></tr></thead><tbody>'
        for (t1,t2,g1,g2,ht1,ht2,d) in g['spiele']:
            res = f'{g1}:{g2}'
            ht = f'({ht1}:{ht2})'
            html += f'<tr><td class="dt">{d}</td><td class="ra">{t1}</td><td class="sc">{res} <span class="ht">{ht}</span></td><td>{t2}</td></tr>'
        html += '</tbody></table></div>'
    html += '</div>'
    return html

def render_spielplan():
    # Collect all group games
    all_games = []
    for g in GRUPPEN:
        for (t1,t2,g1,g2,ht1,ht2,d) in g['spiele']:
            all_games.append((d, g['name'], t1, t2, g1, g2, ht1, ht2, False, ''))
    # Sort by date (crude: convert DD.MM. to sortable)
    def dkey(r):
        d = r[0]
        parts = d.rstrip('.').split('.')
        return (int(parts[1]), int(parts[0]))
    all_games.sort(key=dkey)

    html = '<h3 style="margin-bottom:10px">Vorrunde</h3>'
    html += '<table class="ptable" data-export="1"><thead><tr><th>Datum</th><th>Runde</th><th>Heim</th><th>Erg. (HZ)</th><th>Gast</th></tr></thead><tbody>'
    for (d,rnd,t1,t2,g1,g2,ht1,ht2,ext,notiz) in all_games:
        html += f'<tr><td class="dt">{d}</td><td class="rnd">{rnd}</td><td class="ra">{t1}</td><td class="sc">{g1}:{g2} <span class="ht">({ht1}:{ht2})</span></td><td>{t2}</td></tr>'
    html += '</tbody></table>'

    for rnd_key, rnd_label in [('R16','Achtelfinale'),('QF','Viertelfinale'),('SF','Halbfinale'),('P3','Spiel um Platz 3'),('F','Finale')]:
        html += f'<h3 style="margin:18px 0 8px">{rnd_label}</h3>'
        html += '<table class="ptable" data-export="1"><thead><tr><th>Datum</th><th>Heim</th><th>Ergebnis</th><th>Gast</th><th>Anm.</th></tr></thead><tbody>'
        for row in KO[rnd_key]:
            t1,t2,g1,g2,ext,notiz,d,paar = row
            sc = f'{g1}:{g2}' + (' n.V.' if ext else '')
            html += f'<tr><td class="dt">{d}</td><td class="ra">{t1}</td><td class="sc">{sc}</td><td>{t2}</td><td class="ht">{notiz}</td></tr>'
        html += '</tbody></table>'
    return html

def render_ko():
    # Render a bracket-style layout
    def game_box(row, cls=''):
        t1,t2,g1,g2,ext,notiz,d,paar = row
        w = winner(g1,g2,ext,notiz,t1,t2)
        sc_label = f'{g1}:{g2}' + (' n.V.' if ext else '')
        def row_html(t, is_winner):
            name = t.split(' ', 1)[-1] if ' ' in t else t
            flag = t.split(' ')[0]
            pts_cls = ' winner' if is_winner else ''
            return f'<tr class="brow{pts_cls}"><td class="bflag">{flag}</td><td class="bname">{name}</td><td class="bsc">{g1 if t==t1 else g2}</td></tr>'
        box  = f'<div class="kbox {cls}">'
        if paar:
            box += f'<div class="kpaar">{paar}</div>'
        box += f'<table class="ktab"><tbody>'
        box += row_html(t1, t1==w)
        box += row_html(t2, t2==w)
        box += '</tbody></table>'
        if notiz:
            box += f'<div class="kpen">{notiz}</div>'
        box += f'<div class="kdate">{d}</div></div>'
        return box

    html  = '<div class="bracket">'
    html += '<div class="bracket-col"><h4>Achtelfinale</h4>'
    for i,row in enumerate(KO['R16']):
        html += game_box(row)
    html += '</div>'
    html += '<div class="bracket-col"><h4>Viertelfinale</h4>'
    for row in KO['QF']:
        html += game_box(row)
    html += '</div>'
    html += '<div class="bracket-col"><h4>Halbfinale</h4>'
    for row in KO['SF']:
        html += game_box(row)
    html += '</div>'
    html += '<div class="bracket-col final-col"><h4>Finale</h4>'
    html += game_box(KO['F'][0], 'finale')
    html += '<h4 style="margin-top:20px">Platz 3</h4>'
    html += game_box(KO['P3'][0])
    html += '</div></div>'
    return html

def render_torschuetzen():
    html = '<table class="ptable" data-export="1">'
    html += '<thead><tr><th>Rang</th><th>Spieler</th><th>Land</th><th>Tore</th></tr></thead><tbody>'
    rank = 1
    prev_goals = None
    for i,(goals,spieler,land) in enumerate(TORSCHUETZEN):
        if goals != prev_goals:
            rank = i + 1
            prev_goals = goals
        html += f'<tr><td>{rank}</td><td>{spieler}</td><td>{land}</td><td><b>{goals}</b></td></tr>'
    html += '</tbody></table>'
    return html

# ═══════════════════════════════════════════════════════════════════════════
#  H A U P T - H T M L
# ═══════════════════════════════════════════════════════════════════════════

def generate_html():
    gruppen_html     = render_gruppen()
    spielplan_html   = render_spielplan()
    ko_html          = render_ko()
    torsch_html      = render_torschuetzen()

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WM 2022 Katar – Archiv</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',sans-serif;background:#f2f2f7;color:#1c1c1e;min-height:100vh;display:flex;flex-direction:column}}

/* ── Layout ── */
#layout{{display:flex;flex:1;min-height:100vh}}
#sidebar{{width:220px;min-width:160px;background:#fff;border-right:1px solid #e5e5ea;display:flex;flex-direction:column;position:sticky;top:0;height:100vh;overflow-y:auto}}
#main{{flex:1;display:flex;flex-direction:column;overflow:hidden}}

/* ── Sidebar ── */
.sb-header{{padding:18px 14px 12px;border-bottom:1px solid #e5e5ea}}
.sb-title{{font-size:14px;font-weight:700;color:#1c1c1e}}
.sb-sub{{font-size:10px;color:#8e8e93;margin-top:2px}}
.sb-nav{{padding:8px 8px;flex:1}}
.sb-link{{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;cursor:pointer;font-size:13px;color:#1c1c1e;text-decoration:none;border:none;background:none;width:100%;text-align:left;transition:background .15s}}
.sb-link:hover{{background:#f2f2f7}}
.sb-link.active{{background:#e8f0fd;color:#1a50a0;font-weight:600}}
.sb-icon{{font-size:16px;width:22px;text-align:center}}
.sb-back{{padding:12px 8px;border-top:1px solid #e5e5ea}}
.sb-back a{{display:flex;align-items:center;gap:6px;font-size:12px;color:#8e8e93;text-decoration:none;padding:6px 10px;border-radius:8px}}
.sb-back a:hover{{background:#f2f2f7}}

/* ── Content ── */
#content-header{{background:#fff;border-bottom:1px solid #e5e5ea;padding:14px 24px 12px}}
.ch-title{{font-size:18px;font-weight:700;color:#1c1c1e}}
.ch-meta{{font-size:12px;color:#6c6c70;margin-top:3px}}
.ch-champions{{display:flex;gap:16px;margin-top:10px;flex-wrap:wrap}}
.ch-item{{background:#f2f2f7;border-radius:8px;padding:6px 12px;font-size:12px}}
.ch-item .lbl{{color:#6c6c70;font-size:10px;text-transform:uppercase;letter-spacing:.5px}}
.ch-item .val{{font-weight:700;color:#1c1c1e;margin-top:1px}}
.ch-item.gold{{background:#fff8e0;border:1px solid #f5c842}}
.ch-item.gold .val{{color:#b8860b}}
#section-area{{flex:1;overflow-y:auto;padding:20px 24px 40px}}
section{{display:none}}
section.active{{display:block}}

/* ── Gruppen ── */
.gruppen-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:16px}}
.gruppe-box{{background:#fff;border-radius:12px;padding:14px 16px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.gruppe-box h3{{font-size:13px;font-weight:700;color:#1a50a0;margin-bottom:10px;text-transform:uppercase;letter-spacing:.5px}}

/* ── Tables ── */
.ptable{{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:12px}}
.ptable th{{background:#1e3764;color:#fff;font-weight:600;font-size:10px;padding:5px 7px;text-align:left;white-space:nowrap}}
.ptable td{{padding:4px 7px;border-bottom:1px solid #f2f2f7;white-space:nowrap}}
.ptable tr:hover td{{background:#f7f9fd}}
.ptable tr.qf td{{background:#e8f0fd}}
.ptable tr.qf:hover td{{background:#dce8fb}}
.stab{{width:100%;border-collapse:collapse;font-size:11px}}
.stab th{{background:#4a5568;color:#fff;font-weight:600;font-size:10px;padding:4px 6px;text-align:left}}
.stab td{{padding:3px 6px;border-bottom:1px solid #f2f2f7}}
.stab tr:hover td{{background:#f7f9fd}}
td.dt{{color:#8e8e93;font-size:10px;white-space:nowrap}}
td.ra{{text-align:right}}
td.sc{{text-align:center;font-weight:700;font-size:12px}}
td.rnd{{font-size:10px;color:#6c6c70}}
.ht{{font-size:10px;color:#8e8e93;font-weight:400}}
.pen{{font-size:10px;color:#a0522d;font-weight:600}}

/* ── KO Bracket ── */
.bracket{{display:flex;gap:8px;overflow-x:auto;padding-bottom:10px}}
.bracket-col{{display:flex;flex-direction:column;gap:8px;min-width:200px}}
.bracket-col h4{{font-size:11px;font-weight:700;color:#6c6c70;text-transform:uppercase;letter-spacing:.5px;padding:4px 0 6px;text-align:center}}
.kbox{{background:#fff;border-radius:10px;padding:8px 10px;box-shadow:0 1px 4px rgba(0,0,0,.07);position:relative}}
.kbox.finale{{border:2px solid #f5c842;background:#fff8e0}}
.kpaar{{font-size:9px;color:#8e8e93;margin-bottom:4px;text-align:right}}
.kdate{{font-size:9px;color:#8e8e93;margin-top:4px;text-align:right}}
.kpen{{font-size:10px;color:#a0522d;font-weight:600;text-align:center;margin-top:3px}}
.ktab{{width:100%;border-collapse:collapse}}
.brow td{{padding:2px 4px;font-size:12px}}
.brow.winner td{{font-weight:700;color:#1a50a0}}
td.bflag{{font-size:14px;width:20px}}
td.bname{{flex:1}}
td.bsc{{text-align:right;font-variant-numeric:tabular-nums;min-width:18px}}
.final-col{{min-width:210px}}

/* ── Scrollbar ── */
::-webkit-scrollbar{{width:6px;height:6px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:#c7c7cc;border-radius:3px}}

@media(max-width:640px){{
  #sidebar{{width:52px}}
  .sb-title,.sb-sub,.sb-link span:not(.sb-icon){{display:none}}
  .sb-link{{justify-content:center;padding:10px}}
  #section-area{{padding:14px 12px 30px}}
  .gruppen-grid{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>
<div id="layout">

  <!-- Sidebar -->
  <div id="sidebar">
    <div class="sb-header">
      <div class="sb-title">WM 2022</div>
      <div class="sb-sub">Katar · Archiv</div>
    </div>
    <nav class="sb-nav">
      <button class="sb-link active" onclick="showSection('gruppen',this)"><span class="sb-icon">🗂</span><span>Gruppen</span></button>
      <button class="sb-link" onclick="showSection('spielplan',this)"><span class="sb-icon">📋</span><span>Spielplan</span></button>
      <button class="sb-link" onclick="showSection('korunde',this)"><span class="sb-icon">⚡</span><span>KO-Runde</span></button>
      <button class="sb-link" onclick="showSection('torschuetzen',this)"><span class="sb-icon">⚽</span><span>Torschützen</span></button>
    </nav>
    <div class="sb-back"><a href="index.html">← Alle Turniere</a></div>
  </div>

  <!-- Main -->
  <div id="main">
    <div id="content-header">
      <div class="ch-title">🏆 WM 2022 – Katar</div>
      <div class="ch-meta">{META['datum']} · {META['teams']} Teams · {META['spiele']} Spiele</div>
      <div class="ch-champions">
        <div class="ch-item gold"><div class="lbl">🥇 Weltmeister</div><div class="val">{META['weltmeister']}</div></div>
        <div class="ch-item"><div class="lbl">🥈 Finalist</div><div class="val">{META['finalist']}</div></div>
        <div class="ch-item"><div class="lbl">🥉 3. Platz</div><div class="val">{META['dritter']}</div></div>
        <div class="ch-item"><div class="lbl">4. Platz</div><div class="val">{META['vierter']}</div></div>
      </div>
    </div>

    <div id="section-area">
      <section id="gruppen" class="active">{gruppen_html}</section>
      <section id="spielplan">{spielplan_html}</section>
      <section id="korunde">{ko_html}</section>
      <section id="torschuetzen">{torsch_html}</section>
    </div>
  </div>
</div>

<script>
function showSection(id, btn) {{
  document.querySelectorAll('#section-area section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.sb-link').forEach(b => b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  if(btn) btn.classList.add('active');
}}
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════════
#  I N D E X . H T M L  A K T U A L I S I E R E N
# ═══════════════════════════════════════════════════════════════════════════

def update_index(output_filename):
    index_path = os.path.join(ROOT_DIR, 'web', 'index.html')
    if not os.path.exists(index_path):
        print('ℹ️  index.html nicht gefunden – überspringe Update')
        return
    with open(index_path, encoding='utf-8') as f:
        content = f.read()

    # Extract current TURNIERE array
    m = re.search(r'const TURNIERE\s*=\s*(\[.*?\]);', content, re.DOTALL)
    if not m:
        print('ℹ️  TURNIERE nicht in index.html gefunden')
        return

    try:
        turniere = json.loads(m.group(1))
    except Exception:
        print('⚠️  TURNIERE-JSON nicht parsbar')
        return

    # Check if WM 2022 already present
    existing = [t.get('datei') for t in turniere]
    if output_filename in existing:
        print(f'ℹ️  {output_filename} bereits in index.html')
        return

    turniere.append({
        'name': 'WM 2022',
        'datei': output_filename,
        'sub': 'Fussball-Weltmeisterschaft Katar',
        'aktiv': False,
    })

    new_array = json.dumps(turniere, ensure_ascii=False, indent=2)
    new_content = content[:m.start(1)] + new_array + content[m.end(1):]
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f'✅ index.html → {output_filename} hinzugefügt')


def update_rangverlauf(output_filename):
    """Fügt WM 2022 zum TURNIERE-Array in WM_Rangverlauf.html hinzu."""
    rv_path = os.path.join(ROOT_DIR, 'web', 'WM_Rangverlauf.html')
    if not os.path.exists(rv_path):
        print('ℹ️  WM_Rangverlauf.html nicht gefunden')
        return
    with open(rv_path, encoding='utf-8') as f:
        content = f.read()

    m = re.search(r'/\*TURNIERE_START\*/const TURNIERE=(.*?);/\*TURNIERE_END\*/', content, re.DOTALL)
    if not m:
        print('ℹ️  TURNIERE-Block in WM_Rangverlauf.html nicht gefunden')
        return

    try:
        turniere = json.loads(m.group(1))
    except Exception:
        print('⚠️  TURNIERE-JSON in WM_Rangverlauf.html nicht parsbar')
        return

    existing = [t.get('datei') for t in turniere]
    if output_filename in existing:
        print(f'ℹ️  {output_filename} bereits in WM_Rangverlauf.html')
        return

    turniere.append({
        'name': 'WM 2022',
        'datei': output_filename,
        'sub': 'Fussball-Weltmeisterschaft Katar',
        'aktiv': False,
    })

    new_block = f'/*TURNIERE_START*/const TURNIERE={json.dumps(turniere, ensure_ascii=False)};/*TURNIERE_END*/'
    new_content = content[:m.start()] + new_block + content[m.end():]
    with open(rv_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f'✅ WM_Rangverlauf.html → Switcher um {output_filename} erweitert')


# ═══════════════════════════════════════════════════════════════════════════
#  M A I N
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    output_filename = 'WM_2022_Archiv.html'
    web_dir = os.path.join(ROOT_DIR, 'web')
    os.makedirs(web_dir, exist_ok=True)
    output_path = os.path.join(web_dir, output_filename)

    html = generate_html()
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'✅ {output_path}')

    update_index(output_filename)
    update_rangverlauf(output_filename)
    print('🏁 Fertig.')
