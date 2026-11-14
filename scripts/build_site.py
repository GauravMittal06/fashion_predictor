"""Write index.html: the GitHub Pages site. It runs app.py in the visitor's browser with stlite (Streamlit on
Pyodide), so no server is needed. Re-run after scripts/build_forecasts.py so the site lists every current file.

    python scripts/build_site.py
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STLITE = '1.12.0'
SITE_URL = 'https://gauravmittal06.github.io/fashion_predictor/'
TITLE = 'Fashion Trend Forecast'
DESCRIPTION = ('Where interest in outfit items is heading over the next 3 and 6 months in England, France and Denmark, '
               'validated on a held-out year.')

files = ['app.py'] + sorted(str(p.relative_to(ROOT)).replace('\\', '/') for p in
                            (ROOT / 'outputs' / 'forecast').glob('*')
                            if p.name not in ('improve_preds.npz', 'improve_results.csv'))

def version(f):
    """Short content hash: the URL changes whenever the file does, so browsers never mix old and new files."""
    return hashlib.sha1((ROOT / f).read_bytes()).hexdigest()[:10]


mount = {'requirements': ['plotly'], 'entrypoint': 'app.py',
         'files': {f: {'url': f'./{f}?v={version(f)}'} for f in files},
         'streamlitConfig': {'client.toolbarMode': 'viewer', 'theme.base': 'light', 'theme.primaryColor': '#1d4ed8',
                             'theme.font': 'sans serif'}}

html = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
  <title>{TITLE}</title>
  <meta name="description" content="{DESCRIPTION}" />
  <meta property="og:title" content="{TITLE}" />
  <meta property="og:description" content="{DESCRIPTION}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="{SITE_URL}" />
  <meta property="og:image" content="{SITE_URL}assets/preview.png" />
  <meta name="twitter:card" content="summary_large_image" />
  <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📈</text></svg>" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/browser@{STLITE}/build/stlite.css" />
  <style>
    html, body {{ margin: 0; background: #ffffff; }}
    #loading {{ font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: #374151;
               max-width: 560px; margin: 18vh auto 0; padding: 0 16px; text-align: center; }}
    #loading h1 {{ font-size: 1.6rem; margin: 0 0 .5rem; color: #111827; }}
    #loading p {{ margin: .25rem 0; line-height: 1.5; }}
    .bar {{ height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; margin: 1.5rem auto; width: 220px; }}
    .bar::after {{ content: ""; display: block; height: 100%; width: 40%; background: #1d4ed8;
                  animation: slide 1.2s ease-in-out infinite; }}
    @keyframes slide {{ from {{ transform: translateX(-100%); }} to {{ transform: translateX(250%); }} }}
  </style>
</head>
<body>
  <div id="loading">
    <h1>{TITLE}</h1>
    <p>Starting the app in your browser&hellip;</p>
    <div class="bar"></div>
    <p style="font-size:.9rem;color:#6b7280">The first visit can take up to a minute while Python loads in your browser.
      Later visits are faster.</p>
  </div>
  <div id="root"></div>
  <script type="module">
    import {{ mount }} from "https://cdn.jsdelivr.net/npm/@stlite/browser@{STLITE}/build/stlite.js";
    const options = {json.dumps(mount, indent=2)};
    mount(options, document.getElementById("root"));
    const hide = () => {{ const l = document.getElementById("loading"); if (l) l.remove(); }};
    new MutationObserver((_, obs) => {{
      if (document.querySelector('[data-testid="stApp"] h1')) {{ hide(); obs.disconnect(); }}
    }}).observe(document.body, {{ childList: true, subtree: true }});
  </script>
</body>
</html>
'''
(ROOT / 'index.html').write_text(html, encoding='utf-8')
(ROOT / '.nojekyll').write_text('', encoding='utf-8')     # serve files as they are (no Jekyll processing)
print(f'index.html written: {len(files)} files mounted')
