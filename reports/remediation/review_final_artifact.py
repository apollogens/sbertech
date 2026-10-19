"""Validate actual final bundle and training record without retraining/inference."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src.artifacts import file_hash
from src.predict import load_bundle

bundle=load_bundle(ROOT/'model')
manifest=bundle['manifest']
record=json.loads((ROOT/'model/training_record.json').read_text(encoding='utf-8'))
assert manifest['provenance']['status']=='training_recorded'
assert manifest['provenance']['training_run_id']==record['training_run_id']
assert manifest['files']['training_record.json']==file_hash(ROOT/'model/training_record.json')
assert record['training_cutoff']=='2026-07-31'
assert record['rounds_used']==bundle['config']['rounds']==bundle['model'].num_trees()==220
assert record['training_rows']==bundle['config']['training_rows']
assert record['training_data_sha256']==manifest['provenance']['training_data_sha256']
paths={'panel.npz':ROOT/'cache/panel.npz','catalogs.json':ROOT/'cache/catalogs.json',
       'selection.json':ROOT/'reports/selection_frozen.json'}
assert {name:file_hash(path) for name,path in paths.items()}==record['training_data_sha256']
assert {name:file_hash(ROOT/'src'/name) for name in record['training_source_sha256']}==record['training_source_sha256']
with np.load(ROOT/'cache/panel.npz') as panel:
    assert str(panel['dates'][-1])[:10]=='2026-07-31'
with zipfile.ZipFile(ROOT/'reports/remediation/original_release.zip') as archive:
    unchanged={name:archive.read('model/'+name)==(ROOT/'model'/name).read_bytes()
               for name in ('catalogs.json','config.json','lightgbm.txt')}
assert all(unchanged.values())
result=dict(status='passed',bundle_id=manifest['bundle_id'],training_run_id=record['training_run_id'],
            provenance_status=manifest['provenance']['status'],model_sha256=file_hash(ROOT/'model/lightgbm.txt'),
            training_record_sha256=file_hash(ROOT/'model/training_record.json'),
            original_release_bytes_unchanged=unchanged,training_rows=record['training_rows'],
            cutoff=record['training_cutoff'],trees=bundle['model'].num_trees(),
            actual_input_hashes_match_record=True,actual_source_hashes_match_record=True,
            record_in_manifest_hashes=True,recorded_fit_seconds=record['fit_seconds'],
            limitation='Reviewer сверил реальный traceable refit output и журнал; не выполнял отдельный полный повторный fit')
(ROOT/'reports/remediation/review_final_artifact.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
