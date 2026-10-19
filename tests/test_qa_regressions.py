"""Controlled regressions discovered during the independent QA audit."""
import json

import numpy as np
import pandas as pd
import pytest

from src.data import build_panel
from src.predict import load_bundle
from src.submission import forecast_frame


def inputs():
    sales = pd.DataFrame({"date": ["2025-01-01", "2025-06-30"],
                          "warehouse_name": "w", "article": "a", "quantity": [1., 2.]})
    return sales, sales.drop(columns="quantity").assign(stock=1.)


@pytest.mark.parametrize("date", ["2025-1-1", "2025-01-01 00:00:00"])
def test_offline_requires_strict_date_format(date):
    sales, stock = inputs()
    sales.loc[0, "date"] = date
    with pytest.raises(ValueError, match="date|format"):
        build_panel(sales, stock)


@pytest.mark.parametrize("kind", ["sales", "stock"])
def test_panel_rejects_float32_overflow(kind):
    sales, stock = inputs()
    (sales if kind == "sales" else stock).loc[0, "quantity" if kind == "sales" else "stock"] = 1e40
    with pytest.raises(ValueError, match="range|finite|overflow"):
        build_panel(sales, stock)


def test_panel_rejects_aggregation_overflow():
    sales, stock = inputs()
    sales.quantity = 2e38
    sales = pd.concat([sales, sales], ignore_index=True)
    with pytest.raises(ValueError, match="range|finite|overflow"):
        build_panel(sales, stock)


@pytest.mark.parametrize("identifier", ["", "   "])
def test_offline_rejects_empty_identifier(identifier):
    sales, stock = inputs()
    sales.warehouse_name = stock.warehouse_name = identifier
    with pytest.raises(ValueError, match="key|identifier"):
        build_panel(sales, stock)


def test_forecast_rejects_wrong_axes_with_correct_element_count():
    catalogs = {"warehouses": ["w"], "articles": ["a", "b"]}
    with pytest.raises(ValueError, match="shape"):
        forecast_frame(np.arange(128).reshape(2, 64), "2025-06-30", catalogs)


def test_unknown_model_kind_fails_at_load(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"schema_version": 1, "horizon": 64, "kind": "typo"}))
    (tmp_path / "catalogs.json").write_text(json.dumps({"warehouses": ["w"], "articles": ["a"]}))
    with pytest.raises(ValueError, match="kind"):
        load_bundle(tmp_path)


def test_required_bias_and_smape_independent_fixtures():
    from src.metrics import compute_metrics, smape_include_zero_zero
    truth = np.array([[0., 2., 0.], [10., 2., 0.]])
    prediction = np.array([[0., 4., 1.], [8., 4., 1.]])
    # Hand calculation: series A -20%, B +100%; C excluded -> 60%.
    assert compute_metrics(truth, prediction)["bias"] == pytest.approx(60.)
    sparse = np.array([[0.], [0.], [0.], [10.]])
    assert compute_metrics(sparse, np.zeros_like(sparse))["smape"] == 200.
    assert smape_include_zero_zero(sparse, np.zeros_like(sparse)) == 50.


@pytest.mark.parametrize("payload", [b'a,b,c\n1,2\n', b'a,b\n"broken"suffix,2\n'])
def test_csv_body_structure_is_strict(payload):
    from app.validators import InputError, read_csv
    with pytest.raises(InputError):
        read_csv(payload, "sales")


def test_bundle_rejects_reordered_categorical_mapping(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"schema_version": 1, "horizon": 64, "kind": "baseline", "baseline": "zero"}))
    (tmp_path / "catalogs.json").write_text(json.dumps({"warehouses": ["w"], "articles": ["b", "a"]}))
    with pytest.raises(ValueError, match="catalog"):
        load_bundle(tmp_path)


@pytest.mark.parametrize("actual,predicted,expected", [
    ([1., 2.], [1., 2.], 0.),
    ([1., 2.], [2., 4.], 100.),
    ([1., 2.], [0., 0.], 100.),
    ([0., 0.], [4., 5.], 0.),  # Official fallback, not an informative Bias.
    ([1e-12, 0.], [2e-12, 0.], 100.),
    ([1., 0.], [1000., 0.], 99900.),
    ([0., 10.], [10., 0.], 0.),
])
def test_controlled_bias_edge_cases(actual, predicted, expected):
    from src.metrics import compute_metrics
    truth = np.array(actual)[:, None]
    prediction = np.array(predicted)[:, None]
    assert compute_metrics(truth, prediction)["bias"] == pytest.approx(expected, abs=1e-10)


def test_bias_series_permutation_and_all_excluded_diagnostics():
    from scripts.qa_analysis import bias_diagnostics
    from src.metrics import compute_metrics
    truth = np.array([[0., 2., 0.], [10., 2., 0.]])
    prediction = np.array([[0., 4., 1.], [8., 4., 1.]])
    expected = compute_metrics(truth, prediction)
    assert compute_metrics(truth[:, [2, 0, 1]], prediction[:, [2, 0, 1]]) == pytest.approx(expected)
    diagnostics = bias_diagnostics(truth, prediction)
    assert diagnostics["official_bias_pct"] == 60
    assert diagnostics["mean_signed_series_bias_pct"] == 40
    assert diagnostics["global_signed_volume_bias_pct"] == pytest.approx(100 * 4 / 14)
    assert diagnostics["excluded"] == 1
    empty = bias_diagnostics(np.zeros((2, 3)), np.ones((2, 3)))
    assert empty["official_bias_pct"] == 0
    assert empty["mean_signed_series_bias_pct"] is None
    assert empty["global_signed_volume_bias_pct"] is None
    assert empty["excluded"] == 3


def test_rank_ties_reproduce_original_evaluator_order_dependence():
    from scripts.official_score import METRIC_WEIGHTS, normalize_rank
    identical = dict.fromkeys(METRIC_WEIGHTS, 1.)
    ranked = normalize_rank({"a": identical, "b": identical})
    reversed_rank = normalize_rank({"b": identical, "a": identical})
    assert set(ranked["a"].values()) == {0.}
    assert set(ranked["b"].values()) == {1.}
    assert reversed_rank["a"] == ranked["b"]


@pytest.mark.parametrize("problem", ["missing", "duplicate", "nan", "inf"])
def test_submission_key_and_finite_guards(problem):
    from src.submission import validate_submission
    catalogs = {"warehouses": ["w"], "articles": ["a", "b"]}
    frame = forecast_frame(np.ones((64, 2)), "2025-06-30", catalogs)
    if problem == "missing":
        frame = frame.iloc[1:]
    elif problem == "duplicate":
        frame.iloc[0] = frame.iloc[1]
    else:
        frame.loc[0, "quantity"] = np.nan if problem == "nan" else np.inf
    with pytest.raises(ValueError):
        validate_submission(frame, "2025-06-30", catalogs)
