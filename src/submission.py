from pathlib import Path
import numpy as np
import pandas as pd


def forecast_frame(predictions, origin, catalogs):
    predictions = np.asarray(predictions)
    expected_shape = (64, len(catalogs["warehouses"]) * len(catalogs["articles"]))
    if predictions.shape != expected_shape:
        raise ValueError(f"Wrong prediction shape: expected {expected_shape}, got {predictions.shape}")
    dates = pd.date_range(pd.Timestamp(origin) + pd.Timedelta(days=1), periods=64)
    grid = pd.MultiIndex.from_product([dates, catalogs["warehouses"], catalogs["articles"]],
                                      names=["date", "warehouse_name", "article"])
    frame = grid.to_frame(index=False)
    frame["date"] = frame.date.dt.strftime("%Y-%m-%d")
    frame["quantity"] = predictions.reshape(-1).astype(float)
    validate_submission(frame, origin, catalogs)
    return frame


def validate_submission(frame, origin, catalogs):
    columns = ["date", "warehouse_name", "article", "quantity"]
    if list(frame.columns) != columns:
        raise ValueError("Wrong output columns")
    grid = pd.MultiIndex.from_product([
        pd.date_range(pd.Timestamp(origin)+pd.Timedelta(days=1), periods=64).strftime("%Y-%m-%d"),
        catalogs["warehouses"], catalogs["articles"]], names=columns[:3])
    actual = pd.MultiIndex.from_frame(frame[columns[:3]])
    if len(frame) != len(grid) or actual.has_duplicates or not actual.equals(grid):
        raise ValueError("Incomplete or incorrectly ordered forecast grid")
    q = frame.quantity.to_numpy(dtype=float)
    if not np.isfinite(q).all() or (q < 0).any():
        raise ValueError("Invalid predictions")
    return {"rows": len(frame), "dates": 64, "status": "passed"}


def write_submission(frame, path, origin, catalogs):
    path = Path(path)
    frame.to_csv(path, index=False, float_format="%.10g")
    actual = pd.read_csv(path, dtype={"date": str, "warehouse_name": str, "article": str})
    return validate_submission(actual, origin, catalogs)
