"""Read-only independent QA. Run from any cwd; writes only with explicit output flags.

No production metric/data/forecast function is used to compute OOF results.
"""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import re
import sys
from time import perf_counter

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import official_score
from src.metrics import compute_metrics, normalize_metrics, weighted_score

WEIGHTS = dict(smape=.5, wape=.2, rmse=.15, bias=.1, rmsle=.05)


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def independent_metrics(truth, prediction):
    truth = np.asarray(truth, dtype=np.float64)
    prediction = np.maximum(np.nan_to_num(np.asarray(prediction, dtype=np.float64), nan=0), 0)
    smapes, biases = [], []
    for actual, predicted in zip(truth.T, prediction.T):
        active = actual + predicted > 0
        smapes.append(float((200 * np.abs(actual[active] - predicted[active]) /
                             (actual[active] + predicted[active])).mean()) if active.any() else 0.)
        if actual.sum() > 0:
            biases.append(abs(predicted.sum() - actual.sum()) / actual.sum() * 100)
    error = prediction - truth
    return dict(smape=float(np.mean(smapes)),
                wape=float(np.abs(error).sum() / truth.sum() * 100) if truth.sum() else 0.,
                rmse=float(np.sqrt(np.square(error).mean())),
                bias=float(np.mean(biases)) if biases else 0.,
                rmsle=float(np.sqrt(np.square(np.log1p(prediction) - np.log1p(truth)).mean())))


def independent_score(metrics, baseline):
    return sum(WEIGHTS[k] * (min(metrics[k] / baseline[k], 1) if baseline[k] else
                            float(metrics[k] != 0)) for k in WEIGHTS)


def frame(array):
    days, pairs = array.shape
    return pd.DataFrame(dict(date=np.repeat(pd.date_range('2020-01-01', periods=days), pairs),
                             warehouse_name='w', article=np.tile(np.arange(pairs).astype(str), days),
                             quantity=np.asarray(array).ravel()))


def assert_metrics(actual, expected):
    for key in WEIGHTS:
        assert np.isclose(actual[key], expected[key], atol=1e-10, rtol=1e-10), (key, actual, expected)


def run():
    started = perf_counter()
    source_dir = next(p.parent for p in (Path.home() / 'Desktop').glob('*/markdown hakaton.md'))
    specification = (source_dir / 'markdown hakaton.md').read_text(encoding='utf-8')
    block = next(b for b in re.findall(r'```python\s*\n(.*?)```', specification, re.S)
                 if 'def normalize_rank' in b)
    extracted = block.strip() + '\n'
    copied = (ROOT / 'scripts/official_score.py').read_text(encoding='utf-8').strip() + '\n'
    assert extracted == copied
    assert ast.dump(ast.parse(extracted)) == ast.dump(ast.parse(copied))
    results = dict(scorer_exact_extracted_text_match=True,
                   scorer_sha256_normalized=hashlib.sha256(copied.encode()).hexdigest())
    sources = [source_dir / 'markdown hakaton.md', source_dir / 'sales_dataset_hakaton_train.csv',
               ROOT / 'scripts/official_score.py', ROOT / 'cache/panel.npz',
               ROOT / 'cache/catalogs.json', ROOT / 'model/catalogs.json',
               ROOT / 'reports/selection_frozen.json', ROOT / 'reports/experiment_results.csv']
    results['source_provenance'] = {str(path): dict(bytes=path.stat().st_size, sha256=file_sha256(path))
                                    for path in sources}
    # Bias must average per-series magnitudes (100 and 20), excluding zero truth.
    y = np.array([[10., 10., 0.], [10., 10., 0.]])
    p = np.array([[0., 12., 2.], [0., 12., 2.]])
    expected = dict(smape=(200 + 200 / 11 + 200) / 3, wape=70., rmse=6., bias=60.,
                    rmsle=np.sqrt((np.log(11)**2 + np.log(13/11)**2 + np.log(3)**2) / 3))
    assert_metrics(independent_metrics(y, p), expected)
    assert_metrics(compute_metrics(y, p), expected)
    assert_metrics(official_score.compute_all_metrics(frame(y), frame(p)), expected)
    results['bias_60_fixture'] = expected
    sparse_y = np.array([[0.], [0.], [0.], [1.]])
    sparse_p = np.zeros_like(sparse_y)
    assert independent_metrics(sparse_y, sparse_p)['smape'] == 200
    assert compute_metrics(sparse_y, sparse_p)['smape'] == 200
    assert official_score.compute_all_metrics(frame(sparse_y), frame(sparse_p))['smape'] == 200
    results['smape_200_vs_50'] = dict(executable=200, prose=50)
    for actual, predicted in [(np.zeros((4, 3)), np.ones((4, 3))),
                              (y, np.full_like(y, np.nan)), (y, -p), (y, y)]:
        independent = independent_metrics(actual, predicted)
        assert_metrics(compute_metrics(actual, predicted), independent)
        assert_metrics(official_score.compute_all_metrics(frame(actual), frame(predicted)), independent)
    base = dict(zip(WEIGHTS, [10, 20, 0, 0, 2]))
    metrics = dict(zip(WEIGHTS, [5, 40, 0, 8, 1]))
    expected_norm = dict(smape=.5, wape=1., rmse=0., bias=1., rmsle=.5)
    assert normalize_metrics(metrics, base) == expected_norm
    assert official_score.normalize_minmax({'model': metrics}, base)['model'] == expected_norm
    assert np.isclose(weighted_score(metrics, base), .575)
    results['normalization_fixture_score'] = .575
    tied = {'A': {k: 1 for k in WEIGHTS}, 'B': {k: 1 for k in WEIGHTS}}
    tied_forward = official_score.normalize_rank(tied)
    tied_reverse = official_score.normalize_rank(dict(reversed(list(tied.items()))))
    assert tied_forward['A']['smape'] != tied_reverse['A']['smape']
    assert official_score.normalize_rank({'A': tied['A']})['A']['smape'] == 0
    results['official_rank_ties'] = dict(forward=tied_forward, reverse=tied_reverse,
                                        singleton=0, empty=official_score.normalize_rank({}))

    catalogs = json.loads((ROOT / 'cache/catalogs.json').read_text())
    assert catalogs == json.loads((ROOT / 'model/catalogs.json').read_text())
    pairs = pd.MultiIndex.from_product([catalogs['warehouses'], catalogs['articles']])
    assert len(pairs) == 8789 and pairs.is_unique
    with np.load(ROOT / 'cache/panel.npz') as panel:
        dates = pd.DatetimeIndex(panel['dates'])
        truth_panel = panel['y']
    assert np.isfinite(truth_panel).all() and (truth_panel >= 0).all()
    assert dates.equals(pd.date_range(dates.min(), dates.max()))
    # Independently aggregate original raw sales and check every cached label.
    raw = pd.read_csv(source_dir / 'sales_dataset_hakaton_train.csv',
                      usecols=['date', 'warehouse_name', 'article', 'quantity'])
    raw['date'] = pd.to_datetime(raw['date'])
    grouped = raw.groupby(['date', 'warehouse_name', 'article'], sort=False).quantity.sum()
    rebuilt = np.zeros_like(truth_panel)
    di = dates.get_indexer(grouped.index.get_level_values('date'))
    pi = pairs.get_indexer(grouped.index.droplevel('date'))
    assert (di >= 0).all() and (pi >= 0).all()
    rebuilt[di, pi] = grouped.to_numpy(dtype=np.float32)
    assert np.array_equal(rebuilt, truth_panel)
    results['truth_keys'] = dict(raw_rows=len(raw), aggregated_rows=len(grouped),
        panel_shape=list(truth_panel.shape), warehouse_count=len(catalogs['warehouses']),
        article_count=len(catalogs['articles']), cache_equal_raw_aggregation=True,
        raw_max_float32_rounding=float(np.max(np.abs(grouped.to_numpy() - grouped.to_numpy(dtype=np.float32)))),
        first_date=str(dates.min().date()), last_date=str(dates.max().date()))
    table = pd.read_csv(ROOT / 'reports/experiment_results.csv')
    rows = []
    max_abs_error = 0.
    for row in table.itertuples(index=False):
        with np.load(ROOT / f'reports/oof/{row.model}_fold{row.fold}.npz') as saved:
            prediction = saved['prediction']
            assert set(saved.files) == {'prediction', 'origin'}
            assert saved['origin'].item() == row.origin
        origin = dates.get_loc(pd.Timestamp(row.origin))
        truth = truth_panel[origin + 1:origin + 65]
        assert truth.shape == prediction.shape == (64, 8789)
        assert np.isfinite(prediction).all() and (prediction >= 0).all()
        actual = independent_metrics(truth, prediction)
        assert_metrics(compute_metrics(truth, prediction), actual)
        reference = np.broadcast_to(truth_panel[origin], truth.shape)
        baseline_metrics = independent_metrics(truth, reference)
        score = independent_score(actual, baseline_metrics)
        errors = [abs(actual[k] - getattr(row, k)) for k in WEIGHTS]
        errors.append(abs(score - row.local_minmax_score))
        max_abs_error = max(max_abs_error, *errors)
        assert max(errors) < 1e-9, (row.model, row.fold, errors)
        # Check date blocks and hand-built frames on real sampled series.
        sample = [0, 17, 700, 1900, 7000, 8788]
        assert_metrics(official_score.compute_all_metrics(frame(truth[:, sample]),
                       frame(prediction[:, sample])), independent_metrics(truth[:, sample], prediction[:, sample]))
        if row.model == 'zero':
            assert (prediction == 0).all()
        if row.model == 'last':
            assert np.array_equal(prediction, reference)
        if row.model in ['mean28', 'mean90']:
            window = int(row.model[4:])
            reconstructed = np.broadcast_to(truth_panel[origin-window+1:origin+1].mean(axis=0), truth.shape)
            assert np.array_equal(prediction, reconstructed)
        if row.model == 'seasonal56':
            recent = truth_panel[origin-55:origin+1]
            recent_dow = dates[origin-55:origin+1].dayofweek
            reconstructed = np.stack([recent[recent_dow == dates[origin+h].dayofweek].mean(axis=0)
                                      for h in range(1, 65)])
            assert np.array_equal(prediction, reconstructed)
        if row.model == 'tsb':
            history = truth_panel[origin-179:origin+1]
            probability = (history[:28] > 0).mean(axis=0)
            size = history[:28].sum(axis=0) / np.maximum((history[:28] > 0).sum(axis=0), 1)
            for observation in history[28:]:
                positive = observation > 0
                probability = probability * .95 + positive * .05
                size = np.where(positive, size * .95 + observation * .05, size)
            reconstructed = np.broadcast_to((probability * size).astype(np.float32), prediction.shape)
            assert np.array_equal(prediction, reconstructed)
        if '_z' in row.model and row.fold != 3:
            name, threshold = row.model.split('_z')
            with np.load(ROOT / f'reports/oof/{name}_fold{row.fold}.npz') as saved:
                original = saved['prediction']
            assert np.array_equal(prediction, np.where(original < float(threshold), 0, original))
        if row.model == 'lgb_tweedie_z0.25':
            assert ((prediction == 0) | (prediction >= .25)).all()
        rows.append(dict(model=row.model, fold=row.fold, origin=row.origin,
                         first_forecast=str(dates[origin+1].date()), last_forecast=str(dates[origin+64].date()),
                         **actual, score=score))
    assert len(rows) == 31
    selection = json.loads((ROOT / 'reports/selection_frozen.json').read_text())
    means = pd.DataFrame(rows).query('fold < 3').groupby('model').score.mean().sort_values()
    assert means.index[0] == selection['winner']
    for name, value in means.items():
        assert np.isclose(value, selection['selection_scores'][name], atol=1e-12)
    results['selection_winner'] = str(means.index[0])
    results['selection_margin'] = float(means.iloc[1] - means.iloc[0])
    rank_rows = []
    for fold, group in pd.DataFrame(rows).groupby('fold'):
        all_metrics = {r.model: {k: getattr(r, k) for k in WEIGHTS}
                       for r in group.itertuples()}
        normalized = official_score.normalize_rank(all_metrics)
        rank_rows.extend(dict(fold=int(fold), model=name,
                              score=sum(WEIGHTS[k] * values[k] for k in WEIGHTS))
                         for name, values in normalized.items())
    rank_selection = pd.DataFrame(rank_rows).query('fold < 3').groupby('model').score.mean().sort_values()
    results['diagnostic_rank_selection_scores'] = rank_selection.to_dict()
    results['max_saved_metric_or_score_abs_error'] = max_abs_error
    results['oof_rows'] = rows
    results['runtime_seconds'] = perf_counter() - started
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write-report', action='store_true')
    parser.add_argument('--write-json', action='store_true')
    args = parser.parse_args()
    results = run()
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if args.write_json:
        (ROOT / 'reports/qa/metrics_independent.json').write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.write_report:
        path = ROOT / 'reports/qa/reviewer_metrics.md'
        with path.open('a', encoding='utf-8') as handle:
            handle.write('\n\n## Машинный протокол независимого пересчёта\n\n```json\n')
            handle.write(json.dumps(results, ensure_ascii=False, indent=2))
            handle.write('\n```\n')
