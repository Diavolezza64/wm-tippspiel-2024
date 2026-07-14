#!/usr/bin/env python3
"""WM 2026 Tippspiel – Rangverlauf-Chart (PDF)
Aufruf: python3 wm_chart.py [data_dir [output_dir]]
  data_dir   – Ordner mit WM_Rangverlauf_*.csv  (Standard: Ordner des Scripts)
  output_dir – Zielordner für das PDF            (Standard: data_dir)
"""
import sys, os, csv, glob, subprocess
from datetime import datetime

_script_dir = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = sys.argv[1] if len(sys.argv) > 1 else _script_dir
OUTPUT_DIR = sys.argv[2] if len(sys.argv) > 2 else DATA_DIR

# ── Abhängigkeiten ────────────────────────────────────────────────────────────
def ensure_matplotlib():
    try:
        import matplotlib
        return True
    except ImportError:
        r = subprocess.run([sys.executable, '-m', 'pip', 'install', 'matplotlib', '-q',
                            '--break-system-packages'])
        if r.returncode != 0:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'matplotlib', '-q'], check=True)

ensure_matplotlib()
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ── CSV laden ─────────────────────────────────────────────────────────────────
files = sorted(glob.glob(os.path.join(DATA_DIR, 'WM_Rangverlauf_*.csv')))
if not files:
    print('⚠️  Keine WM_Rangverlauf_*.csv gefunden.'); sys.exit(1)
csv_path = files[-1]
print(f'   Chart-Quelle: {os.path.basename(csv_path)}')

with open(csv_path, encoding='utf-8-sig') as f:
    reader = csv.reader(f, delimiter=';')
    header = next(reader)
    rows = [r for r in reader if r and r[0].strip()]

members, col_pts = [], {}
for i, h in enumerate(header):
    if h.endswith(' Punkte kum.'):
        name = h[:-len(' Punkte kum.')].strip()
        members.append(name)
        col_pts[name] = i

game_nums = [int(r[0]) for r in rows]
points    = {m: [int(r[col_pts[m]]) for r in rows] for m in members}

# Endpunkte für Sortierung & Farben
final_pts = {m: points[m][-1] for m in members}
ranked    = sorted(members, key=lambda m: -final_pts[m])

# ── Farben (30 distinkte) ─────────────────────────────────────────────────────
COLORS = [
    '#e6194b','#3cb44b','#4363d8','#f58231','#911eb4',
    '#42d4f4','#f032e6','#bfef45','#fabed4','#469990',
    '#dcbeff','#9A6324','#fffac8','#800000','#aaffc3',
    '#808000','#ffd8b1','#000075','#a9a9a9','#ffffff',
    '#e6beff','#008080','#ffe119','#000000','#4169e1',
    '#dc143c','#00ced1','#ff8c00','#8b008b','#2e8b57',
]
color_map = {m: COLORS[i % len(COLORS)] for i, m in enumerate(ranked)}

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(18, 10))
fig.patch.set_facecolor('#0d1b2a')
ax.set_facecolor('#0d1b2a')

# Hintergrund-Rasterlinien
ax.yaxis.set_major_locator(ticker.MultipleLocator(20))
ax.grid(axis='y', color='#1e3a5f', linewidth=0.6, zorder=0)
ax.grid(axis='x', color='#1e3a5f', linewidth=0.4, zorder=0)

# Linien zeichnen – Top 5 prominent, Rest gedämpft
for m in reversed(ranked):  # hinten → vorne (Top oben)
    rank = ranked.index(m) + 1
    top5 = rank <= 5
    ax.plot(game_nums, points[m],
            color=color_map[m],
            linewidth=2.2 if top5 else 0.9,
            alpha=1.0 if top5 else 0.45,
            zorder=10 if top5 else 5,
            label=f'{rank}. {m}  ({final_pts[m]} Pkt)')

# Endpunkte beschriften (Top 10)
for m in ranked[:10]:
    ax.annotate(f'{m.split()[0]} {final_pts[m]}',
                xy=(game_nums[-1], points[m][-1]),
                xytext=(4, 0), textcoords='offset points',
                color=color_map[m], fontsize=6.5,
                va='center', ha='left')

# Achsen
ax.set_xlim(game_nums[0] - 0.5, game_nums[-1] + 14)
ax.set_ylim(0, max(final_pts.values()) * 1.08)
ax.tick_params(colors='#8ab0d0', labelsize=8)
for spine in ax.spines.values():
    spine.set_edgecolor('#1e3a5f')

ax.set_xlabel('Spiel #', color='#8ab0d0', fontsize=9)
ax.set_ylabel('Punkte (kumuliert)', color='#8ab0d0', fontsize=9)

today_str = datetime.now().strftime('%d.%m.%Y')
ax.set_title(f'WM 2026 Tippspiel – Rangverlauf  |  Stand {today_str}  |  {len(game_nums)} Spiele',
             color='#c8dff0', fontsize=12, fontweight='bold', pad=14)

# Legende (2 Spalten)
leg = ax.legend(loc='upper left', ncol=2, fontsize=6.5,
                facecolor='#0a1520', edgecolor='#1e3a5f',
                labelcolor='#c8dff0', framealpha=0.85,
                handlelength=1.8, handleheight=0.8,
                borderpad=0.6, labelspacing=0.35)

plt.tight_layout(pad=1.2)

today_file = datetime.now().strftime('%Y-%m-%d')
out = os.path.join(OUTPUT_DIR, f'WM_RangverlaufChart_{today_file}.pdf')
plt.savefig(out, format='pdf', dpi=150, facecolor=fig.get_facecolor())
plt.close()
print(f'   ✅ Chart: {os.path.basename(out)}')
