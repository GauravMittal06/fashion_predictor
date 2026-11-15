"""Fill the generated parts of README.md from the build outputs, so the numbers there are never typed by hand.

Replaces the text between <!-- name:start --> and <!-- name:end --> markers:
- results   key test-year results (outputs/forecast/validation.json, wgsn_check.csv)
- coverage  attributes forecast per type and country (outputs/forecast/items.csv, data/google_trends/not_forecast.csv)

    python scripts/make_readme.py
"""
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FC = ROOT / 'outputs' / 'forecast'
TYPES = ['Garments', 'Fabrics', 'Colours', 'Styles', 'Runway details']
COUNTRIES = [('GB', 'England'), ('FR', 'France'), ('DK', 'Denmark')]


def pct(x):
    return f'{x:.0%}'


def signed(x):
    return f'−{abs(x):.0%}' if x > 0 else f'+{abs(x):.0%}'        # error reduction shown as a minus


def results_block():
    v = json.loads((FC / 'validation.json').read_text())
    a, b = v['3'], v['6']
    rows = [
        ('Labels correct (Rising / Steady / Fading)', f'**{pct(a["labels_right"])}**', f'**{pct(b["labels_right"])}**'),
        ('Rising / Fading calls correct', f'**{a["calls_right"]} / {a["calls"]}** ({pct(a["calls_right"] / a["calls"])})',
         f'**{b["calls_right"]} / {b["calls"]}** ({pct(b["calls_right"] / b["calls"])})'),
        ('Items labelled correctly on most forecast dates', f'**{a["items_mostly_right"]} / {a["items"]}**',
         f'**{b["items_mostly_right"]} / {b["items"]}**'),
        ('Forecast error vs same-months-last-year baseline', f'**{signed(a["error_vs_last_year"])}**',
         f'**{signed(b["error_vs_last_year"])}**'),
        ('Actual values within the 80% forecast range', f'**{pct(a["inside_range"])}**', f'**{pct(b["inside_range"])}**'),
        ('Baseline: recent-trend rule, labels correct', pct(a['trend_rule_labels_right']), pct(b['trend_rule_labels_right'])),
        ('Baseline: always "Steady", labels correct', pct(a['always_steady_right']), pct(b['always_steady_right'])),
    ]
    out = ['| Metric | 3 months | 6 months |', '|---|---|---|'] + [f'| {r} | {x} | {y} |' for r, x, y in rows]
    w = FC / 'wgsn_check.csv'
    if w.exists():
        w = pd.read_csv(w)
        out += ['', f'**Benchmark:** two WGSN trend calls (burgundy, Feb 2025; boho, Jun 2025) were compared with the '
                    f'model\'s forecast made on the same date. The model was correct in {int(w.model_right.sum())} of '
                    f'{len(w)} country cases and WGSN in {int(w.wgsn_right.sum())} of {len(w)}.']
    return '\n'.join(out)


def coverage_block():
    items = pd.read_csv(FC / 'items.csv')
    nf = pd.read_csv(ROOT / 'data' / 'google_trends' / 'not_forecast.csv')
    out = ['| Type | ' + ' | '.join(n for _, n in COUNTRIES) + ' | Examples |', '|---|---|---|---|---|']
    for t in TYPES:
        cells = [str(((items.country == cc) & (items.group == t)).sum()) for cc, _ in COUNTRIES]
        ex = ', '.join(items[items.group == t].english.drop_duplicates().head(6).str.lower())
        out.append(f'| {t} | ' + ' | '.join(cells) + f' | {ex} |')
    out.append('| **Total** | ' + ' | '.join(f'**{(items.country == cc).sum()}**' for cc, _ in COUNTRIES) + ' | |')
    out += ['', f'{len(items)} forecast series in all. {len(nf)} attribute–country pairs are shown from the research '
                'data only, because Google has too few searches for them or they are not searched '
                '(listed in the app and in `data/google_trends/not_forecast.csv`).']
    return '\n'.join(out)


def fill(text, name, block):
    pat = re.compile(rf'(<!-- {name}:start -->\n).*?(<!-- {name}:end -->)', re.S)
    assert pat.search(text), f'marker {name} missing in README.md'
    return pat.sub(lambda m: m.group(1) + block + '\n' + m.group(2), text)


def main():
    p = ROOT / 'README.md'
    text = p.read_text(encoding='utf-8')
    text = fill(text, 'results', results_block())
    text = fill(text, 'coverage', coverage_block())
    p.write_text(text, encoding='utf-8')
    print('README.md updated')


if __name__ == '__main__':
    main()
