"""Dispatcher, provided-history and HTTP contracts without model fitting."""

from copy import deepcopy
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src import runtime
from src.catalog import safe_snapshot
from src.data import build_panel
from src.features import horizon_features
from src.temporal import weekly_frame


@pytest.fixture
def inputs():
    dates = pd.date_range("2024-01-01", periods=180).strftime("%Y-%m-%d")
    sales = pd.DataFrame({"date": dates, "warehouse_name": "w", "article": "a", "quantity": 1.})
    stock = sales.drop(columns="quantity").assign(stock=2.)
    return sales, stock


class RecordingModel:
    def __init__(self, features, value):
        self.features = features
        self.value = value
        self.frames = []

    def feature_name(self):
        return self.features

    def predict(self, frame, num_threads):
        self.frames.append(frame.copy())
        return np.full(len(frame), self.value, dtype=float)


def component_bundle(sales, stock, strategy="equal4:P1", daily_value=1.):
    catalogs = {"warehouses": ["w"], "articles": ["a", "b"]}
    panel = build_panel(sales, stock, catalogs=catalogs)
    first = runtime.first_seen_from_sales(sales)
    snap, _ = safe_snapshot(panel, len(panel.dates) - 1, first)
    features = list(horizon_features(snap, panel.dates[-1], 1))
    weekly_features = list(weekly_frame(snap, panel.dates[-1], 1, 8))
    names = ("daily", "weekly", "shape", "article")
    strategies = {f"{short}:P1": dict(zip(names, [float(name == target) for name in names]))
                  for short, target in zip("DWSA", names)}
    strategies["equal4:P1"] = dict.fromkeys(names, .25)
    return {
        "runtime_kind": "components", "strategy": strategy, "catalogs": catalogs,
        "manifest": {"bundle_id": "synthetic-model-identity"},
        "config": {"kind": "components", "schema_version": 2, "horizon": 64,
                   "model_version": "nonton-equal4-rc1", "catalogs": catalogs,
                   "history_policy": {"mode": "provided", "minimum_days": 180},
                   "strategies": strategies, "postprocessing": "threshold025"},
        "models": {"daily": RecordingModel(features, daily_value),
                   "weekly": RecordingModel(weekly_features, 7.),
                   "article": RecordingModel(features, 2.)},
    }


def test_legacy_dispatch_preserves_bundle_and_result(monkeypatch, tmp_path, inputs):
    sentinel = {"config": {"kind": "baseline"}}
    calls = []
    monkeypatch.setattr(runtime, "legacy_load_bundle", lambda path: sentinel)
    assert runtime.load_bundle(tmp_path, strategy="nonton-v1") is sentinel
    expected = object()

    def predict(sales, stock, bundle):
        calls.append((sales, stock, bundle))
        return expected

    monkeypatch.setattr(runtime, "legacy_predict_64", predict)
    assert runtime.predict_64(*inputs, sentinel) is expected
    assert calls[0][0] is inputs[0] and calls[0][2] is sentinel


@pytest.mark.parametrize("alias,needed", [("D", {"daily"}), ("W", {"weekly"}),
                                         ("S", {"daily", "weekly"}), ("A", {"article"})])
def test_alias_loader_only_deserializes_selected_boosters(monkeypatch, tmp_path, inputs, alias, needed):
    source = component_bundle(*inputs)
    source["config"]["features"] = {name: model.feature_name() for name, model in source["models"].items()}
    (tmp_path / "runtime_manifest.json").write_text("{}")
    monkeypatch.setattr(runtime, "verify_runtime_bundle", lambda path: (source["config"], source["manifest"]))
    loaded = []

    def booster(model_file):
        name = Path(model_file).stem
        loaded.append(name)
        return source["models"][name]

    monkeypatch.setattr(runtime.lgb, "Booster", booster)
    bundle = runtime.load_bundle(tmp_path, strategy=alias)
    assert bundle["strategy"] == alias + ":P1"
    assert set(loaded) == needed and len(loaded) == len(needed)


def test_config_paths_are_relative_to_config_not_cwd(monkeypatch, tmp_path):
    config_dir = tmp_path / "configuration"
    config_dir.mkdir()
    config_path = config_dir / "release.json"
    config_path.write_text(json.dumps({"schema_version": 1, "active_bundle": "../weights",
                                      "active_strategy": "D"}))
    calls = []

    def load(path, strategy):
        calls.append((Path(path).resolve(), strategy))
        return "selected"

    monkeypatch.setattr(runtime, "load_bundle", load)
    monkeypatch.chdir(tmp_path.parent)
    assert runtime.configured_bundle(config_path) == "selected"
    assert calls == [((tmp_path / "weights").resolve(), "D")]


def test_rejects_component_strategy_with_incumbent_artifact(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "legacy_load_bundle", lambda path: pytest.fail("Unexpected model load"))
    with pytest.raises(ValueError, match="nonton-v1"):
        runtime.load_bundle(tmp_path, strategy="equal4:P1")


@pytest.mark.parametrize("strategy,expected", [
    ("D:P1", {"daily": 8, "weekly": 0, "article": 0}),
    ("W:P1", {"daily": 0, "weekly": 10, "article": 0}),
    ("S:P1", {"daily": 8, "weekly": 10, "article": 0}),
    ("A:P1", {"daily": 0, "weekly": 0, "article": 8}),
    ("equal4:P1", {"daily": 8, "weekly": 10, "article": 8}),
])
def test_selected_strategy_shared_boosters_and_full_output(inputs, strategy, expected):
    bundle = component_bundle(*inputs, strategy=strategy)
    result = runtime.predict_64(*inputs, bundle)
    assert len(result) == 128 and result.date.nunique() == 64
    assert not result.duplicated(["date", "warehouse_name", "article"]).any()
    assert np.isfinite(result.quantity).all() and (result.quantity >= 0).all()
    assert result.loc[result.article == "b", "quantity"].eq(0).all()
    assert {name: len(model.frames) for name, model in bundle["models"].items()} == expected


def test_threshold_boundary_is_preserved_without_integer_rounding(inputs):
    bundle = component_bundle(*inputs, strategy="D:P1", daily_value=.25)
    result = runtime.predict_64(*inputs, bundle)
    assert result.loc[result.article == "a", "quantity"].eq(.25).all()
    bundle = component_bundle(*inputs, strategy="D:P1", daily_value=np.nextafter(.25, 0))
    assert runtime.predict_64(*inputs, bundle).quantity.eq(0).all()


def test_provided_history_order_and_future_stock_invariance(inputs):
    sales, stock = inputs
    bundle = component_bundle(sales, stock)
    first = runtime.predict_64(sales, stock, bundle)
    future = stock.iloc[[-1]].copy()
    future["date"] = "2030-01-01"
    future["stock"] = 1e10
    second = runtime.predict_64(sales.sample(frac=1, random_state=31),
                                pd.concat([stock, future]).sample(frac=1, random_state=21), bundle)
    pd.testing.assert_frame_equal(first, second, check_exact=True)


def test_zero_sales_rows_define_known_catalog(inputs):
    sales, stock = inputs
    zero_row = sales.iloc[[-1]].assign(article="b", quantity=0.)
    sales = pd.concat([sales, zero_row], ignore_index=True)
    bundle = component_bundle(sales, stock, strategy="D:P1")
    result = runtime.predict_64(sales, stock, bundle)
    assert result.loc[result.article == "b", "quantity"].eq(1.).all()


def test_minimum_history_and_feature_mismatch_fail(inputs):
    bundle = component_bundle(*inputs, strategy="D:P1")
    with pytest.raises(ValueError):
        runtime.predict_64(inputs[0].iloc[1:], inputs[1].iloc[1:], bundle)
    bundle["models"]["daily"].features = ["wrong_feature"]
    with pytest.raises(ValueError, match="[Ff]eature"):
        runtime.predict_64(*inputs, bundle)


@pytest.mark.parametrize("field,value", [("origin", "2030-01-01"), ("horizon", 63),
                                        ("catalog_sha256", "different-catalog")])
def test_rejects_component_metadata_before_cache_publish(monkeypatch, inputs, field, value):
    from src import components

    original = components.predict_component_frames

    def corrupt(*args, **kwargs):
        frames = original(*args, **kwargs)
        next(iter(frames.values())).attrs["forecast_identity"][field] = value
        return frames

    monkeypatch.setattr(components, "predict_component_frames", corrupt)
    with pytest.raises(ValueError, match="identity"):
        runtime.predict_64(*inputs, component_bundle(*inputs))


def test_real_components_through_http_cache_and_offline_parity(inputs):
    from app.main import create_app
    from app.predictor import Predictor

    sales, stock = deepcopy(inputs)
    for column in ("composite_division", "cities_name", "category_lvl_1", "category_lvl_2",
                   "category_lvl_3", "characteristic"):
        sales[column] = "metadata"
    sales["sales_sum"] = 1.
    sales["discount_sum"] = 0.
    bundle = component_bundle(sales, stock)
    expected = runtime.predict_64(sales, stock, bundle)
    predictor = Predictor(bundle)
    with TestClient(create_app(predictor)) as client:
        response = client.post("/predict", files={
            "sales": ("sales.csv", sales.to_csv(index=False).encode()),
            "stock": ("stock.csv", stock.to_csv(index=False).encode())})
        assert response.status_code == 200, response.text
        actual = pd.read_csv(io.StringIO(response.text), dtype={"date": str, "article": str})
        pd.testing.assert_frame_equal(actual, expected, check_exact=False, atol=1e-14, rtol=1e-14)
        assert client.get("/predict/all").content == response.content
        bad = sales.copy()
        bad.loc[0, "quantity"] = -1
        failed = client.post("/predict", files={"sales": ("bad.csv", bad.to_csv(index=False).encode()),
                                                "stock": ("stock.csv", stock.to_csv(index=False).encode())})
        assert failed.status_code == 422
        assert client.get("/predict/all").content == response.content
