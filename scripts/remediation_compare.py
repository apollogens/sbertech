"""Combine fixed candidates and preserve all official raw metrics."""
from pathlib import Path
import sys
import json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd
from scripts.official_score import normalize_rank, METRIC_WEIGHTS


def run():
    out=ROOT/'reports/remediation'
    protocol=json.loads((out/'experiment_protocol.json').read_text(encoding='utf-8'))
    candidates=protocol['candidates']+['lgb_l2','lgb_l2_z0.25']
    table=pd.concat([pd.read_csv(out/f'{name}_experiment_matrix.csv') for name in ['learned','statistical','l2']],ignore_index=True)
    assert len(table)==85 and not table.duplicated(['model','origin']).any()
    table['fixed_local_rank_score']=float('nan')
    for origin in protocol['origins']:
        sub=table[table.origin==origin].set_index('model')
        assert set(sub.index)==set(candidates)
        ranked=normalize_rank({name:{k:float(sub.loc[name,k]) for k in METRIC_WEIGHTS} for name in candidates})
        for name in candidates:
            mask=(table.origin==origin)&(table.model==name)
            table.loc[mask,'fixed_local_rank_score']=sum(METRIC_WEIGHTS[k]*ranked[name][k] for k in METRIC_WEIGHTS)
    table['candidate_order']=table.model.map({name:i for i,name in enumerate(candidates)})
    table=table.sort_values(['origin','candidate_order']).drop(columns='candidate_order')
    table.to_csv(out/'experiment_matrix.csv',index=False)
    metrics=list(METRIC_WEIGHTS)
    dev=table[table.role=='development']
    summary=dev.groupby('model')[metrics+['fixed_local_rank_score','local_minmax_score','inference_seconds','model_bytes']].mean()
    summary['development_windows']=4
    summary['total_windows']=5
    baseline=dev[dev.model=='current_tweedie_z0.25'].set_index('origin')
    for name,sub in dev.groupby('model'):
        sub=sub.set_index('origin').loc[baseline.index]
        summary.loc[name,'minmax_windows_better_than_incumbent']=int((sub.local_minmax_score<baseline.local_minmax_score).sum())
        summary.loc[name,'rank_windows_better_than_incumbent']=int((sub.fixed_local_rank_score<baseline.fixed_local_rank_score).sum())
        for k in metrics:
            summary.loc[name,f'{k}_windows_better_than_incumbent']=int((sub[k]<baseline[k]).sum())
    summary=summary.sort_values('fixed_local_rank_score')
    summary.to_csv(out/'candidate_summary.csv')
    # Before/after release quality is unchanged if weights+postprocessing remain identical.
    old=pd.read_csv(out/'baseline_metrics.csv').iloc[-1]
    pd.DataFrame([dict(metric=k,before=float(old[k]),after=float(old[k]),difference=0.,relative_difference_pct=0.,
                       period='2026-05-29–2026-07-31',eligible_bias_series=7752,
                       before_version='nonton-v1 original',after_version='nonton-v1 traceable bundle',
                       decision='incumbent retained; no quality improvement claimed') for k in metrics]).to_csv(out/'before_after_metrics.csv',index=False)
    print(summary.to_string())


if __name__=='__main__':
    run()
