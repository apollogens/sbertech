"""Independent Agent B audit: real artifacts plus controlled temporal fixtures.

Run from repository root: .venv/Scripts/python.exe reports/qa/check_temporal_independent.py
Only writes reports/qa/reviewer_leakage.md; never retrains production artifacts.
"""
import json
import hashlib
import platform
import sys
import traceback
from unittest.mock import patch
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import lightgbm as lgb
import numpy as np
import pandas as pd
from src.baselines import baseline_predict
from src.data import Panel, build_panel, clean_stock, load_panel
from src.features import horizon_features, snapshot, training_data
from src.predict import load_bundle, predict_panel
from src.train import train_model
from src.submission import forecast_frame

RESULTS = []
EVIDENCE = {}


def check(name, function):
    start = perf_counter()
    try:
        function()
        RESULTS.append({'test': name, 'status': 'PASS', 'seconds': round(perf_counter()-start, 3)})
    except Exception:
        RESULTS.append({'test': name, 'status': 'FAIL', 'seconds': round(perf_counter()-start, 3),
                        'traceback': traceback.format_exc()})
    print(json.dumps(RESULTS[-1], ensure_ascii=False), flush=True)


def fixture(days=410):
    rng = np.random.default_rng(124)
    y = rng.poisson(.7, (days, 4)).astype(np.float32)
    s = rng.integers(0, 12, (days, 4)).astype(np.float32)
    s[::3, 0] = np.nan
    return Panel(pd.date_range('2024-01-01', periods=days), y, s,
                 {'warehouses': ['W1', 'W2'], 'articles': ['A1', 'A2']})


def independent_metrics(truth, pred):
    a, p = np.asarray(truth, dtype=np.float64), np.asarray(pred, dtype=np.float64)
    error = p-a
    smapes = []
    for j in range(a.shape[1]):
        valid = (a[:, j]+p[:, j]) > 0
        smapes.append(float(np.mean(200*np.abs(error[valid, j])/(a[valid, j]+p[valid, j]))) if valid.any() else 0.)
    totals = a.sum(axis=0)
    eligible = totals != 0
    ratios = (p.sum(axis=0)[eligible]-totals[eligible])/np.abs(totals[eligible])
    return {'smape': float(np.mean(smapes)), 'wape': float(np.abs(error).sum()/a.sum()*100),
            'rmse': float(np.sqrt(np.square(error).mean())),
            'bias': float(np.abs(ratios).mean()*100),
            'rmsle': float(np.sqrt(np.square(np.log1p(p)-np.log1p(a)).mean())),
            'mean_signed_series_bias': float(ratios.mean()*100),
            'global_signed_volume_bias': float(error.sum()/np.abs(a).sum()*100)}


def future_append_and_order():
    days = pd.date_range('2024-01-01', periods=200).strftime('%Y-%m-%d')
    sales = pd.DataFrame({'date': np.repeat(days, 2), 'warehouse_name': 'W1', 'article': 'A1',
                          'quantity': np.tile([1., 2.], len(days)), 'department': np.tile(['x', 'y'], len(days))})
    stock = sales.iloc[::2].drop(columns=['quantity', 'department']).assign(stock=5.)
    cutoff = days[-1]
    p = build_panel(sales, stock, cutoff=cutoff)
    later_sales = pd.concat([sales, sales.iloc[-1:].assign(date='2026-01-01', article='FUTURE', quantity=999)])
    later_stock = pd.concat([stock, stock.iloc[-1:].assign(date='2026-01-01', article='FUTURE', stock=999)])
    q = build_panel(later_sales, later_stock, cutoff=cutoff)
    r = build_panel(sales.sample(frac=1, random_state=72), stock.sample(frac=1, random_state=73), cutoff=cutoff)
    for other in (q, r):
        assert p.catalogs == other.catalogs
        np.testing.assert_array_equal(p.y, other.y)
        np.testing.assert_array_equal(p.stock, other.stock)
        pd.testing.assert_frame_equal(snapshot(p, 199), snapshot(other, 199))
        b = {'config': {'kind': 'baseline', 'baseline': 'seasonal56'}, 'catalogs': p.catalogs}
        np.testing.assert_array_equal(predict_panel(p, 199, b), predict_panel(other, 199, b))
    assert np.all(p.y == 3)


def stock_policy():
    rows = pd.DataFrame({'date': ['2024-01-01']*9, 'warehouse_name': 'W1',
                         'article': ['a', 'a', 'b', 'b', 'c', 'c', 'd', 'd', 'e'],
                         'stock': [0, 0, 2, 9, -1, 3, -2, -2, 5]})
    cleaned = clean_stock(rows)
    assert dict(zip(cleaned.article, cleaned.stock)) == {'a': 0, 'c': 3, 'e': 5}
    pd.testing.assert_frame_equal(cleaned, clean_stock(cleaned))
    pd.testing.assert_frame_equal(cleaned.sort_values('article').reset_index(drop=True),
                                 clean_stock(rows.sample(frac=1, random_state=32)).sort_values('article').reset_index(drop=True))
    sales = pd.DataFrame({'date': ['2024-01-01'], 'warehouse_name': ['W1'], 'article': ['b'], 'quantity': [1.]})
    try:
        build_panel(sales, rows.loc[rows.article == 'b'])
        raise AssertionError('Conflicting stock silently accepted')
    except ValueError as exc:
        assert 'Conflicting stock duplicates' in str(exc)
    EVIDENCE['stock_policy'] = 'Negative rows removed first; remaining contradictory nonnegative daily keys entirely removed; identical duplicates collapsed. Strict builder rejects contradictory keys.'


def temporal_train_and_feature_parity():
    p = fixture()
    cutoff = 345
    x, y, origins = training_data(p, cutoff)
    changed = Panel(p.dates, p.y.copy(), p.stock.copy(), p.catalogs)
    changed.y[cutoff+1:] = 1e6
    changed.stock[cutoff+1:] = 1e6
    xx, yy, oo = training_data(changed, cutoff)
    pd.testing.assert_frame_equal(x, xx)
    np.testing.assert_array_equal(y, yy)
    assert origins == oo
    offset = 0
    for origin in origins:
        snap = snapshot(p, origin)
        for horizon in (1, 7, 14, 21, 28, 42, 56, 64):
            assert origin+horizon <= cutoff
            inference = horizon_features(snap, p.dates[origin], horizon)
            pd.testing.assert_frame_equal(x.iloc[offset:offset+4].reset_index(drop=True), inference)
            np.testing.assert_array_equal(y[offset:offset+4], p.y[origin+horizon])
            offset += 4
    assert offset == len(x)
    # An independent boundary calculation, not a call to the production means.
    origin = origins[-1]
    snap = snapshot(p, origin)
    np.testing.assert_array_equal(snap.last_y, p.y[origin])
    np.testing.assert_array_equal(snap.mean_28, p.y[origin-27:origin+1].mean(axis=0))
    np.testing.assert_array_equal(snap.mean_180, p.y[origin-179:origin+1].mean(axis=0))
    EVIDENCE['synthetic_training'] = {'origins': origins, 'rows': len(x), 'last_label_index': origins[-1]+64, 'cutoff': cutoff}


def saved_parameters_future_invariance():
    p = fixture()
    changed = Panel(p.dates, p.y.copy(), p.stock.copy(), p.catalogs)
    changed.y[346:] = 1e6
    changed.stock[346:] = 1e6
    a = train_model(p, 345, rounds=2)
    b = train_model(changed, 345, rounds=2)
    assert a['model'].model_to_string() == b['model'].model_to_string()
    np.testing.assert_array_equal(predict_panel(p, 345, a), predict_panel(changed, 345, b))
    EVIDENCE['synthetic_tiny_fit'] = {'rounds': 2, 'identical_serialized_model_strings': True}


def origin_calendar():
    p = fixture()
    for day in ('2024-02-28', '2024-12-31', '2025-12-31'):
        for horizon in (1, 7, 14, 64):
            x = horizon_features(snapshot(p, 200), day, horizon)
            expected = pd.Timestamp(day)+pd.Timedelta(days=horizon)
            assert x.day_of_week.eq(expected.dayofweek).all()
            assert x.month.eq(expected.month).all()
            assert x.horizon.eq(horizon).all()


def real_artifact_schema():
    p = REAL
    assert p.catalogs == BUNDLE['catalogs']
    assert BUNDLE['model'].feature_name() == BUNDLE['config']['features']
    assert BUNDLE['model'].num_trees() == BUNDLE['config']['rounds'] == 220
    x = horizon_features(snapshot(p, len(p.dates)-1), p.dates[-1], 64)
    assert list(x.columns) == BUNDLE['config']['features']
    origins = [p.dates.get_loc(pd.Timestamp(day)) for day in BUNDLE['config']['training_origins']]
    assert max(origins)+64 == len(p.dates)-1
    assert BUNDLE['config']['training_rows'] == len(origins)*8*p.y.shape[1]
    EVIDENCE['real_artifact'] = {'shape': list(p.y.shape), 'dates': [str(p.dates[0].date()), str(p.dates[-1].date())],
                                'features': len(x.columns), 'trees': 220, 'training_rows': BUNDLE['config']['training_rows']}
    if (ROOT/'reports/qa/retraining_reproduction.json').exists():
        verify_retraining_evidence()


def verify_retraining_evidence():
    """Independently inspect root's six completed fits; never calls train_model."""
    from src.train import PARAMS
    reproduction = json.loads((ROOT/'reports/qa/retraining_reproduction.json').read_text(encoding='utf-8'))
    initial = json.loads((ROOT/'reports/qa/initial_manifest.json').read_text(encoding='utf-8'))
    plan = [('lgb_l2_fold1', 192, 'regression', 'reports/oof/lgb_l2_fold1.txt'),
            ('lgb_l2_fold2', 128, 'regression', 'reports/oof/lgb_l2_fold2.txt'),
            ('lgb_tweedie_fold1', 192, 'tweedie', 'reports/oof/lgb_tweedie_fold1.txt'),
            ('lgb_tweedie_fold2', 128, 'tweedie', 'reports/oof/lgb_tweedie_fold2.txt'),
            ('lgb_tweedie_z0.25_fold3', 64, 'tweedie', 'reports/oof/selected_holdout.txt'),
            ('final', 0, 'tweedie', 'model/lightgbm.txt')]
    assert (reproduction['passed'], reproduction['failed'], reproduction['skipped']) == (6, 0, 0)
    assert len(reproduction['fits']) == 6
    by_name = {item['name']: item for item in reproduction['fits']}
    assert set(by_name) == {row[0] for row in plan}
    verified = []
    for name, delta, objective, original_path in plan:
        current_path = ROOT/f'reports/qa/retrained/{name}.txt'
        digest = hashlib.sha256(current_path.read_bytes()).hexdigest()
        original_digest = hashlib.sha256((ROOT/original_path).read_bytes()).hexdigest()
        record = by_name[name]
        assert digest == original_digest == record['model_sha256'] == record['original_sha256']
        assert original_digest == initial[str(Path(original_path))]['sha256']
        model = lgb.Booster(model_file=str(current_path))
        assert model.num_trees() == record['trees'] == 220
        assert model.feature_name() == BUNDLE['config']['features']
        assert model.params['objective'] == objective
        assert model.params['seed'] == 20261018
        assert model.params['num_threads'] == 4
        assert model.params['deterministic'] is True
        assert model.params['force_col_wise'] is True
        if objective == 'tweedie':
            assert model.params['tweedie_variance_power'] == 1.3
        cutoff = len(REAL.dates)-1-delta
        origins = sorted(set(range(179, cutoff-64+1, 35)) | {cutoff-64})
        expected_rows = len(origins)*8*REAL.y.shape[1]
        assert record['training_rows'] == expected_rows
        assert record['cutoff'] == str(REAL.dates[cutoff].date())
        assert record['model_bytes_identical'] is True
        assert record['prediction_max_abs_difference'] <= record['prediction_tolerance']
        if name != 'final':
            assert record['prediction_tolerance'] == record['prediction_max_abs_difference'] == 0.
        verified.append({'name': name, 'sha256': digest, 'matches_original_and_initial_manifest': True,
                         'trees': 220, 'objective': objective, 'training_rows': expected_rows})
    # Reconstruct serialized final training metadata independently, without fitting.
    last = len(REAL.dates)-1
    origins = sorted(set(range(179, last-64+1, 35)) | {last-64})
    expected_config = {'schema_version': 1, 'model_version': 'nonton-v1', 'horizon': 64,
                       'kind': 'lightgbm', 'features': list(horizon_features(snapshot(REAL, 179), REAL.dates[179], 1).columns),
                       'objective': 'tweedie', 'rounds': 220, 'zero_threshold': .25,
                       'training_origins': [str(REAL.dates[o].date()) for o in origins],
                       'training_rows': len(origins)*8*REAL.y.shape[1], 'seed': 20261018,
                       'parameters': dict(PARAMS, objective='tweedie', tweedie_variance_power=1.3)}
    assert expected_config == BUNDLE['config']
    EVIDENCE['independent_retraining_evidence_verification'] = {
        'fits_verified_from_real_files': verified,
        'final_config_independently_reconstructed_equal': True,
        'new_fits_by_reviewer': 0,
        'scope': 'The root reran full fits; independent reviewer checked actual weight bytes, hashes, embedded parameters and metadata. Same environment, not a cross-build reproducibility guarantee.'}
    return EVIDENCE['independent_retraining_evidence_verification']


def artifact_catalog_remap_reproduction():
    # Independently recheck root's guards without modifying artifacts on disk.
    altered = {key: list(value) for key, value in BUNDLE['catalogs'].items()}
    altered['articles'][0], altered['articles'][1] = altered['articles'][1], altered['articles'][0]
    original_read = Path.read_text
    def intercepted(path, *args, **kwargs):
        if path == ROOT/'model/catalogs.json':
            return json.dumps(altered)
        return original_read(path, *args, **kwargs)
    with patch.object(Path, 'read_text', intercepted):
        try:
            load_bundle(ROOT/'model')
            raise AssertionError('Reordered catalog was silently accepted')
        except ValueError as exc:
            assert 'catalog' in str(exc)
    # Sorting guards permutation but cannot establish identity with the training mapping.
    altered = {key: list(value) for key, value in BUNDLE['catalogs'].items()}
    altered['articles'][0] = '!SORTED_BUT_FOREIGN_ID'
    assert altered['articles'] == sorted(altered['articles'])
    with patch.object(Path, 'read_text', intercepted):
        foreign_loaded = load_bundle(ROOT/'model')
    assert foreign_loaded['catalogs'] == altered

    guards = []
    sales = pd.DataFrame({'date': ['2025-01-01', '2025-06-30'], 'warehouse_name': 'W1', 'article': 'A1', 'quantity': [1., 2.]})
    stock = sales.drop(columns='quantity').assign(stock=1.)
    for bad_date in ('2025-1-1', '2025-01-01 00:00:00'):
        invalid = sales.copy()
        invalid.loc[0, 'date'] = bad_date
        try:
            build_panel(invalid, stock)
            raise AssertionError('Malformed date accepted')
        except ValueError:
            guards.append('strict date '+bad_date)
    for frame_kind in ('sales', 'stock', 'aggregation'):
        invalid_sales, invalid_stock = sales.copy(), stock.copy()
        if frame_kind == 'sales':
            invalid_sales.loc[0, 'quantity'] = 1e40
        elif frame_kind == 'stock':
            invalid_stock.loc[0, 'stock'] = 1e40
        else:
            invalid_sales.quantity = 2e38
            invalid_sales = pd.concat([invalid_sales, invalid_sales], ignore_index=True)
        try:
            build_panel(invalid_sales, invalid_stock)
            raise AssertionError('Float32 overflow accepted')
        except ValueError as exc:
            assert 'range' in str(exc)
            guards.append('float32 '+frame_kind)
    for field, value in (('kind', 'invalid'), ('zero_threshold', -1.), ('zero_threshold', float('nan'))):
        invalid_config = dict(BUNDLE['config'], **{field: value})
        def invalid_config_read(path, *args, **kwargs):
            if path == ROOT/'model/config.json':
                return json.dumps(invalid_config)
            return original_read(path, *args, **kwargs)
        with patch.object(Path, 'read_text', invalid_config_read):
            try:
                load_bundle(ROOT/'model')
                raise AssertionError('Invalid model config accepted')
            except ValueError:
                guards.append('config '+field+' '+str(value))
    try:
        forecast_frame(np.arange(128).reshape(2, 64), '2025-06-30', {'warehouses': ['W1'], 'articles': ['A1', 'A2']})
        raise AssertionError('Wrong forecast axes accepted')
    except ValueError as exc:
        assert 'shape' in str(exc)
        guards.append('forecast shape axes')
    EVIDENCE['root_guards_independent_revalidation'] = guards
    EVIDENCE['catalog_artifact_integrity_gap'] = {'before_fix_swapped_mapping_accepted': True,
                                                'after_fix_swapped_mapping_rejected': True,
                                                'sorted_foreign_id_still_accepted': True,
                                                'production_artifacts_modified': False,
                                                'mechanism': 'Mock substitutes only the catalog JSON read; genuine config and genuine LightGBM file are loaded.'}


def real_fixed_origin_future_perturb():
    p = REAL
    origin = len(p.dates)-193
    model = lgb.Booster(model_file=str(ROOT/'reports/oof/lgb_tweedie_fold1.txt'))
    b = dict(BUNDLE, model=model)
    changed = Panel(p.dates, p.y.copy(), p.stock.copy(), p.catalogs)
    changed.y[origin+1:] = 999999
    changed.stock[origin+1:] = 999999
    pd.testing.assert_frame_equal(snapshot(p, origin), snapshot(changed, origin))
    a = predict_panel(p, origin, b)
    z = predict_panel(changed, origin, b)
    np.testing.assert_array_equal(a, z)
    EVIDENCE['real_future_perturbation'] = {'origin': str(p.dates[origin].date()), 'max_abs_prediction_difference': float(np.max(np.abs(a-z)))}


def real_baseline_reproduction():
    values = []
    for fold, origin in enumerate([len(REAL.dates)-193, len(REAL.dates)-129, len(REAL.dates)-65], 1):
        for kind in ('zero', 'last', 'mean28', 'mean90', 'seasonal56', 'tsb'):
            actual = baseline_predict(REAL, origin, kind)
            with np.load(ROOT/f'reports/oof/{kind}_fold{fold}.npz') as saved:
                np.testing.assert_array_equal(actual, saved['prediction'])
            values.append({'fold': fold, 'baseline': kind, 'max_abs_difference': 0.})
    EVIDENCE['baseline_oof_reproduction'] = values


def real_ml_reproduction_and_history():
    values = []
    thresholds = []
    for fold, origin in enumerate([len(REAL.dates)-193, len(REAL.dates)-129, len(REAL.dates)-65], 1):
        path = f'reports/oof/lgb_tweedie_fold{fold}.txt' if fold < 3 else 'reports/oof/selected_holdout.txt'
        model = lgb.Booster(model_file=str(ROOT/path))
        bundle = dict(BUNDLE, model=model)
        full = predict_panel(REAL, origin, bundle)
        with np.load(ROOT/f'reports/oof/lgb_tweedie_z0.25_fold{fold}.npz') as saved:
            np.testing.assert_array_equal(full, saved['prediction'])
            assert str(saved['origin']) == str(REAL.dates[origin].date())
        short = Panel(REAL.dates[origin-179:origin+1], REAL.y[origin-179:origin+1], REAL.stock[origin-179:origin+1], REAL.catalogs)
        limited = predict_panel(short, 179, bundle)
        truth = REAL.y[origin+1:origin+65]
        a = snapshot(REAL, origin)
        z = snapshot(short, 179)
        changed_features = [c for c in a if not np.array_equal(a[c], z[c], equal_nan=True)]
        values.append({'fold': fold, 'origin': str(REAL.dates[origin].date()), 'full_days': origin+1,
                       'full_oof_max_abs_difference': 0., 'short_full_max_abs_difference': float(np.max(np.abs(full-limited))),
                       'short_full_changed_predictions': int(np.count_nonzero(full != limited)),
                       'changed_features': changed_features, 'full_metrics': independent_metrics(truth, full),
                       'short_metrics': independent_metrics(truth, limited)})
        stack = [tree['tree_structure'] for tree in model.dump_model()['tree_info']]
        relevant = []
        while stack:
            node = stack.pop()
            if 'split_feature' in node:
                if model.feature_name()[node['split_feature']] == 'long_mean':
                    relevant.append({'threshold': node['threshold'], 'gain': node['split_gain']})
                stack.extend([node['left_child'], node['right_child']])
        thresholds.append({'fold': fold, 'long_mean_splits': len(relevant),
                           'minimum_threshold': min([v['threshold'] for v in relevant], default=None),
                           'maximum_threshold': max([v['threshold'] for v in relevant], default=None)})
    EVIDENCE['full_vs_180_and_ml_oof_reproduction'] = values
    EVIDENCE['long_mean_tree_thresholds'] = thresholds


def catalog_future_effects():
    p = fixture(250)
    before = snapshot(p, 210)
    # Permitting a future-only article to expand a catalog changes historical hierarchical aggregates.
    y = np.zeros((250, 6), dtype=np.float32)
    s = np.full_like(y, np.nan)
    y[:, [0, 1, 3, 4]] = p.y
    s[:, [0, 1, 3, 4]] = p.stock
    expanded = Panel(p.dates, y, s, {'warehouses': ['W1', 'W2'], 'articles': ['A1', 'A2', 'FUTURE']})
    after = snapshot(expanded, 210).iloc[[0, 1, 3, 4]].reset_index(drop=True)
    assert not np.array_equal(before.warehouse_mean_28, after.warehouse_mean_28)
    # It is not a competition defect: official output mandates a fixed catalog, and cutoff-aware builder filters first.
    sales = pd.read_csv(Path(r'C:/Users/apollo/Desktop/выборка/sales_dataset_hakaton_train.csv'),
                        usecols=['date', 'warehouse_name', 'article'], dtype=str)
    selection = json.loads((ROOT/'reports/selection_frozen.json').read_text(encoding='utf-8'))
    count = []
    for origin in selection['fold_origins']:
        past = sales.loc[sales.date <= origin]
        count.append({'origin': origin, 'articles': past.article.nunique(), 'warehouses': past.warehouse_name.nunique(),
                      'observed_pairs': int(past[['warehouse_name', 'article']].drop_duplicates().shape[0]),
                      'future_only_articles': len(set(sales.article)-set(past.article))})
    EVIDENCE['catalog'] = {'expansion_can_change_past_warehouse_means': True, 'actual_fold_counts': count,
                           'fixed_official_grid': len(REAL.catalogs['articles'])*len(REAL.catalogs['warehouses'])}
    assert count[-1]['articles'] == len(REAL.catalogs['articles'])
    assert all(v['warehouses'] == len(REAL.catalogs['warehouses']) for v in count)
    EVIDENCE['initial_run'] = {'passed': 9, 'failed': 1,
                              'failure': 'Reviewer assumption that all 799 articles were observed by each fold was false: first fold has 793. The official catalog is fixed, so this assertion was replaced with a measured count rather than called a production target-leakage defect.'}


def report():
    passed = sum(item['status'] == 'PASS' for item in RESULTS)
    failed = len(RESULTS)-passed
    out = ['# Независимый ML/temporal audit — Agent B', '',
           'Исполнен 18 октября 2026 года в D:\\SberTech. Это независимый запуск текущего кода и реальных сохранённых моделей. '
           'Reviewer не перезапускал полное обучение; отдельное воспроизведение root проверяется ниже по сохранённым весам.', '',
           f'Команда: `.venv\\Scripts\\python.exe reports/qa/check_temporal_independent.py`. Результат: **{passed} PASS, {failed} FAIL, 0 SKIP**.', '',
           f'Среда: Python {platform.python_version()}, NumPy {np.__version__}, pandas {pd.__version__}, LightGBM {lgb.__version__}; {platform.platform()}.', '',
           '## Область и зависимости', '',
           '`src/data.py` → Panel; `src/features.py` → snapshot/horizon_features/training_data; `src/train.py` → train_model; '
           '`src/baselines.py` и `src/predict.py` → inference. Просмотрены scripts/run_pipeline.py, train_final.py, backtest_baselines.py, '
           'prepare_api_inputs.py, predict.py, verify_parity.py, audit_inputs.py, tests/test_pipeline.py, model/config.json, selection_frozen.json, '
           'training_benchmarks.json, detailed_audit.json, model_selection.md, independent_review.md и оригинальное ТЗ markdown hakaton.md.', '',
           '## Выводы и ограничения', '',
           '- Подтверждённой temporal target leakage в выполненных ветках не обнаружено. Каждый synthetic training label выровнен с origin+h; '
           'последняя label не позднее cutoff. Изменение будущего не меняет features, labels и строки сериализованной tiny-модели.',
           '- Все baseline OOF на трёх окнах и выбранные LightGBM OOF воспроизведены текущим кодом и реальными артефактами с точной численной идентичностью. '
           + ('Root дополнительно повторил все 6 полных fits; reviewer независимо проверил реальные файлы весов, hashes и параметры. '
              'Все 6 побитово совпадают с исходниками и initial_manifest; ограничение невоспроизведённого полного обучения снято.'
              if 'independent_retraining_evidence_verification' in EVIDENCE else
              'Полное переобучение прежних fold-моделей не проводилось, потому отсутствие скрытой модификации их исходного обучения не доказывается одной сериализацией.'),
           '- `scripts/run_pipeline.py` использует одинаковые окна/ключи для кандидатов, выбирает objective и threshold по fold 1/2 и записывает выбор до fold 3. '
           'Факт исторического порядка действий подтверждён кодом и сохранёнными файлами, а не независимым журналом из прошлого. Разница top-2 мала; устойчивое превосходство не доказано.',
           '- `src/features.py:21` long_mean зависит от всей предоставленной истории. Другие признаки ограничены максимум 180 днями. '
           'Результаты full/180 приведены по фактическому инференсу ниже; равенство здесь не является математической гарантией для других входов.',
           '- `src/data.py:37` clean_stock удаляет сначала negative, затем неоднозначные оставшиеся daily keys. Это консервативная политика, '
           'а не восстановленный истинный остаток. При [-1,3] сохраняется 3; при [2,9] удаляются обе строки. '
           'Строгий builder/API отвергает конфликтный сырой файл; предусмотрена явная подготовка через prepare_api_inputs.py.',
           '- `prepare_cache` формирует каталог из всей истории. Добавление future-only ID при глобальном расширении каталога способно менять past warehouse_mean '
           'и integer categorical mapping; это ограничение при переносе на открытый каталог. В официальной задаче каталог фиксирован 11×799. '
           'На первом validation origin реально наблюдались 793 article, на двух следующих — 799; во всех трёх окнах 11 warehouse. '
           'Следовательно, fold1 использует 6 future-only article IDs в фиксированном каталоге. Это transductive knowledge пространства ID; '
           'реальные будущие quantity/stock не используются. Оценку open-catalog deployment этот протокол не доказывает.',
           '- Исправление root независимо подтверждено: `load_bundle` теперь отвергает перестановку categorical ID по проверке sorted order, '
           'которая соответствует фактическому training encoder catalog_from_sales. Текущие bundle/catalog/cache согласованы; '
           'реальные OOF по-прежнему воспроизводятся точно.',
           '- Residual limitation P2: sorted order не заменяет fingerprint каталога. Валидный отсортированный каталог с другим ID '
           'по-прежнему принимается; это отдельно воспроизведено через mock чтения JSON без изменения файлов. '
           'Риск относится к неверной ручной комплектации чужими artifacts, не к обнаруженной порче текущего bundle. '
           'Минимальное дальнейшее усиление: persist canonical catalog fingerprint/model checksum и сверять при загрузке.',
           '- Отдельно независимо исполнены root guards: нестрогая дата, float32 overflow sales/stock и после aggregation, '
           'неизвестный kind, отрицательный/NaN threshold, неверные оси forecast shape — всё отвергается.',
           '- Уточнение воспроизводимости аудита: первоначальный запуск дал 9 PASS/1 FAIL на неверном предположении ревьюера, '
           'что каждый ID уже наблюдался на каждом fold. Этот результат сохранён в evidence initial_run; тест заменён измерением actual catalog counts '
           'в соответствии с официальным fixed-catalog scope. Это исправление тестовой предпосылки, не исправление production-кода.',
           '- Reviewer лично не запускал container benchmark и HTTP API; они принадлежат общему аудиту. '
           'Синтетические tiny fit имеют 2 дерева и проверяют только temporal invariance, не качество. '
           'Full training reproduction выполнено root и независимо проверяется по сохранённым весам и metadata при наличии retraining_reproduction.json.', '',
           '## Исправленный P2 и оставшееся ограничение артефактов', '',
           'Файл: `src/predict.py`, функция `load_bundle`, чтение `catalogs.json` и проверка feature schema. '
           'Repro: тест `root_guards_and_catalog_remap_rejection` подменяет только read_text каталога на JSON с двумя переставленными article IDs; '
           'настоящие config и LightGBM model читаются с диска. Ожидание усиленного integrity-контракта: несогласованный mapping отвергается. '
           'До root fix load_bundle принимал перестановку; после fix отвергает её. Исправление принято reviewer независимо. '
           'Дополнительный negative probe заменяет первый ID на другой с сохранением sorted order: load_bundle принимает такой каталог. '
           'Это оставшееся ограничение fingerprint P2: текущие артефакты согласованы, риск возникает при неверной ручной сборке bundle. '
           'Предложение: хранить canonical catalog fingerprint при training/export и проверять при загрузке; '
           'применение такого изменения требует повторной artifact parity, но не меняет признаки и не требует переобучения деревьев. '
           'Статус: root permutation guard проверен; fingerprint limitation раскрыт. Этим read-only reviewer production artifacts не изменялись.', '',
           '## Результаты тестов', '',
           '```json', json.dumps(RESULTS, ensure_ascii=False, indent=2), '```', '',
           '## Измеренные доказательства', '', '```json', json.dumps(EVIDENCE, ensure_ascii=False, indent=2), '```', '',
           '## Независимый verdict', '',
           ('CONDITIONAL PASS для temporal/features/inference paths: подтверждённых P0/P1 здесь не найдено. '
            'Итоговый release verdict требует отдельной проверки scoring/API/Docker/submission главным QA.' if not failed else
            'FAIL для проверенного объёма: присутствуют неуспешные проверки; см. traceback. Это не автоматическая классификация каждой ошибки как P0.')]
    (ROOT/'reports/qa/reviewer_leakage.md').write_text('\n'.join(out)+'\n', encoding='utf-8')
    print(json.dumps({'passed': passed, 'failed': failed, 'report': 'reports/qa/reviewer_leakage.md'}), flush=True)


if __name__ == '__main__':
    REAL = load_panel(ROOT/'cache')
    BUNDLE = load_bundle(ROOT/'model')
    if '--verify-retraining-only' in sys.argv:
        verified = verify_retraining_evidence()
        target = ROOT/'reports/qa/reviewer_leakage.md'
        previous = target.read_text(encoding='utf-8')
        previous = previous.replace('Это независимый запуск текущего кода и реальных сохранённых моделей; production training не запускался.',
                                    'Это независимый запуск текущего кода и реальных сохранённых моделей. Reviewer не перезапускал полное обучение; отдельное воспроизведение root проверено ниже по сохранённым весам.')
        previous = previous.replace('Полное переобучение прежних fold-моделей не проводилось, потому отсутствие скрытой модификации их исходного обучения не доказывается одной сериализацией.',
                                    'Root повторил все 6 полных fits; reviewer независимо сверил файлы весов, hashes, встроенные параметры и metadata. Все 6 побитово совпадают с исходниками и initial_manifest; ограничение невоспроизведённого полного обучения снято.')
        previous = previous.replace('Не выполнены independent full retraining, container benchmark и HTTP API; они принадлежат общему аудиту.',
                                    'Reviewer лично не выполнял container benchmark и HTTP API. Full training reproduction выполнено root; сохранённые веса и metadata независимо проверены reviewer без повторного fit.')
        marker = '\n## Независимая проверка полного переобучения\n'
        previous = previous.split(marker)[0]
        previous += marker+'\nКоманда: `.venv\\Scripts\\python.exe reports/qa/check_temporal_independent.py --verify-retraining-only`. '
        previous += 'Независимо подтверждены **6/6** файлов моделей: SHA256 новых весов = SHA256 исходников = initial_manifest, 220 деревьев, objective, seed, threads, deterministic flags, training rows и cutoff. '
        previous += 'Финальный config независимо восстановлен из текущего feature schema, origins и frozen parameters без fit и точно совпал. '
        previous += 'Сами 6 fits исполнил root, reviewer их повторно не запускал. Одинаковые веса вместе с прежде независимо воспроизведённым inference подтверждают сохранение прогнозов; новые quality improvements не заявляются. '
        previous += 'Проверка остаётся ограничена текущими installed builds. Residual catalog fingerprint limitation P2 остаётся раскрытым.\n\n```json\n'+json.dumps(verified, ensure_ascii=False, indent=2)+'\n```\n'
        target.write_text(previous, encoding='utf-8')
        print(json.dumps({'retrained_files_independently_verified': 6, 'new_fits': 0, 'report': str(target)}))
        raise SystemExit(0)
    for name, test in [('future_append_new_id_fixed_cutoff_row_order_sales_aggregation', future_append_and_order),
                       ('stock_duplicate_negative_and_shuffle_policy', stock_policy),
                       ('training_boundary_label_alignment_feature_parity', temporal_train_and_feature_parity),
                       ('tiny_saved_model_future_parameter_invariance', saved_parameters_future_invariance),
                       ('calendar_leap_year_and_year_boundaries', origin_calendar),
                       ('real_artifact_schema_catalog_and_training_origins', real_artifact_schema),
                       ('root_guards_and_catalog_remap_rejection', artifact_catalog_remap_reproduction),
                       ('real_model_future_perturbation_invariance', real_fixed_origin_future_perturb),
                       ('real_all_18_baseline_oof_reproduction', real_baseline_reproduction),
                       ('real_ml_3fold_oof_reproduction_and_full_vs_180', real_ml_reproduction_and_history),
                       ('future_catalog_expansion_and_actual_fold_catalogs', catalog_future_effects)]:
        check(name, test)
    report()
    raise SystemExit(any(item['status'] != 'PASS' for item in RESULTS))
