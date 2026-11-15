"""Print the next requests in fetch_plan.csv that are not yet in fetch_log.csv (for resuming the download)."""
import sys
from pathlib import Path
import pandas as pd
GT = Path(__file__).resolve().parents[1] / "data/google_trends"
plan = pd.read_csv(GT / "fetch_plan.csv")
done = set(pd.read_csv(GT / "fetch_log.csv").file) if (GT / "fetch_log.csv").exists() else set()
todo = plan[~plan.file.isin(done)]
print(f"{len(plan) - len(todo)} of {len(plan)} done")
for r in todo.head(int(sys.argv[1]) if len(sys.argv) > 1 else 4).itertuples():
    print(r.req_id, r.geo, r.cat, r.url)
