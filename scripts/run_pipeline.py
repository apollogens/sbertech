"""Reproduce audit, frozen candidate comparison, holdout and final submission."""
import argparse
import gc
import json
from pathlib import Path
import sys
from time import perf_counter
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import psutil
from src.data import load_panel, prepare_cache
from src.baselines import baseline_predict
from src.metrics import compute_metrics, evaluate
from src.features import snapshot
from src.predict import predict_panel
from src.submission import forecast_frame, write_submission
from src.train import train_model
from src.artifacts import file_hash, fingerprint, write_manifest, write_training_manifest


def run(args):
    started = perf_counter()
    peak = [0]
    stop = threading.Event()
    def monitor():
        process = psutil.Process()
        while not stop.wait(.1):
            peak[0] = max(peak[0], process.memory_info().rss)
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    Path("reports/oof").mkdir(parents=True, exist_ok=True)
    Path("model").mkdir(exist_ok=True)
    panel = prepare_cache(args.data_dir) if args.refresh or not Path("cache/panel.npz").exists() else load_panel()
    print("Panel", panel.y.shape, flush=True)
    last = len(panel.dates)-1
    baseline_names = ["zero", "last", "mean28", "mean90", "seasonal56", "tsb"]
    # First valid reproducible artifact is available before expensive fitting.
    provisional = forecast_frame(baseline_predict(panel,last,"mean28"), panel.dates[-1], panel.catalogs)
    write_submission(provisional, "submission_baseline.csv", panel.dates[-1], panel.catalogs)
    print("Baseline submission validated", len(provisional), flush=True)
    records, segments, timing = [], [], []
    forecasts = {}
    origins = [last-192, last-128, last-64]
    def record(name, fold, origin, pred, truth, reference, elapsed):
        result = evaluate(truth, pred, reference)
        records.append({"model":name,"fold":fold,"origin":str(panel.dates[origin].date()),
                        "role":"holdout" if fold==3 else "selection",
                        **result["raw"],"local_minmax_score":result["score"],
                        "smape_text":result["smape_include_zero_zero"],"inference_seconds":elapsed})
        np.savez_compressed(f"reports/oof/{name}_fold{fold}.npz", prediction=pred,
                            origin=str(panel.dates[origin].date()))
        snap = snapshot(panel, origin)
        masks = {"sparse":snap.freq_180.to_numpy()<.1,
                 "high_demand":snap.mean_180.to_numpy()>=np.quantile(snap.mean_180,.9),
                 "stockout":(snap.stock_zero_rate.to_numpy()>.5)&(snap.stock_coverage.to_numpy()>.5)}
        for segment, sl in [("days1_14",slice(0,14)),("days15_35",slice(14,35)),
                             ("days36_64",slice(35,64)),("days57_64",slice(56,64))]:
            segments.append({"model":name,"fold":fold,"segment":segment,**compute_metrics(truth[sl],pred[sl])})
        for segment, mask in masks.items():
            if mask.any():
                segments.append({"model":name,"fold":fold,"segment":segment,**compute_metrics(truth[:,mask],pred[:,mask])})
        pd.DataFrame(records).to_csv("reports/experiment_results.csv",index=False)
        pd.DataFrame(segments).to_csv("reports/segment_metrics.csv",index=False)
        print(f"fold={fold} {name} score={result['score']:.6f} smape={result['raw']['smape']:.3f} wape={result['raw']['wape']:.3f}",flush=True)
    objectives = {"lgb_l2":"regression","lgb_tweedie":"tweedie"}
    for fold, origin in enumerate(origins[:2],1):
        truth = panel.y[origin+1:origin+65]
        reference = baseline_predict(panel,origin,"last")
        for name in baseline_names:
            t=perf_counter(); pred=baseline_predict(panel,origin,name)
            record(name,fold,origin,pred,truth,reference,perf_counter()-t)
        for name,objective in objectives.items():
            t=perf_counter(); bundle=train_model(panel,origin,objective,args.rounds)
            fit_time=perf_counter()-t
            bundle["model"].save_model(f"reports/oof/{name}_fold{fold}.txt")
            t=perf_counter(); raw=predict_panel(panel,origin,bundle); inference=perf_counter()-t
            timing.append({"model":name,"fold":fold,"train_seconds":fit_time,"inference_seconds":inference,
                           "train_rows":bundle["config"]["training_rows"]})
            # Threshold candidates are frozen in advance and selected only on folds 1/2.
            for threshold in [0.,.25,.5]:
                candidate=name if threshold==0 else f"{name}_z{threshold}"
                record(candidate,fold,origin,np.where(raw<threshold,0,raw),truth,reference,inference)
            del bundle
            gc.collect()
    table=pd.DataFrame(records)
    ranking=table.groupby("model").local_minmax_score.mean().sort_values()
    winner=str(ranking.index[0])
    # Decision is written before opening the final holdout.
    selection={"winner":winner,"selection_scores":ranking.to_dict(),"holdout_was_used_for_selection":False,
               "objectives":objectives,"rounds":args.rounds,"fold_origins":[str(panel.dates[o].date()) for o in origins]}
    Path("reports/selection_frozen.json").write_text(json.dumps(selection,indent=2),encoding="utf-8")
    print("FROZEN WINNER",winner,flush=True)
    base_name=winner.split("_z")[0]
    threshold=float(winner.split("_z")[1]) if "_z" in winner else 0.
    def fit_selected(cutoff):
        if base_name in objectives:
            result=train_model(panel,cutoff,objectives[base_name],args.rounds)
            result["config"]["zero_threshold"]=threshold
            return result
        return {"catalogs":panel.catalogs,"config":{"kind":"baseline","baseline":base_name,
                "horizon":64,"schema_version":1,"model_version":"nonton-v1","zero_threshold":0}}
    origin=origins[2]; truth=panel.y[origin+1:origin+65]; reference=baseline_predict(panel,origin,"last")
    for name in baseline_names:
        t=perf_counter(); pred=baseline_predict(panel,origin,name)
        record(name,3,origin,pred,truth,reference,perf_counter()-t)
    t=perf_counter(); bundle=fit_selected(origin); holdout_fit=perf_counter()-t
    if base_name in objectives:
        bundle["model"].save_model("reports/oof/selected_holdout.txt")
    t=perf_counter(); pred=predict_panel(panel,origin,bundle)
    if winner not in baseline_names:
        record(winner,3,origin,pred,truth,reference,perf_counter()-t)
    del bundle
    gc.collect()
    t=perf_counter(); bundle=fit_selected(last); final_fit=perf_counter()-t
    if bundle["config"]["kind"]=="lightgbm":
        bundle["model"].save_model("model/lightgbm.txt")
    Path("model/config.json").write_text(json.dumps(bundle["config"],indent=2),encoding="utf-8")
    Path("model/catalogs.json").write_text(json.dumps(panel.catalogs,indent=2),encoding="utf-8")
    if bundle["config"]["kind"] == "lightgbm":
        import hashlib
        import uuid
        from datetime import datetime, timezone
        record = {"training_run_id": "pipeline-" + uuid.uuid4().hex,
                  "completed_at_utc": datetime.now(timezone.utc).isoformat(), "fit_seconds": final_fit,
                  "training_cutoff": str(panel.dates[last].date()), "training_rows": bundle["config"]["training_rows"],
                  "training_data_sha256": {"panel_y": hashlib.sha256(panel.y.tobytes()).hexdigest(),
                      "panel_stock": hashlib.sha256(panel.stock.tobytes()).hexdigest(),
                      "panel_dates": hashlib.sha256(panel.dates.to_numpy().tobytes()).hexdigest(),
                      "catalogs": fingerprint(panel.catalogs), "selection": fingerprint(selection)},
                  "training_source_sha256": {name: file_hash(ROOT / "src" / name)
                                             for name in ("train.py", "features.py", "data.py")},
                  "model_sha256": file_hash("model/lightgbm.txt"), "selection": selection,
                  "invocation": sys.argv,
                  "limitation": "Журнал создан текущим run; независимая проверка проводится отдельно."}
        write_training_manifest("model", record)
    else:
        write_manifest("model")
    t=perf_counter(); pred=predict_panel(panel,last,bundle); inference=perf_counter()-t
    frame=forecast_frame(pred,panel.dates[last],panel.catalogs)
    validation=write_submission(frame,"submission.csv",panel.dates[last],panel.catalogs)
    stop.set(); thread.join()
    benchmark={"pipeline_seconds":perf_counter()-started,"peak_process_rss_bytes":peak[0],
               "fits":timing,"holdout_fit_seconds":holdout_fit,"final_fit_seconds":final_fit,
               "final_inference_seconds":inference,"submission":validation,
               "final_model_bytes":Path("model/lightgbm.txt").stat().st_size if Path("model/lightgbm.txt").exists() else 0}
    Path("reports/training_benchmarks.json").write_text(json.dumps(benchmark,indent=2),encoding="utf-8")
    print(json.dumps(benchmark,indent=2),flush=True)


if __name__=="__main__":
    from scripts.train_final import positive_int
    import os
    from lightgbm.basic import LightGBMError
    p=argparse.ArgumentParser()
    p.add_argument("--data-dir",default=r"C:\Users\apollo\Desktop\выборка")
    p.add_argument("--work-dir",type=Path,default=ROOT,
                   help="Каталог артефактов и кэша; по умолчанию корень проекта")
    p.add_argument("--refresh",action="store_true")
    p.add_argument("--rounds",type=positive_int,default=220)
    args=p.parse_args()
    args.data_dir=str(Path(args.data_dir).resolve())
    try:
        args.work_dir.mkdir(parents=True,exist_ok=True)
        os.chdir(args.work_dir)
        run(args)
    except (OSError,ValueError,KeyError,LightGBMError) as exc:
        p.exit(2,f"Ошибка pipeline: {exc}\n")
