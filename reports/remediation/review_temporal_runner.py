"""Run unchanged legacy temporal audit while preserving its historical report."""
from pathlib import Path
import hashlib
import json
import runpy
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
original_write_text = Path.write_text

def redirected_write(path, *args, **kwargs):
    if path == ROOT / 'reports/qa/reviewer_leakage.md':
        path = ROOT / 'reports/remediation/review_temporal_baseline_report.md'
    return original_write_text(path, *args, **kwargs)

manifest = json.loads((ROOT / 'reports/remediation/initial_manifest.json').read_text(encoding='utf-8-sig'))
observed = []
for item in manifest:
    path = ROOT / item['path']
    if path.is_file() and (item['path'].startswith(('src/', 'app/', 'tests/', 'model/')) or item['path'] == 'scripts/official_score.py'):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        observed.append({'path': item['path'], 'sha256': digest, 'matches_initial': digest == item['sha256']})
(ROOT / 'reports/remediation/review_baseline_hashes.json').write_text(json.dumps(observed, indent=2), encoding='utf-8')
print(json.dumps({'manifest_items': len(observed), 'initial_hash_mismatches': [v['path'] for v in observed if not v['matches_initial']]}), flush=True)
with patch.object(Path, 'write_text', redirected_write):
    runpy.run_path(str(ROOT / 'reports/qa/check_temporal_independent.py'), run_name='__main__')
