"""Record exact runtime, immutable input and serving fingerprints."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
paths = [*sorted((ROOT/'model').glob('*')), *sorted((ROOT/'src').glob('*.py')),
         *sorted((ROOT/'app').rglob('*.py')), ROOT/'submission.csv', ROOT/'cache/panel.npz',
         ROOT/'cache/catalogs.json', ROOT/'requirements.lock', ROOT/'requirements-dev.txt', ROOT/'Dockerfile']
result = dict(python=sys.version, platform=platform.platform(),
              packages={p: importlib.metadata.version(p) for p in ['lightgbm','numpy','pandas','psutil','pytest']},
              fingerprints={str(p.relative_to(ROOT)): sha(p) for p in paths if p.is_file()},
              git_status=subprocess.run(['git','status','--short'], cwd=ROOT, capture_output=True, text=True).stdout,
              note='Снимок текущего состояния в ходе исследования; исторические release hashes проверяются отдельно. Git пока без commits; rollback обеспечен прежними архивами и неизменностью файлов.')
path=ROOT/'research/environment_and_inputs.json'
if path.exists():
    before=json.loads(path.read_text(encoding='utf-8'))
    comparison={p: before['fingerprints'].get(p)==v for p,v in result['fingerprints'].items()}
    (ROOT/'research/release_preservation_check.json').write_text(json.dumps(dict(all_unchanged=all(comparison.values()), files=comparison), ensure_ascii=False, indent=2),encoding='utf-8')
else:
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
