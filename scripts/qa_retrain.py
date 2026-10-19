"""Isolated reproduction of frozen fits; no tuning and no production overwrites."""
from pathlib import Path
import gc
import hashlib
import json
import sys
import threading
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import psutil
from src.data import load_panel
from src.train import train_model
from src.predict import predict_panel
from src.metrics import compute_metrics


def run():
    out=Path('reports/qa/retrained');out.mkdir(exist_ok=True)
    panel=load_panel();last=len(panel.dates)-1
    selected=json.loads(Path('reports/selection_frozen.json').read_text())
    assert selected['winner']=='lgb_tweedie_z0.25' and selected['rounds']==220
    plan=[('lgb_l2_fold1',last-192,'regression',0.,'reports/oof/lgb_l2_fold1.txt'),
          ('lgb_l2_fold2',last-128,'regression',0.,'reports/oof/lgb_l2_fold2.txt'),
          ('lgb_tweedie_fold1',last-192,'tweedie',0.,'reports/oof/lgb_tweedie_fold1.txt'),
          ('lgb_tweedie_fold2',last-128,'tweedie',0.,'reports/oof/lgb_tweedie_fold2.txt'),
          ('lgb_tweedie_z0.25_fold3',last-64,'tweedie',.25,'reports/oof/selected_holdout.txt'),
          ('final',last,'tweedie',.25,'model/lightgbm.txt')]
    records=[];peak=[0];stop=threading.Event()
    def monitor():
        process=psutil.Process()
        while not stop.wait(.05):peak[0]=max(peak[0],process.memory_info().rss)
    thread=threading.Thread(target=monitor,daemon=True);thread.start();started=perf_counter()
    try:
        for name,cutoff,objective,threshold,reference in plan:
            start=perf_counter();bundle=train_model(panel,cutoff,objective,selected['rounds']);fit_seconds=perf_counter()-start
            bundle['config']['zero_threshold']=threshold
            target=out/f'{name}.txt';bundle['model'].save_model(str(target))
            new_hash=hashlib.sha256(target.read_bytes()).hexdigest()
            original_hash=hashlib.sha256(Path(reference).read_bytes()).hexdigest()
            assert new_hash==original_hash,(name,'model bytes differ')
            prediction=predict_panel(panel,cutoff,bundle)
            if name=='final':
                original=pd.read_csv('submission.csv').quantity.to_numpy().reshape(64,-1)
                tolerance=1e-7
                assert bundle['config']==json.loads(Path('model/config.json').read_text())
            else:
                original=np.load(f'reports/oof/{name}.npz')['prediction']
                tolerance=0.
            delta=float(np.abs(prediction-original).max());assert delta<=tolerance
            record={'name':name,'cutoff':str(panel.dates[cutoff].date()),'fit_seconds':fit_seconds,
                    'training_rows':bundle['config']['training_rows'],'trees':bundle['model'].num_trees(),
                    'model_sha256':new_hash,'original_sha256':original_hash,'model_bytes_identical':True,
                    'prediction_max_abs_difference':delta,'prediction_tolerance':tolerance}
            if name!='final':record['metrics']=compute_metrics(panel.y[cutoff+1:cutoff+65],prediction)
            records.append(record);print(json.dumps(record),flush=True)
            del bundle,prediction,original;gc.collect()
    finally:stop.set();thread.join()
    result={'fits':records,'seconds':perf_counter()-started,'peak_process_rss_bytes':peak[0],
            'passed':len(records),'failed':0,'skipped':0,'source':'verified cache from raw sales and stock',
            'scope':'same installed builds, 4 threads, fixed seed/rounds/objectives/threshold; no new selection'}
    Path('reports/qa/retraining_reproduction.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='fits'}),flush=True)


if __name__=='__main__':run()
