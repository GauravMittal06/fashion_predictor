"""Run the quality checks (fpt/quality.py) on every downloaded Trends series and pick one term per attribute
and country. Writes data/google_trends/quality.csv (every series) and prints the attribute-country pairs that
have no passing term yet.

Choice per attribute and country:
- the item already on the site, when there is one (its term is reused);
- otherwise the local-language term if it passes;
- for Denmark, the English term if the Danish one fails and the English one passes.
A later download of the same term (data/google_trends/v2/retry_*.csv) replaces an earlier one.
"""
from __future__ import annotations

import os
import sys
from glob import glob
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fpt.attributes import ATTRIBUTES, country_terms  # noqa: E402
from fpt.quality import check  # noqa: E402

GT = ROOT / "data/google_trends"


def load_all() -> dict:
    """(geo, term) -> (series, file). Files are read in order, so retries (read last) win."""
    files = sorted(glob(str(GT / "[A-Z][A-Z]_*.csv")))
    files += sorted(f for f in glob(str(GT / "v2/*.csv")) if not os.path.basename(f).startswith("retry_"))
    files += sorted(glob(str(GT / "v2/retry_*.csv")))
    out = {}
    for f in files:
        name = os.path.basename(f)
        geo = name.replace("retry_", "")[:2]
        d = pd.read_csv(f, index_col=0, dtype=str)
        d.index = d.index.astype(str)
        for c in d.columns:
            out[(geo, c)] = (d[c], Path(f).relative_to(ROOT).as_posix())
    return out


def main():
    series = load_all()
    old = pd.read_csv(GT / "terms.csv")
    existing = {(r.country, r.english): r.term for r in old.itertuples()}
    q = []
    for (geo, term), (s, f) in series.items():
        q.append(dict(geo=geo, term=term, file=f, **check(s)))
    q = pd.DataFrame(q)
    q.to_csv(GT / "quality.csv", index=False, encoding="utf-8")
    ok = {(r.geo, r.term) for r in q.itertuples() if r.passes}
    missing = []
    for a in ATTRIBUTES:
        for cc, terms in country_terms(a, existing).items():
            if not any((cc, t) in ok for t in terms):
                for t in terms:
                    r = q[(q.geo == cc) & (q.term == t)].iloc[0]
                    missing.append(dict(attribute=a["name"], geo=cc, term=t, dev_mean=r.dev_mean,
                                        empty_share=r.empty_share, file=r.file))
    m = pd.DataFrame(missing)
    print(f"{int(q.passes.sum())} of {len(q)} series pass")
    print(f"{m.groupby(['attribute', 'geo']).ngroups if len(m) else 0} attribute-country pairs without a passing term")
    if len(m):
        print(m.to_string(index=False))


if __name__ == "__main__":
    main()
