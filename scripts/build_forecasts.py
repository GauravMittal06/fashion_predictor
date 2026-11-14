"""Forecast Google search interest in outfit items in England, France and Denmark, 3 and 6 months ahead, and test how
good those forecasts are.

Data: data/google_trends/{GB,FR,DK}_*.csv, monthly Google Trends (Nov 2019 - Oct 2026), saved from the Google Trends
website; terms.csv names each item in English. Scores and the choice of method use Jan 2022 onwards (Google changed
how it counts on 1 Jan 2022); the improved Chronos-2 also reads the earlier months as background.

Fairness rule: the last 12 months (Nov 2025 - Oct 2026) are LOCKED. The forecaster is chosen on earlier months only;
the locked months are then forecast once, as the final test. Finally the chosen forecaster predicts Nov 2026 - Apr 2027.

    python scripts/build_forecasts.py   ->  outputs/forecast/*.csv, meta.json
"""
import glob
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fpt import config as C, forecast as F  # noqa: E402

SRC = C.ROOT / 'data' / 'google_trends'
OUT = C.OUT / 'forecast'
OUT.mkdir(parents=True, exist_ok=True)
START = '2022-01'
LOCKED = 12
MIN_MEAN = 3.0           # items averaging under 3 (out of 100) before the locked year are too sparse to forecast
HORIZONS = (3, 6)
COUNTRY = {'GB': 'England', 'FR': 'France', 'DK': 'Denmark'}

# 1. Read the saved Google Trends tables ('<1' means under 1 -> 0.5)
terms = pd.read_csv(SRC / 'terms.csv').fillna('')
cols = []
for f in sorted(glob.glob(str(SRC / '*_*.csv'))):
    code = Path(f).name.split('_')[0]
    if code not in COUNTRY:
        continue
    d = pd.read_csv(f, dtype=str).set_index('month').replace('<1', '0.5').astype(float)
    d.columns = [f'{code}|{c}' for c in d.columns]
    cols.append(d)
wide = pd.concat(cols, axis=1)
wide = wide.loc[:, ~wide.columns.duplicated()]
wide.index = pd.to_datetime(wide.index)
full = wide.copy()                         # from Nov 2019: longer memory for the improved Chronos-2
wide = wide[wide.index >= START]
terms['key'] = terms.country + '|' + terms.term
terms = terms[terms.key.isin(wide.columns)].set_index('key')
n = len(wide)
dev = n - LOCKED
dev_mean = wide.iloc[:dev].mean()
keep = [k for k in terms.index if dev_mean[k] >= MIN_MEAN]
dropped = [k for k in terms.index if k not in keep]
wide = wide[keep]
terms = terms.loc[keep]
print(f'{len(keep)} items kept, {len(dropped)} too sparse: {[k for k in dropped]}')
print(f'{n} months ({wide.index[0]:%b %Y} - {wide.index[-1]:%b %Y}); locked test {wide.index[dev]:%b %Y} - '
      f'{wide.index[-1]:%b %Y}')

scale = dev_mean[keep].to_numpy()          # each item divided by its own average before the locked year
Y = wide.to_numpy().T / scale[:, None]
YL = full[keep].to_numpy().T / scale[:, None]
OFFSET = YL.shape[1] - Y.shape[1]          # months before Jan 2022
country_of = np.array([k[:2] for k in keep])


def chronos2_long_cross(Ys, h):
    """Chronos-2 with (a) the history from Nov 2019, not just Jan 2022, and (b) cross-learning: the items of one
    country are forecast together, so the model can see when searches for everything are moving."""
    YLt = YL[:, :OFFSET + Ys.shape[1]]
    if F._chronos2 is None:
        F.chronos2(YLt[:1], 1)
    out = np.zeros((len(YLt), h, 3))
    stamps = pd.date_range('2000-01-01', periods=YLt.shape[1], freq='MS')
    for c in np.unique(country_of):
        idx = np.where(country_of == c)[0]
        df = pd.concat([pd.DataFrame({'item_id': i, 'timestamp': stamps, 'target': YLt[i]}) for i in idx],
                       ignore_index=True)
        p = F._chronos2.predict_df(df, prediction_length=h, quantile_levels=C.QUANTILES, freq='MS',
                                   cross_learning=True).sort_values(['item_id', 'timestamp'])
        out[idx] = np.sort(p[[str(q) for q in C.QUANTILES]].to_numpy().reshape(len(idx), h, 3), axis=2)
    return out


# 2. Every forecaster, from every start month (each forecast sees only earlier months)
lstm = F.QuantileLSTM().to(F.DEVICE)
lstm.load_state_dict(torch.load(C.OUT / 'models' / 'lstm_44cities.pt', map_location=F.DEVICE))
lstm.eval()
base = {'same month last year': F.snaive, 'holt-winters': F.holt, 'trend + season': F.cycle,
        'chronos-2': F.chronos2, 'lstm': F.lstm_forecaster(lstm),
        'chronos-2 long memory + cross-learning': chronos2_long_cross}
cutoffs = list(range(C.MIN_HISTORY, n + 1))
preds = F.forecast_all_cutoffs(Y, base, cutoffs, h=6)
preds['chronos-2 + lstm'] = (preds['chronos-2'] + preds['lstm']) / 2
preds['chronos-2 + holt-winters'] = (preds['chronos-2'] + preds['holt-winters']) / 2


def scored(h):
    d = F.score(Y, {k: v[:, :, :h] for k, v in preds.items()}, cutoffs, h=h)
    d['item'] = [keep[s] for s in d.series]
    return d.rename(columns={'forecaster': 'forecaster'})


def summary(d):
    s = F.summarise(d.assign(forecaster=d.forecaster.replace({'same month last year': 'snaive'})))
    return s.rename(index={'snaive': 'same month last year'})


# 3. Choose on development months only; 4. score the locked year once
rows, chosen = [], {}
for h in HORIZONS:
    d = scored(h)
    dv = d[d.cutoff + h <= dev]
    lk = d[(d.cutoff >= dev) & (d.cutoff + h <= n)]
    sd, sl = summary(dv), summary(lk)
    chosen[h] = sd.index[0]
    for part, s in (('development', sd), ('locked test', sl)):
        for name, r in s.iterrows():
            rows.append({'horizon': h, 'part': part, 'forecaster': name, 'error': r.mae,
                         'direction_right': r.direction_ok, 'inside_range': r.coverage,
                         'better_than_last_year': r.skill_vs_last_year, 'start_months': int(
                             (dv if part == 'development' else lk).cutoff.nunique())})
    print(f'\n{h} months ahead - chosen on development: {chosen[h]}')
    print(pd.DataFrame(rows)[lambda x: (x.horizon == h)].pivot_table(
        index='forecaster', columns='part', values=['direction_right', 'better_than_last_year']).round(2).to_string())
pd.DataFrame(rows).to_csv(OUT / 'test_summary.csv', index=False)

# 5. How to turn a forecast into a label (Rising / Steady / Fading), chosen on DEVELOPMENT months only:
#      'range agrees'   Rising/Fading only when the whole likely range agrees (cautious; the first version)
#      'middle'         from the middle forecast alone
#      'trend score w'  from w x forecast change + (1 - w) x momentum (last 3 months vs the same 3 months a year before)
#    (A shift that removed the model's average miss was also tried on 14 Nov 2026 and rejected: it mostly learned that
#    searches for everything grow, labelled nearly every item Rising and made the numbers less accurate.)
def label(change, th=C.CALL_THRESHOLD):
    return np.where(change >= th, 'rising', np.where(change <= -th, 'fading', 'stable'))


def momentum(t):
    return Y[:, t - 3:t].mean(1) / Y[:, t - 15:t - 12].mean(1) - 1


def labels_for(band, ly_m, mom, rule):
    q = band.mean(1) / ly_m.mean(1)[:, None] - 1                         # (items, 3): low, mid, high change
    if rule == 'range agrees':
        lab = np.where((q[:, 1] >= .1) & (q[:, 0] > 0), 'rising',
                       np.where((q[:, 1] <= -.1) & (q[:, 2] < 0), 'fading', 'stable'))
        return lab, q, q[:, 1]
    w = 1.0 if rule == 'middle' else float(rule.split()[-1])
    score = w * q[:, 1] + (1 - w) * mom
    return label(score), q, score


RULES = ['range agrees', 'middle', 'trend score 0.25', 'trend score 0.5', 'trend score 0.75']
RULE, RULE_DEV = {}, {}
for h in HORIZONS:
    P = preds[chosen[h]]
    dev_right = {r: [] for r in RULES}
    for ci, t in enumerate(cutoffs):
        if t + h > dev:
            continue
        ly_m = Y[:, t - C.SEASON:t - C.SEASON + h]
        truth = label(Y[:, t:t + h].mean(1) / ly_m.mean(1) - 1)
        for r in RULES:
            dev_right[r].append(labels_for(P[ci][:, :h], ly_m, momentum(t), r)[0] == truth)
    RULE_DEV[h] = {r: float(np.concatenate(v).mean()) for r, v in dev_right.items()}
    RULE[h] = max(RULES, key=lambda r: RULE_DEV[h][r])
    print(f'{h} months: labels right on development {RULE_DEV[h]} -> using "{RULE[h]}"')

# 6. Final forecasts after the data: Nov 2026 - Apr 2027
last = len(cutoffs) - 1
future = pd.date_range(wide.index[-1] + pd.offsets.MonthBegin(), periods=6, freq='MS')
fc, calls = [], []
for h in HORIZONS:
    ly_m = Y[:, n - C.SEASON:n - C.SEASON + h]
    P = preds[chosen[h]][last][:, :h]
    mom = momentum(n)
    lab, q, score = labels_for(P, ly_m, mom, RULE[h])
    for s, k in enumerate(keep):
        calls.append({'item': k, 'horizon': h, 'forecaster': chosen[h], 'rule': RULE[h], 'call': lab[s],
                      'change': q[s, 1], 'low_change': q[s, 0], 'high_change': q[s, 2],
                      'trend_score': score[s], 'momentum': mom[s]})
        for i in range(h):
            fc.append({'item': k, 'horizon': h, 'month': future[i].strftime('%Y-%m'),
                       'low': P[s, i, 0] * scale[s], 'mid': P[s, i, 1] * scale[s], 'high': P[s, i, 2] * scale[s]})
pd.DataFrame(fc).to_csv(OUT / 'forecast.csv', index=False)
pd.DataFrame(calls).to_csv(OUT / 'calls.csv', index=False)
hist = wide.copy()
hist.index = hist.index.strftime('%Y-%m')
hist.to_csv(OUT / 'history.csv')
items = terms.assign(country_name=terms.country.map(COUNTRY))[['country', 'country_name', 'term', 'english', 'group', 'note']]
items.to_csv(OUT / 'items.csv')

# 7. Evidence: every past forecast (time machine) and every label it gave, right or wrong - same rule as the app
months = list(hist.index)
np.savez_compressed(OUT / 'past_forecasts.npz', items=np.array(keep), scale=scale, cutoffs=np.array(cutoffs),
                    months=np.array(months), model3=preds[chosen[3]][:, :, :3], model6=preds[chosen[6]])
track, proof = [], {}
for h in HORIZONS:
    P = preds[chosen[h]]
    for ci, t in enumerate(cutoffs):
        if t + h > n:
            continue
        ly_m = Y[:, t - C.SEASON:t - C.SEASON + h]
        band, real = P[ci][:, :h], Y[:, t:t + h]
        mom = momentum(t)
        lab, q, score = labels_for(band, ly_m, mom, RULE[h])
        act = real.mean(1) / ly_m.mean(1) - 1
        truth = label(act)
        inside = ((real >= band[:, :, 0]) & (real <= band[:, :, 2])).mean(1)
        err = np.abs(band[:, :, 1] - real).mean(1)
        err_ly = np.abs(ly_m - real).mean(1)
        mom_lab = label(mom)
        for s, k in enumerate(keep):
            track.append({'item': k, 'horizon': h, 'made_with_data_to': months[t - 1], 'first_month': months[t],
                          'period': 'test year' if t >= dev else 'earlier', 'call': lab[s],
                          'predicted_change': q[s, 1], 'low_change': q[s, 0], 'high_change': q[s, 2],
                          'trend_score': score[s], 'momentum': mom[s],
                          'actual_change': act[s], 'actual_direction': truth[s], 'right': lab[s] == truth[s],
                          'inside_range': inside[s], 'error': err[s], 'error_last_year': err_ly[s],
                          'trend_rule_call': mom_lab[s]})
tr = pd.DataFrame(track)
tr.to_csv(OUT / 'track_record.csv', index=False)
for h in HORIZONS:
    T = tr[(tr.horizon == h) & (tr.period == 'test year')]
    made = T[T.call != 'stable']
    tm = T[T.trend_rule_call != 'stable']
    by = T.groupby('item')[['error', 'error_last_year']].mean()
    proof[str(h)] = {'labels_right': T.right.mean(), 'labels': len(T), 'calls': len(made),
                     'calls_right': int(made.right.sum()),
                     'always_steady_right': (T.actual_direction == 'stable').mean(),
                     'trend_rule_labels_right': (T.trend_rule_call == T.actual_direction).mean(),
                     'trend_rule_calls': len(tm),
                     'trend_rule_calls_right': int((tm.trend_rule_call == tm.actual_direction).sum()),
                     'inside_range': T.inside_range.mean(),
                     'error_vs_last_year': 1 - T.error.mean() / T.error_last_year.mean(),
                     'items_beating_last_year': int((by.error < by.error_last_year).sum()), 'items': len(by),
                     'items_mostly_right': int((T.groupby('item').right.mean() >= .5).sum()),
                     'start_months': int(T.made_with_data_to.nunique()), 'rule': RULE[h],
                     'rule_development': RULE_DEV[h], 'forecaster': chosen[h]}
    p = proof[str(h)]
    print(f'\nTEST YEAR {h} months: labels right {p["labels_right"]:.0%} (always Steady {p["always_steady_right"]:.0%}, '
          f'momentum rule {p["trend_rule_labels_right"]:.0%}); Rising/Fading calls {p["calls_right"]}/{p["calls"]}; '
          f'items mostly right {p["items_mostly_right"]}/{p["items"]}; inside range {p["inside_range"]:.0%}; '
          f'error vs last year {p["error_vs_last_year"]:+.0%}')
(OUT / 'proof.json').write_text(json.dumps(proof, indent=1, default=float))
meta = {'months': [hist.index[0], hist.index[-1]], 'locked_from': hist.index[dev],
        'chosen': {str(h): chosen[h] for h in HORIZONS}, 'kept': len(keep), 'dropped_sparse': dropped,
        'future': [future[0].strftime('%Y-%m'), future[-1].strftime('%Y-%m')],
        'rule': {str(h): RULE[h] for h in HORIZONS}}
(OUT / 'meta.json').write_text(json.dumps(meta, indent=1, default=float))

# 8. Seal today's forecast: a fingerprint (SHA-256) of the exact numbers, so nobody can change them later unnoticed
import hashlib  # noqa: E402
SEAL = C.ROOT / 'sealed'
SEAL.mkdir(exist_ok=True)
body = {'made_on': pd.Timestamp.today().strftime('%Y-%m-%d'), 'data_up_to': months[-1],
        'forecaster': chosen[6], 'rule': RULE, 'forecast': pd.DataFrame(fc).round(4).to_dict('records'),
        'calls': pd.DataFrame(calls).round(4).to_dict('records')}
text = json.dumps(body, sort_keys=True, ensure_ascii=False)
seal = {'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(), 'sealed': body}
name = SEAL / f'forecast_data_to_{months[-1]}.json'
if name.exists():
    print('sealed forecast already exists, not overwritten:', name.name)
else:
    name.write_text(json.dumps(seal, ensure_ascii=False, indent=1), encoding='utf-8')
    print('sealed', name.name, 'fingerprint', seal['sha256'])

print('\nNext 6 months, not stable:')
c6 = pd.DataFrame(calls).query('horizon == 6 and call != "stable"')
print(c6[['item', 'call', 'change']].round(2).to_string(index=False))
