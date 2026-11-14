"""Our forecaster against WGSN, using two WGSN trend posts recorded in our Instagram dataset.

For each WGSN call, we go back to the month it was posted and take the label our model gave then (data up to then
only, from outputs/forecast/track_record.csv), and compare both with what searches actually did over the next 6 months.

    python scripts/check_wgsn.py   ->  outputs/forecast/wgsn_check.csv   (needs scripts/build_forecasts.py first)
"""
from pathlib import Path
import pandas as pd

FC = Path(__file__).resolve().parent.parent / 'outputs' / 'forecast'
H = 6
# (WGSN post date, what WGSN said, what WGSN's call means for searches, items to check, our data up to)
WGSN = [('10 Feb 2025', 'Berry Tones for A/W 25/26 (burgundy)', 'rising', ['GB|burgundy dress', 'FR|robe bordeaux'], '2025-01'),
        ('29 Jun 2025', 'The boho style is back', 'rising', ['GB|boho dress', 'FR|robe bohème'], '2025-05')]

track = pd.read_csv(FC / 'track_record.csv')
names = pd.read_csv(FC / 'items.csv').set_index('key')
rows = []
for posted, said, wgsn_dir, keys, data_to in WGSN:
    for k in keys:
        r = track[(track.item == k) & (track.horizon == H) & (track.made_with_data_to == data_to)].iloc[0]
        rows.append({'wgsn_posted': posted, 'wgsn_said': said, 'item': names.loc[k, 'english'],
                     'country': names.loc[k, 'country_name'], 'our_model_said': r.call, 'our_change': r.trend_score,
                     'actual': r.actual_direction, 'actual_change': r.actual_change,
                     'wgsn_right': wgsn_dir == r.actual_direction, 'model_right': bool(r.right)})
out = pd.DataFrame(rows)
out.to_csv(FC / 'wgsn_check.csv', index=False)
print(out[['wgsn_said', 'country', 'our_model_said', 'actual', 'actual_change', 'wgsn_right', 'model_right']]
      .round(2).to_string(index=False))
