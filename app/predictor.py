"""Адаптер общего ML-инференса и атомарный кэш последнего результата."""

from pathlib import Path
import os
from threading import Lock
from copy import deepcopy
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.runtime import load_bundle, predict_64


class Predictor:
    def __init__(self, bundle: dict):
        self.bundle = deepcopy(bundle)
        self.post_lock = Lock()
        self.cache_lock = Lock()
        self._cached_forecast = None
        self._cache_version = 0

    @classmethod
    def load(cls, model_dir: Path):
        strategy = os.environ.get("FORECAST_STRATEGY")
        return cls(load_bundle(model_dir, strategy=strategy) if strategy else load_bundle(model_dir))

    @property
    def catalogs(self):
        return self.bundle["catalogs"]

    def predict(self, sales: pd.DataFrame, stock: pd.DataFrame, input_identity=None) -> pd.DataFrame:
        result = predict_64(sales, stock, self.bundle)
        expected = ["date", "warehouse_name", "article", "quantity"]
        if list(result.columns) != expected:
            raise ValueError("Inference returned unexpected columns")
        result = result.copy()
        result["date"] = pd.to_datetime(result["date"]).dt.strftime("%Y-%m-%d")
        quantities = pd.to_numeric(result["quantity"], errors="coerce")
        if not np.isfinite(quantities).all() or (quantities < 0).any():
            raise ValueError("Inference returned invalid quantities")
        dates = pd.date_range(pd.to_datetime(sales["date"]).max() + pd.Timedelta(days=1), periods=64).strftime("%Y-%m-%d")
        index = pd.MultiIndex.from_product([dates, self.catalogs["warehouses"], self.catalogs["articles"]], names=expected[:3])
        actual = pd.MultiIndex.from_frame(result[expected[:3]])
        if len(result) != len(index) or actual.has_duplicates or not actual.isin(index).all():
            raise ValueError("Inference returned incomplete or invalid forecast grid")
        result["quantity"] = quantities
        result.sort_values(expected[:3], kind="stable", inplace=True, ignore_index=True)
        with self.cache_lock:
            self._cache_version += 1
            result.attrs["cache_metadata"] = {
                "version": self._cache_version,
                "model_id": self.bundle.get("manifest", {}).get("bundle_id", "unverified-in-memory"),
                "input_sha256": deepcopy(input_identity or {}),
                "committed_at": datetime.now(timezone.utc).isoformat(),
            }
            self._cached_forecast = result.copy(deep=True)
        return result

    def get_cached_forecast(self):
        # Копия не позволяет вызывающему изменить опубликованный snapshot.
        with self.cache_lock:
            return None if self._cached_forecast is None else self._cached_forecast.copy(deep=True)

    def diagnostics(self):
        with self.cache_lock:
            metadata = None if self._cached_forecast is None else deepcopy(self._cached_forecast.attrs["cache_metadata"])
            return {"worker_policy": "single-process-only", "restart_policy": "empty-cache",
                    "post_in_progress": self.post_lock.locked(),
                    "model_id": self.bundle.get("manifest", {}).get("bundle_id", "unverified-in-memory"),
                    "cache": metadata}
