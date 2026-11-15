"""Save one Google Trends download (read from the Trends page in a browser) as a CSV, and log it.

The browser step returns one compact line:  terms|first_epoch|n_months|v,v,v;v,v,v;...
("<1" marks a month Google shows as below 1; it is kept as "<1", like the site's first downloads.)

Usage:  python scripts/save_trends.py REQ_ID < compact.txt     (a request in fetch_plan.csv; raw text kept in v2/raw/)
        python scripts/save_trends.py REQ_ID                   (re-save from the kept raw text)
        python scripts/save_trends.py OUT.csv GEO CATEGORY < compact.txt
Appends a row to data/google_trends/fetch_log.csv (file, geo, category, terms, months, fetched_on).
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "data/google_trends/fetch_log.csv"
FIRST, LAST = "2019-11", "2026-10"


def parse(compact: str) -> pd.DataFrame:
    terms, epoch, n, body = compact.strip().split("|", 3)
    terms = terms.split(",")
    rows = [r.split(",") for r in body.split(";")]
    assert len(rows) == int(n), f"expected {n} months, got {len(rows)}"
    start = dt.datetime.fromtimestamp(int(epoch), dt.timezone.utc)
    months = pd.period_range(f"{start.year}-{start.month:02d}", periods=len(rows), freq="M").astype(str)
    for r in rows:  # every value is a whole number 0-100 or "<1", exactly as Google gives it
        assert len(r) == len(terms), f"row has {len(r)} values for {len(terms)} terms"
        assert all(v == "<1" or (v.isdigit() and 0 <= int(v) <= 100) for v in r), f"bad value in {r}"
    df = pd.DataFrame(rows, columns=terms, index=months)
    df.index.name = "month"
    assert df.index[0] == FIRST and df.index[-1] == LAST, f"range {df.index[0]}..{df.index[-1]}"
    return df


def main():
    if len(sys.argv) == 2:  # a request id from fetch_plan.csv; the terms must match the plan
        plan = pd.read_csv(ROOT / "data/google_trends/fetch_plan.csv").set_index("req_id")
        r = plan.loc[sys.argv[1]]
        out, geo, cat = (ROOT / r["file"]).resolve(), r["geo"], str(r["cat"])
        raw = out.parent / "raw" / (out.stem + ".txt")
        raw.parent.mkdir(parents=True, exist_ok=True)
        text = sys.stdin.read()
        if text.strip():
            raw.write_text(text.strip() + "\n", encoding="utf-8")  # keep the exact download first
        df = parse(raw.read_text(encoding="utf-8"))
        assert list(df.columns) == r["terms"].split(";"), f"terms {list(df.columns)} != plan {r['terms']}"
    else:
        out, geo, cat = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3]
        df = parse(sys.stdin.read())
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, encoding="utf-8")
    row = pd.DataFrame([dict(file=out.relative_to(ROOT).as_posix(), geo=geo, category=cat,
                             terms=";".join(df.columns), months=len(df), fetched_on=dt.date.today().isoformat())])
    if LOG.exists():
        log = pd.read_csv(LOG)
        log = pd.concat([log[log.file != row.file[0]], row], ignore_index=True)
    else:
        log = row
    log.to_csv(LOG, index=False, encoding="utf-8")
    sys.path.insert(0, str(ROOT))
    from fpt.quality import check
    res = {c: check(df[c]) for c in df.columns}
    print(f"saved {out.name}: " + "; ".join(f"{c} {'ok' if r['passes'] else 'FAIL ' + r['reason']}"
                                            for c, r in res.items()))


if __name__ == "__main__":
    main()
