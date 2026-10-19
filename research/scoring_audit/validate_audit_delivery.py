"""Validate audit outputs and confirm release preservation; no fitting."""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
import pandas as pd
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
REQUIRED=['scoring_objective_audit.md','per_fold_candidate_metrics.csv','pareto_frontier.csv',
          'weighted_rank_sensitivity.csv','normalization_sensitivity.md','catalog_provenance_audit.md',
          'revised_model_selection_policy.md','independent_verification.md','final_recommendation_ru.md']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run():
    assert all((OUT/p).is_file() and (OUT/p).stat().st_size>0 for p in REQUIRED)
    x=pd.read_csv(OUT/'per_fold_candidate_metrics.csv')
    assert len(x)==119 and x.model.nunique()==25 and not x.duplicated(['origin','model']).any()
    inv=pd.read_csv(OUT/'prediction_inventory.csv');assert len(inv)==151
    assert len(pd.read_csv(OUT/'prediction_aliases.csv'))==32
    for row in inv.itertuples():assert sha(ROOT/row.path)==row.sha256
    cross=json.loads((OUT/'root_reviewer_c_crosscheck.json').read_text(encoding='utf-8'))
    assert cross['compared']==119 and max(cross['max_errors'].values())<1e-10
    a=json.loads((OUT/'reviewer_a_rank_crosscheck.json').read_text(encoding='utf-8'))
    assert a['status']=='PASS' and a['independently_computed_rank_rows_matched']==680 and a['independently_computed_minmax_rows_matched']==680
    # Contributions must reconstruct the corresponding global paired differences.
    contributions=pd.read_csv(OUT/'focus_group_contributions.csv');contributions=contributions[contributions.segment=='all']
    paired=pd.read_csv(OUT/'paired_incumbent_differences.csv')
    joined=contributions.merge(paired,on=['origin','model'],validate='one_to_one')
    assert len(joined)==15
    for comp,metric in [('smape_contribution_pp','smape'),('bias_contribution_pp','bias'),('wape_contribution_pp','wape')]:
        assert (joined[comp]-joined['delta_'+metric]).abs().max()<1e-10
    # Check the final frozen production delivery, not the obsolete initial manifest.
    manifest=json.loads((ROOT/'reports/remediation/delivery_manifest.json').read_text(encoding='utf-8'))
    # Reviewer C provides normalized paths and expected hashes from that manifest.
    checks=pd.read_csv(OUT/'reviewer_c_release_hashes.csv')
    expected_col=next(c for c in ['expected_sha256','sha256_expected','expected_hash','sha256'] if c in checks.columns)
    path_col='path'
    for row in checks.to_dict(orient='records'):
        assert sha(ROOT/row[path_col])==row[expected_col]
    c=json.loads((OUT/'reviewer_c_verification.json').read_text(encoding='utf-8'))
    assert sha(ROOT/'nonton_solution_remediated_verified.zip')==c['release_archive_sha256']
    result=dict(status='PASS',evaluation_date_moscow='2026-10-19',no_training=True,required_deliverables=9,
                canonical_forecasts=119,source_npz=151,release_files_checked=len(checks),
                release_archive_sha256=c['release_archive_sha256'],root_metric_crosscheck=cross)
    (OUT/'delivery_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    files=[p for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='audit_manifest.json']
    (OUT/'audit_manifest.json').write_text(json.dumps({str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in files},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':run()
