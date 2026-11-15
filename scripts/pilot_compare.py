"""Compare the two search forms in the pilot (see data/google_trends/pilot/decision.md)."""
import pandas as pd, numpy as np
from pathlib import Path
P=str(Path(__file__).resolve().parents[1]/"data/google_trends/pilot")+"/"
a=pd.concat([pd.read_csv(P+"GB_a_fabrics.csv",index_col=0),pd.read_csv(P+"GB_a_colours.csv",index_col=0)],axis=1)
b=pd.concat([pd.read_csv(P+"GB_b_fabrics.csv",index_col=0),pd.read_csv(P+"GB_b_colours.csv",index_col=0)],axis=1)
pairs=list(zip(a.columns,b.columns))
dev=lambda s:s.loc[:"2025-10"]
def nov_bump(s):
    # November vs the mean of October and December, averaged over the years (Black Friday check)
    r=[]
    for y in range(2020,2026):
        o,n,d=s.get(f"{y}-10"),s.get(f"{y}-11"),s.get(f"{y}-12")
        if o is not None and d is not None and (o+d)>0: r.append(n/((o+d)/2))
    return np.mean(r)
rows=[]
for pa,pb in pairs:
    sa,sb=a[pa],b[pb]
    # seasonal shape: average by calendar month, then correlation of the two shapes
    ma=dev(sa).groupby(dev(sa).index.str[5:]).mean(); mb=dev(sb).groupby(dev(sb).index.str[5:]).mean()
    rows.append(dict(plain=pa,garment=pb,corr_all=round(sa.corr(sb),2),corr_season=round(ma.corr(mb),2),
        nov_bump_plain=round(nov_bump(sa),2),nov_bump_garment=round(nov_bump(sb),2),
        zero_plain=round((sa==0).mean(),2),zero_garment=round((sb==0).mean(),2),
        min_plain=int(sa.min()),min_garment=int(sb.min())))
print(pd.DataFrame(rows).to_string(index=False))
