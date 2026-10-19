"""Execute frozen rolling-origin challengers without replacing the release."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import sys
import threading
from time import perf_counter
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import lightgbm as lgb
import numpy as np
import pandas as pd
import psutil
from src.baselines import baseline_predict
from src.data import load_panel
from src.features import snapshot
from src.metrics import compute_metrics, weighted_score, smape_include_zero_zero
from src.predict import predict_panel
from src.remediation_models import fit_two_part, predict_two_part
from src.train import train_model
from scripts.qa_analysis import bias_diagnostics


def run(args):
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    predictions = out/'predictions'; predictions.mkdir(exist_ok=True)
    panel = load_panel(ROOT/'cache')
    protocol = json.loads(Path(args.protocol).read_text(encoding='utf-8'))
    (out/'executed_protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
    records, calibration, reliability = [], [], []
    stop = threading.Event(); peak=[psutil.Process().memory_info().rss]
    def monitor():
        while not stop.wait(.05):
            peak[0] = max(peak[0], psutil.Process().memory_info().rss)
    thread = threading.Thread(target=monitor,daemon=True); thread.start()
    def record(name, origin, pred, train_seconds=0., inference_seconds=0., model_bytes=0, model_path='', features='', objective=''):
        date = str(panel.dates[origin].date()); truth=panel.y[origin+1:origin+65]
        file=predictions/f'{name}_{date}.npz'
        np.savez_compressed(file,prediction=pred,origin=date)
        snap=snapshot(panel,origin); sparse=snap.freq_180.to_numpy()<.1
        rows=dict(experiment='remediation-v1',model=name,origin=date,start=str(panel.dates[origin+1].date()),end=str(panel.dates[origin+64].date()),
                  role='terminal_diagnostic' if date==protocol['origins'][-1] else 'development',
                  **compute_metrics(truth,pred),**bias_diagnostics(truth,pred),
                  smape_text=smape_include_zero_zero(truth,pred),
                  local_minmax_score=weighted_score(compute_metrics(truth,pred),compute_metrics(truth,baseline_predict(panel,origin,'last'))),
                  train_seconds=train_seconds,inference_seconds=inference_seconds,model_bytes=model_bytes,
                  process_peak_rss_bytes=peak[0],prediction_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                  model_path=model_path,feature_schema=features,objective=objective,
                  sparse_series=int(sparse.sum()),zero_daily_fraction=float((pred==0).mean()))
        rows.update({f'sparse_{k}':v for k,v in compute_metrics(truth[:,sparse],pred[:,sparse]).items()})
        rows.update({f'days36_64_{k}':v for k,v in compute_metrics(truth[35:],pred[35:]).items()})
        records.append(rows)
        pd.DataFrame(records).to_csv(out/'learned_experiment_matrix.csv',index=False)
        print(f'{date} {name}: SMAPE={rows["smape"]:.6f}, WAPE={rows["wape"]:.6f}, Bias={rows["bias"]:.6f}, score={rows["local_minmax_score"]:.6f}',flush=True)
    try:
        for date in protocol['origins']:
            origin=panel.dates.get_loc(date)
            for kind in ['zero','last','mean28','mean90','seasonal56','tsb']:
                start=perf_counter(); pred=baseline_predict(panel,origin,kind)
                record(kind,origin,pred,inference_seconds=perf_counter()-start,objective='fixed_statistical')
            # Reuse exact preserved weights where available, fit only additional earlier origins.
            old={'2026-01-20':'lgb_tweedie_fold1.txt','2026-03-25':'lgb_tweedie_fold2.txt','2026-05-28':'selected_holdout.txt'}
            fit=0.
            if date in old:
                path=ROOT/'reports/oof'/old[date]
                bundle=dict(model=lgb.Booster(model_file=str(path)),config=json.loads((ROOT/'model/config.json').read_text()),catalogs=panel.catalogs)
                bundle['config']['zero_threshold']=0
            else:
                start=perf_counter(); bundle=train_model(panel,origin,'tweedie',protocol['rounds']); fit=perf_counter()-start
                path=predictions/f'tweedie_{date}.txt'; bundle['model'].save_model(str(path))
            start=perf_counter(); pred=predict_panel(panel,origin,bundle); elapsed=perf_counter()-start
            features='|'.join(bundle['config']['features'])
            record('tweedie_raw',origin,pred,fit,elapsed,path.stat().st_size,str(path),features,'tweedie(1.3)')
            record('current_tweedie_z0.25',origin,np.where(pred<.25,0,pred),fit,elapsed,path.stat().st_size,str(path),features,'tweedie(1.3)')
            del bundle; gc.collect()
            start=perf_counter(); bundle=train_model(panel,origin,'regression_l1',protocol['rounds']); fit=perf_counter()-start
            path=predictions/f'l1_{date}.txt'; bundle['model'].save_model(str(path))
            start=perf_counter(); pred=predict_panel(panel,origin,bundle); elapsed=perf_counter()-start
            record('lgb_l1',origin,pred,fit,elapsed,path.stat().st_size,str(path),features,'regression_l1')
            record('lgb_l1_z0.25',origin,np.where(pred<.25,0,pred),fit,elapsed,path.stat().st_size,str(path),features,'regression_l1')
            del bundle; gc.collect()
            start=perf_counter(); fitted=fit_two_part(panel,origin,protocol['rounds']); fit=perf_counter()-start
            pfile=predictions/f'occurrence_{date}.txt'; mfile=predictions/f'magnitude_{date}.txt'
            fitted['occurrence'].save_model(str(pfile)); fitted['magnitude'].save_model(str(mfile))
            start=perf_counter(); pred,p,m=predict_two_part(panel,origin,fitted); elapsed=perf_counter()-start
            size=pfile.stat().st_size+mfile.stat().st_size
            record('two_part_gamma',origin,pred,fit,elapsed,size,f'{pfile}|{mfile}',features,'binary * gamma')
            record('two_part_gamma_z0.25',origin,np.where(pred<.25,0,pred),fit,elapsed,size,f'{pfile}|{mfile}',features,'binary * gamma')
            target=(panel.y[origin+1:origin+65]>0).astype(float); safe=np.clip(p,1e-15,1-1e-15)
            calibration.append(dict(origin=date,positive_rate=float(target.mean()),predicted_rate=float(p.mean()),
                                    brier_score=float(np.mean((target-p)**2)),constant_history_brier=float(np.mean((target-snapshot(panel,origin).freq_180.to_numpy())**2)),
                                    log_loss=float(-np.mean(target*np.log(safe)+(1-target)*np.log1p(-safe))),
                                    positive_train_rows=fitted['positive_training_rows'],train_rows=fitted['training_rows']))
            for i in range(10):
                mask=(p>=i/10)&(p<(i+1)/10) if i<9 else p>=.9
                if mask.any():
                    reliability.append(dict(origin=date,bin_left=i/10,bin_right=(i+1)/10,count=int(mask.sum()),mean_probability=float(p[mask].mean()),actual_frequency=float(target[mask].mean())))
            pd.DataFrame(calibration).to_csv(out/'probability_calibration.csv',index=False)
            pd.DataFrame(reliability).to_csv(out/'probability_reliability.csv',index=False)
            del fitted,p,m,pred; gc.collect()
    finally:
        stop.set();thread.join()
    print('Завершено. Обработка релизной модели не выполнялась.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--protocol',default=str(ROOT/'reports/remediation/experiment_protocol.json'))
    parser.add_argument('--output',default=str(ROOT/'reports/remediation'))
    run(parser.parse_args())
