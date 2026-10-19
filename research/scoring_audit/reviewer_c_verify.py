"""Reviewer C: saved forecast and release verification; never fits a model.

Uses the original official scalar primitives, not src.metrics or another audit.
Run from any directory: .venv/Scripts/python.exe research/scoring_audit/reviewer_c_verify.py
"""
from pathlib import Path
import hashlib
import json
import sys
import time
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from scripts import official_score as official

METRICS = list(official.METRIC_WEIGHTS)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def score(y, p):
    # Explicit float64 matches compute_all_metrics' post-merge coercion.
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    smapes = [official.smape_series(y[:, i], p[:, i]) for i in range(y.shape[1])]
    biases = [official.bias_abs_series(y[:, i], p[:, i]) for i in range(y.shape[1])]
    eligible = [value for value in biases if value is not None]
    den = (np.abs(y) + np.abs(p)) / 2
    written = np.divide(np.abs(y-p), den, out=np.zeros_like(y), where=den > 0)
    return dict(smape=float(np.mean(smapes)), wape=official.wape(y, p),
                rmse=official.rmse(y, p), bias=float(np.mean(eligible)) if eligible else 0.,
                rmsle=official.rmsle(y, p), smape_text=float(written.mean(axis=0).mean()*100),
                bias_eligible_series=len(eligible), bias_excluded_series=y.shape[1]-len(eligible))


def main():
    started = time.perf_counter()
    old = pd.read_csv(ROOT/'reports/remediation/experiment_matrix.csv')
    new = pd.read_csv(ROOT/'research/experiment_results.csv')
    legacy = pd.read_csv(ROOT/'reports/experiment_results.csv')
    assert len(old) == 85 and len(new) == 35
    with np.load(ROOT/'cache/panel.npz') as z:
        dates = pd.DatetimeIndex(z['dates'])
        truth = z['y']
    catalogs = json.loads((ROOT/'cache/catalogs.json').read_text(encoding='utf-8'))
    assert len(catalogs['warehouses']) == 11 and len(catalogs['articles']) == 799
    tasks = []
    for source, table in [('remediation', old), ('architecture', new)]:
        assert not table.duplicated(['model', 'origin']).any()
        for row in table.to_dict('records'):
            path = ROOT/(row['prediction_path'] if source == 'architecture' else
                         f"reports/remediation/predictions/{row['model']}_{row['origin']}.npz")
            tasks.append((source, row['model'], row, path))
    for path in sorted((ROOT/'reports/oof').glob('*.npz')):
        model, fold = path.stem.rsplit('_fold', 1)
        matches = legacy[(legacy.model == model) & (legacy.fold == int(fold))]
        assert len(matches) == 1, path
        tasks.append(('legacy_oof', model, matches.iloc[0].to_dict(), path))
    assert len(tasks) == 151
    rows = []
    seen = {}
    measured = {}
    for source, model, row, path in tasks:
        digest = sha(path)
        with np.load(path, allow_pickle=False) as z:
            assert set(z.files) == {'origin', 'prediction'}, path
            origin = str(z['origin'].item())
            p = z['prediction']
        assert origin == row['origin'], path
        assert p.shape == (64, 8789) and np.isfinite(p).all() and (p >= 0).all(), path
        index = dates.get_loc(origin)
        y = truth[index+1:index+65]
        assert y.shape == p.shape
        array_sha = hashlib.sha256(np.ascontiguousarray(p, dtype=np.float64).tobytes()).hexdigest()
        key = (origin, array_sha)
        if key not in measured:
            measured[key] = score(y, p)
            seen[key] = f'{source}:{model}:{origin}'
        values = measured[key]
        comparisons = [abs(values[m] - float(row[m])) for m in METRICS + ['smape_text']]
        error = max(comparisons)
        assert error < 1e-9, (path, error)
        has_recorded_sha = isinstance(row.get('prediction_sha256'), str)
        if has_recorded_sha:
            assert digest == row['prediction_sha256'], path
        role = 'terminal_diagnostic' if origin == '2026-05-28' else 'development'
        rows.append(dict(source=source, model=model, origin=origin, role=role,
                         path=path.relative_to(ROOT).as_posix(), file_sha256=digest,
                         canonical_float64_sha256=array_sha, duplicate_of=seen[key],
                         file_hash_compared_to_original_csv=has_recorded_sha,
                         shape='64x8789', dtype=str(p.dtype), max_csv_metric_error=error,
                         first_forecast=str(dates[index+1].date()),
                         last_forecast=str(dates[index+64].date()), **values))
        print(f'{len(rows)}/{len(tasks)} {source} {model} {origin}', flush=True)
    result = pd.DataFrame(rows)
    result.to_csv(OUT/'reviewer_c_metrics.csv', index=False)
    unique = result.drop_duplicates(['origin', 'canonical_float64_sha256'])
    unique.to_csv(OUT/'reviewer_c_unique_forecasts.csv', index=False)
    manifest_path = ROOT/'reports/remediation/delivery_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    release = []
    for entry in manifest['files']:
        path = ROOT/entry['path']
        release.append(dict(path=entry['path'], expected_sha256=entry['sha256'],
                            measured_sha256=sha(path), size_ok=path.stat().st_size == entry['bytes']))
    assert len(release) == 409
    assert all(r['size_ok'] and r['expected_sha256'] == r['measured_sha256'] for r in release)
    pd.DataFrame(release).to_csv(OUT/'reviewer_c_release_hashes.csv', index=False)
    archive = Path(manifest['archive'])
    assert sha(archive) == manifest['archive_sha256']
    assert archive.stat().st_size == manifest['archive_bytes']
    with zipfile.ZipFile(archive) as z:
        bad_zip_member = z.testzip()
        assert bad_zip_member is None
    summary = dict(no_training=True, forecast_files_checked=len(rows),
                   source_counts=result.source.value_counts().to_dict(),
                   unique_numerical_forecasts=len(unique), duplicate_file_forecasts=len(rows)-len(unique),
                   original_csv_hash_checks=int(result.file_hash_compared_to_original_csv.sum()),
                   max_csv_metric_error=float(result.max_csv_metric_error.max()),
                   release_files_matched=len(release), release_archive_sha256=sha(archive),
                   release_zip_crc_check_passed=True, scorer_sha256=sha(ROOT/'scripts/official_score.py'),
                   panel_sha256=sha(ROOT/'cache/panel.npz'), catalog_sha256=sha(ROOT/'cache/catalogs.json'),
                   delivery_manifest_sha256=sha(manifest_path),
                   seconds=time.perf_counter()-started,
                   limitations=['NPZ has no series identifiers: column order relies on frozen cache/catalog contract.',
                                'CSV hash checks apply to 120 remediation/architecture forecasts; legacy OOF current hashes are inventoried, not authenticated by the metrics CSV.',
                                'Numerical dedup is exact float64 byte equality at the same origin, never metric similarity.',
                                'Full 562496-row compute_all_metrics merge not run; exact original scalar primitives applied to all 8789 columns.'])
    (OUT/'reviewer_c_verification.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
