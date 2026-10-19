"""Independent checks of temporal boundaries and the shared offline pipeline."""
import json

import numpy as np
import pandas as pd
import pytest

from src.data import Panel, build_panel, clean_stock
from src.features import snapshot, horizon_features, training_data
from src.predict import load_bundle, predict_panel
from src.submission import forecast_frame, write_submission, validate_submission
from src.train import train_model
from src.artifacts import write_manifest


def small_panel(days=330):
    dates = pd.date_range("2024-01-01", periods=days)
    catalogs = {"warehouses": ["001", "002"], "articles": ["0007", "0008"]}
    day = np.arange(days)[:, None]
    y = ((day % 7) + np.arange(4)[None, :]).astype(np.float32)
    stock = np.full_like(y, 8)
    stock[:, 0] = np.nan
    stock[:, 1] = 0
    return Panel(dates, y, stock, catalogs)


def test_future_data_invariance_snapshot_and_horizons():
    panel = small_panel()
    origin = 210
    changed = Panel(panel.dates, panel.y.copy(), panel.stock.copy(), panel.catalogs)
    changed.y[origin+1:] = 1e6
    changed.stock[origin+1:] = 1e6
    before, after = snapshot(panel, origin), snapshot(changed, origin)
    pd.testing.assert_frame_equal(before, after)
    for h in [1, 14, 64]:
        pd.testing.assert_frame_equal(horizon_features(before, panel.dates[origin], h),
                                      horizon_features(after, panel.dates[origin], h))


def test_appending_future_input_rows_does_not_change_fixed_cutoff():
    sales = pd.DataFrame({"date": ["2024-01-01", "2024-07-01"],
                          "warehouse_name": "001", "article": "0007", "quantity": [2., 3.]})
    stock = sales.drop(columns="quantity").assign(stock=9.)
    catalogs = {"warehouses": ["001"], "articles": ["0007"]}
    original = build_panel(sales, stock, catalogs, cutoff="2024-07-01")
    later_sales = pd.concat([sales, sales.tail(1).assign(date="2025-01-01", quantity=9999)])
    later_stock = pd.concat([stock, stock.tail(1).assign(date="2025-01-01", stock=9999)])
    extended = build_panel(later_sales, later_stock, catalogs, cutoff="2024-07-01")
    np.testing.assert_array_equal(original.y, extended.y)
    np.testing.assert_array_equal(original.stock, extended.stock)
    pd.testing.assert_frame_equal(snapshot(original, len(original.dates)-1),
                                  snapshot(extended, len(extended.dates)-1))


def test_departments_sum_missing_sales_zero_missing_stock_nan():
    sales = pd.DataFrame({"date": ["2024-01-01"] * 2 + ["2024-01-03"],
                          "warehouse_name": "001", "article": "0007",
                          "composite_division": ["a", "b", "a"], "quantity": [2., 3., 7.]})
    stock = pd.DataFrame({"date": ["2024-01-01", "2024-01-03"],
                          "warehouse_name": "001", "char_article": "0007", "stock": [0., 4.]})
    panel = build_panel(sales, stock)
    np.testing.assert_array_equal(panel.y[:, 0], [5., 0., 7.])
    assert panel.stock[0, 0] == 0
    assert np.isnan(panel.stock[1, 0])
    assert panel.stock[2, 0] == 4


def test_stock_observability_is_not_confused_with_zero():
    panel = small_panel()
    frame = snapshot(panel, 200)
    assert frame.loc[0, "stock_coverage"] == 0
    assert np.isnan(frame.loc[0, "last_stock"])
    assert frame.loc[0, "stock_age"] == 180
    assert frame.loc[1, "stock_coverage"] == 1
    assert frame.loc[1, "last_stock"] == 0
    assert frame.loc[1, "stock_zero_rate"] == 1
    assert frame.loc[1, "stock_age"] == 0


def test_training_labels_all_known_by_cutoff_and_correct_horizon():
    panel = small_panel()
    cutoff = 300
    x, labels, origins = training_data(panel, cutoff, step=35)
    changed = Panel(panel.dates, panel.y.copy(), panel.stock.copy(), panel.catalogs)
    changed.y[cutoff+1:] = 99999
    changed.stock[cutoff+1:] = 99999
    changed_x, changed_labels, changed_origins = training_data(changed, cutoff, step=35)
    pd.testing.assert_frame_equal(x, changed_x)
    np.testing.assert_array_equal(labels, changed_labels)
    assert origins == changed_origins
    expected = []
    for origin in origins:
        for horizon in [1, 7, 14, 21, 28, 42, 56, 64]:
            assert origin + horizon <= cutoff
            expected.append(panel.y[origin+horizon])
    np.testing.assert_array_equal(labels, np.concatenate(expected))
    assert x.iloc[0].horizon == 1
    assert x.iloc[-1].horizon == 64


def test_horizon_calendar_and_grid_serialization(tmp_path):
    panel = small_panel()
    origin = pd.Timestamp("2024-12-31")
    first = horizon_features(snapshot(panel, 200), origin, 1)
    last = horizon_features(snapshot(panel, 200), origin, 64)
    assert first.horizon.eq(1).all() and first.month.eq(1).all()
    assert first.day_of_week.eq(pd.Timestamp("2025-01-01").dayofweek).all()
    assert last.horizon.eq(64).all() and last.month.eq(3).all()
    values = np.arange(64 * 4).reshape(64, 4).astype(float)
    frame = forecast_frame(values, origin, panel.catalogs)
    assert len(frame) == 256
    assert frame.date.iloc[0] == "2025-01-01"
    assert frame.date.iloc[-1] == "2025-03-05"
    assert frame.iloc[:4][["warehouse_name", "article"]].values.tolist() == [
        ["001", "0007"], ["001", "0008"], ["002", "0007"], ["002", "0008"]]
    path = tmp_path / "submission.csv"
    assert write_submission(frame, path, origin, panel.catalogs)["status"] == "passed"
    actual = pd.read_csv(path, dtype={"warehouse_name": str, "article": str})
    pd.testing.assert_frame_equal(frame, actual, check_dtype=False)
    with pytest.raises(ValueError, match="grid"):
        validate_submission(frame.iloc[::-1], origin, panel.catalogs)


def test_tiny_trained_model_save_load_feature_order_and_determinism(tmp_path):
    panel = small_panel()
    bundle = train_model(panel, 300, rounds=2)
    before = predict_panel(panel, 300, bundle)
    assert before.shape == (64, 4)
    assert np.isfinite(before).all() and (before >= 0).all()
    bundle["model"].save_model(str(tmp_path / "lightgbm.txt"))
    (tmp_path / "config.json").write_text(json.dumps(bundle["config"]), encoding="utf-8")
    (tmp_path / "catalogs.json").write_text(json.dumps(bundle["catalogs"]), encoding="utf-8")
    write_manifest(tmp_path)
    loaded = load_bundle(tmp_path)
    np.testing.assert_allclose(before, predict_panel(panel, 300, loaded), rtol=0, atol=0)
    np.testing.assert_allclose(before, predict_panel(panel, 300, loaded), rtol=0, atol=0)
    loaded["config"]["features"] = loaded["config"]["features"][::-1]
    with pytest.raises(ValueError, match="feature order"):
        predict_panel(panel, 300, loaded)


def test_conflicting_stock_duplicates_are_rejected():
    sales = pd.DataFrame({"date": ["2024-01-01"], "warehouse_name": ["001"],
                          "article": ["0007"], "quantity": [1]})
    stock = pd.concat([sales.drop(columns="quantity").assign(stock=value) for value in [0, 1]])
    with pytest.raises(ValueError, match="Conflicting stock"):
        build_panel(sales, stock)


def test_clean_stock_removes_all_ambiguous_rows_and_preserves_true_zero():
    source = pd.DataFrame({"date": ["2024-01-01"] * 9,
                           "warehouse_name": "001",
                           "article": ["a", "a", "b", "b", "c", "c", "d", "d", "e"],
                           "stock": [0, 0, 2, 9, -1, 3, -2, -2, 5]})
    clean = clean_stock(source)
    assert clean.article.tolist() == ["a", "c", "e"]
    assert clean.stock.tolist() == [0, 3, 5]
    assert source.shape[0] == 9  # Caller input is unchanged.
    pd.testing.assert_frame_equal(clean, clean_stock(source.sample(frac=1, random_state=2)).sort_values("article").reset_index(drop=True))
    alias = clean_stock(source.rename(columns={"article": "char_article"}))
    pd.testing.assert_frame_equal(clean, alias)


def test_shared_panel_rejects_conflicting_article_aliases():
    sales = pd.DataFrame({"date": ["2024-01-01"], "warehouse_name": ["001"],
                          "article": ["0007"], "quantity": [1]})
    stock = sales.drop(columns="quantity").assign(stock=0, char_article="0008")
    with pytest.raises(ValueError, match="aliases"):
        build_panel(sales, stock)
