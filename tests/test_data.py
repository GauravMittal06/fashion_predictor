"""Google Trends downloads and the series chosen for forecasting."""
from glob import glob
from pathlib import Path

import pandas as pd
import pytest

from conftest import GT, ROOT
from fpt.attributes import ATTRIBUTES, country_terms
from fpt.quality import check

MONTHS = [str(p) for p in pd.period_range('2019-11', '2026-10', freq='M')]
FILES = sorted(glob(str(GT / '[A-Z][A-Z]_*.csv'))) + sorted(glob(str(GT / 'v2' / '*.csv')))


@pytest.mark.parametrize('f', FILES, ids=[Path(f).name for f in FILES])
def test_every_download_is_complete(f):
    d = pd.read_csv(f, dtype=str).set_index('month')
    assert list(d.index) == MONTHS, 'months missing or out of order'
    assert not d.columns.duplicated().any()
    vals = d.stack()
    ok = vals.eq('<1') | vals.str.fullmatch(r'\d{1,3}')
    assert ok.all(), f'unexpected values: {set(vals[~ok])}'
    nums = vals[vals != '<1'].astype(int)
    assert nums.between(0, 100).all()
    assert (nums == 100).any(), 'Google scales each download so its peak is 100'


def test_raw_text_matches_saved_files():
    """Every v2 file is exactly what save_trends.py parses from the kept raw download."""
    from save_trends import parse
    for raw in sorted((GT / 'v2' / 'raw').glob('*.txt')):
        saved = pd.read_csv(GT / 'v2' / f'{raw.stem}.csv', dtype=str).set_index('month')
        parsed = parse(raw.read_text(encoding='utf-8'))
        assert parsed.equals(saved), raw.name


def test_plan_and_log_agree():
    plan = pd.read_csv(GT / 'fetch_plan.csv')
    log = pd.read_csv(GT / 'fetch_log.csv')
    v2 = log[log.file.str.startswith('data/google_trends/v2/')]
    assert set(plan.file) == set(v2.file), 'every planned request is downloaded, nothing else'
    for r in plan.itertuples():
        logged = v2[v2.file == r.file].iloc[0]
        assert logged.terms == r.terms and str(logged.category) == str(r.cat) and logged.months == 84


def test_selection():
    items = pd.read_csv(GT / 'selected_items.csv')
    series = pd.read_csv(GT / 'selected_series.csv', dtype=str).set_index('month')
    nf = pd.read_csv(GT / 'not_forecast.csv')
    assert list(series.columns) == list(items.key)
    assert items.key.is_unique
    assert list(series.index) == MONTHS
    for r in items.itertuples():
        assert check(series[r.key])['passes'], r.key
        # the chosen series is the one in the file it names
        src = pd.read_csv(ROOT / r.file, dtype=str).set_index('month')[r.term]
        assert src.equals(series[r.key].rename(r.term)), r.key
    # every attribute x country is either forecast or listed with a reason, never both
    pairs = {(r.attribute, r.country) for r in items.itertuples()}
    skipped = {(r.attribute, r.country) for r in nf.itertuples()}
    assert not pairs & skipped
    assert pairs | skipped == {(a['name'], c) for a in ATTRIBUTES for c in ('GB', 'FR', 'DK')}
    assert nf.reason.str.len().gt(5).all()


def test_danish_first_then_english():
    items = pd.read_csv(GT / 'selected_items.csv')
    q = pd.read_csv(GT / 'quality.csv')
    ok = {(r.geo, r.term) for r in q.itertuples() if r.passes}
    old = pd.read_csv(GT / 'terms.csv')
    existing = {(r.country, r.english): r.term for r in old.itertuples()}
    by = {(r.attribute, r.country): r.term for r in items.itertuples()}
    for a in ATTRIBUTES:
        terms = country_terms(a, existing).get('DK')
        if not terms or (a['name'], 'DK') not in by:
            continue
        first_ok = next(t for t in terms if ('DK', t) in ok)
        assert by[(a['name'], 'DK')] == first_ok, a['name']


def test_old_items_kept():
    """The 41 items on the first version of the site are all still forecast, except Denmark's 'leopard' (all searches
    for the word), replaced by 'leopard kjole' (leopard dress)."""
    items = pd.read_csv(GT / 'selected_items.csv')
    first = {'GB|leather jacket', 'GB|trench coat', 'GB|bomber jacket', 'GB|suede jacket', 'GB|wool coat',
             'GB|satin dress', 'GB|lace dress', 'GB|bodycon dress', 'GB|slip dress', 'GB|boho dress', 'GB|blazer',
             'GB|cardigan', 'GB|wide leg jeans', 'GB|tweed jacket', 'GB|burgundy dress', 'GB|leopard print dress',
             'GB|polka dot dress', 'GB|brown dress', 'GB|yellow dress', 'FR|veste en cuir', 'FR|trench', 'FR|bomber',
             'FR|manteau en laine', 'FR|robe en satin', 'FR|robe en dentelle', 'FR|robe moulante', 'FR|robe nuisette',
             'FR|robe bohème', 'FR|blazer', 'FR|cardigan', 'FR|jean large', 'FR|robe bordeaux', 'FR|robe marron',
             'FR|robe jaune', 'DK|læderjakke', 'DK|trenchcoat', 'DK|blazer', 'DK|cardigan', 'DK|uldfrakke',
             'DK|satin kjole', 'DK|leopard'}
    assert len(first) == 41
    missing = first - set(items.key)
    assert missing == {'DK|leopard'}
    assert 'DK|leopard kjole' in set(items.key)
