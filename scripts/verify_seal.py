"""Check that a sealed forecast has not been changed since it was made.

The fingerprint (SHA-256) is worked out again from the sealed numbers. If even one digit was edited, it no longer
matches. Share the fingerprint (email it to the teacher, or put it in the report) on the day it is made: anyone
can then check later that the forecast was not touched.

    python scripts/verify_seal.py                  (checks every file in sealed/)
"""
import hashlib
import json
from pathlib import Path

for f in sorted((Path(__file__).resolve().parent.parent / 'sealed').glob('*.json')):
    seal = json.loads(f.read_text(encoding='utf-8'))
    text = json.dumps(seal['sealed'], sort_keys=True, ensure_ascii=False)
    ok = hashlib.sha256(text.encode('utf-8')).hexdigest() == seal['sha256']
    print(f'{f.name}: made {seal["sealed"]["made_on"]}, fingerprint {seal["sha256"][:16]}... '
          f'{"UNCHANGED" if ok else "CHANGED - does not match its fingerprint"}')
