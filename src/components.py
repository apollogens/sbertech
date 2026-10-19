"""Loaded-model component inference without training or research dependencies."""

import numpy as np
import pandas as pd

from .catalog import asof_panel, expand_to_output, safe_snapshot, stable_codes
from .data import Panel
from .features import horizon_features, snapshot
from .ensemble import forecast_identity
from .submission import forecast_frame
from .temporal import (
    BUCKETS,
    allocate_buckets,
    warehouse_shares,
    weekday_weights,
    weekly_frame,
)

COMPONENT_MODELS = {
    "daily": ("daily",),
    "weekly": ("weekly",),
    "shape": ("daily", "weekly"),
    "article": ("article",),
}


def required_models(components):
    """Return the shared Booster dependencies of the requested representations."""
    components = tuple(components)
    if not components or len(set(components)) != len(components):
        raise ValueError("Expected distinct, nonempty component names")
    if set(components) - COMPONENT_MODELS.keys():
        raise ValueError("Unknown component")
    return tuple(sorted({name for component in components for name in COMPONENT_MODELS[component]}))


def article_snapshot(panel, origin, first_observed):
    active, positions = asof_panel(panel, origin, first_observed)
    nw, na = len(active.catalogs["warehouses"]), len(active.catalogs["articles"])
    stock = active.stock.reshape(-1, nw, na)
    aggregate = Panel(
        active.dates,
        active.y.reshape(-1, nw, na).sum(axis=1),
        np.where(np.isfinite(stock).all(axis=1), np.nansum(stock, axis=1), np.nan),
        dict(warehouses=["all_warehouses"], articles=active.catalogs["articles"]),
    )
    frame = snapshot(aggregate, len(active.dates) - 1)
    frame["warehouse_id"] = np.repeat(stable_codes(["all_warehouses"], "aggregate_warehouse"), na)
    frame["article_id"] = stable_codes(active.catalogs["articles"], "article")
    return frame, active, positions


def _daily_prediction(model, frame, origin_date):
    chunks = []
    for start in range(1, 65, 8):
        features = pd.concat(
            [horizon_features(frame, origin_date, h) for h in range(start, start + 8)],
            ignore_index=True,
        )
        if list(features.columns) != model.feature_name():
            raise ValueError("Feature schema mismatch")
        chunks.append(model.predict(features, num_threads=4).reshape(8, -1))
    return np.concatenate(chunks)


def predict_component_frames(
    panel,
    origin,
    models,
    first_observed,
    components=("daily", "weekly", "shape", "article"),
):
    """Predict named representations, sharing daily and weekly model evaluations.

    All history through origin is preserved. No implicit truncation or global
    first-observation catalog is used. Unknown output identities receive zero.
    """
    components = tuple(components)
    required = required_models(components)
    if set(required) - models.keys():
        raise ValueError("Missing required component model")
    snap, positions = safe_snapshot(panel, origin, first_observed)
    active, _ = asof_panel(panel, origin, first_observed)
    if len(active.dates) < 180:
        raise ValueError("At least 180 input days required")
    values = {}
    raw = None
    totals = None
    if "daily" in required:
        raw = _daily_prediction(models["daily"], snap, panel.dates[origin])
        if "daily" in components:
            values["daily"] = raw
    if "weekly" in required:
        totals = []
        for start, end in BUCKETS:
            features = weekly_frame(snap, panel.dates[origin], start, end)
            if list(features.columns) != models["weekly"].feature_name():
                raise ValueError("Feature schema mismatch")
            totals.append(models["weekly"].predict(features, num_threads=4))
        totals = np.stack(totals)
        if "weekly" in components:
            dows = pd.date_range(
                panel.dates[origin] + pd.Timedelta(days=1), periods=64
            ).dayofweek.to_numpy()
            values["weekly"] = allocate_buckets(
                totals, weekday_weights(active, len(active.dates) - 1)[dows]
            )
    if "shape" in components:
        values["shape"] = allocate_buckets(totals, raw)
    if "article" in components:
        article, _, _ = article_snapshot(panel, origin, first_observed)
        article_totals = _daily_prediction(models["article"], article, panel.dates[origin])
        shares = warehouse_shares(active, len(active.dates) - 1)
        values["article"] = (article_totals[:, None, :] * shares[None, :, :]).reshape(64, -1)
    frames = {
        name: forecast_frame(
            expand_to_output(values[name], positions, panel.y.shape[1]),
            panel.dates[origin],
            panel.catalogs,
        )
        for name in components
    }
    for frame in frames.values():
        frame.attrs['forecast_identity'] = forecast_identity(panel.dates[origin], panel.catalogs)
    return frames
