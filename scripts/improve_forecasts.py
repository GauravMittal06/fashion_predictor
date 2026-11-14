"""Experiment: can the forecast labels (Rising / Steady / Fading) be made more accurate - fairly?

Forecasts (Chronos-2, every start month, only earlier data):
  short       Jan 2022 onwards (what the app uses now)
  long        Nov 2019 onwards (longer memory)
  short+x     short, all items of a country forecast together (cross-learning)
  long+x      long, with cross-learning
Ways to turn a forecast into a label:
  strict      Rising/Fading only when the whole likely range agrees (what the app uses now)
  middle      from the middle forecast alone (10% line)
  middle+fix  middle, after removing the model's average miss over the last 12 months whose truth was already known
  blend w     middle, from w * model change + (1 - w) * recent trend (last 3 months vs a year before)

Choice rule, fixed before looking at the test year: most labels right on DEVELOPMENT months (forecasts ending by
Oct 2025), among options whose development error is no worse than the current app's. The hidden test year
(Nov 2025 - Oct 2026) is then scored once.

    python scripts/improve_forecasts.py   ->  outputs/forecast/improve_results.csv, improve_preds.npz
"""
import glob
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fpt import config as C, forecast as F  # noqa: E402

SRC, OUT = C.ROOT / 'data' / 'google_trends', C.OUT / 'forecast'
items = [str(x) for x in np.load(OUT / 'past_forecasts.npz')['items']]
cols = []
for f in sorted(glob.glob(str(SRC / '*_*.csv'))):
    code = Path(f).name.split('_')[0]
    if code in ('GB', 'FR', 'DK'):
        d = pd.read_csv(f, dtype=str).set_index('month').replace('<1', '0.5').astype(float)
        d.columns = [f'{code}|{c}' for c in d.columns]
        cols.append(d)
full = pd.concat(cols, axis=1)
full = full.loc[:, ~full.columns.duplicated()][items]
full.index = pd.to_datetime(full.index)
months = list(full.index)
start = months.index(pd.Timestamp('2022-01-01'))          # 26: the short series starts here
dev_m = months.index(pd.Timestamp('2025-11-01'))         # first locked month
scale = full.iloc[start:dev_m].mean().to_numpy()
YL = full.to_numpy().T / scale[:, None]                  # long, every item on its own usual level
N = YL.shape[1]
cut = list(range(start + C.MIN_HISTORY, N + 1))          # same calendar start months as the app
country = np.array([k[:2] for k in items])
H = 6


def chronos(Y, cross):
    if not cross:
        return F.chronos2(Y, H)
    out = np.zeros((len(Y), H, 3))
    for c in np.unique(country):                          # one group per country
        idx = np.where(country == c)[0]
        pipe = F._chronos2 or (F.chronos2(Y[:1], 1), F._chronos2)[1]
        stamps = pd.date_range('2000-01-01', periods=Y.shape[1], freq='MS')
        df = pd.concat([pd.DataFrame({'item_id': i, 'timestamp': stamps, 'target': Y[i]}) for i in idx], ignore_index=True)
        p = pipe.predict_df(df, prediction_length=H, quantile_levels=C.QUANTILES, freq='MS', cross_learning=True)
        p = p.sort_values(['item_id', 'timestamp'])
        out[idx] = np.sort(p[[str(q) for q in C.QUANTILES]].to_numpy().reshape(len(idx), H, 3), axis=2)
    return out


cache = OUT / 'improve_preds.npz'
if cache.exists():
    P = dict(np.load(cache))
else:
    P = {}
    for name, long, cross in (('short', False, False), ('long', True, False), ('short+x', False, True), ('long+x', True, True)):
        print('forecasting', name)
        P[name] = np.stack([chronos(YL[:, (0 if long else start):t], cross) for t in cut])
    np.savez_compressed(cache, **P)


def lab(x):
    return np.where(x >= .1, 'rising', np.where(x <= -.1, 'fading', 'stable'))


rows = []
for h in (3, 6):
    ly = np.stack([YL[:, t - 12:t - 12 + h] for t in cut])                      # (cut, items, h)
    act = np.stack([YL[:, t:t + h].mean(1) if t + h <= N else np.full(len(items), np.nan) for t in cut]) / ly.mean(2) - 1
    real = [YL[:, t:t + h] if t + h <= N else None for t in cut]
    recent = np.stack([YL[:, t - 3:t].mean(1) / YL[:, t - 15:t - 12].mean(1) - 1 for t in cut])
    done = np.array([t + h <= N for t in cut])
    dev = np.array([t + h <= dev_m for t in cut])
    test = np.array([t >= dev_m for t in cut]) & done
    for fname, Pf in P.items():
        band = Pf[:, :, :h]                                                        # (cut, items, h, 3)
        chg = band.mean(2) / ly.mean(2)[:, :, None] - 1                            # (cut, items, 3)
        miss = act - chg[:, :, 1]
        # rolling fix: average miss over the last 12 start months whose whole forecast period had ended by month t
        fix = np.array([np.nanmean(miss[[j for j, u in enumerate(cut) if u + h <= t][-12:]])
                        if any(u + h <= t for u in cut) else 0.0 for t in cut])
        options = {'strict': (np.where((chg[:, :, 1] >= .1) & (chg[:, :, 0] > 0), 'rising',
                                       np.where((chg[:, :, 1] <= -.1) & (chg[:, :, 2] < 0), 'fading', 'stable')), 0 * fix),
                   'middle': (lab(chg[:, :, 1]), 0 * fix),
                   'middle+fix': (lab(chg[:, :, 1] + fix[:, None]), fix)}
        for w in (0.25, 0.5, 0.75):
            b = w * chg[:, :, 1] + (1 - w) * recent
            options[f'blend {w}'] = (lab(b), (b - chg[:, :, 1]).mean(1))           # shift = average gap, for the numbers
        for oname, (L, shift) in options.items():
            for part, m in (('development', dev), ('test year', test)):
                idx = np.where(m)[0]
                truth = lab(act[idx])
                right = (L[idx] == truth)
                made = L[idx] != 'stable'
                err, err_ly, inside = [], [], []
                for k, ci in enumerate(idx):
                    b2 = band[ci] + shift[ci] * ly[ci][:, :, None] if np.ndim(shift) else band[ci]
                    err.append(np.abs(b2[:, :, 1] - real[ci]).mean(1))
                    err_ly.append(np.abs(ly[ci] - real[ci]).mean(1))
                    inside.append(((real[ci] >= b2[:, :, 0]) & (real[ci] <= b2[:, :, 2])).mean(1))
                rows.append({'horizon': h, 'forecast': fname, 'labels': oname, 'part': part,
                             'labels_right': right.mean(), 'calls': int(made.sum()),
                             'calls_right': right[made].mean() if made.any() else np.nan,
                             'better_than_last_year': 1 - np.mean(err) / np.mean(err_ly),
                             'inside_range': np.mean(inside),
                             'items_mostly_right': int(((right.reshape(len(idx), -1)).mean(0) >= .5).sum())})
res = pd.DataFrame(rows)
res.to_csv(OUT / 'improve_results.csv', index=False)
pd.set_option('display.width', 220)
for h in (3, 6):
    r = res[res.horizon == h].pivot_table(index=['forecast', 'labels'], columns='part',
                                          values=['labels_right', 'calls_right', 'better_than_last_year', 'inside_range',
                                                  'items_mostly_right'])
    print(f'\n===== {h} months =====')
    print(r.round(2).to_string())
