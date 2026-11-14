"""Fashion Trend Forecast: search-interest forecasts for outfit items, 3 and 6 months ahead, with model validation.

Reads outputs/forecast/ (made by scripts/build_forecasts.py).

    streamlit run app.py
"""
import json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
FC = ROOT / 'outputs' / 'forecast'
WORD = {'rising': 'Rising', 'stable': 'Steady', 'fading': 'Fading'}
ICON = {'rising': '▲', 'stable': '●', 'fading': '▼'}
COLOURS = ['#2563eb', '#dc2626', '#16a34a', '#9333ea', '#ea580c', '#0891b2']

st.set_page_config(page_title='Fashion Trend Forecast', layout='wide')


@st.cache_data
def load(stamp):
    items = pd.read_csv(FC / 'items.csv').set_index('key')
    hist = pd.read_csv(FC / 'history.csv', index_col=0)
    hist.index = pd.to_datetime(hist.index)
    fc = pd.read_csv(FC / 'forecast.csv', parse_dates=['month'])
    calls = pd.read_csv(FC / 'calls.csv')
    test = pd.read_csv(FC / 'test_summary.csv')
    # per item, hidden test year, scored with the SAME rule the app uses for its labels
    tt = pd.read_csv(FC / 'track_record.csv').query('period == "test year"')
    tt = tt.assign(miss=(tt.predicted_change - tt.actual_change).abs(),
                   steady_but_rose=(tt.call == 'stable') & (tt.actual_direction == 'rising'))
    by_item = {h: tt[tt.horizon == h].groupby('item').agg(right=('right', 'sum'), checks=('right', 'size'),
                                                           miss=('miss', 'median'),
                                                           steady_but_rose=('steady_but_rose', 'sum'))
               for h in (3, 6)}
    meta = json.loads((FC / 'meta.json').read_text())
    meta['validation'] = json.loads((FC / 'validation.json').read_text())
    return items, hist, fc, calls, test, by_item, meta


@st.cache_data
def load_validation(stamp):
    import numpy as np
    z = np.load(FC / 'past_forecasts.npz')
    past = {k: z[k] for k in z.files}
    track = pd.read_csv(FC / 'track_record.csv')
    wgsn = pd.read_csv(FC / 'wgsn_check.csv') if (FC / 'wgsn_check.csv').exists() else None
    return past, track, wgsn


if not (FC / 'meta.json').exists():
    st.error('No forecasts yet. Run: python scripts/build_forecasts.py')
    st.stop()
STAMP = (FC / 'meta.json').stat().st_mtime          # reload when the forecasts are rebuilt
items, hist, fc, calls, test, by_item, meta = load(STAMP)


def rule_weight(h):
    """Share of the forecast in the trend score (the rest is recent momentum)."""
    r = meta['rule'][str(h)]
    return 1.0 if r in ('middle', 'range agrees') else float(r.split()[-1])
base = hist[hist.index < meta['locked_from']].mean()          # each item's usual level = 100

st.title('Fashion Trend Forecast')
st.caption('Search-interest forecasts for outfit items in England, France and Denmark, based on monthly Google Trends. '
           f'History {pd.Timestamp(meta["months"][0]):%b %Y} – {pd.Timestamp(meta["months"][1]):%b %Y}; '
           f'forecast {pd.Timestamp(meta["future"][0]):%b %Y} onwards.')

c1, c2, c3 = st.columns([1, 3, 1])
country = c1.selectbox('Country', ['England', 'France', 'Denmark'])
here = items[items.country_name == country].sort_values(['group', 'english'])
names = dict(zip(here.index, here.english))
default = [k for k in here.index if here.loc[k, 'english'] in ('Leather jacket', 'Trench coat')][:2]
chosen = c2.multiselect('Outfit items', list(here.index), default=default, format_func=lambda k: names[k],
                        max_selections=6, placeholder='Choose items')
h = c3.radio('Forecast', [3, 6], format_func=lambda x: f'{x} months', horizontal=True)

if not chosen:
    st.info('Select one or more items.')
    st.stop()

# ---------------- chart ----------------
fig = go.Figure()
for i, k in enumerate(chosen):
    col = COLOURS[i % len(COLOURS)]
    y = hist[k] / base[k] * 100
    f = fc[(fc.item == k) & (fc.horizon == h)]
    lo, mid, hi = (f[c] / base[k] * 100 for c in ('low', 'mid', 'high'))
    x_band = list(f.month) + list(f.month[::-1])
    fig.add_trace(go.Scatter(x=x_band, y=list(hi) + list(lo[::-1]), fill='toself', fillcolor=col, opacity=0.15,
                             line=dict(width=0), hoverinfo='skip', showlegend=False))
    fig.add_trace(go.Scatter(x=y.index, y=y, name=names[k], line=dict(color=col, width=2),
                             hovertemplate='%{x|%b %Y}: %{y:.0f}<extra>' + names[k] + '</extra>'))
    fig.add_trace(go.Scatter(x=[y.index[-1]] + list(f.month), y=[y.iloc[-1]] + list(mid), showlegend=False,
                             line=dict(color=col, width=2, dash='dash'),
                             hovertemplate='%{x|%b %Y}: %{y:.0f} (forecast)<extra>' + names[k] + '</extra>'))
fig.add_vline(x=hist.index[-1], line=dict(color='#9ca3af', dash='dot'))
fig.add_annotation(x=hist.index[-1], y=1, yref='paper', text='Forecast', showarrow=False, xanchor='left',
                   font=dict(color='#6b7280'))
fig.update_xaxes(range=[pd.Timestamp('2024-01-01'), fc.month.max() + pd.Timedelta(days=20)])
fig.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10), hovermode='x unified',
                  yaxis_title='Search interest (100 = usual level)', legend=dict(orientation='h', y=-0.12))
st.plotly_chart(fig, use_container_width=True)
st.caption('Solid: observed. Dashed: forecast. Shaded: 80% forecast range. Index 100 = the item\'s average level '
           '(Jan 2022 – Oct 2025), so items are comparable. Double-click the chart to show the full history.')

# ---------------- one line per chosen item ----------------
st.subheader(f'Outlook: next {h} months vs the same months last year')
for k in chosen:
    c = calls[(calls.item == k) & (calls.horizon == h)].iloc[0]
    t = by_item[h].loc[k] if k in by_item[h].index else None
    trust = ''
    if t is not None:
        trust = (f'  \nTest-year accuracy for this item: **{int(t.right)} of {int(t.checks)}** labels correct; median '
                 f'error **±{t.miss * 100:.0f} points**.' + (' Lower reliability for this item.'
                                                             if t.right / t.checks < 0.5 else ''))
    st.markdown(f'{ICON[c.call]} **{names[k]}: {WORD[c.call]}** · trend score {c.trend_score:+.0%} '
                f'(forecast {c.change:+.0%}, range {c.low_change:+.0%} to {c.high_change:+.0%}; '
                f'recent momentum {c.momentum:+.0%}).{trust}')
wt = rule_weight(h)
st.caption(f'**Labelling rule:** trend score = {wt:.0%} × forecast change + {1 - wt:.0%} × recent momentum (last 3 '
           'months vs the same 3 months a year earlier). Rising at +10% or more, Fading at −10% or less, otherwise Steady. '
           'The weighting was selected on data before the test year.')

# ---------------- all items in the country ----------------
with st.expander(f'All items in {country}, next {h} months', expanded=True):
    t = calls[(calls.horizon == h) & calls.item.isin(here.index)].copy()
    t['Item'] = t.item.map(names)
    t['Group'] = t.item.map(here.group)
    t['Trend'] = t.call.map(lambda c: f'{ICON[c]} {WORD[c]}')
    t['Trend score'] = t.trend_score.map('{:+.0%}'.format)
    t['Forecast vs last year'] = t.change.map('{:+.0%}'.format)
    t['Likely range'] = [f'{a:+.0%} to {b:+.0%}' for a, b in zip(t.low_change, t.high_change)]
    t['Recent momentum'] = t.momentum.map('{:+.0%}'.format)
    bi = by_item[h]
    t['Test-year accuracy'] = t.item.map(lambda k: f'{int(bi.right[k])} of {int(bi.checks[k])}' if k in bi.index else '')
    t = t.sort_values('trend_score', ascending=False)
    st.dataframe(t[['Item', 'Group', 'Trend', 'Trend score', 'Forecast vs last year', 'Likely range', 'Recent momentum',
                    'Test-year accuracy']], hide_index=True, use_container_width=True)

# ---------------- how good is it ----------------
with st.expander('Accuracy and method'):
    s = test[(test.part == 'locked test') & (test.horizon == h)].set_index('forecaster')
    p = meta['validation'][str(h)]
    st.markdown(
        f'**Test design.** Model and labelling rule were selected on data before Nov 2025. The 12 months Nov 2025 – '
        f'Oct 2026 were held out and forecast from {p["start_months"]} successive forecast dates, each using only '
        'earlier data.\n\n'
        f'- **Forecast error:** {p["error_vs_last_year"]:.0%} lower than a same-months-last-year baseline; lower on '
        f'{p["items_beating_last_year"]} of {p["items"]} items.\n'
        f'- **Labels (Rising / Steady / Fading):** {p["labels_right"]:.0%} correct, against '
        f'{p["trend_rule_labels_right"]:.0%} for a recent-trend rule and {p["always_steady_right"]:.0%} for always '
        f'Steady. Correct on most forecast dates for {p["items_mostly_right"]} of {p["items"]} items.\n'
        f'- **Rising / Fading calls:** {p["calls_right"]} of {p["calls"]} correct ({p["calls_right"] / p["calls"]:.0%}).\n'
        f'- **Forecast range:** contained the actual value {p["inside_range"]:.0%} of the time (target 80%).\n\n'
        '**Model.** Chronos-2 (pretrained time-series transformer), reading each item\'s history from Nov 2019 and '
        'forecasting all items of a country jointly (cross-learning). It had the lowest error on the selection period '
        'among the forecasters below.')
    show = pd.DataFrame({'Forecaster': s.index, 'Average error': s.error.map('{:.2f}'.format).values,
                         'Error vs last year': s.better_than_last_year.map(lambda v: f'{-v:+.0%}').values,
                         'Within range': s.inside_range.map('{:.0%}'.format).values})
    st.dataframe(show, hide_index=True, use_container_width=True)
    st.caption('All forecasters on the held-out test year. 3-month forecasts are more reliable than 6-month forecasts.')

with st.expander('About the data'):
    st.markdown(
        '- **Source:** monthly Google Trends search interest per country, Nov 2019 – Oct 2026, queried in each '
        'country\'s language.\n'
        '- **Items:** selected from outfits recorded in our Instagram dataset (leather and suede jackets, trench coats, '
        'satin and lace dresses, blazers, burgundy, leopard print and others).\n'
        f'- **Excluded (search volume too low):** {", ".join(meta["dropped_sparse"])}.\n'
        '- **Note:** the Danish term "leopard" includes searches unrelated to clothing.\n'
        '- **Scope:** forecasts describe search interest, not sales, and cannot anticipate sudden events such as a '
        'viral post.')

# =====================================================================================================================
# MODEL VALIDATION
# =====================================================================================================================
past, track, wgsn = load_validation(STAMP)
RESULT = {True: 'Correct', False: 'Incorrect'}
st.divider()
st.header('Model validation')
st.caption('All results below come from a held-out test year (Nov 2025 – Oct 2026). Each forecast used only the data '
           'available at its forecast date, and the model and labelling rule were selected on earlier months. '
           'Chronos-2 is used as a pretrained model and was not trained on these series.')

tt = track[(track.period == 'test year') & (track.horizon == h)]
made = tt[tt.call != 'stable']
per_item = tt.groupby('item')[['error', 'error_last_year']].mean()
pr = meta['validation'][str(h)]
m1, m2, m3 = st.columns(3)
m1.metric('Rising / Fading calls correct', f'{made.right.mean():.0%}')
m1.caption(f'{int(made.right.sum())} of {len(made)} calls, {h} months ahead')
m2.metric("Items more accurate than last year's values", f'{(per_item.error < per_item.error_last_year).sum()} of {len(per_item)}')
m2.caption('Lower average error over the test year')
m3.metric('Actual values within forecast range', f'{pr["inside_range"]:.0%}')
m3.caption('Target: 80%')

# ---------------- backtest ----------------
st.subheader('Backtest: forecast vs actual')
st.caption('Select an item and a forecast date to compare the forecast made at that date with the values observed '
           'afterwards.')
p_items, p_cut, p_months = [str(x) for x in past['items']], [int(x) for x in past['cutoffs']], \
    [str(x) for x in past['months']]
n_m = len(p_months)
starts = [p_months[t - 1] for t in p_cut if t + h <= n_m]
a1, a2 = st.columns([1, 3])
bt_item = a1.selectbox('Item', chosen, format_func=lambda k: names[k], key='bt_item')
bt_month = a2.select_slider('Forecast date (data available up to)', starts, value=starts[-1],
                            format_func=lambda m: pd.Timestamp(m).strftime('%b %Y'))
t = p_months.index(bt_month) + 1
s = p_items.index(bt_item)
q = past[f'model{h}'][p_cut.index(t), s, :h] * past['scale'][s] / base[bt_item] * 100
yy = hist[bt_item] / base[bt_item] * 100
fmonths = pd.to_datetime(p_months[t:t + h])
g = go.Figure()
g.add_trace(go.Scatter(x=list(fmonths) + list(fmonths[::-1]), y=list(q[:, 2]) + list(q[::-1, 0]), fill='toself',
                       fillcolor='#2563eb', opacity=0.15, line=dict(width=0), hoverinfo='skip', showlegend=False))
g.add_trace(go.Scatter(x=yy.index[:t], y=yy.iloc[:t], name='Observed (before forecast date)', line=dict(color='#6b7280')))
g.add_trace(go.Scatter(x=[yy.index[t - 1]] + list(fmonths), y=[yy.iloc[t - 1]] + list(q[:, 1]), name='Forecast',
                       line=dict(color='#2563eb', dash='dash', width=2)))
g.add_trace(go.Scatter(x=[yy.index[t - 1]] + list(fmonths), y=[yy.iloc[t - 1]] + list(yy.iloc[t:t + h]),
                       name='Actual', line=dict(color='#16a34a', width=3), mode='lines+markers'))
g.add_vline(x=yy.index[t - 1], line=dict(color='#9ca3af', dash='dot'))
g.update_xaxes(range=[yy.index[max(0, t - 24)], fmonths[-1] + pd.Timedelta(days=20)])
g.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), hovermode='x unified',
                yaxis_title='Search interest (100 = usual level)', legend=dict(orientation='h', y=-0.15))
st.plotly_chart(g, use_container_width=True)
r = track[(track.item == bt_item) & (track.horizon == h) & (track.made_with_data_to == bt_month)].iloc[0]
st.markdown(f'**Forecast** (data to {pd.Timestamp(bt_month):%b %Y}, next {h} months): {ICON[r.call]} {WORD[r.call]}, '
            f'trend score {r.trend_score:+.0%} (forecast change {r.predicted_change:+.0%}).  \n'
            f'**Actual:** {ICON[r.actual_direction]} {WORD[r.actual_direction]}, {r.actual_change:+.0%}.  \n'
            f'**Result:** {RESULT[bool(r.right)]}.')

# ---------------- call log ----------------
with st.expander(f'Test-year call log ({len(made)} Rising / Fading calls, {h} months ahead)'):
    tr = made.copy()
    tr['Forecast date'] = pd.to_datetime(tr.made_with_data_to).dt.strftime('%b %Y')
    tr['Item'] = tr.item.map(items.english)
    tr['Country'] = tr.item.map(items.country_name)
    tr['Forecast'] = [f'{WORD[c]} {v:+.0%}' for c, v in zip(tr.call, tr.trend_score)]
    tr['Actual'] = [f'{WORD[c]} {v:+.0%}' for c, v in zip(tr.actual_direction, tr.actual_change)]
    tr['Result'] = tr.right.map(RESULT)
    st.dataframe(tr[['Forecast date', 'Country', 'Item', 'Forecast', 'Actual', 'Result']],
                 hide_index=True, use_container_width=True)
    st.caption('Forecast shows the trend score. Baseline for comparison: a "recent trend continues" rule made '
               f'{pr["trend_rule_calls"]} calls over the same period, {pr["trend_rule_calls_right"] / pr["trend_rule_calls"]:.0%} '
               'correct.')

# ---------------- benchmark ----------------
if wgsn is not None:
    with st.expander('Benchmark: WGSN trend calls'):
        st.markdown('WGSN is a leading commercial trend-forecasting service. Two WGSN trend calls in our dataset were '
                    'compared with the model\'s forecast made at the same date, against the following six months of '
                    'search data in England and France.')
        w = wgsn.copy()
        w['WGSN call'] = w.wgsn_posted + ': ' + w.wgsn_said
        w['Model forecast'] = w.our_model_said.map(lambda c: WORD[c])
        w['Actual'] = [f'{WORD[c]} {v:+.0%}' for c, v in zip(w.actual, w.actual_change)]
        w['WGSN'] = w.wgsn_right.map(RESULT)
        w['Model'] = w.model_right.map(RESULT)
        st.dataframe(w[['WGSN call', 'country', 'Model forecast', 'Actual', 'WGSN', 'Model']]
                     .rename(columns={'country': 'Country'}), hide_index=True, use_container_width=True)
        st.markdown(f'WGSN: **{int(w.wgsn_right.sum())} of {len(w)}** correct. Model: **{int(w.model_right.sum())} of '
                    f'{len(w)}** correct.')
        st.caption('A search-based model detects a trend once search interest starts to move; expert forecasters can '
                   'identify trends earlier from runway and industry signals. The two approaches are complementary.')
