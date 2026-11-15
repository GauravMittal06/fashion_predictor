"""Shared paths and fixtures. Tests that need the team's private workbook export (posts.csv, trims.csv) look for it in
FPT_PRIVATE (default: ../fashion_predictor_team2) and are skipped when it is not there."""
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
PRIVATE = Path(os.environ.get('FPT_PRIVATE', ROOT.parent / 'fashion_predictor_team2'))
GT = ROOT / 'data' / 'google_trends'
FC = ROOT / 'outputs' / 'forecast'
INS = ROOT / 'data' / 'insights'


@pytest.fixture(scope='session')
def posts():
    f = PRIVATE / 'data' / 'clean' / 'posts.csv'
    if not f.exists():
        pytest.skip('private posts.csv not available')
    sys.path.insert(0, str(PRIVATE / 'scripts'))
    from build_catalogue import load_posts
    return load_posts()


@pytest.fixture(scope='session')
def trims():
    f = PRIVATE / 'data' / 'clean' / 'trims.csv'
    if not f.exists():
        pytest.skip('private trims.csv not available')
    return pd.read_csv(f)
