"""Independently inspect completed Docker output and image source/model bytes."""
from pathlib import Path
import hashlib
import json
import subprocess
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
benchmark=json.loads((ROOT/'reports/remediation/docker_benchmark.json').read_text(encoding='utf-8-sig'))
assert benchmark['status']=='passed' and benchmark['network_mode']=='none'
assert benchmark['cgroup_memory_peak_bytes']<6*1024**3
types={'date':str,'warehouse_name':str,'article':str}
docker=pd.read_csv(ROOT/'reports/remediation/docker_forecast.csv',dtype=types)
offline=pd.read_csv(ROOT/'data/parity/offline.csv',dtype=types)
catalogs=json.loads((ROOT/'model/catalogs.json').read_text(encoding='utf-8'))
keys=['date','warehouse_name','article']
expected=pd.MultiIndex.from_product([pd.date_range('2026-08-01',periods=64).strftime('%Y-%m-%d'),catalogs['warehouses'],catalogs['articles']],names=keys)
actual=pd.MultiIndex.from_frame(docker[keys])
assert len(actual)==562496 and actual.is_unique
assert actual.difference(expected).empty and expected.difference(actual).empty
assert docker[keys].equals(offline[keys])
assert np.isfinite(docker.quantity).all() and (docker.quantity>=0).all()
difference=float(np.max(np.abs(docker.quantity.to_numpy()-offline.quantity.to_numpy())))
assert difference==benchmark['max_abs_difference'] and difference<=1e-7
image_id=subprocess.run(['docker','image','inspect','nonton-forecast:remediation','--format','{{.Id}}'],check=True,text=True,capture_output=True).stdout.strip()
code="""from pathlib import Path
import hashlib,json
root=Path('/app')
paths=sorted([*root.glob('src/*.py'),*root.glob('app/*.py'),*[p for p in root.glob('model/*') if p.is_file()],root/'requirements.lock'])
print(json.dumps({p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},sort_keys=True))
"""
image_output=subprocess.run(['docker','run','--rm','-i','--network','none','--memory','128m','--cpus','1','--entrypoint','python',image_id,'-'],input=code,check=True,text=True,capture_output=True).stdout
image_hashes=json.loads(image_output)
local_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in image_hashes}
assert image_hashes==local_hashes
assert 'model/manifest.json' in image_hashes and 'model/training_record.json' in image_hashes
result=dict(status='passed',image_id=image_id,image_source_model_dependency_hashes=image_hashes,
            actual_image_matches_current_local_files=True,docker_csv_rows=len(docker),grid_exact=True,
            offline_docker_max_abs=difference,docker_csv_sha256=hashlib.sha256((ROOT/'reports/remediation/docker_forecast.csv').read_bytes()).hexdigest(),
            probe_reported_post_seconds=benchmark['post_seconds'],probe_reported_cgroup_peak_bytes=benchmark['cgroup_memory_peak_bytes'],
            probe_reported_image_bytes=benchmark['image_bytes'],probe_reported_build_seconds=benchmark['build_seconds'],
            limitation='Reviewer independently inspected real image bytes and forecast CSV; actual full HTTP request/runtime/cgroup measurement executed by root probe. Build used cached layers.')
(ROOT/'reports/remediation/review_docker_artifacts.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
