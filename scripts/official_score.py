#!/usr/bin/env python3
"""
Автоматический скоринг для хакатона «Прогноз продаж по складам и товарам».

Метрики и веса:
    SMAPE  — 50%   (считается по сериям, усредняется)
    WAPE   — 20%   (глобально)
    RMSE   — 15%   (глобально)
    Bias   — 10%   (|MPE| по сериям, усредняется)
    RMSLE  — 5%    (глобально, log1p)

Чем ниже итоговый скор — тем лучше.

Режимы нормализации:
    minmax — 0 = идеальный прогноз, 1 = наивный бейзлайн
    rank   — ранги участников от 0 (лучший) до 1 (худший)

Usage:
    python score.py --truth ground_truth.csv \
        --submissions model_a.csv model_b.csv \
        --baseline naive_forecast.csv \
        --output leaderboard.csv
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from typing import Dict, List, Optional

# ─────────────────────────────────────────────────────────────
# Константы
# ─────────────────────────────────────────────────────────────

METRIC_WEIGHTS: Dict[str, float] = {
    "smape": 0.50,
    "wape":  0.20,
    "rmse":  0.15,
    "bias":  0.10,
    "rmsle": 0.05,
}

REQUIRED_COLUMNS = ["date", "warehouse_name", "article", "quantity"]
NUM_WAREHOUSES = 11
NUM_ARTICLES = 799
FORECAST_HORIZON = 64
EXPECTED_ROWS = NUM_WAREHOUSES * NUM_ARTICLES * FORECAST_HORIZON  # 562 496


# ─────────────────────────────────────────────────────────────
# Метрики
# ─────────────────────────────────────────────────────────────

def smape_series(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """SMAPE для одной серии. Возвращает значение в процентах (0..200)."""
    numerator = np.abs(y_true - y_pred)
    denominator = (np.abs(y_true) + np.abs(y_pred)) / 2.0
    mask = denominator > 0
    if not mask.any():
        return 0.0
    return float(np.mean(numerator[mask] / denominator[mask]) * 100.0)


def smape(y_true: np.ndarray, y_pred: np.ndarray,
          series_ids: np.ndarray) -> float:
    """SMAPE по сериям (склад × товар), усреднённый."""
    unique = np.unique(series_ids)
    values = []
    for sid in unique:
        mask = series_ids == sid
        values.append(smape_series(y_true[mask], y_pred[mask]))
    return float(np.mean(values))


def wape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """WAPE — глобально. Возвращает значение в процентах."""
    denom = np.sum(np.abs(y_true))
    if denom == 0:
        return 0.0
    return float(np.sum(np.abs(y_true - y_pred)) / denom * 100.0)


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """RMSE — глобально."""
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def bias_abs_series(y_true: np.ndarray, y_pred: np.ndarray) -> Optional[float]:
    """|Bias| для одной серии. None если mean(y_true) == 0."""
    mean_y = np.mean(y_true)
    if mean_y == 0:
        return None
    return float(abs(np.mean(y_pred) - mean_y) / mean_y * 100.0)


def bias_abs(y_true: np.ndarray, y_pred: np.ndarray,
             series_ids: np.ndarray) -> float:
    """|Bias| по сериям, усреднённый. Серии с mean(y)=0 исключаются."""
    unique = np.unique(series_ids)
    values = []
    for sid in unique:
        mask = series_ids == sid
        val = bias_abs_series(y_true[mask], y_pred[mask])
        if val is not None:
            values.append(val)
    if not values:
        return 0.0
    return float(np.mean(values))


def rmsle(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """RMSLE — глобально, с log1p для безопасности."""
    return float(np.sqrt(np.mean((np.log1p(y_pred) - np.log1p(y_true)) ** 2)))


def compute_all_metrics(
    df_true: pd.DataFrame,
    df_pred: pd.DataFrame
) -> Dict[str, float]:
    """Считает все 5 метрик для пары (truth, prediction)."""
    df = df_true.merge(
        df_pred, on=["date", "warehouse_name", "article"], how="left",
        suffixes=("_true", "_pred")
    )
    nan_count = df["quantity_pred"].isna().sum()
    if nan_count > 0:
        print(f"  ⚠  Пропуски в submission: {nan_count} строк. "
              f"Заполнены нулями.")
    df["quantity_pred"] = df["quantity_pred"].fillna(0).clip(lower=0)

    y_true = df["quantity_true"].values.astype(float)
    y_pred = df["quantity_pred"].values.astype(float)
    series_ids = (
        df["warehouse_name"].astype(str) + "|" + df["article"].astype(str)
    ).values

    return {
        "smape": smape(y_true, y_pred, series_ids),
        "wape":  wape(y_true, y_pred),
        "rmse":  rmse(y_true, y_pred),
        "bias":  bias_abs(y_true, y_pred, series_ids),
        "rmsle": rmsle(y_true, y_pred),
    }


# ─────────────────────────────────────────────────────────────
# Нормализация
# ─────────────────────────────────────────────────────────────

def normalize_minmax(
    metrics: Dict[str, Dict[str, float]],
    baseline_metrics: Dict[str, float]
) -> Dict[str, Dict[str, float]]:
    """Min-max: 0 = идеал, 1 = бейзлайн. Всё хуже бейзлайна → 1."""
    normalized = {}
    for name, m in metrics.items():
        normalized[name] = {}
        for key in METRIC_WEIGHTS:
            val = m[key]
            base = baseline_metrics[key]
            if base == 0:
                norm = 0.0 if val == 0 else 1.0
            else:
                norm = min(val / base, 1.0)
            normalized[name][key] = norm
    return normalized


def normalize_rank(
    metrics: Dict[str, Dict[str, float]]
) -> Dict[str, Dict[str, float]]:
    """Ранговая нормализация: 0 = лучший, 1 = худший."""
    names = list(metrics.keys())
    n = len(names)
    normalized = {name: {} for name in names}
    for key in METRIC_WEIGHTS:
        values = [metrics[name][key] for name in names]
        order = np.argsort(values)
        ranks = np.empty(n, dtype=float)
        ranks[order] = np.arange(n, dtype=float)
        for i, name in enumerate(names):
            normalized[name][key] = (
                ranks[i] / (n - 1) if n > 1 else 0.0
            )
    return normalized


# ─────────────────────────────────────────────────────────────
# Валидация формата submission
# ─────────────────────────────────────────────────────────────

def validate_submission(df: pd.DataFrame, name: str = "submission") -> List[str]:
    """Проверяет формат submission и возвращает список предупреждений."""
    warnings_list = []

    missing_cols = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing_cols:
        warnings_list.append(f"Отсутствуют колонки: {missing_cols}")
        return warnings_list

    nan_count = df["quantity"].isna().sum()
    if nan_count > 0:
        warnings_list.append(f"NaN в quantity: {nan_count} строк")

    neg_count = (df["quantity"] < 0).sum()
    if neg_count > 0:
        warnings_list.append(
            f"Отрицательные значения в quantity: {neg_count} строк"
        )

    if len(df) != EXPECTED_ROWS:
        warnings_list.append(
            f"Ожидается {EXPECTED_ROWS} строк, получено {len(df)}"
        )

    dates = pd.to_datetime(df["date"], errors="coerce")
    unique_dates = dates.dropna().unique()
    if len(unique_dates) != FORECAST_HORIZON:
        warnings_list.append(
            f"Ожидается {FORECAST_HORIZON} уникальных дат, "
            f"получено {len(unique_dates)}"
        )

    if len(unique_dates) == FORECAST_HORIZON:
        sorted_dates = pd.to_datetime(np.sort(unique_dates))
        gaps = sorted_dates.to_series().diff().dropna()
        if (gaps != pd.Timedelta(days=1)).any():
            warnings_list.append("Даты не идут подряд")

    combos = df.groupby(["warehouse_name", "article"]).ngroups
    expected_combos = NUM_WAREHOUSES * NUM_ARTICLES
    if combos != expected_combos:
        warnings_list.append(
            f"Ожидается {expected_combos} уникальных комбинаций "
            f"склад × товар, получено {combos}"
        )

    return warnings_list


# ─────────────────────────────────────────────────────────────
# Главная функция
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Скоринг для хакатона «Прогноз продаж»"
    )
    parser.add_argument(
        "--truth", required=True,
        help="Путь к ground truth CSV (date, warehouse_name, article, quantity)"
    )
    parser.add_argument(
        "--submissions", nargs="+", required=True,
        help="Пути к submission CSV (один или несколько)"
    )
    parser.add_argument(
        "--baseline",
        help="Путь к baseline CSV для min-max нормализации"
    )
    parser.add_argument(
        "--method", choices=["minmax", "rank"], default="minmax",
        help="Метод нормализации (по умолчанию: minmax)"
    )
    parser.add_argument(
        "--output", help="Путь для сохранения лидерборда в CSV"
    )
    parser.add_argument(
        "--weights", type=str, default=None,
        help=(
            "Веса метрик в формате JSON: "
            '{"smape":0.5,"wape":0.2,"rmse":0.15,"bias":0.1,"rmsle":0.05}'
        )
    )

    args = parser.parse_args()

    if args.weights:
        import json
        custom_weights = json.loads(args.weights)
        global METRIC_WEIGHTS
        METRIC_WEIGHTS = custom_weights
        print(f"Веса метрик переопределены: {METRIC_WEIGHTS}")

    print("=" * 70)
    print("СКООРИНГ ХАКАТОНА «ПРОГНОЗ ПРОДАЖ»")
    print("=" * 70)
    print(f"Веса метрик: {METRIC_WEIGHTS}")
    print(f"Метод нормализации: {args.method}")
    print(f"Ground truth: {args.truth}")
    print(f"Submissions: {args.submissions}")
    print()

    df_truth = pd.read_csv(args.truth)
    df_truth["date"] = pd.to_datetime(df_truth["date"])
    print(f"Ground truth загружен: {len(df_truth)} строк, "
          f"{df_truth['date'].nunique()} дат")

    baseline_metrics = None
    if args.method == "minmax":
        if args.baseline is None:
            print("⚠  Метод minmax требует --baseline. "
                  "Переключаюсь на rank.")
            args.method = "rank"
        else:
            df_base = pd.read_csv(args.baseline)
            df_base["date"] = pd.to_datetime(df_base["date"])
            print(f"Baseline загружен: {len(df_base)} строк")
            baseline_metrics = compute_all_metrics(df_truth, df_base)
            print(f"Метрики baseline: {baseline_metrics}")

    all_metrics: Dict[str, Dict[str, float]] = {}
    for sub_path in args.submissions:
        name = Path(sub_path).stem
        print(f"\n--- {name} ---")
        df_sub = pd.read_csv(sub_path)
        df_sub["date"] = pd.to_datetime(df_sub["date"])

        warns = validate_submission(df_sub, name)
        for w in warns:
            print(f"  ⚠  {w}")
        if any("Отсутствуют колонки" in w for w in warns):
            print(f"  ✗  Пропуск {name} — нет обязательных колонок")
            continue

        m = compute_all_metrics(df_truth, df_sub)
        all_metrics[name] = m
        print(f"  SMAPE = {m['smape']:.4f}%")
        print(f"  WAPE  = {m['wape']:.4f}%")
        print(f"  RMSE  = {m['rmse']:.4f}")
        print(f"  |Bias|= {m['bias']:.4f}%")
        print(f"  RMSLE = {m['rmsle']:.4f}")

    if not all_metrics:
        print("\n✗  Нет валидных submissions для оценки.")
        sys.exit(1)

    if args.method == "minmax" and baseline_metrics is not None:
        normalized = normalize_minmax(all_metrics, baseline_metrics)
    else:
        normalized = normalize_rank(all_metrics)

    print("\n" + "=" * 70)
    print("ЛИДЕРБОРД")
    print("=" * 70)
    leaderboard = []
    for name in all_metrics:
        score = sum(
            METRIC_WEIGHTS[k] * normalized[name][k]
            for k in METRIC_WEIGHTS
        )
        row = {"submission": name, "score": score}
        for k in METRIC_WEIGHTS:
            row[f"{k}_raw"] = all_metrics[name][k]
            row[f"{k}_norm"] = normalized[name][k]
        leaderboard.append(row)

    df_lb = pd.DataFrame(leaderboard).sort_values("score")
    print(df_lb.to_string(index=False, float_format="%.4f"))

    if args.output:
        df_lb.to_csv(args.output, index=False)
        print(f"\nЛидерборд сохранён в {args.output}")

    print(f"\nПобедитель: {df_lb.iloc[0]['submission']} "
          f"(score = {df_lb.iloc[0]['score']:.4f})")


if __name__ == "__main__":
    main()
