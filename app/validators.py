"""Проверка публичного CSV-контракта без изменения исторических значений."""

import csv
import io
import warnings

import numpy as np
import pandas as pd


SALES_REQUIRED_COLS = {
    "date", "composite_division", "cities_name", "warehouse_name",
    "category_lvl_1", "category_lvl_2", "category_lvl_3", "article",
    "characteristic", "quantity", "sales_sum", "discount_sum",
}


class InputError(ValueError):
    def __init__(self, detail: str, status_code: int = 422):
        super().__init__(detail)
        self.status_code = status_code


def read_csv(content: bytes, name: str) -> pd.DataFrame:
    if not content or not content.strip():
        raise InputError(f"{name}: empty CSV", 400)
    try:
        # pandas допускает недостающие поля и часть повреждённых кавычек.
        # Проверяем структуру всех записей до числового/семантического разбора.
        decoded = content.decode("utf-8-sig")
        records = csv.reader(io.StringIO(decoded), strict=True)
        header = next(records)
        if not header:
            raise InputError(f"{name}: missing CSV header", 400)
        if len(header) != len(set(header)):
            raise InputError(f"{name}: duplicate column names", 400)
        for row in records:
            if not row or (len(row) == 1 and not row[0].strip()):
                continue  # Same blank-line policy as pandas.
            if len(row) != len(header):
                raise InputError(f"{name}: inconsistent CSV field count", 400)
        with warnings.catch_warnings():
            warnings.simplefilter("error", pd.errors.ParserWarning)
            frame = pd.read_csv(io.StringIO(decoded), dtype=str, keep_default_na=False, index_col=False)
    except InputError:
        raise
    except (UnicodeError, ValueError, pd.errors.ParserError, pd.errors.ParserWarning, pd.errors.EmptyDataError, csv.Error, StopIteration) as exc:
        raise InputError(f"{name}: invalid CSV", 400) from exc
    if frame.empty:
        raise InputError(f"{name}: empty CSV", 400)
    return frame


def validate_history(frame: pd.DataFrame, name: str, catalogs: dict) -> pd.DataFrame:
    frame = frame.copy()
    if name == "stock" and "article" not in frame and "char_article" in frame:
        frame.rename(columns={"char_article": "article"}, inplace=True)
    value = "quantity" if name == "sales" else "stock"
    required = SALES_REQUIRED_COLS if name == "sales" else {"date", "warehouse_name", "article", value}
    missing = required - set(frame)
    if missing:
        raise InputError(f"{name}: missing columns: {', '.join(sorted(missing))}")
    if name == "stock" and "char_article" in frame:
        if not frame["article"].eq(frame["char_article"]).all():
            raise InputError("stock: article and char_article disagree")
    for column, catalog in (("warehouse_name", "warehouses"), ("article", "articles")):
        if frame[column].isna().any() or frame[column].str.strip().eq("").any():
            raise InputError(f"{name}: empty {column}")
        unknown = sorted(set(frame[column]) - set(catalogs[catalog]))
        if unknown:
            raise InputError(f"{name}: unknown {column}: {unknown[:10]}")
    if not frame["date"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise InputError(f"{name}: date must have YYYY-MM-DD format")
    dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="coerce")
    if dates.isna().any():
        raise InputError(f"{name}: invalid date")
    span = (dates.max() - dates.min()).days + 1
    if span < 180:
        raise InputError(f"{name}: history is {span} calendar days; minimum is 180")
    numeric = pd.to_numeric(frame[value], errors="coerce")
    if not np.isfinite(numeric.to_numpy(dtype=float)).all() or (numeric < 0).any():
        raise InputError(f"{name}: {value} must be finite numeric values >= 0")
    if (numeric > np.finfo(np.float32).max).any():
        raise InputError(f"{name}: {value} exceeds supported numeric range")
    frame[value] = numeric
    if name == "sales":
        totals = frame.groupby(["date", "warehouse_name", "article"], observed=True)[value].sum().to_numpy(dtype=float)
        if not np.isfinite(totals).all() or (totals > np.finfo(np.float32).max).any():
            raise InputError("sales: aggregated quantity exceeds supported numeric range")
    if name == "stock":
        keys = ["date", "warehouse_name", "article"]
        duplicated = frame.duplicated(keys, keep=False)
        if duplicated.any():
            counts = frame.loc[duplicated].groupby(keys, observed=True)[value].nunique()
            if (counts > 1).any():
                raise InputError("stock: conflicting duplicate date/warehouse/article")
            frame = frame.drop_duplicates(keys)
    return frame
