"""README.md numbers come from the build outputs (scripts/make_readme.py), and the counts written in its text are right."""
import pandas as pd

from conftest import INS, ROOT
import make_readme


def test_generated_blocks_are_current():
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert make_readme.results_block() in text
    assert make_readme.coverage_block() in text


def test_counts_in_the_text():
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    pc = pd.read_csv(INS / 'post_counts.csv', dtype={'year': str})
    n_posts = int(pc[(pc.season == 'all') & (pc.year == 'all')].groupby('country').total_posts.first().sum())
    rw = pd.read_csv(INS / 'runway.csv')
    n_looks = int(rw.drop_duplicates(['brand', 'year']).total_looks.sum())
    assert f'{n_posts} Instagram posts' in text and n_posts == 202
    assert f'{n_looks} Chanel and Dior looks' in text and n_looks == 118
