"""Quality checks for Google Trends series (step 3 of the attribute plan).

Values are kept as Google gives them: whole numbers 0-100, or "<1" for "some searches, under 1".
For the model "<1" counts as 0.5 (the same rule build_forecasts.py has always used).

A series passes when:
- it has all 84 months (Nov 2019 – Oct 2026) and every value is between 0 and 100;
- at most 10% of months are empty ("0" or "<1"): too many empty months means Google has too little data;
- its average over the model's development period (Jan 2022 – Oct 2025, the months before the locked test
  year) is at least 3, the same threshold the site has used since the start.
"""
from __future__ import annotations

import pandas as pd

FIRST, LAST = "2019-11", "2026-10"
DEV_START, DEV_END = "2022-01", "2025-10"
N_MONTHS = 84
MAX_EMPTY_SHARE = 0.10
MIN_DEV_MEAN = 3.0


def numeric(raw: pd.Series) -> pd.Series:
    """Google's values as numbers ("<1" -> 0.5)."""
    return raw.astype(str).str.strip().replace("<1", "0.5").astype(float)


def check(raw: pd.Series) -> dict:
    raw = raw.astype(str).str.strip()
    s = numeric(raw)
    months_ok = len(s) == N_MONTHS and str(s.index[0]) == FIRST and str(s.index[-1]) == LAST and s.notna().all()
    range_ok = bool(((s >= 0) & (s <= 100)).all())
    empty = float(raw.isin(["0", "<1"]).mean())
    dev = float(s.loc[DEV_START:DEV_END].mean())
    reasons = []
    if not months_ok:
        reasons.append("missing months")
    if not range_ok:
        reasons.append("values outside 0-100")
    if empty > MAX_EMPTY_SHARE:
        reasons.append(f"{empty:.0%} empty months")
    if dev < MIN_DEV_MEAN:
        reasons.append(f"average {dev:.1f} < {MIN_DEV_MEAN:g}")
    return dict(passes=not reasons, empty_share=round(empty, 3), dev_mean=round(dev, 2), reason="; ".join(reasons))
