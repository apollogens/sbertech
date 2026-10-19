from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_DATA = Path(r"C:\Users\apollo\Desktop\выборка")


def read_inputs(sales_path, stock_path):
    sales = pd.read_csv(sales_path, dtype={"warehouse_name": str, "article": str})
    stock = pd.read_csv(stock_path, dtype={"warehouse_name": str, "article": str, "char_article": str})
    return sales, stock


def catalog_from_sales(sales):
    return {"warehouses": sorted(sales.warehouse_name.unique().tolist()),
            "articles": sorted(sales.article.unique().tolist())}


@dataclass
class Panel:
    dates: pd.DatetimeIndex
    y: np.ndarray
    stock: np.ndarray
    catalogs: dict

    @property
    def pairs(self):
        return pd.MultiIndex.from_product(
            [self.catalogs["warehouses"], self.catalogs["articles"]],
            names=["warehouse_name", "article"])


def clean_stock(stock):
    """Conservative source repair: remove negatives and ALL ambiguous key rows."""
    stock = stock.copy()
    if "article" not in stock and "char_article" in stock:
        stock = stock.rename(columns={"char_article": "article"})
    stock = stock.loc[pd.to_numeric(stock.stock) >= 0]
    keys = ["date", "warehouse_name", "article"]
    values = stock.groupby(keys, observed=True).stock.transform("nunique")
    return stock.loc[values == 1].drop_duplicates(keys).reset_index(drop=True)


def build_panel(sales, stock, catalogs=None, cutoff=None, negative_stock="error"):
    """Missing sales=0 is an explicit event-export assumption; missing stock=NaN."""
    sales, stock = sales.copy(), stock.copy()
    if "article" in stock and "char_article" in stock:
        if not stock.article.equals(stock.char_article):
            raise ValueError("Conflicting article aliases")
        stock = stock.drop(columns="char_article")
    if "article" not in stock and "char_article" in stock:
        stock = stock.rename(columns={"char_article": "article"})
    for frame, value in [(sales, "quantity"), (stock, "stock")]:
        required = {"date", "warehouse_name", "article", value}
        if not required.issubset(frame.columns):
            raise ValueError(f"Missing columns: {required - set(frame.columns)}")
        if not pd.api.types.is_datetime64_any_dtype(frame["date"]):
            if not frame["date"].astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
                raise ValueError("Invalid date format; expected YYYY-MM-DD")
        frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
        if not frame["date"].eq(frame["date"].dt.normalize()).all():
            raise ValueError("Invalid date: time of day is not supported")
        if frame[["date", "warehouse_name", "article"]].isna().any().any():
            raise ValueError("Missing key")
        if any(frame[key].astype(str).str.strip().eq("").any() for key in ("warehouse_name", "article")):
            raise ValueError("Empty key identifier")
        frame[value] = pd.to_numeric(frame[value], errors="raise")
        if not np.isfinite(frame[value].to_numpy(dtype=float)).all():
            raise ValueError(f"Nonfinite {value}")
    cutoff = pd.Timestamp(cutoff) if cutoff is not None else sales.date.max()
    sales = sales.loc[sales.date <= cutoff]
    stock = stock.loc[stock.date <= cutoff]
    if sales.empty:
        raise ValueError("Empty sales history")
    if (sales.quantity < 0).any():
        raise ValueError("Negative quantity")
    negative = stock.stock < 0
    if negative.any():
        if negative_stock != "missing":
            raise ValueError("Negative stock")
        stock = stock.loc[~negative]
    catalogs = catalogs or catalog_from_sales(sales)
    for frame in [sales, stock]:
        if not frame.warehouse_name.isin(catalogs["warehouses"]).all() or not frame.article.isin(catalogs["articles"]).all():
            raise ValueError("Unknown catalog ID")
    keys = ["date", "warehouse_name", "article"]
    conflicts = stock.groupby(keys, observed=True).stock.nunique()
    if (conflicts > 1).any():
        raise ValueError("Conflicting stock duplicates")
    stock = stock.drop_duplicates(keys)
    sales = sales.groupby(keys, observed=True, as_index=False).quantity.sum()
    # Finite float64 inputs can overflow during aggregation or the float32 cast.
    for frame, value in [(sales, "quantity"), (stock, "stock")]:
        values = frame[value].to_numpy(dtype=float)
        if not np.isfinite(values).all() or (np.abs(values) > np.finfo(np.float32).max).any():
            raise ValueError(f"{value} is outside the finite float32 range after aggregation")
    dates = pd.date_range(sales.date.min(), cutoff, freq="D")
    pairs = pd.MultiIndex.from_product([catalogs["warehouses"], catalogs["articles"]])
    width = len(pairs)
    y = np.zeros((len(dates), width), dtype=np.float32)
    s = np.full_like(y, np.nan)
    for frame, value, target in [(sales, "quantity", y), (stock, "stock", s)]:
        frame = frame.loc[frame.date >= dates[0]]
        di = dates.get_indexer(frame.date)
        pi = pairs.get_indexer(pd.MultiIndex.from_frame(frame[["warehouse_name", "article"]]))
        target[di, pi] = frame[value].to_numpy(dtype=np.float32)
    return Panel(dates, y, s, catalogs)


def prepare_cache(data_dir=DEFAULT_DATA, cache_dir="cache"):
    cache = Path(cache_dir)
    cache.mkdir(exist_ok=True)
    sales, stock = read_inputs(Path(data_dir) / "sales_dataset_hakaton_train.csv",
                               Path(data_dir) / "stock_dataset_hakaton_train.csv")
    audit = {}
    for name, frame, value in [("sales", sales, "quantity"), ("stock", stock, "stock")]:
        keys = ["date", "warehouse_name", "article"]
        audit[name] = {"rows": len(frame), "duplicate_key_rows": int(frame.duplicated(keys).sum()),
                       "negative_values": int((frame[value] < 0).sum()),
                       "missing_by_column": frame.isna().sum().to_dict(),
                       "calendar_unique_days": int(frame.date.nunique())}
    audit["stock"]["conflicting_duplicate_keys"] = int((stock.groupby(["date", "warehouse_name", "article"]).stock.nunique() > 1).sum())
    stock = clean_stock(stock)
    audit["stock"]["clean_rows"] = len(stock)
    panel = build_panel(sales, stock)
    audit["panel"] = {"shape": list(panel.y.shape), "zero_fraction": float((panel.y == 0).mean()),
                      "stock_missing_fraction": float(np.isnan(panel.stock).mean()),
                      "sales_missing_dates": len(panel.dates) - sales.date.nunique(),
                      "pair_positive_day_quantiles": np.quantile((panel.y > 0).mean(axis=0), [0,.25,.5,.75,1]).tolist()}
    np.savez_compressed(cache / "panel.npz", y=panel.y, stock=panel.stock, dates=panel.dates.to_numpy())
    (cache / "catalogs.json").write_text(json.dumps(panel.catalogs), encoding="utf-8")
    Path("reports").mkdir(exist_ok=True)
    Path("reports/detailed_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return panel


def load_panel(cache_dir="cache"):
    cache = Path(cache_dir)
    with np.load(cache / "panel.npz") as data:
        return Panel(pd.DatetimeIndex(data["dates"]), data["y"], data["stock"],
                     json.loads((cache / "catalogs.json").read_text(encoding="utf-8")))
