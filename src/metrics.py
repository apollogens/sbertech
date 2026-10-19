"""Vectorized competition metrics; axes are (forecast day, warehouse/article pair)."""
from collections.abc import Mapping

import numpy as np

METRIC_WEIGHTS = {"smape": 0.50, "wape": 0.20, "rmse": 0.15, "bias": 0.10, "rmsle": 0.05}


def _arrays(y_true, y_pred):
    truth = np.asarray(y_true, dtype=np.float64)
    pred = np.asarray(y_pred, dtype=np.float64)
    if truth.ndim != 2 or truth.shape != pred.shape or not truth.size:
        raise ValueError("Expected matching, nonempty (days, pairs) arrays")
    if not np.isfinite(truth).all() or (truth < 0).any():
        raise ValueError("Truth must contain finite nonnegative quantities")
    if np.isinf(pred).any():
        raise ValueError("Prediction must not contain infinity")
    # Same sanitization as official compute_all_metrics after its left merge.
    pred = np.maximum(np.nan_to_num(pred, nan=0.0), 0.0)
    return truth, pred


def compute_metrics(y_true, y_pred) -> dict[str, float]:
    """Exact official semantics, including exclusion of zero/zero SMAPE days.

    Each pair receives equal weight for SMAPE and Bias. A completely zero/zero
    pair contributes zero SMAPE. Pairs with zero mean truth are excluded from
    Bias. The official WAPE is zero when all truth quantities are zero.
    """
    truth, pred = _arrays(y_true, y_pred)
    difference = np.abs(truth - pred)
    denominator = (truth + pred) / 2.0
    valid = denominator > 0
    ratios = np.divide(difference, denominator, out=np.zeros_like(truth), where=valid)
    counts = valid.sum(axis=0)
    pair_smape = np.divide(ratios.sum(axis=0), counts,
                           out=np.zeros(truth.shape[1]), where=counts > 0)
    mean_truth = truth.mean(axis=0)
    nonzero_pairs = mean_truth != 0
    bias = (np.abs(pred.mean(axis=0)[nonzero_pairs] - mean_truth[nonzero_pairs])
            / mean_truth[nonzero_pairs])
    total = truth.sum()
    return {
        "smape": float(pair_smape.mean() * 100),
        "wape": float(difference.sum() / total * 100) if total else 0.0,
        "rmse": float(np.sqrt(np.mean((truth - pred) ** 2))),
        "bias": float(bias.mean() * 100) if bias.size else 0.0,
        "rmsle": float(np.sqrt(np.mean((np.log1p(pred) - np.log1p(truth)) ** 2))),
    }


def smape_include_zero_zero(y_true, y_pred) -> float:
    """Diagnostic formula from the prose: zero/zero days remain in the mean."""
    truth, pred = _arrays(y_true, y_pred)
    denominator = (truth + pred) / 2.0
    ratios = np.divide(np.abs(truth - pred), denominator,
                       out=np.zeros_like(truth), where=denominator > 0)
    return float(ratios.mean(axis=0).mean() * 100)


def normalize_metrics(metrics: Mapping[str, float], baseline_metrics: Mapping[str, float]) -> dict[str, float]:
    """Official baseline normalization; worse-than-baseline values clip to one."""
    normalized = {}
    for key in METRIC_WEIGHTS:
        val, base = float(metrics[key]), float(baseline_metrics[key])
        if not np.isfinite([val, base]).all() or min(val, base) < 0:
            raise ValueError("Metric values must be finite and nonnegative")
        normalized[key] = (0.0 if val == 0 else 1.0) if base == 0 else min(val / base, 1.0)
    return normalized


def weighted_score(metrics: Mapping[str, float], baseline_metrics: Mapping[str, float]) -> float:
    normalized = normalize_metrics(metrics, baseline_metrics)
    return float(sum(weight * normalized[key] for key, weight in METRIC_WEIGHTS.items()))


def evaluate(y_true, y_pred, baseline_pred) -> dict:
    raw = compute_metrics(y_true, y_pred)
    baseline = compute_metrics(y_true, baseline_pred)
    normalized = normalize_metrics(raw, baseline)
    return {"raw": raw, "baseline": baseline, "normalized": normalized,
            "score": weighted_score(raw, baseline),
            "smape_include_zero_zero": smape_include_zero_zero(y_true, y_pred)}
