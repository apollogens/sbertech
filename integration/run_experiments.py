"""Bounded catalog-corrected fits, convex mixtures, and rounding ablations."""
from pathlib import Path
import sys
import hashlib
import json
import gc
import threading
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
import psutil
from src.data import load_panel
from src.metrics import compute_metrics,smape_include_zero_zero
from scripts import official_score
from integration.corrected_models import fit_components,predict_components,save_bundle
from integration.ensemble_engine import align_components,convex_combine,key_hash

OUT=ROOT/'integration'
ORIGINS=['2025-09-14','2025-11-17','2026-01-20','2026-03-25','2026-05-28']
WEIGHTS={
 'D':dict(daily=1.,weekly=0.,shape=0.,article=0.),
 'W':dict(daily=0.,weekly=1.,shape=0.,article=0.),
 'S':dict(daily=0.,weekly=0.,shape=1.,article=0.),
 'A':dict(daily=0.,weekly=0.,shape=0.,article=1.),
 'equal4':dict(daily=.25,weekly=.25,shape=.25,article=.25),
 'DA75':dict(daily=.75,weekly=0.,shape=0.,article=.25),
 'DA50':dict(daily=.5,weekly=0.,shape=0.,article=.5),
 'DA25':dict(daily=.25,weekly=0.,shape=0.,article=.75),
 'DS50':dict(daily=.5,weekly=0.,shape=.5,article=0.),
 'source_DA70':dict(daily=.7,weekly=0.,shape=0.,article=.3)}
POLICIES={'P0':'continuous','P1':'threshold025','P2':'nearest_even','P3':'threshold_then_nearest_even'}
UNIVERSE=[n+':P1' for n in WEIGHTS]+[n+':'+p for n in ['D','W','S','A'] for p in ['P0','P2']]

def run():
    panel=load_panel(ROOT/'cache');records=[];horizons=[];volumes=[]
    (OUT/'predictions').mkdir(exist_ok=True)
    protocol=dict(origins=ORIGINS,weights=WEIGHTS,policies=POLICIES,rank_universe=UNIVERSE,
                  protocol_sha256=hashlib.sha256((OUT/'experiment_protocol.md').read_bytes()).hexdigest())
    (OUT/'executed_protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
    for fold,date in enumerate(ORIGINS):
        origin=panel.dates.get_loc(date);truth=panel.y[origin+1:origin+65].astype(float)
        peak=[psutil.Process().memory_info().rss];stop=threading.Event()
        def monitor():
            process=psutil.Process()
            while not stop.wait(.05):peak[0]=max(peak[0],process.memory_info().rss)
        thread=threading.Thread(target=monitor,daemon=True);thread.start()
        try:
            t=perf_counter();models,metadata=fit_components(panel,origin);fit_seconds=perf_counter()-t
            bundle_path=OUT/'models'/date;save_bundle(models,metadata,panel.catalogs,bundle_path)
            t=perf_counter();frames=predict_components(panel,origin,models);component_seconds=perf_counter()-t
            expected=frames['daily'].iloc[:,:3];kh=key_hash(expected)
            t=perf_counter();aligned=align_components(frames,expected);alignment_seconds=perf_counter()-t
            # Raw components are saved with independently verified key identities.
            for name,frame in frames.items():
                np.savez_compressed(OUT/'predictions'/f'component_{name}_{date}.npz',prediction=frame.quantity.to_numpy().reshape(64,-1),origin=date,key_sha256=kh)
            cases=[(name+':'+p,name,'continuous',policy) for name in WEIGHTS for p,policy in POLICIES.items()]
            cases += [('equal4:components_P1','equal4','threshold025','continuous'),('DA50:components_P1','DA50','threshold025','continuous'),('equal4:components_P2','equal4','nearest_even','continuous')]
            for case,name,component_policy,output_policy in cases:
                t=perf_counter();values=convex_combine(aligned,WEIGHTS[name],component_policy,output_policy);overhead=perf_counter()-t
                raw=convex_combine(aligned,WEIGHTS[name]);pred=values.reshape(64,-1);before=raw.reshape(64,-1)
                file=OUT/'predictions'/f'{case.replace(":","_")}_{date}.npz'
                np.savez_compressed(file,prediction=pred,origin=date,key_sha256=kh)
                actual=truth.sum(axis=0);ptotal=pred.sum(axis=0);eligible=actual>0
                baseline=compute_metrics(truth,np.load(ROOT/f'reports/remediation/predictions/last_{date}.npz')['prediction'])
                metrics=compute_metrics(truth,pred)
                norm=official_score.normalize_minmax({'candidate':metrics},baseline)['candidate']
                records.append(dict(candidate=case,mechanism=name,origin=date,role='terminal_diagnostic' if fold==4 else 'development',
                    **metrics,smape_written=smape_include_zero_zero(truth,pred),
                    signed_series_bias=float(np.mean((ptotal[eligible]-actual[eligible])/actual[eligible])*100),
                    signed_volume_bias=float((ptotal.sum()-actual.sum())/actual.sum()*100),
                    zero_total_eligible=int(((ptotal==0)&eligible).sum()),zero_total_all=int((ptotal==0).sum()),
                    positive_changed_to_zero=int(((before>0)&(pred==0)).sum()),total_volume=float(pred.sum()),
                    volume_change=float(pred.sum()-before.sum()),max_daily_volume_change=float(np.max(np.abs(pred.sum(axis=1)-before.sum(axis=1)))),
                    max_series_volume_change=float(np.max(np.abs(ptotal-before.sum(axis=0)))),
                    minmax_last=sum(official_score.METRIC_WEIGHTS[k]*norm[k] for k in norm),
                    train_seconds=fit_seconds,component_inference_seconds=component_seconds,key_alignment_seconds=alignment_seconds,
                    postprocess_seconds=overhead,process_peak_rss_bytes=peak[0],weights=json.dumps(WEIGHTS[name],sort_keys=True),
                    component_policy=component_policy,output_policy=output_policy,key_sha256=kh,
                    prediction_path=str(file.relative_to(ROOT)),prediction_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                    array_sha256=hashlib.sha256(pred.tobytes()).hexdigest(),model_bundle=str(bundle_path.relative_to(ROOT))))
                for label,sl in [('1_14',slice(0,14)),('15_35',slice(14,35)),('36_64',slice(35,64)),('57_64',slice(56,64))]:
                    horizons.append(dict(candidate=case,origin=date,horizon=label,**compute_metrics(truth[sl],pred[sl])))
                for level,b,a in [('day',before.sum(axis=1),pred.sum(axis=1)),('series',before.sum(axis=0),ptotal)]:
                    volumes.append(dict(candidate=case,origin=date,level=level,changed=int((b!=a).sum()),l1_volume_change=float(np.abs(a-b).sum()),max_abs_change=float(np.max(np.abs(a-b)))))
            pd.DataFrame(records).to_csv(OUT/'per_origin_metrics.csv',index=False)
            pd.DataFrame(records).to_csv(OUT/'ensemble_experiments.csv',index=False)
            pd.DataFrame(records).to_csv(OUT/'rounding_ablation.csv',index=False)
            pd.DataFrame(horizons).to_csv(OUT/'horizon_metrics.csv',index=False)
            pd.DataFrame(volumes).to_csv(OUT/'volume_distortion.csv',index=False)
            print(date,'43 cases complete',metadata['train_seconds'],'full shared-component inference',component_seconds,'RSS',peak[0],flush=True)
            if fold==1:
                early=pd.DataFrame(records);choices=early[early.candidate.isin(['DA75:P1','DA50:P1','DA25:P1'])].groupby('candidate').minmax_last.mean()
                selected=sorted(choices.index,key=lambda n:(choices[n],0 if n=='DA50:P1' else 1,WEIGHTS[n.split(':')[0]]['article']))[0]
                (OUT/'learned_weights.json').write_text(json.dumps(dict(selected=selected,fit_origins=ORIGINS[:2],evaluation_origins=ORIGINS[2:4],
                     objective='mean minmax(last) executable SMAPE P1',early_scores=choices.to_dict(),weights=WEIGHTS[selected.split(':')[0]],
                     caveat='Chronological selection on reused windows; not new untouched test'),indent=2),encoding='utf-8')
        finally:
            stop.set();thread.join()
        del models,frames,aligned;gc.collect()
    print('All fits and fixed cases complete; production not changed',flush=True)

if __name__=='__main__':run()
