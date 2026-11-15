"""Add retry requests to fetch_plan.csv for terms that failed only because a bigger term squashed them.

Rule: a term needed by an attribute (no passing term yet for that attribute and country) is retried when at least
two-thirds of its months have data (empty share <= 1/3) but its development average is under 3. Retried terms are
grouped with other small terms of the same country and category (sorted by size, up to 5 per request), so Google
scales them against each other instead of against a big term. A term with mostly empty months is not retried:
grouping cannot add data Google does not have.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from fpt.attributes import ATTRIBUTES, country_terms, search_terms  # noqa: E402
from make_fetch_plan import url  # noqa: E402

GT = ROOT / "data/google_trends"
MAX_EMPTY = 1 / 3


def main():
    q = pd.read_csv(GT / "quality.csv")
    ok = {(r.geo, r.term) for r in q.itertuples() if r.passes}
    old = pd.read_csv(GT / "terms.csv")
    existing = {(r.country, r.english): r.term for r in old.itertuples()}
    cand = []
    for a in ATTRIBUTES:
        _, cat = search_terms(a)
        for cc, terms in country_terms(a, existing).items():
            if any((cc, t) in ok for t in terms):
                continue
            for t in terms:
                r = q[(q.geo == cc) & (q.term == t)].iloc[0]
                if r.empty_share <= MAX_EMPTY and r.dev_mean < 3:
                    cand.append(dict(geo=cc, cat=cat, term=t, dev_mean=r.dev_mean))
    c = pd.DataFrame(cand).drop_duplicates(["geo", "term"]).sort_values(["geo", "cat", "dev_mean"])
    plan = pd.read_csv(GT / "fetch_plan.csv")
    plan = plan[~plan.req_id.str.startswith("retry_")]
    rows = []
    for (geo, cat), g in c.groupby(["geo", "cat"]):
        terms = g.term.tolist()
        for i in range(0, len(terms), 5):
            req = terms[i:i + 5]
            rid = f"retry_{geo}_c{cat}_{i // 5 + 1:02d}"
            rows.append(dict(req_id=rid, geo=geo, cat=cat, terms=";".join(req),
                             file=f"data/google_trends/v2/{rid}.csv", url=url(geo, cat, req)))
    plan = pd.concat([plan, pd.DataFrame(rows)], ignore_index=True)
    plan.to_csv(GT / "fetch_plan.csv", index=False, encoding="utf-8")
    print(pd.DataFrame(rows)[["req_id", "terms"]].to_string(index=False))


if __name__ == "__main__":
    main()
