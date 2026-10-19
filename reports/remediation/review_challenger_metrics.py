"""Recompute saved challenger metrics without production metric functions."""
from pathlib import Path
import hashlib
import json
import sys
from time import perf_counter
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WEIGHTS = dict(smape=.5, wape=.2, rmse=.15, bias=.1, rmsle=.05)

def independent(a, p):
    a = np.asarray(a, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    error = p-a
    valid = a+p > 0
    ratios = np.divide(200*np.abs(error), a+p, out=np.zeros_like(a), where=valid)
    count = valid.sum(axis=0)
    series_smape = np.divide(ratios.sum(axis=0), count, out=np.zeros(a.shape[1]), where=count>0)
    actual_total = a.sum(axis=0)
    selected = actual_total > 0
    signed = (p.sum(axis=0)[selected]-actual_total[selected])/actual_total[selected]*100
    return dict(smape=float(series_smape.mean()), wape=float(np.abs(error).sum()/a.sum()*100),
                rmse=float(np.sqrt(np.square(error).mean())), bias=float(np.abs(signed).mean()),
                rmsle=float(np.sqrt(np.square(np.log1p(p)-np.log1p(a)).mean())))

def run():
    started = perf_counter()
    partial = '--partial' in sys.argv
    suffix = '_partial' if partial else ''
    protocol = json.loads((ROOT/'reports/remediation/experiment_protocol.json').read_text(encoding='utf-8'))
    candidate_order = list(protocol['candidates'])
    if (ROOT/'reports/remediation/protocol_amendment.md').exists():
        candidate_order += ['lgb_l2', 'lgb_l2_z0.25']
    matrix_path = ROOT/'reports/remediation/experiment_matrix.csv'
    if matrix_path.exists():
        table = pd.read_csv(matrix_path)
    else:
        paths = list((ROOT/'reports/remediation').glob('*experiment_matrix.csv'))
        table = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    assert not table.duplicated(['model','origin']).any()
    models = sorted(table.model.unique())
    expected_models = sorted(candidate_order)
    if not partial:
        assert models == expected_models, (models, expected_models)
        assert len(table) == len(models)*len(protocol['origins'])
    with np.load(ROOT/'cache/panel.npz') as saved:
        dates = pd.DatetimeIndex(saved['dates']); y=saved['y']
    maximum_error = 0.
    errors = []
    metrics_rows = []
    for row in table.itertuples(index=False):
        path=ROOT/f'reports/remediation/predictions/{row.model}_{row.origin}.npz'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row.prediction_sha256, path
        origin=dates.get_loc(row.origin)
        with np.load(path) as saved:
            assert str(saved['origin'].item()) == row.origin
            p=saved['prediction']
        a=y[origin+1:origin+65]
        assert a.shape == p.shape == (64,8789)
        assert np.isfinite(p).all() and (p>=0).all()
        computed=independent(a,p)
        baseline=independent(a,np.broadcast_to(y[origin],a.shape))
        score=sum(WEIGHTS[k]*min(computed[k]/baseline[k],1.) for k in WEIGHTS)
        delta=max(abs(computed[k]-getattr(row,k)) for k in WEIGHTS)
        delta=max(delta,abs(score-row.local_minmax_score))
        future=independent(a[35:],p[35:])
        delta=max(delta,*[abs(future[k]-getattr(row,'days36_64_'+k)) for k in WEIGHTS])
        maximum_error=max(maximum_error,delta)
        if delta>=1e-9:
            errors.append(dict(model=row.model,origin=row.origin,max_error=delta))
        metrics_rows.append(dict(model=row.model,origin=row.origin,role=row.role,**computed,local_minmax_score=score))
    assert not errors, errors
    metrics = pd.DataFrame(metrics_rows)
    metrics.to_csv(ROOT/f'reports/remediation/review_challenger_metrics{suffix}.csv',index=False)
    if partial:
        result=dict(status='partial_scope_passed', rows=len(table),
                    all_prediction_hashes_valid=True,max_metric_or_score_difference=maximum_error,
                    seconds=perf_counter()-started,
                    limitations='Проверены только существующие записи; полный candidate matrix и rank не проверены')
        (ROOT/'reports/remediation/review_challenger_verification_partial.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return
    ranks=[]
    for origin, group in metrics.groupby('origin',sort=False):
        group=group.set_index('model').loc[candidate_order]
        scores=np.zeros(len(group))
        for key,weight in WEIGHTS.items():
            order=np.argsort(group[key].to_numpy())
            ranking=np.empty(len(group)); ranking[order]=np.arange(len(group))
            scores+=weight*ranking/(len(group)-1)
        ranks.extend(dict(model=name,origin=origin,official_local_rank=score) for name,score in zip(group.index,scores))
    combined=metrics.merge(pd.DataFrame(ranks),on=['model','origin'])
    combined.to_csv(ROOT/'reports/remediation/review_challenger_metrics.csv',index=False)
    development=combined[combined.origin.isin(protocol['development_origins'])]
    summary=development.groupby('model')[['official_local_rank','local_minmax_score',*WEIGHTS]].mean().sort_values('official_local_rank')
    summary.to_csv(ROOT/'reports/remediation/review_challenger_development_summary.csv')
    result=dict(status='passed',rows=len(table),origins=protocol['origins'],candidates=candidate_order,
                all_prediction_hashes_valid=True,max_metric_or_score_difference=maximum_error,
                official_local_rank_order=summary.index.tolist(), seconds=perf_counter()-started,
                limitations='Локальные ranks на фиксированных кандидатах; terminal diagnostic исключён из summary; не истинный leaderboard, не доказательство независимых репликаций')
    (ROOT/'reports/remediation/review_challenger_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    run()
