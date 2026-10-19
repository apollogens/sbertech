"""Audit existing forecasts only: no model fitting or serving mutation."""
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts import official_score as official
from src.data import load_panel
from src.features import snapshot
from src.metrics import compute_metrics, smape_include_zero_zero

OUT=Path(__file__).resolve().parent
KEYS=list(official.METRIC_WEIGHTS)
FOCUS=['incumbent','weekly_allocation_z0.25','weekly_direct_shape_z0.25','article_topdown_z0.25']
ORIGINS=['2025-09-14','2025-11-17','2026-01-20','2026-03-25','2026-05-28']
ALIASES={'current_tweedie_z0.25':'incumbent','lgb_tweedie_z0.25':'incumbent','lgb_tweedie':'tweedie_raw'}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def scalar_metrics(truth,pred):
    truth=truth.astype(float);pred=pred.astype(float)
    b=[official.bias_abs_series(truth[:,i],pred[:,i]) for i in range(truth.shape[1])]
    return dict(smape=float(np.mean([official.smape_series(truth[:,i],pred[:,i]) for i in range(truth.shape[1])])),
                wape=official.wape(truth,pred),rmse=official.rmse(truth,pred),
                bias=float(np.mean([v for v in b if v is not None])) if any(v is not None for v in b) else 0.,rmsle=official.rmsle(truth,pred))

def series_components(truth,pred,written=False):
    truth=truth.astype(float);pred=pred.astype(float)
    absolute=np.abs(truth-pred);den=(truth+pred)/2;valid=den>0
    ratios=np.divide(absolute,den,out=np.zeros_like(den),where=valid)
    smape=ratios.mean(axis=0)*100 if written else np.divide(ratios.sum(axis=0),valid.sum(axis=0),out=np.zeros(truth.shape[1]),where=valid.sum(axis=0)>0)*100
    totals=truth.sum(axis=0);forecast=pred.sum(axis=0)
    return dict(smape=smape,bias=np.divide(np.abs(forecast-totals),totals,out=np.full_like(totals,np.nan),where=totals>0)*100,
                absolute_error=absolute.sum(axis=0),squared_error=((truth-pred)**2).sum(axis=0),
                squared_log_error=((np.log1p(truth)-np.log1p(pred))**2).sum(axis=0),actual_total=totals,forecast_total=forecast)

def get_inventory():
    inventory=[];frames={};aliases=[]
    for folder in [ROOT/'reports/remediation/predictions',ROOT/'research/predictions',ROOT/'reports/oof']:
        for path in sorted(folder.glob('*.npz')):
            with np.load(path) as z:
                date=str(z['origin']);pred=z['prediction'].astype(float)
            if date not in ORIGINS: raise ValueError(f'Unregistered origin: {path} {date}')
            name=path.stem.rsplit('_fold',1)[0] if folder.name=='oof' else path.stem.removesuffix('_'+date)
            name=ALIASES.get(name,name)
            assert pred.shape==(64,8789) and np.isfinite(pred).all() and (pred>=0).all()
            key=(date,name)
            if key in frames and not np.array_equal(frames[key][1],pred):
                name='legacy_'+name;key=(date,name)
            if key in frames:
                aliases.append(dict(origin=date,model=name,duplicate_path=str(path.relative_to(ROOT)),canonical_path=str(frames[key][0].relative_to(ROOT))))
            else:frames[key]=(path,pred)
            inventory.append(dict(origin=date,model=name,path=str(path.relative_to(ROOT)),sha256=sha(path),array_sha256=hashlib.sha256(pred.tobytes()).hexdigest(),rows=pred.size))
    pd.DataFrame(inventory).to_csv(OUT/'prediction_inventory.csv',index=False)
    pd.DataFrame(aliases).to_csv(OUT/'prediction_aliases.csv',index=False)
    return frames

def rank_norm(metrics,tie):
    if tie=='official_argsort':return official.normalize_rank(metrics)
    names=list(metrics);normalized={n:{} for n in names}
    for key in KEYS:
        v=np.array([metrics[n][key] for n in names]);n=len(names)
        if tie=='stable_ordinal':
            ranks=np.empty(n);ranks[np.argsort(v,kind='stable')]=np.arange(n)
        else:
            if tie=='rounded6_average':v=np.round(v,6)
            ranks=pd.Series(v).rank(method='average' if tie=='rounded6_average' else tie).to_numpy()-1
        for i,name in enumerate(names):normalized[name][key]=float(ranks[i]/(n-1)) if n>1 else 0.
    return normalized

def run():
    OUT.mkdir(exist_ok=True);start=perf_counter();panel=load_panel(ROOT/'cache');frames=get_inventory()
    rows=[];horizons=[];segments=[];series_rows=[];drivers=[]
    for date in ORIGINS:
        origin=panel.dates.get_loc(date);truth=panel.y[origin+1:origin+65].astype(float);snap=snapshot(panel,origin)
        masks={'all':np.ones(8789,dtype=bool),'sparse_freq_lt_0.1':snap.freq_180.to_numpy()<.1,
               'regular_freq_ge_0.1':snap.freq_180.to_numpy()>=.1,
               'historical_zero180':snap.mean_180.to_numpy()==0,'future_positive':truth.sum(axis=0)>0,'future_zero':truth.sum(axis=0)==0}
        for nw,w in enumerate(panel.catalogs['warehouses']):masks['warehouse:'+w]=np.repeat(np.arange(11)==nw,799)
        incumbent=frames[(date,'incumbent')][1];basecomp=series_components(truth,incumbent)
        for (d,name),(path,pred) in frames.items():
            if d!=date:continue
            metrics=scalar_metrics(truth,pred);v=compute_metrics(truth,pred)
            assert max(abs(metrics[k]-v[k]) for k in KEYS)<1e-10
            total=truth.sum(axis=0);ptotal=pred.sum(axis=0);eligible=total>0
            rows.append(dict(origin=date,role='terminal_diagnostic' if date==ORIGINS[-1] else 'development',model=name,
                             **metrics,smape_written=smape_include_zero_zero(truth,pred),
                             signed_series_bias=float(np.mean((ptotal[eligible]-total[eligible])/total[eligible])*100),
                             signed_volume_bias=float((ptotal.sum()-total.sum())/total.sum()*100),
                             zero_total_eligible=int(((ptotal==0)&eligible).sum()),eligible=int(eligible.sum()),
                             prediction_path=str(path.relative_to(ROOT)),prediction_sha256=sha(path)))
            for label,sl in [('1_14',slice(0,14)),('15_35',slice(14,35)),('36_64',slice(35,64)),('57_64',slice(56,64))]:
                horizons.append(dict(origin=date,model=name,horizon=label,**compute_metrics(truth[sl],pred[sl]),smape_written=smape_include_zero_zero(truth[sl],pred[sl])))
            for label,mask in masks.items():
                if not mask.any():continue
                segments.append(dict(origin=date,model=name,segment=label,series=int(mask.sum()),eligible=int((total[mask]>0).sum()),
                                     **compute_metrics(truth[:,mask],pred[:,mask]),smape_written=smape_include_zero_zero(truth[:,mask],pred[:,mask]),
                                     zero_total_eligible=int(((ptotal[mask]==0)&(total[mask]>0)).sum())))
            if name in FOCUS[1:]:
                comp=series_components(truth,pred)
                data=pd.DataFrame(dict(origin=date,model=name,warehouse=np.repeat(panel.catalogs['warehouses'],799),article=np.tile(panel.catalogs['articles'],11),
                                       sparse=masks['sparse_freq_lt_0.1'],actual_total=total,incumbent_total=incumbent.sum(axis=0),candidate_total=ptotal,
                                       incumbent_zero=incumbent.sum(axis=0)==0,candidate_zero=ptotal==0))
                for key in ['smape','bias','absolute_error','squared_error','squared_log_error']:
                    data['delta_'+key]=comp[key]-basecomp[key]
                    values=data['delta_'+key];n=int(values.notna().sum())
                    drivers.append(dict(origin=date,model=name,metric_component=key,eligible_series=n,improved_series=int((values<0).sum()),
                                        worsened_series=int((values>0).sum()),unchanged_series=int((values==0).sum()),
                                        sum_delta=float(values.sum()),top20_improvement=float(values.nsmallest(20).sum()),top20_deterioration=float(values.nlargest(20).sum())))
                series_rows.append(data)
        print(date,'metrics complete',flush=True)
    matrix=pd.DataFrame(rows).sort_values(['origin','model']);matrix.to_csv(OUT/'per_fold_candidate_metrics.csv',index=False)
    pd.DataFrame(horizons).to_csv(OUT/'horizon_candidate_metrics.csv',index=False)
    pd.DataFrame(segments).to_csv(OUT/'segment_candidate_metrics.csv',index=False)
    pd.concat(series_rows,ignore_index=True).to_csv(OUT/'focus_series_differences.csv.gz',index=False,compression='gzip')
    pd.DataFrame(drivers).to_csv(OUT/'metric_drivers.csv',index=False)
    base=matrix[matrix.model=='incumbent'].set_index('origin');paired=matrix.copy()
    for key in KEYS+['smape_written','signed_series_bias','signed_volume_bias','zero_total_eligible']:
        paired['delta_'+key]=[r[key]-base.loc[r.origin,key] for _,r in matrix.iterrows()]
    paired.to_csv(OUT/'paired_incumbent_differences.csv',index=False)
    old=list(pd.read_csv(ROOT/'reports/remediation/experiment_matrix.csv').model.unique());old=[ALIASES.get(n,n) for n in old]
    new=[n for n in sorted(matrix.model.unique()) if n not in old and not n.startswith('lgb_') and not n.startswith('legacy_')]
    union=sorted(set(old+new));assert len(union)==23
    pools={'legacy17':old,'architecture7':['incumbent']+new,'focus4':FOCUS,'union23':union,
           'learned_only':[n for n in union if n not in ['zero','last','mean28','mean90','seasonal56','tsb','sba_official','tsb_official','adida_official']]}
    for removed in union:
        if removed!='incumbent':pools['union23_without_'+removed]=[n for n in union if n!=removed]
    for name in union:
        if name!='incumbent':pools['pair:'+name]=['incumbent',name]
    pools['all_available']=sorted(matrix.model.unique())
    rank_rows=[];norm_rows=[];pareto=[];domination=[];pool_registry={}
    for date in ORIGINS:
        subset=matrix[matrix.origin==date].set_index('model');role='terminal_diagnostic' if date==ORIGINS[-1] else 'development'
        for pool,names in pools.items():
            available=[n for n in names if n in subset.index]
            pool_registry[date+':'+pool]=available
            for definition in ['executable','written']:
                metrics={name:{k:float(subset.loc[name,'smape_written' if k=='smape' and definition=='written' else k]) for k in KEYS} for name in available}
                for order in ['forward','reverse']:
                    m=metrics if order=='forward' else dict(reversed(list(metrics.items())))
                    for tie in ['official_argsort','stable_ordinal','average','min','max','dense','rounded6_average']:
                        normalized=rank_norm(m,tie)
                        scores={n:sum(official.METRIC_WEIGHTS[k]*normalized[n][k] for k in KEYS) for n in normalized}
                        for n in available:
                            rank_rows.append(dict(origin=date,role=role,pool=pool,pool_size=len(available),order=order,smape_definition=definition,tie_policy=tie,model=n,
                                                  score=scores[n],incumbent_score=scores['incumbent'],delta_vs_incumbent=scores[n]-scores['incumbent'],
                                                  **{k+'_norm':normalized[n][k] for k in KEYS}))
                if pool in ['union23','all_available']:
                    for name in available:
                        values=np.array(list(metrics[name].values()));dom=[];dom_tol=[]
                        for other in available:
                            if other==name:continue
                            ov=np.array(list(metrics[other].values()))
                            if (ov<=values).all() and (ov<values).any():dom.append(other)
                            if (ov<=values+1e-10).all() and (ov<values-1e-10).any():dom_tol.append(other)
                        pareto.append(dict(origin=date,role=role,pool=pool,smape_definition=definition,model=name,is_frontier=len(dom)==0,
                                           is_frontier_tol1e10=len(dom_tol)==0,dominated_by='|'.join(dom),dominated_by_tol1e10='|'.join(dom_tol)))
                        for other in dom:domination.append(dict(origin=date,pool=pool,smape_definition=definition,dominator=other,dominated=name))
        for definition in ['executable','written']:
            metrics={name:{k:float(subset.loc[name,'smape_written' if k=='smape' and definition=='written' else k]) for k in KEYS} for name in subset.index}
            for baseline in ['last','mean28']:
                normalized=official.normalize_minmax(metrics,metrics[baseline])
                scores={n:sum(official.METRIC_WEIGHTS[k]*normalized[n][k] for k in KEYS) for n in normalized}
                for name in normalized:
                    norm_rows.append(dict(origin=date,role=role,smape_definition=definition,baseline=baseline,model=name,score=scores[name],
                                          delta_vs_incumbent=scores[name]-scores['incumbent'],
                                          clipped_metrics='|'.join(k for k in KEYS if metrics[name][k]>metrics[baseline][k]),
                                          **{k+'_norm':normalized[name][k] for k in KEYS},
                                          **{k+'_contribution':official.METRIC_WEIGHTS[k]*(normalized[name][k]-normalized['incumbent'][k]) for k in KEYS}))
    pd.DataFrame(rank_rows).to_csv(OUT/'weighted_rank_sensitivity.csv',index=False)
    pd.DataFrame(norm_rows).to_csv(OUT/'minmax_sensitivity.csv',index=False)
    pd.DataFrame(pareto).to_csv(OUT/'pareto_frontier.csv',index=False)
    pd.DataFrame(domination).to_csv(OUT/'pareto_dominance_pairs.csv',index=False)
    (OUT/'candidate_pools.json').write_text(json.dumps(pool_registry,ensure_ascii=False,indent=2),encoding='utf-8')
    summary=dict(no_training=True,origins=ORIGINS,saved_files=len(pd.read_csv(OUT/'prediction_inventory.csv')),canonical_forecasts=len(frames),candidate_models=len(matrix.model.unique()),
                 rank_diagnostic_rows=len(rank_rows),elapsed_seconds=perf_counter()-start,official_scorer_sha256=sha(ROOT/'scripts/official_score.py'),panel_sha256=sha(ROOT/'cache/panel.npz'))
    (OUT/'analysis_run.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(summary,flush=True)

if __name__=='__main__':run()
