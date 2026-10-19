"""Isolated representation experiments. Never writes serving artifacts."""
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
from src.data import Panel, load_panel
from src.features import snapshot, horizon_features
from src.train import PARAMS, train_model
from src.predict import predict_panel
from src.metrics import compute_metrics, smape_include_zero_zero
from scripts.qa_analysis import bias_diagnostics

from src.temporal import BUCKETS, weekly_frame, weekday_weights, allocate_buckets, warehouse_shares




def fit_weekly(panel, cutoff, rounds):
    last = cutoff - 64
    origins = sorted(set(range(179, last + 1, 35)) | {last})
    if last < 179:
        raise ValueError('Insufficient history')
    xs, ys = [], []
    for origin in origins:
        snap = snapshot(panel, origin)
        for start, end in BUCKETS:
            xs.append(weekly_frame(snap, panel.dates[origin], start, end))
            ys.append(panel.y[origin + start:origin + end].sum(axis=0, dtype=np.float64))
    x = pd.concat(xs, ignore_index=True)
    model = lgb.train(dict(PARAMS, objective='tweedie', tweedie_variance_power=1.3),
                      lgb.Dataset(x, label=np.concatenate(ys), categorical_feature=['warehouse_id', 'article_id']),
                      num_boost_round=rounds)
    return model, dict(origins=[str(panel.dates[o].date()) for o in origins], rows=len(x), features=list(x.columns))






def article_panel(panel):
    nw, na = len(panel.catalogs['warehouses']), len(panel.catalogs['articles'])
    y = panel.y.reshape(-1, nw, na).sum(axis=1)
    stock = panel.stock.reshape(-1, nw, na)
    # Incomplete aggregate stock remains unknown rather than becoming zero.
    s = np.where(np.isfinite(stock).all(axis=1), np.nansum(stock, axis=1), np.nan)
    return Panel(panel.dates, y, s, dict(warehouses=['all_warehouses'], articles=panel.catalogs['articles']))




def run(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    pred_dir = out / 'predictions'; pred_dir.mkdir(exist_ok=True)
    protocol = json.loads((out / 'experiment_protocol.json').read_text(encoding='utf-8'))
    panel = load_panel(ROOT / 'cache')
    rows, horizons, coherence = [], [], []
    process = psutil.Process()
    def record(name, date, truth, pred, train, infer, peak, model_path='', metadata=None):
        if pred.shape != (64, panel.y.shape[1]) or not np.isfinite(pred).all() or (pred < 0).any():
            raise ValueError('Invalid full-grid prediction')
        path = pred_dir / f'{name}_{date}.npz'
        np.savez_compressed(path, prediction=pred, origin=date)
        origin = panel.dates.get_loc(date)
        sparse = snapshot(panel, origin).freq_180.to_numpy() < .1
        row = dict(model=name, origin=date, role='terminal_diagnostic' if date == protocol['origins'][-1] else 'development',
                   **compute_metrics(truth, pred), **bias_diagnostics(truth, pred), smape_text=smape_include_zero_zero(truth, pred),
                   zero_total_series=int((pred.sum(axis=0) == 0).sum()),
                   zero_total_eligible=int(((pred.sum(axis=0) == 0) & (truth.sum(axis=0) > 0)).sum()),
                   train_seconds=train, inference_seconds=infer, process_peak_rss_bytes=peak,
                   prediction_path=str(path.relative_to(ROOT)), prediction_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   model_path=model_path, metadata=json.dumps(metadata or {}, ensure_ascii=False))
        row.update({'sparse_' + k: v for k, v in compute_metrics(truth[:, sparse], pred[:, sparse]).items()})
        rows.append(row)
        for label, sl in [('1_14', slice(0, 14)), ('15_35', slice(14, 35)), ('36_64', slice(35, 64)), ('57_64', slice(56, 64))]:
            horizons.append(dict(model=name, origin=date, horizon=label, **compute_metrics(truth[sl], pred[sl])))
        pd.DataFrame(rows).to_csv(out / 'experiment_results.csv', index=False)
        pd.DataFrame(horizons).to_csv(out / 'horizon_results.csv', index=False)
        print(f'{date} {name} {compute_metrics(truth, pred)}', flush=True)

    for date in protocol['origins']:
        origin = panel.dates.get_loc(date)
        truth = panel.y[origin + 1:origin + 65]
        raw = np.load(ROOT / f'reports/remediation/predictions/tweedie_raw_{date}.npz')['prediction']
        inc = np.load(ROOT / f'reports/remediation/predictions/current_tweedie_z0.25_{date}.npz')['prediction']
        record('incumbent', date, truth, inc, 0, 0, process.memory_info().rss, metadata={'reused_prediction': True})
        peak = [process.memory_info().rss]; stop = threading.Event()
        def monitor():
            while not stop.wait(.05):
                peak[0] = max(peak[0], process.memory_info().rss)
        thread = threading.Thread(target=monitor, daemon=True); thread.start()
        try:
            start_time = perf_counter()
            weekly, meta = fit_weekly(panel, origin, protocol['rounds'])
            train = perf_counter() - start_time
            model_path = pred_dir / f'weekly_{date}.txt'; weekly.save_model(str(model_path))
            start_time = perf_counter()
            snap = snapshot(panel, origin)
            totals = np.stack([weekly.predict(weekly_frame(snap, panel.dates[origin], s, e), num_threads=4) for s, e in BUCKETS])
            dows = pd.date_range(panel.dates[origin] + pd.Timedelta(days=1), periods=64).dayofweek.to_numpy()
            daily = allocate_buckets(totals, weekday_weights(panel, origin)[dows])
            elapsed = perf_counter() - start_time
            reconcile_start = perf_counter()
            reconciled = allocate_buckets(totals, raw)
            reconcile_time = perf_counter() - reconcile_start
            for name, pred, inference in [('weekly_allocation', daily, elapsed), ('weekly_direct_shape', reconciled, elapsed + reconcile_time)]:
                err = max(float(np.max(np.abs(pred[s-1:e-1].sum(axis=0) - totals[i]))) for i, (s, e) in enumerate(BUCKETS))
                coherence.append(dict(model=name, origin=date, max_abs_error=err, scope='pre_threshold_weekly_totals'))
                record(name, date, truth, pred, train, inference, peak[0], str(model_path.relative_to(ROOT)), meta)
                record(name + '_z0.25', date, truth, np.where(pred < .25, 0., pred), train, inference, peak[0], str(model_path.relative_to(ROOT)), meta)
            del weekly; gc.collect()
            start_time = perf_counter()
            agg_panel = article_panel(panel)
            fitted = train_model(agg_panel, origin, 'tweedie', protocol['rounds'])
            train = perf_counter() - start_time
            model_path = pred_dir / f'article_{date}.txt'; fitted['model'].save_model(str(model_path))
            start_time = perf_counter()
            aggregate = predict_panel(agg_panel, origin, fitted)
            shares = warehouse_shares(panel, origin)
            daily = (aggregate[:, None, :] * shares[None, :, :]).reshape(64, -1)
            elapsed = perf_counter() - start_time
            coherence.append(dict(model='article_topdown', origin=date, max_abs_error=float(np.max(np.abs(daily.reshape(64, *shares.shape).sum(axis=1) - aggregate))), scope='pre_threshold_article_totals'))
            for name, pred in [('article_topdown', daily), ('article_topdown_z0.25', np.where(daily < .25, 0., daily))]:
                record(name, date, truth, pred, train, elapsed, peak[0], str(model_path.relative_to(ROOT)), fitted['config'])
            del fitted, agg_panel; gc.collect()
            pd.DataFrame(coherence).to_csv(out / 'coherence_checks.csv', index=False)
        finally:
            stop.set(); thread.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(ROOT / 'research'))
    run(parser.parse_args())
