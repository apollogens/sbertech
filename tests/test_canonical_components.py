"""Runtime-only extraction regressions, including dependency sharing."""

import numpy as np
import pandas as pd
import pytest

from src.catalog import asof_panel, safe_snapshot
from src.components import predict_component_frames, required_models
from src.data import Panel
from src.ensemble import align_components, expected_grid, forecast_identity
from src.features import horizon_features
from src.temporal import allocate_buckets, weekly_frame


def sample_panel():
    dates = pd.date_range("2024-01-01", periods=210)
    values = np.arange(840, dtype=np.float32).reshape(210, 4) % 5
    panel = Panel(dates, values, values.copy(), dict(warehouses=["w1", "w2"], articles=["a", "b"]))
    membership = pd.DataFrame(
        [
            ("sales", "warehouse_name", "w1", "2024-01-01"),
            ("sales", "warehouse_name", "w2", "2024-01-01"),
            ("sales", "article", "a", "2024-01-01"),
            ("sales", "article", "b", "2024-07-20"),
        ],
        columns=["source", "key_type", "key", "first_date"],
    )
    return panel, membership


class CountingModel:
    def __init__(self, features):
        self.features = list(features)
        self.calls = 0

    def feature_name(self):
        return self.features

    def predict(self, frame, num_threads):
        self.calls += 1
        return np.full(len(frame), 2.0)


def test_shape_shares_boosters_and_only_requested_models_are_needed():
    panel, first = sample_panel()
    snap, _ = safe_snapshot(panel, 179, first)
    daily = CountingModel(horizon_features(snap, panel.dates[179], 1).columns)
    weekly = CountingModel(weekly_frame(snap, panel.dates[179], 1, 8).columns)
    frames = predict_component_frames(
        panel, 179, dict(daily=daily, weekly=weekly), first, ("daily", "weekly", "shape")
    )
    assert daily.calls == 8
    assert weekly.calls == 10
    assert required_models(("shape",)) == ("daily", "weekly")
    assert set(frames) == {"daily", "weekly", "shape"}
    assert (frames["daily"].loc[frames["daily"].article == "b", "quantity"] == 0).all()
    only_daily = predict_component_frames(panel, 179, dict(daily=daily), first, ("daily",))
    pd.testing.assert_frame_equal(frames["daily"], only_daily["daily"], check_exact=True)
    assert daily.calls == 16 and weekly.calls == 10


def test_membership_is_explicit_and_future_values_do_not_change_snapshot():
    panel, first = sample_panel()
    before, _ = safe_snapshot(panel, 179, first)
    panel.y[180:] = 1e6
    panel.stock[180:] = -1e6
    after, _ = safe_snapshot(panel, 179, first)
    pd.testing.assert_frame_equal(before, after, check_exact=True)
    active, _ = asof_panel(panel, 179, first)
    assert active.catalogs["articles"] == ["a"]
    with pytest.raises(ValueError, match="Explicit"):
        asof_panel(panel, 179, None)


def test_identity_guard_rejects_same_keys_with_wrong_model_origin_or_catalog():
    catalogs = dict(warehouses=["w"], articles=["a"])
    keys = expected_grid("2024-01-01", catalogs)
    frame = keys.assign(quantity=1.0)
    identity = dict(forecast_identity("2024-01-01", catalogs), model_id="bundle-a")
    frame.attrs["forecast_identity"] = identity
    align_components({"daily": frame}, keys, identity)
    for key in ("origin", "horizon", "catalog_sha256", "model_id"):
        changed = dict(identity, **{key: "wrong"})
        with pytest.raises(ValueError, match="identity"):
            align_components({"daily": frame}, keys, changed)
    wrong_keys = expected_grid("2024-01-02", catalogs)
    with pytest.raises(ValueError, match="keys"):
        align_components({"daily": frame}, wrong_keys)


def test_bucket_conservation_including_one_day_tail():
    totals = np.arange(1, 31, dtype=float).reshape(10, 3)
    prediction = allocate_buckets(totals, np.ones((64, 3)))
    np.testing.assert_array_equal(prediction[-1], totals[-1])
    np.testing.assert_allclose(prediction[:63].reshape(9, 7, 3).sum(axis=1), totals[:9])


def test_missing_or_unknown_component_models_rejected_before_prediction():
    panel, first = sample_panel()
    with pytest.raises(ValueError, match="Missing"):
        predict_component_frames(panel, 179, {}, first, ("shape",))
    with pytest.raises(ValueError, match="Unknown"):
        required_models(("invented",))


def test_history_is_not_silently_truncated_to_180_days():
    panel, first = sample_panel()
    active, _ = asof_panel(panel, 209, first)
    assert len(active.dates) == 210
