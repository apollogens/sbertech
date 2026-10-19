"""Reviewer B: read-only catalog provenance and saved-forecast sensitivity; no fit."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.data import Panel, load_panel
from src.features import snapshot
from scripts import official_score as official

OUT = Path(__file__).resolve().parent
METRICS = ['smape', 'wape', 'rmse', 'bias', 'rmsle']

def sha(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def score(y, p):
    sm = [official.smape_series(a, b) for a, b in zip(y.T, p.T)]
    bias = [official.bias_abs_series(a, b) for a, b in zip(y.T, p.T)]
    bias = [v for v in bias if v is not None]
    return dict(smape=float(np.mean(sm)), bias=float(np.mean(bias)) if bias else 0.,
                wape=official.wape(y, p), rmse=official.rmse(y, p), rmsle=official.rmsle(y, p))

def main():
    OUT.mkdir(exist_ok=True)
    audit = json.loads((ROOT/'reports/input_audit.json').read_text(encoding='utf-8'))
    frames = {}; inputs = []
    first = []
    for source in ['sales', 'stock']:
        path = Path(audit[source]['path'])
        frame = pd.read_csv(path, usecols=['date', 'warehouse_name', 'article'], dtype=str)
        frames[source] = frame
        inputs.append(dict(source=source, path=str(path), rows=len(frame), sha256=sha(path)))
        for col in ['warehouse_name', 'article']:
            dates = frame.groupby(col).date.min()
            first += [dict(source=source, key_type=col, key=k, first_date=v) for k,v in dates.items()]
        pairs = frame.groupby(['warehouse_name', 'article']).date.min()
        first += [dict(source=source, key_type='pair', key=w+'|'+a, first_date=v) for (w,a),v in pairs.items()]
    pd.DataFrame(first).to_csv(OUT/'catalog_first_observed.csv', index=False)
    panel = load_panel(ROOT/'cache')
    pairs = panel.pairs
    catalog = panel.catalogs
    origins = json.loads((ROOT/'research/experiment_protocol.json').read_text(encoding='utf-8'))['origins']
    masks = {}; summaries=[]; feat=[]
    combined = pd.concat(frames.values(), ignore_index=True)
    for date in origins:
        idx=panel.dates.get_loc(date)
        for source, frame in {**frames, 'sales_or_stock': combined}.items():
            hist=frame.loc[frame.date <= date]
            kw=sorted(hist.warehouse_name.unique()); ka=sorted(hist.article.unique())
            idmask=np.asarray(pairs.get_level_values(0).isin(kw)&pairs.get_level_values(1).isin(ka))
            pairmask=np.asarray(pairs.isin(pd.MultiIndex.from_frame(hist[['warehouse_name','article']].drop_duplicates())))
            masks[date,source]=idmask
            summaries.append(dict(origin=date,source=source,known_warehouses=len(kw),known_articles=len(ka),
                known_cartesian_pairs=int(idmask.sum()),observed_pairs=int(pairmask.sum()),
                unknown_id_pairs=int((~idmask).sum()),unobserved_pair_count=int((~pairmask).sum()),
                unknown_id_truth_units=float(panel.y[idx+1:idx+65,~idmask].sum()),
                unobserved_pair_truth_units=float(panel.y[idx+1:idx+65,~pairmask].sum())))
            # Compare identical physical keys after rebuilding a historically observed ID catalog.
            keepw=[i for i,w in enumerate(catalog['warehouses']) if w in kw]
            keepa=[i for i,a in enumerate(catalog['articles']) if a in ka]
            use=np.array([i*len(catalog['articles'])+j for i in keepw for j in keepa])
            reduced=Panel(panel.dates,panel.y[:,use],panel.stock[:,use],
                          dict(warehouses=[catalog['warehouses'][i] for i in keepw],articles=[catalog['articles'][i] for i in keepa]))
            original=snapshot(panel,idx).iloc[use].reset_index(drop=True)
            changed=snapshot(reduced,idx)
            for col in original:
                a=original[col].to_numpy(); b=changed[col].to_numpy()
                different=~np.isclose(a,b,rtol=0,atol=0,equal_nan=True)
                feat.append(dict(origin=date,source=source,feature=col,compared_pairs=len(use),
                    changed_pairs=int(different.sum()),max_abs_change=float(np.nanmax(np.abs(a-b))) if np.isfinite(a-b).any() else 0.))
    pd.DataFrame(summaries).to_csv(OUT/'catalog_origin_summary.csv',index=False)
    pd.DataFrame(feat).to_csv(OUT/'catalog_feature_sensitivity.csv',index=False)
    rows=[]; files=[]
    paths=sorted((ROOT/'research/predictions').glob('*.npz'))+sorted((ROOT/'reports/remediation/predictions').glob('*.npz'))
    for path in paths:
        date=path.stem[-10:]
        if date not in origins:
            continue
        model=path.stem[:-11]
        with np.load(path) as z:
            p=z['prediction'].astype(float)
        idx=panel.dates.get_loc(date); y=panel.y[idx+1:idx+65].astype(float)
        assert p.shape==y.shape
        files.append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path)))
        base=score(y,p)
        rows.append(dict(collection='architecture' if path.is_relative_to(ROOT/'research') else 'remediation',
                         model=model,origin=date,mode='full_catalog',source='full',pairs=p.shape[1],**base))
        for source in ['sales','sales_or_stock']:
            mask=masks[date,source]
            for mode in ['known_ids_only','zero_unknown_ids']:
                if mode=='known_ids_only':
                    values=base if mask.all() else score(y[:,mask],p[:,mask])
                else:
                    altered=p.copy(); altered[:,~mask]=0
                    values=base if mask.all() else score(y,altered)
                rows.append(dict(collection='architecture' if path.is_relative_to(ROOT/'research') else 'remediation',
                         model=model,origin=date,mode=mode,source=source,pairs=int(mask.sum()) if mode=='known_ids_only' else p.shape[1],**values))
    pd.DataFrame(rows).to_csv(OUT/'catalog_metric_sensitivity.csv',index=False)
    # Independent paired diagnostics from freshly recalculated architecture metrics.
    df=pd.DataFrame(rows); full=df[(df.collection=='architecture')&(df['mode']=='full_catalog')]
    incumbent=full[full.model=='incumbent'].set_index('origin')
    paired=[]
    for _,r in full[full.model!='incumbent'].iterrows():
        d={m:float(r[m]-incumbent.loc[r.origin,m]) for m in METRICS}
        paired.append(dict(model=r.model,origin=r.origin,role='terminal' if r.origin==origins[-1] else 'development',**d))
    paired=pd.DataFrame(paired); paired.to_csv(OUT/'reviewer_b_paired_differences.csv',index=False)
    windows=[]
    for i,date in enumerate(origins):
        s=pd.Timestamp(date)+pd.Timedelta(days=1); e=s+pd.Timedelta(days=63)
        for other in origins[i+1:]:
            os=pd.Timestamp(other)+pd.Timedelta(days=1); oe=os+pd.Timedelta(days=63)
            windows.append(dict(origin_a=date,origin_b=other,target_overlap_days=max(0,(min(e,oe)-max(s,os)).days+1)))
    pd.DataFrame(windows).to_csv(OUT/'reviewer_b_window_overlap.csv',index=False)
    result=dict(audit_date='2026-10-19',inputs=inputs,panel_sha256=sha(ROOT/'cache/panel.npz'),
        catalogs_equal_full_sales=catalog==dict(warehouses=sorted(frames['sales'].warehouse_name.unique()),articles=sorted(frames['sales'].article.unique())),
        model_catalog_equals_cache=json.loads((ROOT/'model/catalogs.json').read_text(encoding='utf-8'))==catalog,
        forecast_count=len(files),forecast_fingerprints=files,fits_performed=0,
        max_catalog_metric_difference=max(abs(r[m]-next(a[m] for a in rows if a['collection']==r['collection'] and a['model']==r['model'] and a['origin']==r['origin'] and a['mode']=='full_catalog')) for r in rows for m in METRICS))
    (OUT/'catalog_selection_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ['forecast_fingerprints','inputs']},ensure_ascii=False))

if __name__=='__main__':
    main()
