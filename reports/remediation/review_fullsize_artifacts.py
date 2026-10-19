"""Independently inspect real HTTP probe outputs and submission, no new requests."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src.artifacts import file_hash

out=ROOT/'reports/remediation/backend_fullsize'
benchmark=json.loads((out/'benchmark.json').read_text(encoding='utf-8'))
assert benchmark['status']=='passed'
manifest=json.loads((ROOT/'model/manifest.json').read_text(encoding='utf-8'))
assert benchmark['model_id']==manifest['bundle_id']
assert benchmark['peak_server_rss_bytes']>100_000_000
assert len(benchmark['observed_server_pids'])>=2
assert 'Sum of RSS' in benchmark['memory_measurement']
assert benchmark['input_sha256']=={name:file_hash(ROOT/f'data/parity/{name}.csv') for name in ('sales','stock')}
hashes={name:file_hash(out/f'{name}.csv') for name in ('first','second','during','cached')}
assert len(set(hashes.values()))==1
failure=json.loads((out/'failed.json').read_text(encoding='utf-8'))
rejected=json.loads((out/'rejected.json').read_text(encoding='utf-8'))
assert failure['code']=='VALIDATION_ERROR'
assert rejected['code']=='REQUEST_ERROR'
assert benchmark['failed_post_status']==400 and benchmark['concurrent_post_status']==409
assert benchmark['cache_versions']==['1','2']
types={'date':str,'warehouse_name':str,'article':str}
api=pd.read_csv(out/'first.csv',dtype=types)
offline=pd.read_csv(ROOT/'data/parity/offline.csv',dtype=types)
submission=pd.read_csv(ROOT/'submission.csv',dtype=types)
catalogs=json.loads((ROOT/'model/catalogs.json').read_text(encoding='utf-8'))
keys=['date','warehouse_name','article']
expected=pd.MultiIndex.from_product([pd.date_range('2026-08-01',periods=64).strftime('%Y-%m-%d'),catalogs['warehouses'],catalogs['articles']],names=keys)
for frame in (api,offline,submission):
    assert list(frame.columns)==keys+['quantity']
    actual=pd.MultiIndex.from_frame(frame[keys])
    assert len(actual)==562496 and actual.is_unique
    assert actual.difference(expected).empty and expected.difference(actual).empty
    assert np.isfinite(frame.quantity).all() and (frame.quantity>=0).all()
assert api[keys].equals(offline[keys]) and api[keys].equals(submission[keys])
api_offline=float(np.max(np.abs(api.quantity.to_numpy()-offline.quantity.to_numpy())))
api_submission=float(np.max(np.abs(api.quantity.to_numpy()-submission.quantity.to_numpy())))
assert api_offline==benchmark['max_abs_offline_difference']==0.
assert api_submission<=1e-7
result=dict(status='passed',rows=len(api),dates=['2026-08-01','2026-10-03'],grid_exact=True,
            model_id=benchmark['model_id'],http_artifact_hashes=hashes,
            actual_input_hashes_match=True,api_offline_max_abs=api_offline,
            api_submission_max_abs=api_submission,submission_sha256=file_hash(ROOT/'submission.csv'),
            probe_reported_peak_server_tree_rss=benchmark['peak_server_rss_bytes'],
            probe_reported_post_seconds=benchmark['post_seconds'],
            probe_reported_replacement_seconds=benchmark['replacement_post_seconds'],
            concurrency_failure_artifacts_verified=True,
            limitation='Reviewer пересчитал настоящие HTTP outputs и сверил input/model hashes; runtime/RSS измерил отдельный выполнявшийся probe, не повторный reviewer request')
(ROOT/'reports/remediation/review_fullsize_artifacts.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
