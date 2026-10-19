"""Read-only numerical remediation audit; never alter source or old reports."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import lightgbm as lgb
import numpy as np
import pandas as pd
from src.data import load_panel
from src.features import snapshot
from src.metrics import compute_metrics, smape_include_zero_zero
from src.predict import predict_panel
from scripts.qa_analysis import bias_diagnostics


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    panel = load_panel(ROOT / 'cache')
    config = json.loads((ROOT / 'model/config.json').read_text())
    summary, transformations, segments, horizons, provenance = [], [], [], [], []
    # Categories are reconstructed ONLY from historical rows at each origin.
    cats = pd.read_csv(Path(args.data_dir) / 'sales_dataset_hakaton_train.csv',
                       usecols=['date', 'article', 'category_lvl_1'], dtype=str).fillna('unknown')
    for fold, origin in enumerate([len(panel.dates)-193, len(panel.dates)-129, len(panel.dates)-65], 1):
        date = str(panel.dates[origin].date())
        truth = panel.y[origin+1:origin+65].astype(float)
        saved = np.load(ROOT / f'reports/oof/lgb_tweedie_z0.25_fold{fold}.npz')['prediction']
        weight = ROOT / ('reports/oof/selected_holdout.txt' if fold == 3 else f'reports/oof/lgb_tweedie_fold{fold}.txt')
        raw = predict_panel(panel, origin, {'model': lgb.Booster(model_file=str(weight)),
                            'config': dict(config, zero_threshold=0), 'catalogs': panel.catalogs})
        final = np.where(raw < .25, 0, raw)
        assert np.array_equal(final, saved), (fold, float(np.max(np.abs(final-saved))))
        for name, pred in [('nonnegative_before_threshold', raw), ('serialized_oof_after_threshold', saved)]:
            transformations.append(dict(fold=fold, origin=date, stage=name, zero_daily_fraction=float((pred==0).mean()),
                                        predicted_volume=float(pred.sum()), **compute_metrics(truth, pred),
                                        **bias_diagnostics(truth, pred)))
        # Tweedie inverse link is performed by Booster.predict; no custom inverse/scale exists.
        snap = snapshot(panel, origin)
        actual, predicted = truth.sum(axis=0), saved.sum(axis=0)
        eligible = actual > 0
        signed = np.divide(100*(predicted-actual), actual, out=np.full_like(actual, np.nan), where=eligible)
        series = panel.pairs.to_frame(index=False)
        series['actual_total'] = actual
        series['predicted_total'] = predicted
        series['signed_bias_pct'] = signed
        series['absolute_bias_pct'] = np.abs(signed)
        series['forecast_actual_ratio'] = np.divide(predicted, actual, out=np.full_like(actual, np.nan), where=eligible)
        series['actual_positive_days'] = (truth > 0).sum(axis=0)
        series['predicted_positive_days'] = (saved > 0).sum(axis=0)
        for col in ['freq_180', 'mean_180', 'positive_mean', 'std_180', 'max_180', 'stock_coverage', 'stock_zero_rate', 'stock_age', 'days_since_sale']:
            series[col] = snap[col].to_numpy()
        series['actual_volume_share'] = actual / actual.sum()
        historical = cats[cats.date <= date]
        counts = historical.groupby(['article', 'category_lvl_1']).size().reset_index(name='count')
        mapping = counts.sort_values(['article', 'count', 'category_lvl_1']).drop_duplicates('article', keep='last').set_index('article').category_lvl_1
        series['category_lvl_1'] = series.article.map(mapping).fillna('unknown')
        # Rank deciles break historical-volume ties by fixed catalog position, never future labels.
        series['historical_volume_decile'] = pd.qcut(series.mean_180.rank(method='first'), 10, labels=False)+1
        series.to_csv(out / f'series_diagnostics_fold{fold}.csv', index=False)
        diag = dict(fold=fold, origin=date, start=str(panel.dates[origin+1].date()), end=str(panel.dates[origin+64].date()),
                    **compute_metrics(truth, saved), **bias_diagnostics(truth, saved),
                    eligible_zero_total=int((eligible & (predicted==0)).sum()),
                    eligible_zero_total_pct=float(100*(eligible & (predicted==0)).sum()/eligible.sum()),
                    negative_signed_series=int((signed<0).sum()), positive_signed_series=int((signed>0).sum()),
                    exact_signed_series=int((signed==0).sum()),
                    median_abs_100_zero_total=int((eligible & (np.abs(signed)==100) & (predicted==0)).sum()),
                    median_abs_100_double_actual=int((eligible & (np.abs(signed)==100) & (predicted>0)).sum()),
                    smape_text=smape_include_zero_zero(truth,saved),
                    threshold_removed_volume=float(raw.sum()-saved.sum()),
                    threshold_removed_daily_values=int(((raw>0)&(saved==0)).sum()),
                    raw_min=float(raw.min()), raw_max=float(raw.max()),
                    raw_saved_max_difference=float(np.max(np.abs(final-saved))))
        for threshold in [1e-8, 1e-3, .1, 1.]:
            diag[f'eligible_predicted_total_le_{threshold:g}'] = int((eligible & (predicted<=threshold)).sum())
        summary.append(diag)
        groups = [('warehouse', v, (series.warehouse_name==v).to_numpy()) for v in panel.catalogs['warehouses']]
        groups += [('category_lvl_1',v,(series.category_lvl_1==v).to_numpy()) for v in sorted(series.category_lvl_1.unique())]
        groups += [('historical_volume_decile', str(v), (series.historical_volume_decile==v).to_numpy()) for v in range(1,11)]
        for name, values, edges in [('historical_frequency', series.freq_180, [-1,0,.01,.1,.5,1]),
                                    ('holdout_frequency_DIAGNOSTIC_ONLY', series.actual_positive_days/64, [-1,0,.01,.1,.5,1]),
                                    ('historical_stock_zero_rate', series.stock_zero_rate, [-1,0,.1,.5,1]),
                                    ('historical_stock_coverage', series.stock_coverage, [-1,0,.5,1])]:
            for lo, hi in zip(edges[:-1], edges[1:]):
                groups.append((name, f'({lo},{hi}]', ((values>lo)&(values<=hi)).to_numpy()))
        for kind, label, mask in groups:
            if mask.any():
                segments.append(dict(fold=fold, segment_type=kind, segment=label, pairs=int(mask.sum()),
                                     actual_volume_share=float(actual[mask].sum()/actual.sum()),
                                     zero_total_predictions=int((predicted[mask]==0).sum()),
                                     **compute_metrics(truth[:,mask],saved[:,mask]), **bias_diagnostics(truth[:,mask],saved[:,mask])))
        for name, sl in [('days1_14',slice(0,14)),('days15_35',slice(14,35)),('days36_64',slice(35,64)),('days57_64',slice(56,64))]:
            horizons.append(dict(fold=fold, segment=name, **compute_metrics(truth[sl],saved[sl]), **bias_diagnostics(truth[sl],saved[sl])))
    for file in sorted((ROOT / 'reports/oof').glob('*.npz')):
        with np.load(file) as saved:
            provenance.append(dict(file=file.name, sha256=sha(file), origin=str(saved['origin']), shape=str(saved['prediction'].shape),
                                   role='диагностика уже открытого holdout' if file.stem.endswith('fold3') else 'выбор/разработка',
                                   variant=file.stem.rsplit('_fold',1)[0]))
    pd.DataFrame(summary).to_csv(out/'baseline_metrics.csv',index=False)
    pd.DataFrame(transformations).to_csv(out/'postprocessing_ablation.csv',index=False)
    pd.DataFrame(segments).to_csv(out/'bias_by_segment.csv',index=False)
    pd.DataFrame(horizons).to_csv(out/'horizon_quality.csv',index=False)
    pd.DataFrame(provenance).to_csv(out/'oof_inventory.csv',index=False)
    sources = [Path(args.data_dir)/n for n in ['sales_dataset_hakaton_train.csv','stock_dataset_hakaton_train.csv','markdown hakaton.md']]
    sources += [ROOT/'cache/panel.npz', ROOT/'cache/catalogs.json']
    (out/'data_provenance.json').write_text(json.dumps([dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in sources],ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir',default=r'C:\Users\apollo\Desktop\выборка')
    parser.add_argument('--output',default=str(ROOT/'reports/remediation'))
    run(parser.parse_args())
