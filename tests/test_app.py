"""Run the Streamlit app headless (streamlit.testing AppTest) for every country x attribute type x horizon, plus random
item mixes, and check it never shows an error."""
import random

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from conftest import FC, ROOT

APP = str(ROOT / 'app.py')
TYPES = ['Garments', 'Fabrics', 'Colours', 'Styles', 'Runway details']
COUNTRIES = ['England', 'France', 'Denmark']


def run(at):
    at.run(timeout=120)
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    return at


def widget(at, kind, label):
    found = [w for w in getattr(at, kind) if w.label == label]
    assert found, f'no {kind} labelled {label!r}'
    return found[0]


@pytest.mark.parametrize('country', COUNTRIES)
@pytest.mark.parametrize('h', [3, 6])
def test_every_country_type_horizon(country, h):
    items = pd.read_csv(FC / 'items.csv')
    at = run(AppTest.from_file(APP, default_timeout=120))
    widget(at, 'selectbox', 'Country').set_value(country)
    widget(at, 'radio', 'Forecast').set_value(h)
    run(at)
    for t in TYPES:
        widget(at, 'radio', 'Attribute type').set_value(t)
        run(at)
        n = ((items.country_name == country) & (items.group == t)).sum()
        ms = at.multiselect[0]
        assert len(ms.value) == min(2, n), (country, t)
        assert all(items.set_index('key').loc[k, 'group'] == t for k in ms.value)
        md = ' '.join(m.value for m in at.markdown)
        if n:
            assert 'Outlook' in ' '.join(s.value for s in at.subheader)
            assert 'Google searches for' in md


def test_random_item_mixes():
    items = pd.read_csv(FC / 'items.csv')
    rnd = random.Random(3)
    at = run(AppTest.from_file(APP, default_timeout=120))
    for _ in range(8):
        country = rnd.choice(COUNTRIES)
        t = rnd.choice(TYPES)
        keys = list(items[(items.country_name == country) & (items.group == t)].key)
        if not keys:
            continue
        widget(at, 'selectbox', 'Country').set_value(country)
        widget(at, 'radio', 'Attribute type').set_value(t)
        run(at)
        pick = rnd.sample(keys, min(len(keys), rnd.randint(1, 6)))
        at.multiselect[0].set_value(pick)
        widget(at, 'radio', 'Forecast').set_value(rnd.choice([3, 6]))
        run(at)
        # earliest backtest date too
        sl = at.select_slider[0]
        sl.set_value(sl.options[0])
        run(at)


def test_research_sections():
    at = run(AppTest.from_file(APP, default_timeout=120))
    heads = [h.value for h in at.header]
    assert 'Instagram research' in heads and 'Paris Fashion Week' in heads and 'Model validation' in heads
    for country in COUNTRIES:
        widget(at, 'selectbox', 'Country').set_value(country)
        for t in TYPES:
            at.selectbox(key='ins_type').set_value(t)
            for view in ['All posts', 'Autumn/Winter vs Spring/Summer']:
                at.radio(key='ins_view').set_value(view)
                run(at)
    details = widget(at, 'selectbox', 'Detail')
    for d in details.options:
        details.set_value(d)
        run(at)
        details = widget(at, 'selectbox', 'Detail')
