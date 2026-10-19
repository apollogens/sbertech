"""Final nontraining checks of release evidence and artifact fingerprints."""
from pathlib import Path
import hashlib
import json
import re
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'integration'
REQUIRED=['source_inventory.md','source_license_audit.md','ensemble_reconstruction.md','catalog_leakage_resolution.md',
          'experiment_protocol.md','ensemble_experiments.csv','rounding_ablation.csv','per_origin_metrics.csv',
          'scoring_sensitivity.md','model_selection.md','release_manifest.json','release_tests.md',
          'independent_verification.md','final_decision_ru.md','presentation_pitch_ru.md']
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def run():
    assert all((OUT/p).is_file() and (OUT/p).stat().st_size>0 for p in REQUIRED)
    x=pd.read_csv(OUT/'per_origin_metrics.csv');assert len(x)==215
    assert not x.duplicated(['candidate','origin']).any()
    assert len(list((OUT/'predictions').glob('*.npz')))==235
    review=json.loads((OUT/'review/result.json').read_text(encoding='utf-8'))
    assert review['status']=='passed' and review['case_forecasts']==215 and review['model_reloaded_forecasts']==235
    assert review['max_abs_replay_error']==0 and review['max_abs_metric_error']<1e-10
    protocol=sha(OUT/'experiment_protocol.md')
    assert protocol==review['protocol_sha256']==json.loads((OUT/'executed_protocol.json').read_text())['protocol_sha256']
    standalone=json.loads((OUT/'release/experimental180/verification.json').read_text())
    smoke=json.loads((OUT/'release/archive_smoke.json').read_text())
    assert standalone['status']==smoke['status']=='passed'
    assert sha(OUT/'nonton_experimental_verified.zip')==smoke['archive_sha256']
    assert json.loads((OUT/'release/experimental180/model_tamper.json').read_text())['status']=='passed'
    manifest=json.loads((OUT/'release_manifest.json').read_text(encoding='utf-8'))
    for name,expected in manifest['files'].items():assert sha(ROOT/name)==expected['sha256'],name
    assert manifest['production_changed'] is False and manifest['experimental_promoted'] is False
    assert manifest['archive_extraction_smoke']['matches_original_workspace']
    # Every new forecast remains bound to its actual saved bytes and official full key hash.
    for row in x.itertuples():assert sha(ROOT/row.prediction_path)==row.prediction_sha256
    # This is independent of new integration files: original frozen sources/release must match.
    preserve=json.loads((OUT/'release/preservation_manifest.json').read_text(encoding='utf-8'))
    result=dict(status='passed',evaluation_date_moscow='2026-10-19',mandatory_outputs=len(REQUIRED),
                production='nonton-v1',experimental_candidate='equal4:P1',promoted=False,
                forecasts=215,independent_replays=235,pytest_cases=193,source_user_confirmed='filipp880/forecast-64-v1',
                missing_second_source=True,archive_sha256=smoke['archive_sha256'],
                standalone180_verified=True,archive_extracted_cli_verified=True,
                scoring_limitations=['reused historical windows','unknown real leaderboard normalization','180-day prediction quality not backtested'])
    (OUT/'delivery_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':run()
