"""Bounded author review: frozen arithmetic and independent saved-output scoring."""

import ast
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from scripts import official_score
from src.artifacts import file_hash
from src.data import load_panel
from src.ensemble import expected_grid


def functions(text):
    return {node.name: node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef)}


def main():
    checks = {}
    with zipfile.ZipFile(ROOT / "consolidation/legacy_source.zip") as archive:
        old = functions(archive.read("scripts/architecture_experiments.py").decode("utf-8"))
        new = functions((ROOT / "src/temporal.py").read_text(encoding="utf-8"))
        for name in ("weekly_frame", "weekday_weights", "allocate_buckets", "warehouse_shares"):
            checks[f"temporal_ast_{name}"] = ast.dump(old[name]) == ast.dump(new[name])
        old = functions(archive.read("integration/catalog_policy.py").decode("utf-8"))
        new = functions((ROOT / "src/catalog.py").read_text(encoding="utf-8"))
        for name in ("stable_codes", "expand_to_output"):
            checks[f"catalog_ast_{name}"] = ast.dump(old[name]) == ast.dump(new[name])
    preservation = json.loads((ROOT / "consolidation/pre_merge_manifest.json").read_text())
    preserved_files = {name.replace("\\", "/"): metadata for name, metadata in preservation["files"].items()}
    for name in ("src/data.py", "src/features.py", "src/baselines.py", "src/predict.py",
                 "src/submission.py", "src/artifacts.py", "scripts/official_score.py"):
        checks[f"preserved_{name}"] = file_hash(ROOT / name) == preserved_files[name]["sha256"]
    assert all(checks.values()), checks
    panel = load_panel(ROOT / "cache")
    output = ROOT / "consolidation/backtest_180"
    metrics = pd.read_csv(output / "metrics.csv")
    means = pd.read_csv(output / "development_means.csv")
    columns = ["smape", "wape", "rmse", "bias", "rmsle"]
    dev = metrics[(metrics.role == "development") & (metrics.group == "all")]
    recalculated_means = dev.groupby(["history", "candidate"])[columns].mean().reset_index()
    merged = means.merge(recalculated_means, on=["history", "candidate"], suffixes=("_csv", "_recomputed"))
    mean_error = max(float(np.max(np.abs(merged[c + "_csv"] - merged[c + "_recomputed"]))) for c in columns)
    assert mean_error < 1e-10
    scored = []
    for origin in ("2025-09-14", "2026-03-25"):
        position = panel.dates.get_loc(origin)
        truth = panel.y[position + 1:position + 65].astype(np.float64)
        keys = expected_grid(origin, panel.catalogs)
        assert len(keys) == 562496 and not keys.duplicated().any()
        for candidate in ("D:P1", "W:P1", "S:P1", "A:P1", "equal4:P1"):
            with np.load(output / f"{candidate.replace(':', '_')}_{origin}.npz") as saved:
                assert str(saved["origin"]) == origin and int(saved["history_days"]) == 180
                prediction = saved["prediction"].astype(np.float64)
            assert prediction.shape == truth.shape == (64, 8789)
            assert np.isfinite(prediction).all() and (prediction >= 0).all()
            smapes, biases = [], []
            for actual_series, predicted_series in zip(truth.T, prediction.T):
                smapes.append(official_score.smape_series(actual_series, predicted_series))
                bias = official_score.bias_abs_series(actual_series, predicted_series)
                if bias is not None:
                    biases.append(bias)
            scores = {
                "smape": float(np.mean(smapes)), "bias": float(np.mean(biases)),
                "wape": official_score.wape(truth, prediction),
                "rmse": official_score.rmse(truth, prediction),
                "rmsle": official_score.rmsle(truth, prediction),
            }
            row = metrics[(metrics.origin == origin) & (metrics.candidate == candidate) &
                          (metrics.history == "provided180") & (metrics.group == "all")].iloc[0]
            error = max(abs(scores[name] - row[name]) for name in columns)
            assert error < 1e-10
            scored.append(dict(origin=origin, candidate=candidate, max_metric_error=error))
    result = dict(status="passed", reviewer="Agent A; author of extracted runtime modules, not independent authorship",
                  scope="No training or inference; frozen AST/source checks and saved-output metric recomputation",
                  checks=checks, development_mean_max_abs_error=mean_error, saved_output_checks=scored,
                  limitations=["10 of 25 new predictions rescored; all means recomputed",
                               "No real-component W/S/A parity inference in this bounded review",
                               "CSV real replay covers incumbent and equal4; sum parity alone cannot prove component parity",
                               "Series scorer functions used directly; full quadratic merge not executed"])
    replay_path = ROOT / "consolidation/component_replay_result.json"
    if replay_path.exists():
        result["real_component_replay"] = json.loads(replay_path.read_text(encoding="utf-8"))
        result["limitations"] = [value for value in result["limitations"]
                                 if not value.startswith(("No real-component", "CSV real replay"))]
        result["limitations"].append("Real-weight component parity checked on one final180 input; not on all historical origins")
    (ROOT / "consolidation/ml_output_review.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
