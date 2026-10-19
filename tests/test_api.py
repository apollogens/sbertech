"""Проверки HTTP-контракта на детерминированном синтетическом ML-инференсе."""

import io

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.predictor import Predictor


@pytest.fixture
def setup(monkeypatch):
    bundle = {"catalogs": {"warehouses": ["w1", "w2"], "articles": ["001", "002"]}, "config": {"model_version": "test"}}

    def predict(sales, stock, bundle):
        dates = pd.date_range(pd.to_datetime(sales.date).max() + pd.Timedelta(days=1), periods=64)
        index = pd.MultiIndex.from_product([dates, bundle["catalogs"]["warehouses"], bundle["catalogs"]["articles"]], names=["date", "warehouse_name", "article"])
        frame = index.to_frame(index=False)
        frame["quantity"] = float(sales.quantity.sum()) / 180
        return frame

    monkeypatch.setattr("app.predictor.predict_64", predict)
    engine = Predictor(bundle)
    sales = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=180).strftime("%Y-%m-%d"), "warehouse_name": "w1", "article": "001", "quantity": 1.0})
    for column in ("composite_division", "cities_name", "category_lvl_1", "category_lvl_2", "category_lvl_3", "characteristic"):
        sales[column] = "metadata"
    sales["sales_sum"] = 1.0
    sales["discount_sum"] = 0.0
    stock = sales[["date", "warehouse_name", "article", "quantity"]].rename(columns={"article": "char_article", "quantity": "stock"}).copy()
    with TestClient(create_app(engine)) as client:
        yield client, engine, sales, stock


def post(client, sales, stock):
    return client.post("/predict", files={"sales": ("sales.csv", sales.to_csv(index=False).encode(), "text/csv"), "stock": ("stock.csv", stock.to_csv(index=False).encode(), "text/csv")})


def parse(response):
    return pd.read_csv(io.StringIO(response.text), dtype={"article": str})


def test_full_contract_and_determinism(setup):
    client, engine, sales, stock = setup
    assert client.get("/health").json() == {"status": "ok", "model_loaded": True, "model_version": "test"}
    assert client.get("/predict/all").status_code == 409
    assert client.get("/predict?article=001").status_code == 409
    response = post(client, sales, stock)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    frame = parse(response)
    assert frame.shape == (256, 4)
    assert frame.date.nunique() == 64
    assert frame.date.min() == "2025-06-30"
    assert frame.date.max() == "2025-09-01"
    assert set(frame.article) == {"001", "002"}
    assert np.isfinite(frame.quantity).all() and (frame.quantity >= 0).all()
    assert not frame.duplicated(["date", "warehouse_name", "article"]).any()
    assert post(client, sales, stock).content == response.content
    assert client.get("/predict/all").content == response.content
    assert len(client.get("/predict/all?format=json").json()) == 256
    assert len(parse(client.get("/predict?article=001"))) == 128
    assert len(parse(client.get("/predict?warehouse=w1"))) == 128
    assert len(parse(client.get("/predict?article=001&warehouse=w1"))) == 64
    assert client.get("/predict?article=missing").status_code == 404


@pytest.mark.parametrize("path", ["/predict", "/predict/all?format=xml"])
def test_bad_query_error_shape(setup, path):
    response = setup[0].get(path)
    assert response.status_code == 400
    assert isinstance(response.json()["detail"], str)
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_missing_file(setup):
    response = setup[0].post("/predict")
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert isinstance(response.json()["detail"], str)


@pytest.mark.parametrize("payload", [b"", b"date,warehouse_name,article,quantity\n", b'"unterminated', b"date,date\n1,2", b"date,warehouse_name,article,quantity\n2025-01-01,w1,001,1,unexpected"])
def test_bad_csv(setup, payload):
    client, _, _, stock = setup
    response = client.post("/predict", files={"sales": ("sales.csv", payload), "stock": ("stock.csv", stock.to_csv(index=False).encode())})
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("kind", ["sales", "stock"])
@pytest.mark.parametrize("problem", ["missing", "date", "short", "negative", "nan", "inf", "text", "empty_id", "unknown"])
def test_invalid_history(setup, kind, problem):
    client, _, sales, stock = setup
    frames = {"sales": sales.copy(), "stock": stock.copy()}
    frame = frames[kind]
    value = "quantity" if kind == "sales" else "stock"
    if problem == "missing":
        frame.drop(columns=[value], inplace=True)
    elif problem == "short":
        frames[kind] = frame.iloc[1:]
    else:
        column, bad_value = {"date": ("date", "2025-02-30"), "negative": (value, -1), "nan": (value, "NaN"), "inf": (value, "inf"), "text": (value, "abc"), "empty_id": ("warehouse_name", ""), "unknown": ("warehouse_name", "w3")}[problem]
        frame[column] = frame[column].astype(object)
        frame.loc[0, column] = bad_value
    response = post(client, frames["sales"], frames["stock"])
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_stock_duplicate_policy(setup):
    client, _, sales, stock = setup
    identical = pd.concat([stock, stock.iloc[[0]]], ignore_index=True)
    assert post(client, sales, identical).status_code == 200
    conflict = identical.copy()
    conflict.loc[len(conflict) - 1, "stock"] = 5
    assert post(client, sales, conflict).status_code == 422


def test_sales_duplicates_are_not_dropped(setup):
    client, _, sales, stock = setup
    sales = pd.concat([sales, sales], ignore_index=True)
    result = post(client, sales, stock)
    assert result.status_code == 200
    assert (parse(result).quantity == 2).all()


def test_failed_post_preserves_cache_and_concurrent_post_rejected(setup, monkeypatch):
    client, engine, sales, stock = setup
    good = post(client, sales, stock)
    engine.post_lock.acquire()
    try:
        assert post(client, sales, stock).status_code == 409
        assert client.get("/predict/all").content == good.content
    finally:
        engine.post_lock.release()

    def fail(*args):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr("app.predictor.predict_64", fail)
    assert post(client, sales, stock).status_code == 500
    assert client.get("/predict/all").content == good.content


@pytest.mark.parametrize("problem", ["negative", "incomplete", "duplicate", "bad_date"])
def test_invalid_model_output_not_cached(setup, monkeypatch, problem):
    client, engine, sales, stock = setup
    good = post(client, sales, stock)
    frame = engine.get_cached_forecast().copy()
    if problem == "negative":
        frame.loc[0, "quantity"] = -1
    elif problem == "incomplete":
        frame = frame.iloc[1:]
    elif problem == "duplicate":
        frame.iloc[0] = frame.iloc[1]
    else:
        frame.loc[0, "date"] = "2025-01-01"
    monkeypatch.setattr("app.predictor.predict_64", lambda *args: frame)
    assert post(client, sales, stock).status_code == 500
    assert client.get("/predict/all").content == good.content


def test_stock_article_alias(setup):
    client, _, sales, stock = setup
    stock.rename(columns={"char_article": "article"}, inplace=True)
    assert post(client, sales, stock).status_code == 200


@pytest.mark.parametrize("column", ["composite_division", "cities_name", "category_lvl_1", "category_lvl_2", "category_lvl_3", "characteristic", "sales_sum", "discount_sum"])
def test_required_sales_metadata(setup, column):
    client, _, sales, stock = setup
    response = post(client, sales.drop(columns=[column]), stock)
    assert response.status_code == 422
    assert column in response.json()["detail"]


def test_actual_sales_schema_and_empty_categories(setup):
    client, _, sales, stock = setup
    assert len(sales.columns) == 12
    assert "cost_price" not in sales and "volume_weight" not in sales
    for column in ("category_lvl_1", "category_lvl_2", "category_lvl_3", "characteristic"):
        sales[column] = ""
    assert post(client, sales, stock).status_code == 200


def test_strict_date_format(setup):
    client, _, sales, stock = setup
    sales.loc[0, "date"] = "2025-1-1"
    assert post(client, sales, stock).status_code == 422


@pytest.mark.parametrize("kind", ["sales", "stock", "aggregated_sales"])
def test_unsupported_numeric_range_is_422_and_preserves_cache(setup, kind):
    client, _, sales, stock = setup
    good = post(client, sales, stock)
    if kind == "sales":
        sales.loc[0, "quantity"] = 1e40
    elif kind == "stock":
        stock.loc[0, "stock"] = 1e40
    else:
        sales.quantity = 2e38
        sales = pd.concat([sales, sales], ignore_index=True)
    response = post(client, sales, stock)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert client.get("/predict/all").content == good.content


def test_truncated_metadata_csv_record_is_400(setup):
    client, _, sales, stock = setup
    lines = sales.to_csv(index=False).splitlines()
    lines[1] = lines[1].rsplit(",", 1)[0]
    response = client.post("/predict", files={
        "sales": ("sales.csv", "\n".join(lines).encode()),
        "stock": ("stock.csv", stock.to_csv(index=False).encode()),
    })
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"
