"""Recompute provided180 metrics directly with original official primitives."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
from src.data import load_panel
from scripts.official_score import smape_series, bias_abs_series, wape, rmse, rmsle


def run():
    out = ROOT / "consolidation/independent_review_evidence"
    out.mkdir(exist_ok=True)
    panel = load_panel(ROOT / "cache")
    rows = pd.read_csv(ROOT / "consolidation/backtest_180/metrics.csv")
    rows = rows[(rows.history == "provided180") & (rows.group == "all") & (rows.candidate != "incumbent")]
    errors = []
    for row in rows.itertuples():
        origin = panel.dates.get_loc(row.origin)
        truth = panel.y[origin + 1:origin + 65].astype(float)
        path = ROOT / f"consolidation/backtest_180/{row.candidate.replace(':', '_')}_{row.origin}.npz"
        with np.load(path) as source:
            prediction = source["prediction"]
            assert str(source["origin"]) == row.origin and int(source["history_days"]) == 180
        assert prediction.shape == truth.shape == (64, 8789)
        assert np.isfinite(prediction).all() and (prediction >= 0).all()
        biases = [bias_abs_series(truth[:, i], prediction[:, i]) for i in range(8789)]
        values = {"smape": np.mean([smape_series(truth[:, i], prediction[:, i]) for i in range(8789)]),
                  "bias": np.mean([value for value in biases if value is not None]),
                  "wape": wape(truth, prediction), "rmse": rmse(truth, prediction), "rmsle": rmsle(truth, prediction)}
        errors.append({"origin": row.origin, "candidate": row.candidate,
                       **{key: abs(float(value) - getattr(row, key)) for key, value in values.items()}})
    assert len(errors) == 25
    maximum = max(value for row in errors for key, value in row.items() if key not in ("origin", "candidate"))
    assert maximum < 1e-10
    pd.DataFrame(errors).to_csv(out / "official_metric_errors.csv", index=False)
    result = {"forecasts": len(errors), "metrics_per_forecast": 5, "maximum_absolute_error": maximum,
              "official_primitives_direct": True, "full_compute_all_metrics_merge_performed": False}
    (out / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    run()
