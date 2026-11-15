"""Fashion Trend Forecast: search-interest forecasts for outfit attributes, 3 and 6 months ahead, with model
validation and the team's Instagram and Paris Fashion Week research.

Reads outputs/forecast/ (made by scripts/build_forecasts.py), data/insights/ (totals from the team's workbook) and
data/google_trends/not_forecast.csv.

    streamlit run app.py
"""
import json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
FC = ROOT / 'outputs' / 'forecast'
INS = ROOT / 'data' / 'insights'
NOT_FC = ROOT / 'data' / 'google_trends' / 'not_forecast.csv'
TYPES = ['Garments', 'Fabrics', 'Colours', 'Styles', 'Runway details']
COUNTRIES = {'England': 'GB', 'France': 'FR', 'Denmark': 'DK'}
WORD = {'rising': 'Rising', 'stable': 'Steady', 'fading': 'Fading'}
ICON = {'rising': '▲', 'stable': '●', 'fading': '▼'}
COLOURS = ['#2563eb', '#dc2626', '#16a34a', '#9333ea', '#ea580c', '#0891b2']
BRAND_COLOUR = {'Chanel': '#111827', 'Dior': '#2563eb'}

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
    tt = tt.assign(miss=(tt.predicted_change - tt.actual_change).abs())
    by_item = {h: tt[tt.horizon == h].groupby('item').agg(right=('right', 'sum'), checks=('right', 'size'),
                                                           miss=('miss', 'median'))
               for h in (3, 6)}
    meta = json.loads((FC / 'meta.json').read_text())
    meta['validation'] = json.loads((FC / 'validation.json').read_text())
    return items, hist, fc, calls, test, by_item, meta


@st.cache_data
def load_research(stamp):
    posts = pd.read_csv(INS / 'post_counts.csv', dtype={'year': str})
    runway = pd.read_csv(INS / 'runway.csv')
    direction = pd.read_csv(INS / 'runway_direction.csv')
    not_fc = pd.read_csv(NOT_FC)
    return posts, runway, direction, not_fc


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
posts, runway, direction, not_fc = load_research(STAMP)
ALL_POSTS = posts[(posts.season == 'all') & (posts.year == 'all')].set_index(['attribute', 'country'])


def rule_weight(h):
    """Share of the forecast in the trend score (the rest is recent momentum)."""
    r = meta['rule'][str(h)]
    return 1.0 if r in ('middle', 'range agrees') else float(r.split()[-1])


def post_line(attribute, cc, country):
    """'In the team's Instagram posts: ...' for one attribute and country, or '' when not matched on posts."""
    if (attribute, cc) not in ALL_POSTS.index:
        return ''
    r = ALL_POSTS.loc[(attribute, cc)]
    if r.posts == 0:
        return f'Not recorded in the team\'s {country} Instagram posts.'
    return (f'In the team\'s Instagram posts: **{int(r.posts)} of {int(r.total_posts)}** {country} posts '
            f'({r.posts / r.total_posts:.0%}).')


def runway_line(attribute):
    d = direction[direction.attribute == attribute]
    if d.empty:
        return ''
    parts = []
    for r in d.itertuples():
        if r.direction == 'not seen':
            parts.append(f'{r.brand}: not seen')
        elif r.direction == 'in every look':
            parts.append(f'{r.brand}: in every look')
        else:
            parts.append(f'{r.brand} {r.share_2016_20:.0%} → {r.share_2021_25:.0%} of looks ({r.direction})')
    return 'Paris runway, 2016–20 → 2021–25: ' + '; '.join(parts) + '.'


base = hist[hist.index < meta['locked_from']].mean()          # each item's usual level = 100

st.title('Fashion Trend Forecast')
st.caption('Search-interest forecasts for outfit garments, fabrics, colours, styles and runway details in England, '
           'France and Denmark, based on monthly Google Trends and on the attributes recorded in our Instagram and Paris '
           f'Fashion Week research. History {pd.Timestamp(meta["months"][0]):%b %Y} – '
           f'{pd.Timestamp(meta["months"][1]):%b %Y}; forecast {pd.Timestamp(meta["future"][0]):%b %Y} onwards.')

c1, c2, c3 = st.columns([1, 2, 1])
country = c1.selectbox('Country', list(COUNTRIES))
cc = COUNTRIES[country]
group = c2.radio('Attribute type', TYPES, horizontal=True)
h = c3.radio('Forecast', [3, 6], format_func=lambda x: f'{x} months', horizontal=True)
here = items[(items.country_name == country) & (items.group == group)].sort_values('english')
names = dict(zip(items.index, items.english))


def n_posts(k):
    a = items.loc[k, 'english']
    return int(ALL_POSTS.posts.get((a, cc), 0))


ranked = sorted(here.index, key=lambda k: (-n_posts(k), names[k]))
chosen = st.multiselect(f'{group} ({len(here)} with a forecast in {country})', list(here.index), default=ranked[:2],
                        format_func=lambda k: names[k], max_selections=6, placeholder='Choose items',
                        key=f'items_{cc}_{group}')
skipped = not_fc[(not_fc.country == cc) & (not_fc.type == group)]
if len(skipped):
    st.caption(f'Not forecast in {country}: ' + ', '.join(sorted(skipped.attribute)) +
               ' (too few Google searches, or not searched). Their research data is shown below.')

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

# ---------------- one block per chosen item ----------------
st.subheader(f'Outlook: next {h} months vs the same months last year')
for k in chosen:
    c = calls[(calls.item == k) & (calls.horizon == h)].iloc[0]
    t = by_item[h].loc[k] if k in by_item[h].index else None
    lines = [f'{ICON[c.call]} **{names[k]}: {WORD[c.call]}** · trend score {c.trend_score:+.0%} '
             f'(forecast {c.change:+.0%}, range {c.low_change:+.0%} to {c.high_change:+.0%}; '
             f'recent momentum {c.momentum:+.0%}). Google searches for "{items.loc[k, "term"]}".']
    if t is not None:
        lines.append(f'Test-year accuracy for this item: **{int(t.right)} of {int(t.checks)}** labels correct; median '
                     f'error **±{t.miss * 100:.0f} points**.' + (' Lower reliability for this item.'
                                                                 if t.right / t.checks < 0.5 else ''))
    for extra in (post_line(names[k], cc, country), runway_line(names[k])):
        if extra:
            lines.append(extra)
    st.markdown('  \n'.join(lines))
wt = rule_weight(h)
st.caption(f'**Labelling rule:** trend score = {wt:.0%} × forecast change + {1 - wt:.0%} × recent momentum (last 3 '
           'months vs the same 3 months a year earlier). Rising at +10% or more, Fading at −10% or less, otherwise Steady. '
           'The weighting was selected on data before the test year.')

# ---------------- all items in the country ----------------
with st.expander(f'All items in {country}, next {h} months', expanded=False):
    allc = items[items.country_name == country]
    t = calls[(calls.horizon == h) & calls.item.isin(allc.index)].copy()
    t['Item'] = t.item.map(names)
    t['Type'] = t.item.map(allc.group)
    t['Trend'] = t.call.map(lambda c: f'{ICON[c]} {WORD[c]}')
    t['Trend score'] = t.trend_score.map('{:+.0%}'.format)
    t['Forecast vs last year'] = t.change.map('{:+.0%}'.format)
    t['Likely range'] = [f'{a:+.0%} to {b:+.0%}' for a, b in zip(t.low_change, t.high_change)]
    t['Recent momentum'] = t.momentum.map('{:+.0%}'.format)
    bi = by_item[h]
    t['Test-year accuracy'] = t.item.map(lambda k: f'{int(bi.right[k])} of {int(bi.checks[k])}' if k in bi.index else '')
    t['Instagram posts'] = t.item.map(lambda k: str(n_posts(k)) if (names[k], cc) in ALL_POSTS.index else '')
    t = t.sort_values('trend_score', ascending=False)
    st.dataframe(t[['Item', 'Type', 'Trend', 'Trend score', 'Forecast vs last year', 'Likely range', 'Recent momentum',
                    'Test-year accuracy', 'Instagram posts']], hide_index=True, use_container_width=True)

# ---------------- how good is it ----------------
with st.expander('Accuracy and method'):
    s = test[(test.part == 'locked test') & (test.horizon == h)].set_index('forecaster')
    p = meta['validation'][str(h)]
    st.markdown(
        f'**Test design.** Model and labelling rule were selected on data before Nov 2025. The 12 months Nov 2025 – '
        f'Oct 2026 were held out and forecast from {p["start_months"]} successive forecast dates, each using only '
        f'earlier data. All {p["items"]} items in all three countries are included.\n\n'
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
        '- **Attributes:** every garment, fabric, colour, style and runway detail recorded in our research at least '
        'twice in the Instagram posts or five times in the runway notes; spelling variants are merged (for example '
        '"creme" and "off white" count as cream).\n'
        '- **Search data:** monthly Google Trends search interest per country, Nov 2019 – Oct 2026, in each country\'s '
        'language. Fabrics, colours, styles and runway details are searched with a typical garment (for example '
        '"satin dress").\n'
        '- **Scope:** forecasts describe search interest, not sales, and cannot anticipate sudden events such as a '
        'viral post.')
    nf = not_fc.copy()
    nf['Country'] = nf.country.map({v: k for k, v in COUNTRIES.items()})
    nf['Reason'] = nf.reason.map(lambda r: 'Too few Google searches' if r.startswith('too few') else r[0].upper() + r[1:])
    st.markdown('**Not forecast**')
    st.dataframe(nf[['Country', 'type', 'attribute', 'Reason']].rename(columns={'type': 'Type', 'attribute': 'Attribute'}),
                 hide_index=True, use_container_width=True)

# =====================================================================================================================
# RESEARCH DATA
# =====================================================================================================================
st.divider()
st.header('Instagram research')
p_all = posts[(posts.season == 'all') & (posts.year == 'all') & (posts.country == cc)]
total = int(p_all.total_posts.max())
st.caption(f'{total} Instagram posts from {country} recorded by our team (2024–2025): share of posts that mention '
           'each attribute.')
r1, r2 = st.columns(2)
ins_type = r1.selectbox('Attribute type', TYPES, index=TYPES.index(group), key='ins_type')
view = r2.radio('Compare', ['All posts', 'Autumn/Winter vs Spring/Summer'], horizontal=True, key='ins_view')
pt = p_all[(p_all.type == ins_type) & (p_all.posts > 0)].sort_values('share', ascending=False).head(12)
if pt.empty:
    st.info(f'No {ins_type.lower()} recorded in the {country} posts.')
else:
    g = go.Figure()
    if view == 'All posts':
        g.add_trace(go.Bar(x=pt.share, y=pt.attribute, orientation='h', marker_color='#2563eb',
                           text=[f'{int(a)} of {int(b)}' for a, b in zip(pt.posts, pt.total_posts)],
                           textposition='outside', hovertemplate='%{y}: %{x:.0%}<extra></extra>'))
    else:
        for season, col in (('A/W', '#9333ea'), ('S/S', '#ea580c')):
            ps = posts[(posts.season == season) & (posts.year == 'all') & (posts.country == cc) &
                       posts.attribute.isin(pt.attribute)].set_index('attribute').reindex(pt.attribute)
            n = int(ps.total_posts.max())
            label = 'Autumn/Winter' if season == 'A/W' else 'Spring/Summer'
            g.add_trace(go.Bar(x=ps.share, y=ps.index, orientation='h', name=f'{label} ({n} posts)',
                               marker_color=col, hovertemplate='%{y}: %{x:.0%}<extra>' + label + '</extra>'))
        g.update_layout(barmode='group')
    g.update_yaxes(autorange='reversed')
    g.update_xaxes(tickformat='.0%', title='Share of posts')
    g.update_layout(height=max(260, 34 * len(pt) + 80), margin=dict(l=10, r=40, t=10, b=10),
                    legend=dict(orientation='h', y=-0.2))
    st.plotly_chart(g, use_container_width=True)
    if view != 'All posts':
        st.caption('Posts without a season in the sheet are left out of this comparison.')

st.header('Paris Fashion Week')
looks = runway.drop_duplicates(['brand', 'year']).groupby('brand').total_looks.sum().to_dict()
st.caption(f'Trims recorded by our team for Chanel ({looks.get("Chanel", 0)} looks) and Dior ({looks.get("Dior", 0)} '
           'looks), 2016–2025: share of looks showing each detail.')
details = list(dict.fromkeys(direction.attribute))
pick = st.selectbox('Detail', details, index=details.index('Floral details') if 'Floral details' in details else 0)
rw = runway[runway.attribute == pick]
g = go.Figure()
for brand, d in rw.groupby('brand'):
    g.add_trace(go.Scatter(x=d.year, y=d.share, name=brand, mode='lines+markers',
                           line=dict(color=BRAND_COLOUR.get(brand, '#6b7280'), width=2),
                           customdata=list(zip(d.looks, d.total_looks)),
                           hovertemplate='%{x}: %{y:.0%} (%{customdata[0]} of %{customdata[1]} looks)<extra>' +
                                         brand + '</extra>'))
g.update_yaxes(tickformat='.0%', range=[-0.02, 1.05], title='Share of looks')
g.update_xaxes(dtick=1)
g.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation='h', y=-0.2))
st.plotly_chart(g, use_container_width=True)
dt = direction.copy()
dt['2016–20'] = dt.share_2016_20.map('{:.0%}'.format)
dt['2021–25'] = dt.share_2021_25.map('{:.0%}'.format)
dt['Change'] = dt.change_points.map(lambda v: f'{v:+.0f} pts')
dt['Direction'] = dt.direction.str.capitalize()
st.dataframe(dt[['attribute', 'brand', '2016–20', '2021–25', 'Change', 'Direction']]
             .rename(columns={'attribute': 'Detail', 'brand': 'Brand'}), hide_index=True, use_container_width=True)
st.caption('Direction: Rising or Falling when the share of looks changed by 10 points or more between 2016–20 and '
           '2021–25, otherwise Steady.')

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
    tr['Type'] = tr.item.map(items.group)
    tr['Country'] = tr.item.map(items.country_name)
    tr['Forecast'] = [f'{WORD[c]} {v:+.0%}' for c, v in zip(tr.call, tr.trend_score)]
    tr['Actual'] = [f'{WORD[c]} {v:+.0%}' for c, v in zip(tr.actual_direction, tr.actual_change)]
    tr['Result'] = tr.right.map(RESULT)
    st.dataframe(tr[['Forecast date', 'Country', 'Type', 'Item', 'Forecast', 'Actual', 'Result']],
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
