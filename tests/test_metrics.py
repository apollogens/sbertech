import numpy as np
import pandas as pd
import pytest

from scripts import official_score
from src.metrics import (METRIC_WEIGHTS, compute_metrics, evaluate,
                         normalize_metrics, smape_include_zero_zero, weighted_score)


def as_frame(values):
    days, pairs = values.shape
    return pd.DataFrame({"date": np.repeat(pd.date_range("2025-01-01", periods=days), pairs),
                         "warehouse_name": "w", "article": np.tile(np.arange(pairs).astype(str), days),
                         "quantity": values.ravel()})


@pytest.mark.parametrize("seed", [1, 21, 104])
def test_official_parity(seed):
    rng = np.random.default_rng(seed)
    truth = rng.exponential(2, (64, 13))
    truth[rng.random(truth.shape) < 0.8] = 0
    pred = rng.exponential(3, truth.shape)
    pred[rng.random(pred.shape) < 0.6] = 0
    truth[:, 0] = pred[:, 0] = 0
    truth[:, 1] = 0
    pred[2, 3] = np.nan
    pred[3, 4] = -2
    expected = official_score.compute_all_metrics(as_frame(truth), as_frame(pred))
    assert compute_metrics(truth, pred) == pytest.approx(expected, rel=1e-12, abs=1e-12)


def test_smape_document_conflict_is_explicit():
    truth = np.array([[0., 0.], [1., 0.]])
    pred = np.zeros_like(truth)
    assert compute_metrics(truth, pred)["smape"] == 100
    assert smape_include_zero_zero(truth, pred) == 50


def test_all_zero_truth_official_edge_case():
    truth, pred = np.zeros((64, 3)), np.ones((64, 3))
    actual = compute_metrics(truth, pred)
    assert actual == pytest.approx(official_score.compute_all_metrics(as_frame(truth), as_frame(pred)))
    assert actual["wape"] == actual["bias"] == 0


def test_normalization_and_score_parity():
    baseline = dict(zip(METRIC_WEIGHTS, [10, 20, 0, 0, 2]))
    raw = dict(zip(METRIC_WEIGHTS, [5, 40, 0, 8, 1]))
    expected = official_score.normalize_minmax({"model": raw}, baseline)["model"]
    assert normalize_metrics(raw, baseline) == expected
    assert weighted_score(raw, baseline) == pytest.approx(sum(METRIC_WEIGHTS[k] * expected[k] for k in expected))
    assert expected == {"smape": .5, "wape": 1, "rmse": 0, "bias": 1, "rmsle": .5}


def test_perfect_forecast_score():
    truth = np.arange(12).reshape(4, 3)
    assert evaluate(truth, truth, np.ones_like(truth))["score"] == 0


@pytest.mark.parametrize("truth,pred", [([], []), ([1], [1]), ([[1]], [[1, 2]]),
                                        ([[np.nan]], [[0]]), ([[-1]], [[0]]), ([[1]], [[np.inf]])])
def test_invalid_inputs_rejected(truth, pred):
    with pytest.raises(ValueError):
        compute_metrics(truth, pred)
