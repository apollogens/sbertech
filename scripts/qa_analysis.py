"""Recompute QA diagnostics from preserved historical predictions; never tune them."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from src.data import load_panel
from src.features import snapshot
from src.metrics import compute_metrics
from src.submission import validate_submission


def bias_diagnostics(truth, prediction):
    actual = truth.astype(np.float64).sum(axis=0)
    predicted = prediction.astype(np.float64).sum(axis=0)
    eligible = actual != 0
    signed = 100 * (predicted[eligible] - actual[eligible]) / np.abs(actual[eligible])
    absolute = np.abs(signed)
    return {
        "series": len(actual), "eligible": int(eligible.sum()), "excluded": int((~eligible).sum()),
        "official_bias_pct": float(absolute.mean()) if len(absolute) else 0.,
        "mean_signed_series_bias_pct": float(signed.mean()) if len(signed) else None,
        "global_signed_volume_bias_pct": float(100 * (predicted.sum() - actual.sum()) / np.abs(actual).sum()) if np.abs(actual).sum() else None,
        "median_abs_pct": float(np.median(absolute)) if len(absolute) else None,
        "p75_abs_pct": float(np.quantile(absolute, .75)) if len(absolute) else None,
        "p90_abs_pct": float(np.quantile(absolute, .90)) if len(absolute) else None,
        "p95_abs_pct": float(np.quantile(absolute, .95)) if len(absolute) else None,
        "overforecast_pct": float(100 * (signed > 0).mean()) if len(signed) else None,
        "underforecast_pct": float(100 * (signed < 0).mean()) if len(signed) else None,
        "exact_total_pct": float(100 * (signed == 0).mean()) if len(signed) else None,
    }


def table(frame):
    def value(v):
        if isinstance(v, (float, np.floating)):
            return f"{v:.6f}" if np.isfinite(v) else "NOT MEASURABLE"
        return str(v)
    return "\n".join(["| " + " | ".join(frame.columns) + " |", "|" + "|".join(["---"] * len(frame.columns)) + "|"] + ["| " + " | ".join(value(v) for v in row) + " |" for row in frame.itertuples(index=False, name=None)])


def run(data_dir):
    out = ROOT / 'reports/qa'
    out.mkdir(exist_ok=True)
    panel = load_panel()
    selected = json.loads((ROOT/'reports/selection_frozen.json').read_text())['winner']
    origins = [len(panel.dates)-193, len(panel.dates)-129, len(panel.dates)-65]
    categories = [Counter() for _ in origins]
    category_counts = Counter()
    source_rows = 0
    cols = ['date', 'article', 'category_lvl_1', 'category_lvl_2', 'category_lvl_3']
    for chunk in pd.read_csv(data_dir/'sales_dataset_hakaton_train.csv', usecols=cols, dtype=str, keep_default_na=False, chunksize=100000):
        source_rows += len(chunk)
        for level in cols[2:]:
            for article, category in chunk[['article', level]].drop_duplicates().itertuples(index=False, name=None):
                if category:
                    category_counts[(level, article, category)] = 1
        for i, origin in enumerate(origins):
            history = chunk.loc[chunk.date <= str(panel.dates[origin].date())]
            for (article, category), count in history.groupby(['article', 'category_lvl_1']).size().items():
                categories[i][(article, category)] += int(count)
    conflicts = {}
    for level in cols[2:]:
        per_article = Counter(article for lvl, article, category in category_counts if lvl == level)
        conflicts[level] = sum(n > 1 for n in per_article.values())

    horizon_rows, segment_rows, summaries, extreme_rows, baseline_rows = [], [], [], [], []
    windows = {'1–14': slice(0,14), '15–35': slice(14,35), '36–64': slice(35,64), '57–64': slice(56,64), '1–64': slice(0,64)}
    for fold, origin in enumerate(origins, 1):
        saved = np.load(ROOT/f'reports/oof/{selected}_fold{fold}.npz')
        assert str(saved['origin']) == str(panel.dates[origin].date())
        prediction = saved['prediction']
        truth = panel.y[origin+1:origin+65]
        summary = {'fold': fold, 'origin': str(panel.dates[origin].date()),
                   'first_date': str(panel.dates[origin+1].date()), 'last_date': str(panel.dates[origin+64].date()),
                   **compute_metrics(truth,prediction), **bias_diagnostics(truth,prediction)}
        assert abs(summary['bias'] - summary['official_bias_pct']) < 1e-10
        summaries.append(summary)
        for label, window in windows.items():
            horizon_rows.append({'fold':fold, 'days':label, **compute_metrics(truth[window],prediction[window]), **bias_diagnostics(truth[window],prediction[window])})
        snap = snapshot(panel, origin)
        narticles = len(panel.catalogs['articles'])
        warehouse = np.repeat(panel.catalogs['warehouses'], narticles)
        articles = np.tile(panel.catalogs['articles'], len(panel.catalogs['warehouses']))
        mapping = {}
        for article in panel.catalogs['articles']:
            options = [(count, category) for (a, category), count in categories[fold-1].items() if a == article]
            mapping[article] = max(options)[1] if options else 'unknown'
        category = np.array([mapping[a] for a in articles])
        volume = snap.mean_180.to_numpy()
        masks = [('warehouse', w, warehouse == w) for w in np.unique(warehouse)]
        masks += [('category_lvl_1', c, category == c) for c in np.unique(category)]
        masks += [('demand', 'intermittent_freq_lt_0.1', snap.freq_180.to_numpy() < .1), ('demand', 'regular_freq_ge_0.1', snap.freq_180.to_numpy() >= .1)]
        masks += [('volume', 'low_le_historical_median', volume <= np.median(volume)), ('volume', 'high_gt_historical_median', volume > np.median(volume)), ('volume', 'top10pct', volume >= np.quantile(volume,.9))]
        coverage, zero = snap.stock_coverage.to_numpy(), snap.stock_zero_rate.to_numpy()
        masks += [('stockout', 'unobserved', coverage == 0), ('stockout', 'observed_zero_rate_le_0.5', (coverage > 0) & (zero <= .5)), ('stockout', 'observed_zero_rate_gt_0.5', (coverage > 0) & (zero > .5))]
        for kind, name, mask in masks:
            if mask.any():
                segment_rows.append({'fold': fold, 'segment_type': kind, 'segment': name, **compute_metrics(truth[:,mask],prediction[:,mask]), **bias_diagnostics(truth[:,mask],prediction[:,mask])})
        totals, ptotal = truth.astype(float).sum(axis=0), prediction.astype(float).sum(axis=0)
        eligible_indices = np.flatnonzero(totals != 0)
        signed = 100 * (ptotal[eligible_indices] - totals[eligible_indices]) / totals[eligible_indices]
        for direction, indices in [('over', np.argsort(signed)[-5:][::-1]), ('under', np.argsort(signed)[:5])]:
            for i in indices:
                index = eligible_indices[i]
                anon = hashlib.sha256(f'{warehouse[index]}|{articles[index]}'.encode()).hexdigest()[:12]
                extreme_rows.append({'fold': fold, 'direction': direction, 'anonymized_series_id': anon, 'signed_bias_pct': signed[i], 'actual_total': totals[index], 'predicted_total': ptotal[index]})
        for name in ['zero','last','mean28','mean90','seasonal56','tsb',selected]:
            pred = np.load(ROOT/f'reports/oof/{name}_fold{fold}.npz')['prediction']
            baseline_rows.append({'fold': fold, 'model':name, **compute_metrics(truth,pred), **bias_diagnostics(truth,pred)})

    for name, rows in [('bias_summary',summaries),('horizon_metrics',horizon_rows),('bias_segments',segment_rows),('extreme_series',extreme_rows),('baseline_comparison',baseline_rows)]:
        pd.DataFrame(rows).to_csv(out/f'{name}.csv',index=False)
    frame = pd.read_csv(ROOT/'submission.csv',dtype={'date':str,'warehouse_name':str,'article':str})
    validity = validate_submission(frame,panel.dates[-1],panel.catalogs)
    # Independent set comparison catches equal-row-count replacement keys.
    expected = set(pd.MultiIndex.from_product([pd.date_range(panel.dates[-1]+pd.Timedelta(days=1), periods=64).strftime('%Y-%m-%d'), panel.catalogs['warehouses'], panel.catalogs['articles']]))
    actual = set(frame[['date','warehouse_name','article']].itertuples(index=False,name=None))
    validity.update(missing_keys=len(expected-actual), unexpected_keys=len(actual-expected), unique_keys=len(actual), first_date=frame.date.min(), last_date=frame.date.max())
    assert expected == actual
    original = {key.replace('\\', '/'): value for key, value in json.loads((out/'initial_manifest.json').read_text()).items()}
    preserved = {}
    for path in ['submission.csv','submission_baseline.csv','model/lightgbm.txt','model/config.json','model/catalogs.json','nonton_solution.zip']:
        with (ROOT/path).open('rb') as stream:
            current = hashlib.file_digest(stream,'sha256').hexdigest()
        preserved[path] = current == original[path]['sha256']
        assert preserved[path], path
    stats = {'source_sales_rows_read': source_rows, 'category_conflicting_articles':conflicts, 'submission':validity, 'preserved_original_hashes':preserved}
    (out/'analysis_summary.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf8')

    summary_frame = pd.DataFrame(summaries)
    holdout = summaries[-1]
    segments = pd.DataFrame(segment_rows)
    compact = ['segment','series','eligible','excluded','official_bias_pct','mean_signed_series_bias_pct','global_signed_volume_bias_pct']
    bias_report = f'''# Независимый анализ Bias

Проверка 18.10.2026. Данные анонимизированы и преобразованы: проценты не являются денежным или физическим отклонением запасов компании.

Для ряда s: `100 * abs(sum(pred_s) - sum(actual_s)) / abs(sum(actual_s))`; затем среднее по рядам с ненулевым actual. Никакого epsilon. Ссылка реализации: `scripts/official_score.py::bias_abs_series,bias_abs`; `src/metrics.py::compute_metrics`. Полностью нулевой набор получает fallback 0% по scorer, что неинформативно.

## Исторические окна и распределение

Folds 1 и 2 использовались для выбора модели/порога; fold 3 — единственный holdout. Здесь сохранённые OOF сверены с реальными наблюдениями. Полный CSV: `bias_summary.csv`.

{table(summary_frame[['fold','first_date','last_date','series','eligible','excluded','official_bias_pct','mean_signed_series_bias_pct','global_signed_volume_bias_pct','median_abs_pct','p75_abs_pct','p90_abs_pct','p95_abs_pct','overforecast_pct','underforecast_pct','exact_total_pct']])}

Mean signed series Bias и global signed volume Bias — отдельные диагностические величины; обе не равны официальному абсолютному Bias. Самые крайние ряды представлены только хешированными ID в `extreme_series.csv`.

## Сегменты holdout

Группы строятся только по истории до origin. Intermittent: доля положительных дней за последние 180 дней <0.1; regular >=0.1. Low/high volume: разделение по медиане исторического среднего. Stockout — доля нулевых остатков среди наблюдавшихся; отсутствие записей выделено отдельно. Категория — наиболее частая category_lvl_1 до cutoff; конфликты категорий по всему train: {conflicts}. Это описательная группировка, не автоматическое изменение категории в модели.

В каждой группе пересчитана официальная формула на полном 64-дневном горизонте. Нулевые ряды исключаются внутри группы. Это совпадает с усреднением eligible full-horizon ratios для выбранных рядов; при нарезке дней знаменатели пересчитываются.

{table(segments.loc[(segments.fold==3)&(segments.segment_type=='warehouse'),compact])}

{table(segments.loc[(segments.fold==3)&(segments.segment_type!='warehouse'),compact])}

## Горизонты holdout

Для каждого диапазона дней заново рассчитаны actual/predicted totals и eligible-ряды; это не среднее 64-дневных Bias. Диапазон 57–64 входит в 36–64.

{table(pd.DataFrame(horizon_rows).query('fold==3')[['days','eligible','excluded','official_bias_pct','mean_signed_series_bias_pct','global_signed_volume_bias_pct']])}

## Сравнение с базовыми моделями

{table(pd.DataFrame(baseline_rows).query('fold==3')[['model','smape','wape','rmse','bias','rmsle','mean_signed_series_bias_pct','global_signed_volume_bias_pct']])}

Изменения QA затрагивают проверки и отклонение повреждённого ввода, не признаки, обучение, веса или порог. Для допустимого исходного ввода метрики до/после одинаковы; улучшение Bias не заявляется. Порог 0.25 имеет компромисс: на selection хуже Bias/RMSE/RMSLE относительно raw Tweedie, лучше SMAPE/WAPE. Другие варианты не подбирались по holdout.

Будущий Bias на submission 2026-08-01–2026-10-03: **NOT MEASURABLE** — скрытые фактические продажи не предоставлены. Нет доказательства устойчивости по множеству независимых holdout.
'''
    (out/'bias_analysis.md').write_text(bias_report,encoding='utf8')
    horizon_report = f'''# Качество по горизонту

Фактические результаты выбранной модели `{selected}`. Полные числа: `horizon_metrics.csv`; данные получены из сохранённых OOF и исторической панели. Дни в каждой группе заново проходят все официальные формулы, в том числе исключение zero/zero в SMAPE и zero-actual рядов в Bias.

{table(pd.DataFrame(horizon_rows)[['fold','days','smape','wape','rmse','bias','rmsle']])}

Это прямая horizon-conditioned модель: предыдущие прогнозы не поступают обратно в lag. Отсутствие рекурсивного накопления не гарантирует точность дня 64. Различия окон включают календарь и состав ненулевого спроса; это не изолированное измерение дрейфа. Значения не обязаны монотонно ухудшаться с горизонтом. Единственный untouched holdout — fold3; folds1/2 участвовали в выборе. По этим данным нельзя отделить дрейф распределения от случайной вариации или заявить статистически устойчивый прирост.

Проверки sparse/high-volume/stockout/warehouses/category — `bias_segments.csv` и `bias_analysis.md`. График `horizon_quality.png` построен из вычисленных чисел. В `bias_distribution.png` показано распределение signed Bias holdout eligible рядов, крайние значения визуально обрезаны до [-100,300] исключительно на рисунке; CSV и процентили не клиппируются. Полное представление правого хвоста — `bias_tail.png`.
'''
    (out/'horizon_analysis.md').write_text(horizon_report,encoding='utf8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    hframe = pd.DataFrame(horizon_rows)
    fig, axes = plt.subplots(1,3,figsize=(12,3.5))
    for ax, metric in zip(axes,['smape','wape','bias']):
        for fold in [1,2,3]:
            rows = hframe.loc[(hframe.fold==fold)&hframe.days.isin(['1–14','15–35','36–64','57–64'])]
            ax.plot(rows.days,rows[metric],marker='o',label=f'Срез {fold}')
        ax.set_title(metric.upper()+' (%)');ax.set_xlabel('Дни горизонта');ax.grid(alpha=.2)
    axes[-1].legend();fig.tight_layout();fig.savefig(out/'horizon_quality.png',dpi=160);plt.close(fig)
    origin = origins[-1];truth=panel.y[origin+1:origin+65].astype(float)
    pred=np.load(ROOT/f'reports/oof/{selected}_fold3.npz')['prediction'].astype(float)
    eligible=truth.sum(axis=0)!=0;signed=100*(pred.sum(axis=0)[eligible]-truth.sum(axis=0)[eligible])/truth.sum(axis=0)[eligible]
    fig,ax=plt.subplots(figsize=(8,3.5));ax.hist(np.clip(signed,-100,300),bins=60);ax.set_xlabel('Signed Bias по ряду (%), клиппирование только графика');ax.set_ylabel('Число рядов');fig.tight_layout();fig.savefig(out/'bias_distribution.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,3.5));ax.plot(np.arange(1,len(signed)+1)/len(signed)*100,np.sort(np.abs(signed)));ax.set_yscale('symlog',linthresh=1);ax.set_xlabel('Перцентиль рядов');ax.set_ylabel('Абсолютный Bias (%), symlog');ax.grid(alpha=.2);fig.tight_layout();fig.savefig(out/'bias_tail.png',dpi=160);plt.close(fig)
    print(json.dumps({'holdout':holdout,**stats},ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',type=Path,default=Path(r'C:\Users\apollo\Desktop\выборка'));args=parser.parse_args();run(args.data_dir)
