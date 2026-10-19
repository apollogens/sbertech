"""Read existing cache/NPZ only; write independent research diagnostics, never fit."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from src.data import load_panel
from src.metrics import compute_metrics


def main():
    panel = load_panel(ROOT / 'cache')
    out = ROOT / 'research' / 'diagnostics'
    out.mkdir(parents=True, exist_ok=True)
    rows, stocks, segments, thresholds = [], [], [], []
    for path in sorted((ROOT / 'reports/remediation/predictions').glob('*.npz')):
        with np.load(path) as z:
            origin = str(z['origin'])
            pred = z['prediction']
        idx = panel.dates.get_loc(origin)
        truth = panel.y[idx+1:idx+65].astype(float)
        model = path.name[:-(len(origin)+5)]
        score = compute_metrics(truth, pred)
        rows.append(dict(model=model, origin=origin, shape=str(pred.shape),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            role='terminal_diagnostic' if origin == '2026-05-28' else 'development',
            **score, eligible=int((truth.sum(0)>0).sum()),
            eligible_allzero=int(((truth.sum(0)>0)&(pred.sum(0)==0)).sum())))
        if model != 'current_tweedie_z0.25':
            continue
        hist = panel.y[max(0,idx-179):idx+1]
        stock = panel.stock[max(0,idx-179):idx+1]
        observed = np.isfinite(stock)
        stocks.append(dict(origin=origin, observed_fraction=float(observed.mean()),
            missing_fraction=float((~observed).mean()),
            zero_fraction_among_observed=float((stock==0).sum()/observed.sum()),
            no_stock_history_pairs=int((~observed.any(0)).sum()),
            last_day_missing_pairs=int((~observed[-1]).sum()),
            last_day_zero_pairs=int((stock[-1]==0).sum()),
            sales_positive_stock_zero_days=int(((hist>0)&(stock==0)).sum())))
        for name, mask in [('sparse_freq180_lt_0.1',(hist>0).mean(0)<.1),
                           ('non_sparse_freq180_ge_0.1',(hist>0).mean(0)>=.1),
                           ('very_sparse_freq180_le_0.05',(hist>0).mean(0)<=.05),
                           ('non_sparse_freq180_gt_0.05',(hist>0).mean(0)>.05)]:
            actual=truth[:,mask].sum(0)
            estimated=pred[:,mask].sum(0)
            segments.append(dict(origin=origin, segment=name, pairs=int(mask.sum()),
                eligible=int((actual>0).sum()), eligible_allzero=int(((actual>0)&(estimated==0)).sum()),
                volume_share=float(actual.sum()/truth.sum()), **compute_metrics(truth[:,mask],pred[:,mask])))
        with np.load(path.with_name('tweedie_raw_'+origin+'.npz')) as z:
            raw=z['prediction']
        assert np.array_equal(pred,np.where(raw<.25,0,raw))
        for name, forecast in [('raw',raw),('threshold_0.25',pred)]:
            thresholds.append(dict(origin=origin,stage=name,volume=float(forecast.sum()),
                positive_days=int((forecast>0).sum()), **compute_metrics(truth,forecast)))
    metrics=pd.DataFrame(rows)
    matrix=pd.read_csv(ROOT/'reports/remediation/experiment_matrix.csv')
    joined=metrics.merge(matrix,on=['model','origin'],suffixes=('_new','_old'),validate='one_to_one')
    maxdiff={m:float(np.max(np.abs(joined[m+'_new']-joined[m+'_old']))) for m in ['smape','wape','rmse','bias','rmsle']}
    metrics.to_csv(out/'recomputed_85_metrics.csv',index=False)
    pd.DataFrame(stocks).to_csv(out/'stock_by_cutoff.csv',index=False)
    pd.DataFrame(segments).to_csv(out/'sparse_by_cutoff.csv',index=False)
    pd.DataFrame(thresholds).to_csv(out/'threshold_ablation.csv',index=False)
    gpu=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader'],capture_output=True,text=True)
    summary=dict(no_training=True,panel_shape=list(panel.y.shape), first_date=str(panel.dates[0].date()),
        last_date=str(panel.dates[-1].date()), warehouses=len(panel.catalogs['warehouses']),articles=len(panel.catalogs['articles']),
        zero_fraction=float((panel.y==0).mean()),stock_missing_fraction=float(np.isnan(panel.stock).mean()),
        cache_array_bytes=int(panel.y.nbytes+panel.stock.nbytes), candidates=int(metrics.model.nunique()),
        windows=int(metrics.origin.nunique()),npz_count=len(rows),metric_max_difference_vs_report=maxdiff,
        gpu_probe=gpu.stdout.strip(),python_packages={n:bool(importlib.util.find_spec(n)) for n in ['torch','transformers','lightning']},
        sparse_definition='historical positive frequency over last 180 days < 0.1; additional <= 0.05 diagnostic; cutoff inclusive',
        notes=['stock zero is observed balance, not causal stockout label','terminal was previously opened, not independent test'])
    (out/'artifact_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
