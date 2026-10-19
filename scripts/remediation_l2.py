"""Explicit exploratory amendment: unchanged original L2 on all five origins."""
from pathlib import Path
import sys
import json
import hashlib
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import lightgbm as lgb
import numpy as np
import pandas as pd
from src.data import load_panel
from src.features import snapshot
from src.metrics import compute_metrics, weighted_score, smape_include_zero_zero
from src.baselines import baseline_predict
from src.train import train_model
from src.predict import predict_panel
from scripts.qa_analysis import bias_diagnostics


def run():
    out=ROOT/'reports/remediation'; pred_dir=out/'predictions'
    protocol=json.loads((out/'experiment_protocol.json').read_text(encoding='utf-8'))
    panel=load_panel(ROOT/'cache'); rows=[]
    for date in protocol['origins']:
        origin=panel.dates.get_loc(date); fit=0.
        old={'2026-01-20':'lgb_l2_fold1.txt','2026-03-25':'lgb_l2_fold2.txt'}
        if date in old:
            path=ROOT/'reports/oof'/old[date]
            bundle=dict(model=lgb.Booster(model_file=str(path)),config=json.loads((ROOT/'model/config.json').read_text()),catalogs=panel.catalogs)
            bundle['config']['zero_threshold']=0
        else:
            start=perf_counter(); bundle=train_model(panel,origin,'regression',220); fit=perf_counter()-start
            path=pred_dir/f'l2_{date}.txt'; bundle['model'].save_model(str(path))
        start=perf_counter(); raw=predict_panel(panel,origin,bundle); inference=perf_counter()-start
        truth=panel.y[origin+1:origin+65]; sparse=snapshot(panel,origin).freq_180.to_numpy()<.1
        for name,pred in [('lgb_l2',raw),('lgb_l2_z0.25',np.where(raw<.25,0,raw))]:
            file=pred_dir/f'{name}_{date}.npz';np.savez_compressed(file,prediction=pred,origin=date)
            row=dict(experiment='remediation-v1-L2-amendment',model=name,origin=date,start=str(panel.dates[origin+1].date()),end=str(panel.dates[origin+64].date()),
                     role='terminal_diagnostic' if date==protocol['origins'][-1] else 'development',
                     **compute_metrics(truth,pred),**bias_diagnostics(truth,pred),
                     smape_text=smape_include_zero_zero(truth,pred),local_minmax_score=weighted_score(compute_metrics(truth,pred),compute_metrics(truth,baseline_predict(panel,origin,'last'))),
                     train_seconds=fit,inference_seconds=inference,model_bytes=path.stat().st_size,model_path=str(path),
                     objective='regression',feature_schema='|'.join(bundle['config']['features']),
                     prediction_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),zero_daily_fraction=float((pred==0).mean()),sparse_series=int(sparse.sum()))
            row.update({f'sparse_{k}':v for k,v in compute_metrics(truth[:,sparse],pred[:,sparse]).items()})
            row.update({f'days36_64_{k}':v for k,v in compute_metrics(truth[35:],pred[35:]).items()})
            rows.append(row)
            pd.DataFrame(rows).to_csv(out/'l2_experiment_matrix.csv',index=False)
            print(f'{date} {name}: score={row["local_minmax_score"]:.6f} SMAPE={row["smape"]:.6f} Bias={row["bias"]:.6f}',flush=True)


if __name__=='__main__':
    run()
