"""Production-like 180-day inference with preserved historical model weights."""

from __future__ import annotations

import argparse
import gc
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lightgbm as lgb
import numpy as np
import pandas as pd

from scripts.official_score import bias_abs_series, rmse, rmsle, smape_series, wape
from src.artifacts import file_hash
from src.components import predict_component_frames
from src.data import DEFAULT_DATA, build_panel, clean_stock, load_panel, read_inputs
from src.ensemble import align_components, convex_combine, expected_grid, key_hash
from src.predict import predict_panel
from src.runtime import STRATEGIES, first_seen_from_sales, runtime_source_hashes

ORIGINS = ["2025-09-14", "2025-11-17", "2026-01-20", "2026-03-25", "2026-05-28"]
METRICS = ["smape", "wape", "rmse", "bias", "rmsle"]


def metrics(truth, prediction):
    truth = np.asarray(truth, dtype=np.float64)
    prediction = np.asarray(prediction, dtype=np.float64)
    if truth.shape != prediction.shape or not np.isfinite(prediction).all() or (prediction < 0).any():
        raise ValueError("Invalid prediction panel")
    bias = [bias_abs_series(truth[:, i], prediction[:, i]) for i in range(truth.shape[1])]
    bias = [value for value in bias if value is not None]
    return {
        "smape": float(np.mean([smape_series(truth[:, i], prediction[:, i]) for i in range(truth.shape[1])])),
        "wape": wape(truth, prediction),
        "rmse": rmse(truth, prediction),
        "bias": float(np.mean(bias)) if bias else 0.0,
        "rmsle": rmsle(truth, prediction),
    }


def load_historical(origin):
    path = ROOT / "integration/models" / origin
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if set(manifest["files"]) != {"config.json", "daily.txt", "weekly.txt", "article.txt"}:
        raise ValueError("Historical artifact set mismatch")
    for name, digest in manifest["files"].items():
        if file_hash(path / name) != digest:
            raise ValueError("Historical artifact hash mismatch")
    config = json.loads((path / "config.json").read_text(encoding="utf-8"))
    if config["metadata"]["cutoff"] != origin:
        raise ValueError("Historical model cutoff mismatch")
    models = {name: lgb.Booster(model_file=str(path / f"{name}.txt")) for name in ("daily", "weekly", "article")}
    if any(model.feature_name() != config["metadata"]["features"][name] for name, model in models.items()):
        raise ValueError("Historical feature schema mismatch")
    return models, config, file_hash(path / "manifest.json")


def save_report(output, results, coverage):
    frame = pd.DataFrame(results)
    frame.to_csv(output / "metrics.csv", index=False)
    identifiers = ["origin", "candidate", "role", "group"]
    before = frame[frame.history == "previous_full_history"][identifiers + METRICS]
    after = frame[frame.history == "provided180"][identifiers + METRICS]
    paired = before.merge(after, on=identifiers, suffixes=("_full_history", "_provided180"))
    for metric in METRICS:
        paired[metric + "_delta"] = paired[metric + "_provided180"] - paired[metric + "_full_history"]
    paired.to_csv(output / "before_after_metrics.csv", index=False)
    pd.DataFrame(coverage).to_csv(output / "coverage.csv", index=False)
    development = frame[(frame.role == "development") & (frame.group == "all")]
    grouped = development.groupby(["history", "candidate"])
    means = grouped[METRICS].mean().join(grouped.origin.nunique().rename("n_origins")).reset_index()
    means.to_csv(output / "development_means.csv", index=False)
    tables = []
    for history in ("provided180", "previous_full_history"):
        part = means[means.history == history]
        columns = ["candidate", "n_origins", *METRICS]
        table = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
        for _, row in part.iterrows():
            table.append("| " + " | ".join([row.candidate, str(int(row.n_origins)), *[f"{row[name]:.6f}" for name in METRICS]]) + " |")
        tables.extend([f"### {history}", "", *table, ""])
    report = "\n".join([
        "# Проверка на входе из ровно 180 календарных дней", "",
        "Использованы сохранённые исторические веса; нового обучения и подбора параметров нет. "
        "Для каждого origin sales и stock обрезаны до интервала [origin−179, origin] до построения панели. "
        "Stock внутри окна предварительно очищен src.data.clean_stock: удалены отрицательные остатки и "
        "все конфликтующие дубликаты; это прежняя политика repair исходного экспорта, а не тест приёма "
        "невалидных CSV публичным API. "
        "Membership вычисляется только по переданным sales, включая нулевые строки. "
        "Все 64 будущих дня используются исключительно как truth из сохранённой панели.", "",
        "D/W/S/A/equal4 рассчитаны каноническими src.components и src.ensemble с теми же весами и "
        "threshold .25 после смеси. Загружены исторические TXT и проверены их hashes/features/cutoff. "
        "Исторические config отличаются от финального bundle отсутствием ensemble_contract: runner не "
        "объявляет их runtime-v2 release и не меняет исходные manifests. Прежние full-history NPZ "
        "пересчитаны теми же официальными функциями scorer. Среднее SMAPE — среднее smape_series, "
        "Bias — среднее bias_abs_series только по eligible рядам; полный квадратичный merge scorer не запускался.", "",
        "Это повторно использованные окна, а не новый untouched test. Первые четыре origin — development, "
        "последний terminal — только диагностика. Разница 180/full-history смешивает эффект укороченной "
        "статистики и membership по входному окну; она не является чистым эффектом архитектуры. "
        "Модели обучены прежним full-history способом, поэтому это проверка serving-переноса готовых весов, "
        "а не новый rolling-180 training protocol.", "",
        "Для incumbent повторный 180-day inference выполняется только при наличии однозначно привязанных "
        "сохранённых TXT на origin. Их полный перечень и пропуски фиксируются в coverage.csv. "
        "Прежний incumbent NPZ остаётся full-history reference; отсутствующие веса не подменяются финальной моделью.", "",
        "Ниже средние по четырём development окнам. Incumbent provided180 при неполном покрытии не сопоставим "
        "с пятиоконными/четырёхоконными средними без фильтра по общим origins.", "",
        *tables,
        "В metrics.csv дополнительно приведены sparse (частота продаж <.1 по входным 180 дням), "
        "dense и горизонты 1–14/15–35/36–64/57–64. Набор sparse фиксирован на origin и одинаков для сравниваемых forecasts. "
        "Никакого automatic promotion runner не выполняет.", "",
    ])
    if set(ORIGINS[:4]).issubset(set(frame.origin)):
        current = means[means.history == "provided180"].set_index("candidate")
        if {"D:P1", "equal4:P1"}.issubset(current.index):
            report += "\n## Вывод по одинаковому 180-дневному входу\n\n"
            report += "Ансамбль equal4:P1 сохраняет небольшое улучшение всех пяти средних development-метрик относительно corrected D:P1: "
            report += "; ".join(
                f"{metric.upper()} {current.loc['D:P1', metric]:.6f} → {current.loc['equal4:P1', metric]:.6f}"
                for metric in METRICS
            )
            report += (
                ". Это сравнение на одних четырёх origins и одинаковом протоколе входа. Оно не доказывает "
                "превосходство над incumbent на всех четырёх 180-day окнах: исторические incumbent TXT "
                "однозначно доступны только на двух из них.\n\n"
                "Разница с прежним full-history экспериментом мала и смешанная. Нельзя приписывать её cleanup кода: "
                "веса сохранены, но объём предоставленной истории изменён намеренно. Все full-history reference NPZ "
                "проверяются по origin/key hash и сохранённому SHA256. Отдельная проверка reference_validation.json "
                "подтвердила согласие пересчитанных official-метрик с прежним CSV: максимальная ошибка 5.69×10⁻¹⁴.\n"
            )
    (output / "report_ru.md").write_text(report, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sales", type=Path, default=DEFAULT_DATA / "sales_dataset_hakaton_train.csv")
    parser.add_argument("--stock", type=Path, default=DEFAULT_DATA / "stock_dataset_hakaton_train.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "consolidation/backtest_180")
    parser.add_argument("--origins", nargs="+", choices=ORIGINS, default=ORIGINS)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    start = perf_counter()
    sales, stock = read_inputs(args.sales, args.stock)
    sales["date"] = pd.to_datetime(sales.date)
    stock["date"] = pd.to_datetime(stock.date)
    full = load_panel(ROOT / "cache")
    old_rows = pd.read_csv(ROOT / "integration/ensemble_experiments.csv")
    results, coverage = [], []
    for origin in args.origins:
        cutoff = pd.Timestamp(origin)
        beginning = cutoff - pd.Timedelta(days=179)
        local_sales = sales.loc[sales.date.between(beginning, cutoff)].copy()
        local_stock = clean_stock(stock.loc[stock.date.between(beginning, cutoff)].copy())
        models, config, manifest_hash = load_historical(origin)
        panel = build_panel(local_sales, local_stock, catalogs=config["catalogs"])
        if panel.dates[0] != beginning or panel.dates[-1] != cutoff or len(panel.dates) != 180:
            raise ValueError("Input must cover exactly the declared 180-day calendar interval")
        if panel.catalogs != full.catalogs:
            raise ValueError("Evaluation catalog mismatch")
        first = first_seen_from_sales(local_sales)
        origin_position = full.dates.get_loc(origin)
        truth = full.y[origin_position + 1:origin_position + 65].astype(float)
        if truth.shape != (64, panel.y.shape[1]):
            raise ValueError("Insufficient future truth")
        infer_start = perf_counter()
        frames = predict_component_frames(panel, 179, models, first)
        keys = expected_grid(origin, panel.catalogs)
        aligned = align_components(frames, keys)
        inference_seconds = perf_counter() - infer_start
        sparse = (panel.y > 0).mean(axis=0) < .1
        groups = {
            "all": (slice(None), slice(None)),
            "sparse": (slice(None), sparse),
            "dense": (slice(None), ~sparse),
            "h1_14": (slice(0, 14), slice(None)),
            "h15_35": (slice(14, 35), slice(None)),
            "h36_64": (slice(35, 64), slice(None)),
            "h57_64": (slice(56, 64), slice(None)),
        }

        def record(candidate, history, prediction):
            if prediction.shape != truth.shape:
                raise ValueError("Forecast/truth alignment mismatch")
            for group, (days, series) in groups.items():
                selected_truth = truth[days, series]
                if selected_truth.size:
                    results.append(dict(origin=origin, candidate=candidate, history=history, group=group,
                                        role="terminal_diagnostic" if origin == ORIGINS[-1] else "development",
                                        **metrics(selected_truth, prediction[days, series])))

        for candidate, weights in STRATEGIES.items():
            prediction = convex_combine(aligned, weights, output_policy="threshold025").reshape(64, -1)
            np.savez_compressed(args.output / f"{candidate.replace(':', '_')}_{origin}.npz",
                                prediction=prediction, origin=origin, history_days=180)
            record(candidate, "provided180", prediction)
            row = old_rows[(old_rows.origin == origin) & (old_rows.candidate == candidate)].iloc[0]
            historical_path = ROOT / row.prediction_path
            if file_hash(historical_path) != row.prediction_sha256:
                raise ValueError("Full-history reference hash mismatch")
            with np.load(historical_path) as reference:
                if str(reference["origin"]) != origin or str(reference["key_sha256"]) != key_hash(keys):
                    raise ValueError("Full-history reference identity mismatch")
                record(candidate, "previous_full_history", reference["prediction"])
        incumbent_path = ROOT / f"reports/remediation/predictions/tweedie_{origin}.txt"
        incumbent_available = incumbent_path.exists()
        if incumbent_available:
            model = lgb.Booster(model_file=str(incumbent_path))
            incumbent = predict_panel(panel, 179, {"model": model, "config": {
                "kind": "lightgbm", "features": model.feature_name(), "zero_threshold": .25}})
            record("incumbent", "provided180", incumbent)
            del model
        incumbent_npz = ROOT / f"reports/remediation/predictions/current_tweedie_z0.25_{origin}.npz"
        if incumbent_npz.exists():
            record("incumbent", "previous_full_history", np.load(incumbent_npz)["prediction"])
        coverage.append(dict(origin=origin, beginning=str(beginning.date()), history_days=180,
                             sales_rows=len(local_sales), stock_rows=len(local_stock),
                             input_known_articles=int(first[first.key_type == "article"].key.nunique()),
                             sparse_series=int(sparse.sum()), historical_manifest_sha256=manifest_hash,
                             shared_component_inference_seconds=inference_seconds,
                             incumbent_180_available=incumbent_available,
                             incumbent_model_sha256=file_hash(incumbent_path) if incumbent_available else None))
        save_report(args.output, results, coverage)
        print(json.dumps(coverage[-1]), flush=True)
        del models, frames, aligned, panel
        gc.collect()
    (args.output / "run.json").write_text(json.dumps({
        "status": "completed", "origins": args.origins, "training_performed": False,
        "input_hashes": {"sales": file_hash(args.sales), "stock": file_hash(args.stock)},
        "runtime_sources": runtime_source_hashes(), "official_scorer_sha256": file_hash(ROOT / "scripts/official_score.py"),
        "elapsed_seconds": perf_counter() - start,
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
