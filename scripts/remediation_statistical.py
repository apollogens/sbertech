"""Official StatsForecast benchmarks in a separate dependency environment."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
import statsforecast
from statsforecast.models import CrostonSBA, TSB, ADIDA
from src.data import load_panel
from src.baselines import baseline_predict
from src.features import snapshot
from src.metrics import compute_metrics, weighted_score, smape_include_zero_zero
from scripts.qa_analysis import bias_diagnostics


def run(args):
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    pred_dir=out/'predictions'; pred_dir.mkdir(exist_ok=True)
    panel=load_panel(ROOT/'cache')
    protocol=json.loads((out/'experiment_protocol.json').read_text(encoding='utf-8'))
    models={'sba_official':CrostonSBA(),'tsb_official':TSB(alpha_d=.05,alpha_p=.05),'adida_official':ADIDA()}
    # Executed behavioral checks include zeros, fractional sales, late activation,
    # long zero tails, one positive, and short history. No future values supplied.
    fixtures={'all_zero':np.zeros(180), 'fractional':np.array([0.,.2,0.,.6,0.,.1]),
              'new_active':np.r_[np.zeros(179),.7], 'one_positive':np.r_[.5,np.zeros(179)],
              'long_zero_tail':np.r_[[.2,.5,.1],np.zeros(177)], 'short':np.array([.4])}
    checks=[]
    for name,model in models.items():
        for case,y in fixtures.items():
            forecast=model.forecast(y=y.astype(float),h=64,fitted=False)['mean']
            assert forecast.shape==(64,) and np.isfinite(forecast).all() and (forecast>=0).all(), (name,case,forecast)
            if case=='all_zero':
                assert not forecast.any()
            checks.append(dict(model=name,case=case,first_prediction=float(forecast[0]),status='passed'))
    pd.DataFrame(checks).to_csv(out/'statistical_behavior_checks.csv',index=False)
    records=[]
    for date in protocol['origins']:
        origin=panel.dates.get_loc(date); truth=panel.y[origin+1:origin+65]
        history=panel.y[max(0,origin-179):origin+1].astype(float)
        sparse=snapshot(panel,origin).freq_180.to_numpy()<.1
        for name,model in models.items():
            start=perf_counter()
            pred=np.stack([model.forecast(y=history[:,i],h=64,fitted=False)['mean'] for i in range(history.shape[1])],axis=1)
            elapsed=perf_counter()-start
            assert np.isfinite(pred).all() and (pred>=0).all()
            file=pred_dir/f'{name}_{date}.npz'; np.savez_compressed(file,prediction=pred,origin=date)
            row=dict(experiment='remediation-v1',model=name,origin=date,start=str(panel.dates[origin+1].date()),end=str(panel.dates[origin+64].date()),
                     role='terminal_diagnostic' if date==protocol['origins'][-1] else 'development',
                     **compute_metrics(truth,pred),**bias_diagnostics(truth,pred),
                     smape_text=smape_include_zero_zero(truth,pred),
                     local_minmax_score=weighted_score(compute_metrics(truth,pred),compute_metrics(truth,baseline_predict(panel,origin,'last'))),
                     train_seconds=0.,inference_seconds=elapsed,model_bytes=0,objective='official statistical recurrence; 180 days',
                     package_version=statsforecast.__version__,prediction_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                     zero_daily_fraction=float((pred==0).mean()),sparse_series=int(sparse.sum()))
            row.update({f'sparse_{k}':v for k,v in compute_metrics(truth[:,sparse],pred[:,sparse]).items()})
            row.update({f'days36_64_{k}':v for k,v in compute_metrics(truth[35:],pred[35:]).items()})
            records.append(row); pd.DataFrame(records).to_csv(out/'statistical_experiment_matrix.csv',index=False)
            print(f'{date} {name} SMAPE={row["smape"]:.6f} Bias={row["bias"]:.6f} seconds={elapsed:.3f}',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default=ROOT/'reports/remediation')
    run(parser.parse_args())
