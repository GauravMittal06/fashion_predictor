"""Trend forecast: pick a country and outfit items, see where interest is heading 3 or 6 months ahead.

Reads outputs/forecast/ (made by scripts/build_forecasts.py). No photos, no image generation.

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
    meta['proof'] = json.loads((FC / 'proof.json').read_text())
    return items, hist, fc, calls, test, by_item, meta


@st.cache_data
def load_proof(stamp):
    import numpy as np
    z = np.load(FC / 'past_forecasts.npz')
    past = {k: z[k] for k in z.files}
    track = pd.read_csv(FC / 'track_record.csv')
    wgsn = pd.read_csv(FC / 'wgsn_check.csv') if (FC / 'wgsn_check.csv').exists() else None
    seals = [json.loads(f.read_text(encoding='utf-8')) for f in sorted((ROOT / 'sealed').glob('*.json'))]
    return past, track, wgsn, seals


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

st.title('Fashion trend forecast')
st.caption('Monthly Google searches for outfit items in England, France and Denmark. '
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
    st.info('Choose one or more outfit items.')
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
fig.add_annotation(x=hist.index[-1], y=1, yref='paper', text='forecast →', showarrow=False, xanchor='left',
                   font=dict(color='#6b7280'))
fig.update_xaxes(range=[pd.Timestamp('2024-01-01'), fc.month.max() + pd.Timedelta(days=20)])
fig.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10), hovermode='x unified',
                  yaxis_title='Search interest (100 = usual level)', legend=dict(orientation='h', y=-0.12))
st.plotly_chart(fig, use_container_width=True)
st.caption('Solid line: real searches. Dashed line: forecast. Shaded area: likely range (8 times in 10). '
           '100 means the item\'s usual level (its average for 2022 – Oct 2025), so items can be compared. '
           'The chart starts at 2024; double-click it to see from 2022.')

# ---------------- one line per chosen item ----------------
st.subheader(f'Next {h} months, compared with the same months last year')
for k in chosen:
    c = calls[(calls.item == k) & (calls.horizon == h)].iloc[0]
    t = by_item[h].loc[k] if k in by_item[h].index else None
    trust = ''
    if t is not None:
        trust = (f'  \nTest year: label right **{int(t.right)} of {int(t.checks)}** times; the forecast change was '
                 f'usually within **±{t.miss * 100:.0f} points** of the real one.')
        if t.right / t.checks < 0.5:
            trust += (' ⚠️ It often said Steady while searches for this item rose, so it may miss a rise.'
                      if t.steady_but_rose >= t.checks / 2 else ' ⚠️ Treat with caution.')
    st.markdown(f'{ICON[c.call]} **{names[k]}: {WORD[c.call]}** · trend score {c.trend_score:+.0%} '
                f'(forecast {c.change:+.0%}, likely {c.low_change:+.0%} to {c.high_change:+.0%}; '
                f'recent momentum {c.momentum:+.0%}).{trust}')
wt = rule_weight(h)
st.caption(f'**How the label is decided:** trend score = {wt:.0%} × the forecast change + {1 - wt:.0%} × recent momentum '
           '(the last 3 months against the same 3 months a year before). Rising if the score is +10% or more, Fading if '
           '−10% or less, otherwise Steady. This mix was chosen on months before the test year because it got the most '
           f'labels right. The test-year checks for one item overlap (each covers the next {h} months), so they are only '
           'one or two separate events.')

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
    t['Test year: label right'] = t.item.map(lambda k: f'{int(bi.right[k])} of {int(bi.checks[k])}' if k in bi.index else '')
    t = t.sort_values('trend_score', ascending=False)
    st.dataframe(t[['Item', 'Group', 'Trend', 'Trend score', 'Forecast vs last year', 'Likely range', 'Recent momentum',
                    'Test year: label right']], hide_index=True, use_container_width=True)

# ---------------- how good is it ----------------
with st.expander('How accurate are these forecasts?'):
    s = test[(test.part == 'locked test') & (test.horizon == h)].set_index('forecaster')
    m = meta['chosen'][str(h)]
    p = meta['proof'][str(h)]
    st.markdown(
        f'The model (**{m}**) was chosen using months before Nov 2025 only. The 12 months Nov 2025 – Oct 2026 were then '
        f'kept hidden and forecast as a test, {p["start_months"]} times, each time using only earlier months.\n\n'
        f'- **Size of the change:** its error was **{p["error_vs_last_year"]:.0%} smaller** than simply repeating last '
        f'year\'s numbers, and smaller on {p["items_beating_last_year"]} of {p["items"]} items.\n'
        f'- **When it calls Rising or Fading:** right **{p["calls_right"]} of {p["calls"]}** times '
        f'({p["calls_right"] / p["calls"]:.0%}). A simple "the recent trend continues" rule: '
        f'{p["trend_rule_calls_right"]} of {p["trend_rule_calls"]} ({p["trend_rule_calls_right"] / p["trend_rule_calls"]:.0%}).\n'
        f'- **Every label, Steady included:** right **{p["labels_right"]:.0%}** of the time; the recent-trend rule alone '
        f'{p["trend_rule_labels_right"]:.0%}; always saying Steady {p["always_steady_right"]:.0%}. It was right most of '
        f'the time on **{p["items_mostly_right"]} of {p["items"]} items**.\n'
        f'- **Shaded range:** held the real value **{p["inside_range"]:.0%}** of the time (aim: 80%).')
    show = pd.DataFrame({'Forecaster': s.index, 'Average error': s.error.map('{:.2f}'.format).values,
                         'Better than last year': s.better_than_last_year.map('{:+.0%}'.format).values,
                         'Inside range': s.inside_range.map('{:.0%}'.format).values})
    st.dataframe(show, hide_index=True, use_container_width=True)
    st.caption('All forecasters tried, on the hidden test year. Shorter forecasts are more reliable: 3 months ahead is '
               'better than 6.')
    st.markdown('**How it was improved (14 Nov 2026).** The first version labelled only 52% (3 months) and 41% '
                '(6 months) right: it said Steady too often while searches rose. Three changes, each chosen on the months '
                'before the test year: Chronos-2 now sees the history from Nov 2019, not just 2022; it forecasts all '
                'items of a country together, so it notices when searches for everything move; and the label mixes the '
                'forecast with recent momentum.')

with st.expander('About the data'):
    st.markdown(
        '- **What is measured:** how often people in each country searched Google for each item, month by month '
        '(Google Trends). More searches usually means more interest in wearing or buying it.\n'
        '- **Items** were picked from the outfits recorded in our Instagram posts (leather and suede jackets, trench coats, '
        'satin and lace dresses, blazers, burgundy, leopard print and so on), searched in each country\'s language.\n'
        f'- **Left out as too rare to forecast:** {", ".join(meta["dropped_sparse"])}.\n'
        '- **Denmark "leopard"** counts every search for the word, not only clothes.\n'
        '- Forecasts are for searches, not sales, and a sudden fashion moment (a celebrity, a viral post) cannot be '
        'seen in advance.')

# =====================================================================================================================
# PROOF
# =====================================================================================================================
past, track, wgsn, seals = load_proof(STAMP)
st.divider()
st.header('Proof: can we trust these predictions?')
st.caption('Everything below is checked against what really happened. The model (Chronos-2) was never trained on these '
           'searches: it saw each item\'s past months and nothing else, so it could not have memorised the answers.')

tt = track[(track.period == 'test year') & (track.horizon == h)]
made = tt[tt.call != 'stable']
per_item = tt.groupby('item')[['error', 'error_last_year']].mean()
pr = meta['proof'][str(h)]
m1, m2, m3 = st.columns(3)
m1.metric('Rising / Fading calls that came true', f'{made.right.mean():.0%}',
          help='Hidden test year, Nov 2025 – Oct 2026, all countries.')
m1.caption(f'{int(made.right.sum())} of {len(made)} calls, {h} months ahead')
m2.metric('Items where it beats "repeat last year"', f'{(per_item.error < per_item.error_last_year).sum()} of {len(per_item)}')
m2.caption('Smaller average error in the test year')
m3.metric('Real value inside the shaded range', f'{pr["inside_range"]:.0%}')
m3.caption('The range is meant to hold it 8 times in 10')

# ---------------- time machine ----------------
st.subheader('🕰️ Time machine')
st.markdown('Go back to any month. The model forecasts using **only the data up to then**; the green line is what then '
            'really happened.')
p_items, p_cut, p_months = [str(x) for x in past['items']], [int(x) for x in past['cutoffs']], \
    [str(x) for x in past['months']]
n_m = len(p_months)
starts = [p_months[t - 1] for t in p_cut if t + h <= n_m]
a1, a2 = st.columns([1, 3])
tm_item = a1.selectbox('Item', chosen, format_func=lambda k: names[k], key='tm_item')
default_start = p_months[p_months.index(meta['locked_from']) - 1]
tm_month = a2.select_slider('Pretend it is the end of', starts,
                            value=default_start if default_start in starts else starts[-1],
                            format_func=lambda m: pd.Timestamp(m).strftime('%b %Y'))
t = p_months.index(tm_month) + 1
s = p_items.index(tm_item)
q = past[f'model{h}'][p_cut.index(t), s, :h] * past['scale'][s] / base[tm_item] * 100
yy = hist[tm_item] / base[tm_item] * 100
fmonths = pd.to_datetime(p_months[t:t + h])
g = go.Figure()
g.add_trace(go.Scatter(x=list(fmonths) + list(fmonths[::-1]), y=list(q[:, 2]) + list(q[::-1, 0]), fill='toself',
                       fillcolor='#2563eb', opacity=0.15, line=dict(width=0), hoverinfo='skip', showlegend=False))
g.add_trace(go.Scatter(x=yy.index[:t], y=yy.iloc[:t], name='What the model could see', line=dict(color='#6b7280')))
g.add_trace(go.Scatter(x=[yy.index[t - 1]] + list(fmonths), y=[yy.iloc[t - 1]] + list(q[:, 1]), name='Its forecast',
                       line=dict(color='#2563eb', dash='dash', width=2)))
g.add_trace(go.Scatter(x=[yy.index[t - 1]] + list(fmonths), y=[yy.iloc[t - 1]] + list(yy.iloc[t:t + h]),
                       name='What really happened', line=dict(color='#16a34a', width=3), mode='lines+markers'))
g.add_vline(x=yy.index[t - 1], line=dict(color='#9ca3af', dash='dot'))
g.update_xaxes(range=[yy.index[max(0, t - 24)], fmonths[-1] + pd.Timedelta(days=20)])
g.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), hovermode='x unified',
                yaxis_title='Search interest (100 = usual level)', legend=dict(orientation='h', y=-0.15))
st.plotly_chart(g, use_container_width=True)
r = track[(track.item == tm_item) & (track.horizon == h) & (track.made_with_data_to == tm_month)].iloc[0]
said = f'{ICON[r.call]} {WORD[r.call]} (trend score {r.trend_score:+.0%}, forecast {r.predicted_change:+.0%})'
real = f'{ICON[r.actual_direction]} {WORD[r.actual_direction]} ({r.actual_change:+.0%})'
st.markdown(f'Using data up to **{pd.Timestamp(tm_month):%b %Y}**, for the next {h} months the model said **{said}**. '
            f'What happened: **{real}**. ' + ('✅ Right.' if r.right else '❌ Wrong label' + (
                f', though the trend score was within {abs(r.trend_score - r.actual_change):.0%} of the real change.'
                if abs(r.trend_score - r.actual_change) <= 0.05 else '.')))

# ---------------- track record ----------------
with st.expander(f'📋 Every Rising / Fading call in the hidden test year ({len(made)} calls, {h} months ahead)'):
    tr = made.copy()
    tr['Made with data up to'] = pd.to_datetime(tr.made_with_data_to).dt.strftime('%b %Y')
    tr['Item'] = tr.item.map(items.english)
    tr['Country'] = tr.item.map(items.country_name)
    tr['Model said'] = [f'{ICON[c]} {WORD[c]} {v:+.0%}' for c, v in zip(tr.call, tr.trend_score)]
    tr['What happened'] = [f'{ICON[c]} {WORD[c]} {v:+.0%}' for c, v in zip(tr.actual_direction, tr.actual_change)]
    tr['Right?'] = tr.right.map({True: '✅', False: '❌'})
    st.dataframe(tr[['Made with data up to', 'Country', 'Item', 'Model said', 'What happened', 'Right?']],
                 hide_index=True, use_container_width=True)
    st.caption('"Model said" shows the trend score. For comparison, a simple "the recent trend continues" rule made '
               f'{pr["trend_rule_calls"]} calls on the same year and got {pr["trend_rule_calls_right"] / pr["trend_rule_calls"]:.0%} '
               'right.')

# ---------------- against WGSN ----------------
if wgsn is not None:
    with st.expander('🥊 Against the professionals: our model vs WGSN', expanded=True):
        st.markdown("WGSN is one of the world's biggest paid trend-forecasting services. Our Instagram data includes two of its "
                    'trend calls. For each, we went back to the month it was posted, asked our model (data up to then '
                    'only), and checked what searches did over the next 6 months.')
        w = wgsn.copy()
        w['WGSN said'] = w.wgsn_posted + ': ' + w.wgsn_said
        w['Our model said'] = w.our_model_said.map(lambda c: f'{ICON[c]} {WORD[c]}')
        w['What happened'] = [f'{ICON[c]} {WORD[c]} {v:+.0%}' for c, v in zip(w.actual, w.actual_change)]
        w['WGSN right?'] = w.wgsn_right.map({True: '✅', False: '❌'})
        w['Our model right?'] = w.model_right.map({True: '✅', False: '❌'})
        st.dataframe(w[['WGSN said', 'country', 'Our model said', 'What happened', 'WGSN right?', 'Our model right?']]
                     .rename(columns={'country': 'Country'}), hide_index=True, use_container_width=True)
        st.markdown(f'**Score (2 trend calls × 2 countries): WGSN {int(w.wgsn_right.sum())} of {len(w)}, our model '
                    f'{int(w.model_right.sum())} of {len(w)}.** On burgundy both were right: our model picked it up from '
                    'the first rise in searches, while WGSN read it from the catwalks. On boho, WGSN said it was coming '
                    'back, but searches had already peaked, and our model said so. A model like this still cannot see '
                    'a trend before anyone starts searching for it, so the best use is both together.')

# ---------------- sealed forecast ----------------
with st.expander('🔒 Sealed forecast: proof we did not change it afterwards', expanded=True):
    for sl in seals:
        b = sl['sealed']
        st.markdown(f'Made on **{b["made_on"]}** with data up to {pd.Timestamp(b["data_up_to"]):%b %Y}. Fingerprint:')
        st.code(sl['sha256'], language=None)
        st.markdown('The fingerprint is worked out from every number in the forecast. Change one digit and it no longer '
                    'matches. Send it to the teacher today; later anyone can run `python scripts/verify_seal.py` to '
                    'check the forecast was not touched.')
        sc = pd.DataFrame(b['calls'])
        sc = sc[sc.horizon == h]
        sf = pd.DataFrame(b['forecast'])
        have = set(hist.index.strftime('%Y-%m'))
        arrived = [m for m in sf.month.unique() if m in have]
        done = []
        for c in sc.itertuples():
            f = sf[(sf.item == c.item) & (sf.horizon == h)]
            if not len(f) or not all(m in have for m in f.month):
                continue
            mm = pd.to_datetime(f.month)
            chg = hist.loc[mm, c.item].mean() / hist.loc[mm - pd.DateOffset(years=1), c.item].mean() - 1
            d = 'rising' if chg >= 0.10 else 'fading' if chg <= -0.10 else 'stable'
            done.append({'Item': items.english.get(c.item), 'Country': items.country_name.get(c.item),
                         'Sealed call': WORD[c.call], 'What happened': f'{WORD[d]} {chg:+.0%}',
                         'Right?': '✅' if d == c.call else '❌'})
        if done:
            st.dataframe(pd.DataFrame(done), hide_index=True, use_container_width=True)
        else:
            first = pd.Timestamp(b['data_up_to']) + pd.offsets.MonthBegin()
            st.info(f'Nothing to score yet ({len(arrived)} of the forecast months have arrived). When Google Trends '
                    f'data from {first:%b %Y} onwards is added and `scripts/build_forecasts.py` is run, this box '
                    'scores the sealed calls automatically.')
        nonstable = sc[sc.call != 'stable']
        if len(nonstable):
            st.markdown(f'**What we committed to ({h} months):** ' + '; '.join(
                f'{items.english.get(k)} in {items.country_name.get(k)}: {WORD[c]} {v:+.0%}'
                for k, c, v in zip(nonstable.item, nonstable.call, nonstable.trend_score)) + ' (trend scores).')
