import json
from pathlib import Path
import numpy as np
import lightgbm as lgb

from .data import build_panel
from .features import snapshot, horizon_features
from .baselines import baseline_predict
from .submission import forecast_frame
from .artifacts import verify_manifest


def load_bundle(path="model"):
    path = Path(path)
    config = json.loads((path / "config.json").read_text(encoding="utf-8"))
    if config["schema_version"] != 1 or config["horizon"] != 64:
        raise ValueError("Unsupported model schema")
    if config["kind"] not in ("lightgbm", "baseline"):
        raise ValueError("Unsupported model kind")
    if config["kind"] == "baseline" and config.get("baseline") not in ("zero", "last", "mean28", "mean90", "seasonal56", "tsb"):
        raise ValueError("Unsupported baseline kind")
    threshold = config.get("zero_threshold", 0.)
    if not isinstance(threshold, (int, float)) or not np.isfinite(threshold) or threshold < 0:
        raise ValueError("Invalid zero threshold")
    bundle = {"config": config, "catalogs": json.loads((path / "catalogs.json").read_text(encoding="utf-8"))}
    for key in ("warehouses", "articles"):
        values = bundle["catalogs"][key]
        # The training encoder always uses catalog_from_sales' sorted order.
        if not values or any(not isinstance(v, str) or not v.strip() for v in values) or len(set(values)) != len(values) or values != sorted(values):
            raise ValueError(f"Invalid {key} catalog")
    bundle["manifest"] = verify_manifest(path, config, bundle["catalogs"])
    if config["kind"] == "lightgbm":
        bundle["model"] = lgb.Booster(model_file=str(path / "lightgbm.txt"))
        if bundle["model"].feature_name() != config["features"]:
            raise ValueError("Model feature schema mismatch")
    return bundle


def predict_panel(panel, origin, bundle):
    config = bundle["config"]
    if config["kind"] == "baseline":
        prediction = baseline_predict(panel, origin, config["baseline"])
    else:
        snap = snapshot(panel, origin)
        prediction = []
        # Moderate batches avoid 64 separate OpenMP setup overheads and huge frames.
        import pandas as pd
        for start in range(1, 65, 8):
            frame = pd.concat([horizon_features(snap, panel.dates[origin], h) for h in range(start,start+8)], ignore_index=True)
            if frame.columns.tolist() != config["features"]:
                raise ValueError("Inference feature order mismatch")
            prediction.append(bundle["model"].predict(frame, num_threads=4).reshape(8,-1))
        prediction = np.concatenate(prediction)
    if not np.isfinite(prediction).all():
        raise ValueError("Model returned nonfinite values")
    prediction = np.maximum(prediction, 0)
    threshold = config.get("zero_threshold", 0)
    return np.where(prediction < threshold, 0, prediction)


def predict_64(sales, stock, bundle):
    panel = build_panel(sales, stock, catalogs=bundle["catalogs"])
    if len(panel.dates) < 180:
        raise ValueError("At least 180 days required")
    return forecast_frame(predict_panel(panel, len(panel.dates)-1, bundle), panel.dates[-1], panel.catalogs)
