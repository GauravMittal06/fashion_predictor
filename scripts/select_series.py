"""Pick one Google Trends series per attribute and country (the forecast input), after the quality checks.

Order of preference for each attribute and country (see fpt/attributes.py: country_terms):
1. the item already on the site, when its series passes;
2. the local-language term;
3. Denmark only: the England (English) term, when the Danish one fails. Danish words come first because some
   English words mean something else in Danish (for example "tights" usually means sports leggings there).
A later download of the same term (a retry in a group of small terms) replaces the earlier one.

Writes, in data/google_trends/:
- selected_items.csv  one row per forecast item (key = "GB|term")
- selected_series.csv the chosen series, Nov 2019 - Oct 2026, values exactly as Google gave them ("<1" kept)
- not_forecast.csv    attribute-country pairs without a usable series, with the reason
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from check_quality import load_all  # noqa: E402
from fpt.attributes import ATTRIBUTES, country_terms, search_terms  # noqa: E402
from fpt.quality import check  # noqa: E402

GT = ROOT / "data/google_trends"
COUNTRY = {"GB": "England", "FR": "France", "DK": "Denmark"}


def main():
    series = load_all()
    old = pd.read_csv(GT / "terms.csv")
    existing = {(r.country, r.english): r.term for r in old.itertuples()}
    items, cols, missing = [], {}, []
    for a in ATTRIBUTES:
        _, cat = search_terms(a)
        per = country_terms(a, existing)
        for cc in COUNTRY:
            if a["excluded"]:
                missing.append(dict(country=cc, attribute=a["name"], type=a["type"], reason=a["excluded"]))
                continue
            if cc not in per:
                missing.append(dict(country=cc, attribute=a["name"], type=a["type"], reason="no search term"))
                continue
            chosen, why = None, []
            for i, term in enumerate(per[cc]):
                s, f = series[(cc, term)]
                r = check(s)
                if r["passes"]:
                    from_site = a["existing"] is not None and existing.get((cc, a["existing"])) == term
                    source = "site item" if from_site else ("English term" if i > 0 else "local term")
                    chosen = dict(term=term, file=f, source=source, **r)
                    break
                why.append(f"'{term}': {r['reason']}")
            if chosen is None:
                missing.append(dict(country=cc, attribute=a["name"], type=a["type"],
                                    reason="too few Google searches (" + "; ".join(why) + ")"))
                continue
            key = f"{cc}|{chosen['term']}"
            assert key not in cols, f"{key} chosen twice"
            cat_used = 68 if (a["type"] == "Garments" and chosen["source"] != "site item") else 0
            items.append(dict(key=key, country=cc, country_name=COUNTRY[cc], attribute=a["name"], type=a["type"],
                              term=chosen["term"], source=chosen["source"], category=cat_used, file=chosen["file"],
                              dev_mean=chosen["dev_mean"], empty_share=chosen["empty_share"], note=a["note"]))
            cols[key] = series[(cc, chosen["term"])][0]
    sel = pd.DataFrame(items)
    ser = pd.DataFrame(cols)
    ser.index.name = "month"
    nf = pd.DataFrame(missing)
    sel.to_csv(GT / "selected_items.csv", index=False, encoding="utf-8")
    ser.to_csv(GT / "selected_series.csv", encoding="utf-8")
    nf.to_csv(GT / "not_forecast.csv", index=False, encoding="utf-8")
    print(f"{len(sel)} items selected; {len(nf)} attribute-country pairs not forecast")
    print(sel.pivot_table(index="type", columns="country", values="key", aggfunc="count", fill_value=0)
          .reindex(columns=list(COUNTRY)).to_string())
    print(sel.source.value_counts().to_string())


if __name__ == "__main__":
    main()
