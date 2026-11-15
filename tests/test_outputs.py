"""The forecast outputs (outputs/forecast/, made by scripts/build_forecasts.py) agree with each other, every label can
be worked out again from the saved numbers, and no forecast can see later months."""
import json

import numpy as np
import pandas as pd
import pytest

from conftest import FC, GT

TH = 0.10


def lab(x):
    return np.where(x >= TH, 'rising', np.where(x <= -TH, 'fading', 'stable'))


@pytest.fixture(scope='module')
def out():
    meta = json.loads((FC / 'meta.json').read_text())
    return dict(meta=meta, val=json.loads((FC / 'validation.json').read_text()),
                items=pd.read_csv(FC / 'items.csv'), calls=pd.read_csv(FC / 'calls.csv'),
                fc=pd.read_csv(FC / 'forecast.csv'), hist=pd.read_csv(FC / 'history.csv', index_col=0),
                tr=pd.read_csv(FC / 'track_record.csv'))


def weight(rule):
    return 1.0 if rule in ('middle', 'range agrees') else float(rule.split()[-1])


def test_same_items_everywhere(out):
    keys = list(pd.read_csv(GT / 'selected_items.csv').key)
    assert list(out['items'].key) == keys
    assert list(out['hist'].columns) == keys
    for h in (3, 6):
        assert sorted(out['calls'][out['calls'].horizon == h].item) == sorted(keys)
        f = out['fc'][out['fc'].horizon == h]
        assert (f.groupby('item').size() == h).all() and f.item.nunique() == len(keys)
    assert (out['fc'].low <= out['fc'].mid).all() and (out['fc'].mid <= out['fc'].high).all()
    assert out['meta']['dropped_sparse'] == []


def test_history_is_the_selected_data(out):
    """history.csv is selected_series.csv from Jan 2022 ('<1' -> 0.5), with only the documented UK Feb 2026 fix."""
    raw = pd.read_csv(GT / 'selected_series.csv', dtype=str).set_index('month').replace('<1', '0.5').astype(float)
    raw = raw.loc['2022-01':]
    hist = out['hist']
    assert list(hist.index) == list(raw.index)
    diff = (hist - raw).abs() > 1e-9
    changed = diff.stack()[lambda s: s]
    assert set(changed.index.get_level_values(0)) <= {'2026-02'}
    assert all(c.startswith('GB|') for c in changed.index.get_level_values(1))
    gb = [c for c in hist.columns if c.startswith('GB|')]
    want = (raw.loc['2026-01', gb] + raw.loc['2026-03', gb]) / 2
    assert np.allclose(hist.loc['2026-02', gb], want)
    assert out['meta']['uk_feb_2026_fixed'] is True


def test_labels_can_be_worked_out_again(out):
    tr = out['tr']
    for h in (3, 6):
        rule = out['meta']['rule'][str(h)]
        t = tr[tr.horizon == h]
        if rule != 'range agrees':
            w = weight(rule)
            assert np.allclose(t.trend_score, w * t.predicted_change + (1 - w) * t.momentum)
            assert (lab(t.trend_score) == t.call).all()
        assert (lab(t.actual_change) == t.actual_direction).all()
        assert ((t.call == t.actual_direction) == t.right).all()
        assert (lab(t.momentum) == t.trend_rule_call).all()
        c = out['calls'][out['calls'].horizon == h]
        if rule != 'range agrees':
            assert np.allclose(c.trend_score, w * c.change + (1 - w) * c.momentum)
            assert (lab(c.trend_score) == c.call).all()


def test_validation_numbers(out):
    tr = out['tr']
    for h in (3, 6):
        v = out['val'][str(h)]
        T = tr[(tr.horizon == h) & (tr.period == 'test year')]
        made = T[T.call != 'stable']
        assert v['labels'] == len(T) and np.isclose(v['labels_right'], T.right.mean())
        assert v['calls'] == len(made) and v['calls_right'] == int(made.right.sum())
        assert np.isclose(v['inside_range'], T.inside_range.mean())
        assert np.isclose(v['error_vs_last_year'], 1 - T.error.mean() / T.error_last_year.mean())
        assert v['items'] == T.item.nunique() == len(out['items'])
        # test-year forecasts start in the locked year and end by its last month
        assert T.first_month.min() == out['meta']['locked_from']
        months = list(out['hist'].index)
        last_start = months[len(months) - h]
        assert T.first_month.max() == last_start


def test_rule_was_chosen_on_development_months(out):
    for h in (3, 6):
        v = out['val'][str(h)]
        dev = v['rule_development']
        assert v['rule'] == max(dev, key=dev.get)


def test_no_leakage_simple_forecasters():
    from fpt import forecast as F
    rng = np.random.default_rng(0)
    Y = rng.uniform(0.5, 1.5, size=(4, 58))
    cut = 40
    Y2 = Y.copy()
    Y2[:, cut:] = rng.uniform(5, 9, size=(4, 58 - cut))        # very different "future"
    for f in (F.snaive, F.holt, F.cycle):
        a = F.forecast_all_cutoffs(Y, {'f': f}, [24, 30, cut], h=6, log=lambda *_: None)['f']
        b = F.forecast_all_cutoffs(Y2, {'f': f}, [24, 30, cut], h=6, log=lambda *_: None)['f']
        assert np.allclose(a, b)


@pytest.mark.slow
def test_no_leakage_chronos2_long_cross():
    """The model used on the site: changing months after a forecast date does not change that forecast."""
    pytest.importorskip('chronos')
    from fpt import forecast as F
    rng = np.random.default_rng(1)
    off, n = 26, 58
    YL = rng.uniform(0.5, 1.5, size=(4, off + n))
    countries = np.array(['GB', 'GB', 'FR', 'FR'])
    t = 40
    YL2 = YL.copy()
    YL2[:, off + t:] *= 5
    a = F.chronos2_long_cross_factory(YL, off, countries)(YL[:, off:off + t], 6)
    b = F.chronos2_long_cross_factory(YL2, off, countries)(YL2[:, off:off + t], 6)
    assert np.allclose(a, b)
    c = F.chronos2_long_cross_factory(YL2, off, countries)(YL2[:, off:off + t + 6], 6)
    assert not np.allclose(a, c)          # sanity: later data does change later forecasts
