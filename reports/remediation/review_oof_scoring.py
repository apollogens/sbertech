"""Read-only independent scoring, OOF inventory and source evidence."""
from pathlib import Path
import hashlib
import json
import sys
from time import perf_counter
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import official_score

started = perf_counter()
table = pd.read_csv(ROOT / 'reports/experiment_results.csv')
rows = []
for path in sorted((ROOT / 'reports/oof').glob('*.npz')):
    with np.load(path) as saved:
        pred = saved['prediction']
        origin = str(saved['origin'].item())
        match = table.loc[(table.model + '_fold' + table.fold.astype(str)) == path.stem]
        assert len(match) == 1
        record = match.iloc[0]
        rows.append(dict(file=path.name, model=record.model, fold=int(record.fold), role=record.role,
                         origin=origin, first_forecast=str((pd.Timestamp(origin)+pd.Timedelta(days=1)).date()),
                         last_forecast=str((pd.Timestamp(origin)+pd.Timedelta(days=64)).date()),
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         prediction_sha256=hashlib.sha256(pred.tobytes()).hexdigest(),
                         npz_fields=','.join(saved.files), shape=str(pred.shape), dtype=str(pred.dtype)))
pd.DataFrame(rows).to_csv(ROOT / 'reports/remediation/review_oof_inventory.csv', index=False)
with np.load(ROOT / 'cache/panel.npz') as panel:
    dates = pd.DatetimeIndex(panel['dates'])
    cutoff = dates.get_loc('2026-05-28')
    y = panel['y'][cutoff+1:cutoff+65].astype(np.float64)
with np.load(ROOT / 'reports/oof/lgb_tweedie_z0.25_fold3.npz') as saved:
    p = saved['prediction'].astype(np.float64)
catalogs = json.loads((ROOT / 'cache/catalogs.json').read_text())
index = pd.MultiIndex.from_product([dates[cutoff+1:cutoff+65], catalogs['warehouses'], catalogs['articles']],
                                  names=['date','warehouse_name','article'])
truth = index.to_frame(index=False).assign(quantity=y.ravel())
prediction = index.to_frame(index=False).assign(quantity=p.ravel())
# The exact original primitives on the known complete grid avoid quadratic
# string masking in compute_all_metrics. No scoring definition is changed.
series_smape = [official_score.smape_series(y[:,i],p[:,i]) for i in range(y.shape[1])]
series_bias = [official_score.bias_abs_series(y[:,i],p[:,i]) for i in range(y.shape[1])]
official = dict(smape=float(np.mean(series_smape)),
                wape=official_score.wape(y.ravel(),p.ravel()),
                rmse=official_score.rmse(y.ravel(),p.ravel()),
                bias=float(np.mean([v for v in series_bias if v is not None])),
                rmsle=official_score.rmsle(y.ravel(),p.ravel()))
totals = y.sum(axis=0)
pred_totals = p.sum(axis=0)
eligible = totals > 0
signed = (pred_totals[eligible] - totals[eligible]) / totals[eligible] * 100
denom = y + p
prose_smape = float(np.divide(200*np.abs(y-p), denom, out=np.zeros_like(y), where=denom>0).mean())
sources = {}
for path in (Path(r'C:/Users/apollo/Desktop/выборка/markdown hakaton.md'),
             Path(r'C:/Users/apollo/Desktop/выборка/sales_dataset_hakaton_train.csv'),
             Path(r'C:/Users/apollo/Desktop/выборка/stock_dataset_hakaton_train.csv')):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            h.update(chunk)
    sources[str(path)] = dict(bytes=path.stat().st_size, sha256=h.hexdigest())
result = dict(official_full_grid_metrics=official, written_spec_diagnostic_smape=prose_smape,
              scorer_execution='Exact original per-series primitives + original global primitives; known full-grid aggregation',
              grid_rows=len(truth), eligible_series=int(eligible.sum()), excluded_series=int((~eligible).sum()),
              mean_signed_series_bias=float(signed.mean()), global_signed_volume_bias=float((p.sum()-y.sum())/y.sum()*100),
              median_absolute_bias=float(np.median(np.abs(signed))), p90_absolute_bias=float(np.quantile(np.abs(signed), .9)),
              p95_absolute_bias=float(np.quantile(np.abs(signed), .95)),
              positive_actual_zero_forecast_series=int(((pred_totals==0)&eligible).sum()),
              oof_files=len(rows), unique_origins=sorted(set(r['origin'] for r in rows)),
              per_origin_counts=pd.DataFrame(rows).groupby('origin').size().to_dict(),
              source_provenance=sources, seconds=perf_counter()-started)
(ROOT / 'reports/remediation/review_scoring_full_grid.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2), flush=True)
