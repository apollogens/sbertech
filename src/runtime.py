"""One inference interface for preserved incumbent and versioned component bundles."""
from __future__ import annotations

import importlib.metadata
import json
import platform
from pathlib import Path

import lightgbm as lgb
import pandas as pd

from .artifacts import file_hash, fingerprint
from .data import build_panel
from .predict import load_bundle as legacy_load_bundle
from .predict import predict_64 as legacy_predict_64
from .submission import validate_submission

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SOURCES = (
    "src/runtime.py", "src/catalog.py", "src/temporal.py", "src/ensemble.py",
    "src/components.py", "src/data.py", "src/features.py", "src/submission.py", "src/artifacts.py",
)
STRATEGIES = {
    "D:P1": {"daily": 1., "weekly": 0., "shape": 0., "article": 0.},
    "W:P1": {"daily": 0., "weekly": 1., "shape": 0., "article": 0.},
    "S:P1": {"daily": 0., "weekly": 0., "shape": 1., "article": 0.},
    "A:P1": {"daily": 0., "weekly": 0., "shape": 0., "article": 1.},
    "equal4:P1": {"daily": .25, "weekly": .25, "shape": .25, "article": .25},
}


def runtime_source_hashes():
    return {name: file_hash(ROOT / name) for name in RUNTIME_SOURCES}


def dependency_versions():
    versions = {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "lightgbm")}
    versions["python"] = ".".join(platform.python_version().split(".")[:2])
    return versions


def normalize_strategy(strategy):
    return strategy + ":P1" if strategy in {"D", "W", "S", "A"} else strategy


def _catalogs(value):
    if not isinstance(value, dict) or set(value) != {"warehouses", "articles"}:
        raise ValueError("Invalid runtime catalog")
    for values in value.values():
        if (not isinstance(values, list) or not values or
                any(not isinstance(v, str) or not v.strip() for v in values) or
                len(values) != len(set(values)) or values != sorted(values)):
            raise ValueError("Invalid runtime catalog identity/order")
    return value


def verify_runtime_bundle(path):
    """Exact allowed file set and provenance are checked before model deserialization."""
    path = Path(path)
    try:
        manifest = json.loads((path / "runtime_manifest.json").read_text(encoding="utf-8"))
        config = json.loads((path / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Missing or invalid runtime bundle") from exc
    identity = dict(manifest)
    bundle_id = identity.pop("bundle_id", None)
    if manifest.get("runtime_contract_version") != 2 or fingerprint(identity) != bundle_id:
        raise ValueError("Runtime manifest identity mismatch")
    expected = {"config.json", "daily.txt", "weekly.txt", "article.txt"}
    if set(manifest.get("files", {})) != expected:
        raise ValueError("Runtime artifact file contract mismatch")
    for name in sorted(expected):
        candidate = path / name
        if not candidate.resolve().is_relative_to(path.resolve()) or file_hash(candidate) != manifest["files"][name]:
            raise ValueError(f"Runtime artifact hash mismatch: {name}")
    if manifest.get("runtime_sources") != runtime_source_hashes():
        raise ValueError("Runtime source contract mismatch")
    if manifest.get("dependencies") != dependency_versions():
        raise ValueError("Runtime dependency contract mismatch")
    if (config.get("schema_version") != 2 or config.get("kind") != "components" or config.get("horizon") != 64 or
            config.get("history_policy") != {"mode": "provided", "minimum_days": 180} or
            config.get("strategies") != STRATEGIES or config.get("postprocessing") != "threshold025"):
        raise ValueError("Unsupported runtime feature/strategy contract")
    catalogs = _catalogs(config.get("catalogs"))
    if manifest.get("catalog_sha256") != fingerprint(catalogs):
        raise ValueError("Runtime catalog identity mismatch")
    from .catalog import stable_codes
    encodings = {kind: [{"identifier": name, "code": int(code)} for name, code in
                        zip(catalogs[kind], stable_codes(catalogs[kind], namespace))]
                 for kind, namespace in (("warehouses", "warehouse"), ("articles", "article"))}
    if config.get("category_encodings") != encodings:
        raise ValueError("Runtime categorical encoding mismatch")
    if set(config.get("features", {})) != {"daily", "weekly", "article"}:
        raise ValueError("Runtime feature schema mismatch")
    for features in config["features"].values():
        if not isinstance(features, list) or not features or len(features) != len(set(features)):
            raise ValueError("Runtime feature schema mismatch")
    if not manifest.get("parent", {}).get("manifest_sha256"):
        raise ValueError("Runtime migration provenance missing")
    return config, manifest


def load_bundle(path="model", strategy=None):
    path = Path(path)
    if not (path / "runtime_manifest.json").exists():
        if strategy not in (None, "nonton-v1"):
            raise ValueError("Incumbent bundle only supports nonton-v1")
        return legacy_load_bundle(path)
    from .components import required_models

    config, manifest = verify_runtime_bundle(path)
    selected = normalize_strategy(strategy or config["strategy"])
    if selected not in STRATEGIES:
        raise ValueError("Unsupported forecasting strategy")
    components = tuple(name for name, weight in STRATEGIES[selected].items() if weight > 0)
    models = {name: lgb.Booster(model_file=str(path / f"{name}.txt")) for name in sorted(required_models(components))}
    if any(model.feature_name() != config["features"][name] for name, model in models.items()):
        raise ValueError("Runtime model feature schema mismatch")
    return {"runtime_kind": "components", "strategy": selected, "models": models, "config": config,
            "manifest": manifest, "catalogs": config["catalogs"]}


def first_seen_from_sales(sales):
    """Membership comes only from request rows, including zero-quantity observations."""
    dates = pd.to_datetime(sales.date, errors="raise").dt.strftime("%Y-%m-%d")
    rows = []
    for column in ("warehouse_name", "article"):
        frame = pd.DataFrame({"key": sales[column].astype(str), "date": dates})
        rows.extend({"source": "sales", "key_type": column, "key": key, "first_date": str(day)}
                    for key, day in frame.groupby("key", sort=True).date.min().items())
    return pd.DataFrame(rows)


def predict_64(sales, stock, bundle):
    if bundle.get("runtime_kind") != "components":
        return legacy_predict_64(sales, stock, bundle)
    from .components import predict_component_frames
    from .ensemble import align_components, convex_combine, expected_grid, forecast_identity

    panel = build_panel(sales, stock, catalogs=bundle["catalogs"])
    if len(panel.dates) < 180:
        raise ValueError("At least 180 days required")
    selected = bundle["strategy"]
    weights = {name: weight for name, weight in bundle["config"]["strategies"][selected].items() if weight > 0}
    frames = predict_component_frames(panel, len(panel.dates)-1, bundle["models"],
                                      first_seen_from_sales(sales), components=tuple(weights))
    identity = forecast_identity(panel.dates[-1], panel.catalogs)
    for frame in frames.values():
        if frame.attrs.get("forecast_identity") != identity:
            raise ValueError("Component origin/horizon/catalog identity mismatch")
        frame.attrs["forecast_identity"] = dict(identity, model_id=bundle["manifest"]["bundle_id"])
    identity["model_id"] = bundle["manifest"]["bundle_id"]
    expected = expected_grid(panel.dates[-1], panel.catalogs)
    aligned = align_components(frames, expected, expected_identity=identity)
    result = expected.copy()
    result["quantity"] = convex_combine(aligned, weights, output_policy="threshold025")
    validate_submission(result, panel.dates[-1], panel.catalogs)
    return result


def configured_selection(config_path=None):
    """Resolve one active release relative to its versioned configuration."""
    path = Path(config_path or ROOT / "config/runtime.json").resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1 or set(config) != {"schema_version", "active_bundle", "active_strategy"}:
        raise ValueError("Invalid runtime selection configuration")
    model_dir = Path(config["active_bundle"])
    return (model_dir if model_dir.is_absolute() else path.parent / model_dir).resolve(), config["active_strategy"]


def configured_bundle(config_path=None):
    model_dir, strategy = configured_selection(config_path)
    return load_bundle(model_dir, strategy=strategy)
