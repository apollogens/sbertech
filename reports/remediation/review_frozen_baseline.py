"""Independently rerun legacy checks on preserved source and model bytes."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
target = Path(tempfile.mkdtemp(prefix='nonton-review-baseline-'))
with zipfile.ZipFile(ROOT / 'reports/remediation/original_release.zip') as archive:
    for name in archive.namelist():
        if not name.endswith('.zip'):
            archive.extract(name, target)
for relative in ('cache', 'reports/oof', 'reports/qa'):
    shutil.copytree(ROOT / relative, target / relative, dirs_exist_ok=True)
for name in ('selection_frozen.json', 'experiment_results.csv'):
    shutil.copy2(ROOT / 'reports' / name, target / 'reports' / name)
initial = json.loads((ROOT / 'reports/remediation/initial_manifest.json').read_text(encoding='utf-8-sig'))
checks = []
for item in initial:
    if item['path'].startswith(('src/', 'app/', 'tests/', 'model/')):
        path = target / item['path']
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        checks.append({'path': item['path'], 'sha256': digest, 'matches_initial': digest == item['sha256']})
assert all(row['matches_initial'] for row in checks)
(ROOT / 'reports/remediation/review_frozen_baseline_hashes.json').write_text(json.dumps({'snapshot': str(target), 'files': checks}, indent=2), encoding='utf-8')
env = dict(os.environ, PYTHONIOENCODING='utf-8')
commands = [
    ('pytest', ['-m', 'pytest', 'tests', 'reports/qa/check_backend_independent.py', '-q']),
    ('temporal', ['reports/qa/check_temporal_independent.py']),
    ('backend_real', ['reports/qa/check_backend_independent.py', '--real']),
]
for label, args in commands:
    output = ROOT / f'reports/remediation/review_{label}_frozen_baseline.txt'
    with output.open('w', encoding='utf-8') as handle:
        handle.write(f'SNAPSHOT={target}\nCOMMAND={sys.executable} {args}\n')
        handle.flush()
        result = subprocess.run([sys.executable, *args], cwd=target, env=env, stdout=handle, stderr=subprocess.STDOUT)
        handle.write(f'\nPROCESS_EXIT_CODE={result.returncode}\n')
    print(json.dumps({'check': label, 'exit_code': result.returncode, 'output': str(output)}), flush=True)
shutil.copy2(target / 'reports/qa/reviewer_leakage.md', ROOT / 'reports/remediation/review_temporal_frozen_baseline_report.md')
