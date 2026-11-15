"""Step 3: list every Google Trends request needed for the attribute list (data/google_trends/fetch_plan.csv).

- Terms already downloaded for the site (data/google_trends/terms.csv) are reused, not fetched again.
- At most 5 terms per request (Google's limit); one country and one category per request.
- Denmark: a Danish term and its English alternative go in the same request so their volumes compare directly.
A request is skipped later if its file is already in fetch_log.csv, so the download can resume after a stop.
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fpt.attributes import ATTRIBUTES, country_terms, search_terms  # noqa: E402

GT = ROOT / "data/google_trends"
HL = {"GB": "en-GB", "FR": "fr", "DK": "da"}
DATE = "2019-11-01%202026-10-31"


def url(geo, cat, terms):
    q = ",".join(quote(t) for t in terms)
    c = f"cat={cat}&" if cat else ""
    return f"https://trends.google.com/trends/explore?{c}date={DATE}&geo={geo}&q={q}&hl={HL[geo]}"


def chunks(units, size=5):
    """Pack units (lists of 1 or 2 terms that must stay together) into requests of at most `size` terms."""
    out, cur = [], []
    for u in units:
        if len(cur) + len(u) > size:
            out.append(cur)
            cur = []
        cur = cur + u
    if cur:
        out.append(cur)
    return out


def main():
    old = pd.read_csv(GT / "terms.csv")
    existing = {(r.country, r.english): r.term for r in old.itertuples()}
    have = {(r.country, r.term) for r in old.itertuples()}
    units = {}  # (geo, cat) -> list of term groups (a Danish term and its English alternative stay together)
    for a in ATTRIBUTES:
        _, cat = search_terms(a)
        for geo, terms in country_terms(a, existing).items():
            u = [t for t in terms if (geo, t) not in have]
            if u:
                units.setdefault((geo, cat), []).append(u)
    rows = []
    for (geo, cat), us in units.items():
        for i, req in enumerate(chunks(us), 1):
            assert len(set(req)) == len(req), f"duplicate term in request {req}"
            rid = f"{geo}_c{cat}_{i:02d}"
            rows.append(dict(req_id=rid, geo=geo, cat=cat, terms=";".join(req),
                             file=f"data/google_trends/v2/{rid}.csv", url=url(geo, cat, req)))
    plan = pd.DataFrame(rows)
    plan.to_csv(GT / "fetch_plan.csv", index=False, encoding="utf-8")
    print(plan.groupby(["geo", "cat"]).size().to_string())
    print(len(plan), "requests,", plan.terms.str.count(";").add(1).sum(), "terms")


if __name__ == "__main__":
    main()
