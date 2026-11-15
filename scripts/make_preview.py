"""Draw assets/preview.png (1200 x 630): the README picture and the card shown when the site link is shared.

    python scripts/make_preview.py
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FC = ROOT / 'outputs' / 'forecast'
SHOW = [('GB|leather jacket', 'Leather jacket', '#1d4ed8'), ('GB|trench coat', 'Trench coat', '#dc2626'),
        ('GB|wool coat', 'Wool coat', '#059669')]

hist = pd.read_csv(FC / 'history.csv', index_col=0)
hist.index = pd.to_datetime(hist.index)
fc = pd.read_csv(FC / 'forecast.csv', parse_dates=['month'])
meta = json.loads((FC / 'meta.json').read_text())
base = hist[hist.index < meta['locked_from']].mean()
proof = json.loads((FC / 'validation.json').read_text())['3']

fig = plt.figure(figsize=(12, 6.3), dpi=100)
fig.patch.set_facecolor('white')
fig.text(0.05, 0.9, 'Fashion Trend Forecast', fontsize=30, weight='bold', color='#111827')
fig.text(0.05, 0.84, 'Garments, fabrics, colours and styles · England · France · Denmark · 3 and 6 months ahead',
         fontsize=14, color='#4b5563')
ax = fig.add_axes([0.05, 0.14, 0.62, 0.62])
for key, name, col in SHOW:
    y = hist[key] / base[key] * 100
    y = y[y.index >= '2024-01-01']
    f = fc[(fc.item == key) & (fc.horizon == 6)]
    lo, mid, hi = (f[c] / base[key] * 100 for c in ('low', 'mid', 'high'))
    ax.plot(y.index, y, color=col, lw=2.2, label=name)
    ax.plot([y.index[-1]] + list(f.month), [y.iloc[-1]] + list(mid), color=col, lw=2.2, ls='--')
    ax.fill_between(f.month, lo, hi, color=col, alpha=0.12, lw=0)
ax.axvline(hist.index[-1], color='#9ca3af', ls=':', lw=1.5)
ax.text(hist.index[-1], ax.get_ylim()[1], '  forecast', color='#6b7280', va='top', fontsize=11)
for s in ('top', 'right'):
    ax.spines[s].set_visible(False)
ax.spines['left'].set_color('#d1d5db')
ax.spines['bottom'].set_color('#d1d5db')
ax.tick_params(colors='#6b7280', labelsize=10)
import matplotlib.dates as mdates  # noqa: E402
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
ax.set_ylabel('Search interest (100 = usual level)', color='#6b7280', fontsize=10)
ax.legend(frameon=False, loc='upper left', fontsize=11)

stats = [(f'{proof["labels_right"]:.0%}', 'labels correct on a\nheld-out year'),
         (f'{proof["error_vs_last_year"]:.0%}', 'lower error than a\nlast-year baseline'),
         (f'{proof["inside_range"]:.0%}', 'of actual values within\nthe forecast range')]
for i, (big, small) in enumerate(stats):
    y0 = 0.66 - i * 0.21
    fig.text(0.73, y0, big, fontsize=34, weight='bold', color='#1d4ed8')
    fig.text(0.73, y0 - 0.07, small, fontsize=12, color='#374151', va='top')
fig.text(0.05, 0.04, '3-month forecasts · held-out test year Nov 2025 – Oct 2026 · Chronos-2',
         fontsize=10, color='#9ca3af')
(ROOT / 'assets').mkdir(exist_ok=True)
fig.savefig(ROOT / 'assets' / 'preview.png', facecolor='white')
print('assets/preview.png written')
