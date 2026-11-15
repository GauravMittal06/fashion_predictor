"""The totals published from the team's workbook, and the privacy rule (nothing per post is published).
These tests need the private export of the workbook and are skipped without it."""
import re
import subprocess

import pandas as pd

from conftest import INS, ROOT
from fpt.attributes import ATTRIBUTES, POST_FIELDS


def test_post_totals_per_country(posts):
    pc = pd.read_csv(INS / 'post_counts.csv', dtype={'year': str})
    allp = pc[(pc.season == 'all') & (pc.year == 'all')]
    for cc, n in posts.cc.value_counts().items():
        assert set(allp[allp.country == cc].total_posts) == {n}
    assert posts.cc.value_counts().sum() == len(posts) == 202


def test_post_counts_match_an_independent_count(posts):
    """Re-count with pandas string matching (a different code path from fpt.attributes.match_post)."""
    pc = pd.read_csv(INS / 'post_counts.csv', dtype={'year': str})
    allp = pc[(pc.season == 'all') & (pc.year == 'all')].set_index(['attribute', 'country'])
    for a in ATTRIBUTES:
        if a['posts'] is None:
            continue
        text = posts[POST_FIELDS[a['type']]].fillna('').astype(str).agg(' | '.join, axis=1)
        rx = r'(?<![a-zà-ÿ])(?:' + a['posts'] + r')(?![a-zà-ÿ])'
        hit = text.map(lambda s: re.search(rx, s, flags=re.IGNORECASE) is not None)
        for cc in ('GB', 'FR', 'DK'):
            assert allp.loc[(a['name'], cc), 'posts'] == int(hit[posts.cc == cc].sum()), (a['name'], cc)


def test_hand_counted_spot_checks(posts):
    """Counted directly from the raw cells, without the synonym table."""
    pc = pd.read_csv(INS / 'post_counts.csv', dtype={'year': str})
    allp = pc[(pc.season == 'all') & (pc.year == 'all')].groupby('attribute').posts.sum()
    col = posts.colour.fillna('').str.lower()
    cat = posts.category.fillna('').str.lower()
    assert allp['Burgundy'] == col.str.contains('burgundy').sum() == 7
    assert allp['Camel'] == col.str.contains('camel').sum() == 5
    assert allp['Trench coat'] == cat.str.contains('trench').sum() == 8
    assert allp['Black'] == col.str.contains('black').sum()
    assert allp['Hat'] == cat.str.contains(r'\bhat\b|\bcap\b').sum()


def test_season_and_year_splits_add_up(posts):
    pc = pd.read_csv(INS / 'post_counts.csv', dtype={'year': str})
    for (a, cc), g in pc.groupby(['attribute', 'country']):
        allv = g[(g.season == 'all') & (g.year == 'all')].posts.iloc[0]
        seasons = g[(g.season != 'all') & (g.year == 'all')].posts.sum()
        years = g[(g.season == 'all') & (g.year != 'all')].posts.sum()
        assert seasons <= allv and years <= allv, (a, cc)


def test_runway_shares(trims):
    rw = pd.read_csv(INS / 'runway.csv')
    looks = trims.groupby(['brand', 'year']).line_in_year.nunique()
    name = {'Chanel': 'Chanel', 'Christian Dior': 'Dior'}
    for (brand, year), n in looks.items():
        got = rw[(rw.brand == name[brand]) & (rw.year == year)].total_looks
        assert set(got) == {n}, (brand, year)
    assert (rw.looks <= rw.total_looks).all()
    assert ((rw.share - rw.looks / rw.total_looks).abs() < 1e-4).all()
    d = pd.read_csv(INS / 'runway_direction.csv')
    assert set(d.brand) == {'Chanel', 'Dior'}
    for r in d.itertuples():
        if r.direction == 'rising':
            assert r.change_points >= 10
        elif r.direction == 'falling':
            assert r.change_points <= -10
        elif r.direction == 'steady':
            assert abs(r.change_points) < 10


def public_files():
    out = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split('\n')
    return [ROOT / f for f in out if f and (ROOT / f).is_file()]


def test_nothing_per_post_is_published(posts, trims):
    """No caption, link, profile, follower count or team-member name from the workbook appears in any file of the
    public repository."""
    needles = set()
    for c in posts.caption.dropna().astype(str):
        c = c.strip()
        if len(c) >= 20:
            needles.add(c[:25].lower())
        needles |= {m.lower() for m in re.findall(r'@[\w.]{4,}', c)}
    needles |= {str(x).strip().lower() for x in posts.link.dropna() if len(str(x)) > 10}
    needles |= {str(x).strip().lower() for x in posts.source.dropna() if len(str(x)) > 6}
    # the team's sheet names (read from the data, so no name is written in this public file); a word that is also
    # fashion vocabulary in the attribute table (such as "pearl") is checked only as part of the full sheet name
    vocab = (ROOT / 'fpt' / 'attributes.py').read_text(encoding='utf-8').lower()
    for s in set(posts.sheet.dropna()) | set(trims.sheet.dropna()):
        s = str(s).strip().lower()
        if ' ' in s or s not in vocab:
            needles.add(s)
        needles |= {w.lower() for w in re.findall(r'[A-Za-z]{4,}', str(s))
                    if w.lower() not in ('fashion', 'week') and w.lower() not in vocab}
    bad = []
    for f in public_files():
        if f.suffix in ('.png', '.jpg', '.npz', '.pt', '.ico'):
            continue
        text = f.read_text(encoding='utf-8', errors='ignore').lower()
        bad += [(f.name, n) for n in needles if n in text]
    assert not bad, bad[:10]
