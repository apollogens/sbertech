"""Fixed-universe scoring and reports derived from corrected forecasts."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.data import load_panel
from src.features import snapshot
from src.metrics import compute_metrics,smape_include_zero_zero
from scripts import official_score as scorer
from integration.run_experiments import UNIVERSE,ORIGINS,WEIGHTS
OUT=ROOT/'integration';KEYS=list(scorer.METRIC_WEIGHTS)

def table(frame):
    def f(x):return f'{x:.6f}' if isinstance(x,(float,np.floating)) else str(x)
    return '\n'.join(['| '+' | '.join(map(str,frame.columns))+' |','|'+'|'.join(['---']*len(frame.columns))+'|']+['| '+' | '.join(f(x) for x in r)+' |' for r in frame.itertuples(index=False,name=None)])

def analyze():
    x=pd.read_csv(OUT/'per_origin_metrics.csv');assert len(x)==215 and not x.duplicated(['candidate','origin']).any()
    # Canonicalization uses the concatenated FOUR development arrays, not a changing per-fold pool.
    hashes={n:tuple(g[g.origin.isin(ORIGINS[:4])].sort_values('origin').array_sha256) for n,g in x.groupby('candidate')}
    def dedup(names):
        seen={};canonical=[];aliases={}
        for name in names:
            identity=hashes[name]
            if identity in seen:aliases[name]=seen[identity]
            else:seen[identity]=name;canonical.append(name)
        return canonical,aliases
    main,main_aliases=dedup(UNIVERSE)
    expanded,expanded_aliases=dedup(sorted(x.candidate.unique(),key=lambda n:('P3' in n,n)))
    base,_=dedup(['D:P1','W:P1','S:P1','A:P1'])
    pools={'main18':main,'expanded':expanded,'components4':base}
    for n in main:
        if n!='D:P1':pools['main_without_'+n]=[a for a in main if a!=n]
    (OUT/'scoring_universe.json').write_text(json.dumps(dict(pools=pools,main_aliases=main_aliases,expanded_aliases=expanded_aliases,
         dedup='Exact float64 array hashes on all four development origins; fixed across all folds'),indent=2),encoding='utf-8')
    scores=[];minmax=[];paired=[];sparse=[];legacy=[]
    panel=load_panel(ROOT/'cache')
    for date in ORIGINS:
        g=x[x.origin==date].set_index('candidate');inc=g.loc['D:P1'];origin=panel.dates.get_loc(date);truth=panel.y[origin+1:origin+65]
        last=np.load(ROOT/f'reports/remediation/predictions/last_{date}.npz')['prediction']
        baseline=compute_metrics(truth,last);baseline_written=dict(baseline,smape=smape_include_zero_zero(truth,last))
        old=np.load(ROOT/f'reports/remediation/predictions/current_tweedie_z0.25_{date}.npz')['prediction']
        legacy.append(dict(origin=date,reference='legacy_incumbent',**compute_metrics(truth,old),smape_written=smape_include_zero_zero(truth,old),comparison='Different catalog/encoding pipeline; not pure model quality change'))
        mask=snapshot(panel,origin).freq_180.to_numpy()<.1
        for name,row in g.iterrows():
            paired.append(dict(origin=date,candidate=name,**{'delta_'+k:row[k]-inc[k] for k in KEYS},
                               delta_signed_bias=row.signed_series_bias-inc.signed_series_bias,delta_zero_total=row.zero_total_eligible-inc.zero_total_eligible))
            prediction=np.load(ROOT/row.prediction_path)['prediction']
            sparse.append(dict(origin=date,candidate=name,series=int(mask.sum()),**compute_metrics(truth[:,mask],prediction[:,mask]),
                               zero_total_eligible=int(((prediction[:,mask].sum(axis=0)==0)&(truth[:,mask].sum(axis=0)>0)).sum())))
        for definition in ['executable','written']:
            allmetrics={name:{k:float(row['smape_written' if k=='smape' and definition=='written' else k]) for k in KEYS} for name,row in g.iterrows()}
            nm=scorer.normalize_minmax(allmetrics,baseline if definition=='executable' else baseline_written)
            ms={n:sum(scorer.METRIC_WEIGHTS[k]*v for k,v in vals.items()) for n,vals in nm.items()}
            for n,v in ms.items():minmax.append(dict(origin=date,candidate=n,smape_definition=definition,score=v,delta=v-ms['D:P1']))
            for pool,members in pools.items():
                for order in ['forward','reverse']:
                    names=members if order=='forward' else list(reversed(members))
                    metrics={n:allmetrics[n] for n in names}
                    for tie in ['official_argsort','average']:
                        if tie=='official_argsort':norm=scorer.normalize_rank(metrics)
                        else:
                            frame=pd.DataFrame(metrics).T
                            norm=((frame.rank(method='average')-1)/(len(frame)-1)).to_dict(orient='index')
                        scalar={n:sum(scorer.METRIC_WEIGHTS[k]*norm[n][k] for k in KEYS) for n in names}
                        for n,v in scalar.items():scores.append(dict(origin=date,candidate=n,pool=pool,tie=tie,order=order,smape_definition=definition,score=v,delta=v-scalar['D:P1']))
    pd.DataFrame(scores).to_csv(OUT/'rank_sensitivity.csv',index=False)
    pd.DataFrame(minmax).to_csv(OUT/'minmax_sensitivity.csv',index=False)
    pd.DataFrame(paired).to_csv(OUT/'paired_corrected_reference.csv',index=False)
    pd.DataFrame(sparse).to_csv(OUT/'sparse_metrics.csv',index=False)
    pd.DataFrame(legacy).to_csv(OUT/'legacy_reference.csv',index=False)
    dev=x[x.origin.isin(ORIGINS[:4])];means=dev.groupby('candidate')[KEYS+['signed_series_bias','zero_total_eligible','total_volume']].mean()
    means.to_csv(OUT/'development_summary.csv')
    rank=pd.DataFrame(scores);minmax=pd.DataFrame(minmax)
    r=rank[(rank.pool=='main18')&(rank.tie=='official_argsort')&(rank.order=='forward')&(rank.smape_definition=='executable')]
    mm=minmax[minmax.smape_definition=='executable'];decisions=[]
    for name in main:
        record=dict(candidate=name)
        for period,dates in [('early',ORIGINS[:2]),('later',ORIGINS[2:4]),('development',ORIGINS[:4])]:
            for key,data in [('rank',r),('minmax',mm)]:
                subset=data[(data.candidate==name)&data.origin.isin(dates)]
                record[period+'_'+key+'_delta']=float(subset.delta.mean())
                record[period+'_'+key+'_wins']=int((subset.delta < -1e-12).sum())
        record['quality_screen']=bool(all(record[period+'_'+key+'_delta']<0 for period in ['early','later'] for key in ['rank','minmax']) and record['development_rank_wins']>=3 and record['development_minmax_wins']>=3)
        decisions.append(record)
    gates=pd.DataFrame(decisions);gates.to_csv(OUT/'quality_gates.csv',index=False)
    learned=json.loads((OUT/'learned_weights.json').read_text(encoding='utf-8'));n=learned['selected']
    learned['later_metrics']=x[(x.origin.isin(ORIGINS[2:4]))&(x.candidate==n)][['origin','candidate']+KEYS+['minmax_last']].to_dict(orient='records')
    (OUT/'learned_weight_evaluation.json').write_text(json.dumps(learned,indent=2),encoding='utf-8')
    # Pareto status is descriptive, never the sole gate.
    pf=[]
    for date in ORIGINS:
        g=x[(x.origin==date)&x.candidate.isin(main)].set_index('candidate')[KEYS]
        for n,row in g.iterrows():
            dom=[other for other,v in g.iterrows() if other!=n and (v<=row+1e-10).all() and (v<row-1e-10).any()]
            pf.append(dict(origin=date,candidate=n,is_frontier=not dom,dominated_by='|'.join(dom)))
    pd.DataFrame(pf).to_csv(OUT/'pareto_frontier.csv',index=False)
    selected=[n+':P1' for n in WEIGHTS]
    scoremean=r[r.origin.isin(ORIGINS[:4])].groupby('candidate')[['score','delta']].mean().add_prefix('rank_')
    scoremean=scoremean.join(mm[mm.origin.isin(ORIGINS[:4])].groupby('candidate')[['score','delta']].mean().add_prefix('minmax_'),how='outer')
    scoremean.to_csv(OUT/'development_scores.csv')
    text='''# Чувствительность scoring

Используется исходный executable evaluator: SMAPE исключает (0,0), веса .50/.20/.15/.10/.05. Written SMAPE сохранён отдельно. Нормализация реального leaderboard не подтверждена; rank и minmax(last) ниже — локальная диагностика, не обещание конкурсного места.

Каждый origin оценивается отдельно, средние считаются после нормализации. Основной universe заявлен до fits:18 вариантов, точные aliases удаляются один раз по четырём development forecast arrays. Порядок и aliases находятся в `scoring_universe.json`. P3 эквивалентен P2 и не получает отдельный ранг. Также проверены expanded universe всех уникальных43вариантов, components4 и leave-one-out основного пула, оба порядка и ties original/average. Average — sensitivity, не установленное правило организатора.

Средние development scores:

'''+table(scoremean.loc[[n for n in selected if n in scoremean.index]].reset_index())+'''

Все raw metrics, signed Bias, объём/нули, пары с corrected reference, sparse и horizons сохранены отдельно. Будущие labels не применяются для распределения или инициализации новых товаров. Прежний incumbent приведён отдельно: его pipeline содержит исторический полный каталог, поэтому сравнение с ним смешивает исправление кодирования/каталога и метод. Чистое ensemble/rounding сравнение проводится с corrected D на одинаковых ключах.

Первые два origins используются только для выбора одного из трёх заранее заданных D/A весов; последующие два — chronological diagnostic на ранее открытых данных. Это не новый untouched test. Выбранный вес и поздние результаты — `learned_weight_evaluation.json`. Terminal не выбирает веса и не влияет на gate.
'''
    (OUT/'scoring_sensitivity.md').write_text(text,encoding='utf-8')
    print('Quality gates\n'+gates.to_string(index=False),flush=True)
    print('Selected weight',learned['selected'],flush=True)

if __name__=='__main__':analyze()
