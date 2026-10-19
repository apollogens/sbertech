"""Регрессии: целостность комплекта и транзакционная публикация кэша."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import sys
import types
import zipfile
from threading import Event

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import create_app, enforce_single_worker
from app.predictor import Predictor
from src.artifacts import fingerprint, write_manifest, write_training_manifest
from src.predict import load_bundle

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def artifact(tmp_path):
    for name in ("config.json", "catalogs.json", "lightgbm.txt"):
        shutil.copyfile(ROOT / "model" / name, tmp_path / name)
    write_manifest(tmp_path)
    return tmp_path


def rewrite(path, change):
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_artifact_identity_and_exact_prediction_parity(artifact):
    loaded = load_bundle(artifact)
    import lightgbm as lgb
    before = lgb.Booster(model_file=str(artifact / "lightgbm.txt"))
    frame = pd.DataFrame(np.zeros((4, len(loaded["config"]["features"])), dtype=np.float32), columns=loaded["config"]["features"])
    np.testing.assert_array_equal(before.predict(frame, num_threads=1), loaded["model"].predict(frame, num_threads=1))
    assert loaded["manifest"]["provenance"]["status"] == "reconstructed_unverified"
    assert write_manifest(artifact)["bundle_id"] == loaded["manifest"]["bundle_id"]


def test_frozen_original_accepts_wrong_sorted_catalog_fixed_loader_rejects(artifact):
    with zipfile.ZipFile(ROOT / "reports/remediation/original_release.zip") as frozen:
        original = types.ModuleType("src.legacy_predict")
        exec(compile(frozen.read("src/predict.py"), "frozen/src/predict.py", "exec"), original.__dict__)
    rewrite(artifact / "catalogs.json", lambda data: data["articles"].__setitem__(-1, data["articles"][-1] + "_changed"))
    legacy = original.load_bundle(artifact)
    assert legacy["catalogs"]["articles"][-1].endswith("_changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_bundle(artifact)


def test_frozen_original_cache_exposes_mutable_internal_frame():
    with zipfile.ZipFile(ROOT / "reports/remediation/original_release.zip") as frozen:
        original = types.ModuleType("app.legacy_predictor")
        exec(compile(frozen.read("app/predictor.py"), "frozen/app/predictor.py", "exec"), original.__dict__)
    legacy = original.Predictor({})
    legacy._cached_forecast = pd.DataFrame({"quantity": [1.]})
    exported = legacy.get_cached_forecast()
    exported.loc[0, "quantity"] = 999.
    assert legacy.get_cached_forecast().quantity.iloc[0] == 999.


@pytest.mark.parametrize("problem", ["article_order", "warehouse_order", "article_identity", "warehouse_identity", "feature_order", "model_bytes", "config_threshold", "mapping_corrupt", "schema_dtype", "dependency", "preprocessing", "version", "missing_version", "missing_provenance", "missing_manifest", "manifest_corrupt"])
def test_contract_rejects_mismatches(artifact, problem):
    if problem in ("article_order", "warehouse_order", "article_identity", "warehouse_identity"):
        key = "articles" if problem.startswith("article") else "warehouses"
        def mutate(data):
            if problem.endswith("order"):
                data[key].reverse()
            else:
                data[key][-1] += "_changed"
        rewrite(artifact / "catalogs.json", mutate)
    elif problem == "feature_order":
        rewrite(artifact / "config.json", lambda data: data["features"].reverse())
    elif problem == "config_threshold":
        rewrite(artifact / "config.json", lambda data: data.update(zero_threshold=0.0))
    elif problem == "model_bytes":
        with (artifact / "lightgbm.txt").open("ab") as stream:
            stream.write(b"\nchanged")
    elif problem == "missing_manifest":
        (artifact / "manifest.json").unlink()
    elif problem == "manifest_corrupt":
        (artifact / "manifest.json").write_text("{")
    else:
        def mutate(data):
            if problem == "version":
                data["artifact_contract_version"] = 999
            elif problem == "missing_version":
                data.pop("artifact_contract_version")
            elif problem == "missing_provenance":
                data.pop("provenance")
            elif problem == "mapping_corrupt":
                data["metadata"]["category_mapping"]["articles"][0]["id"] = 3
            elif problem == "schema_dtype":
                data["metadata"]["feature_schema"][0]["dtype"] = "float64"
            elif problem == "dependency":
                data["metadata"]["dependencies"]["numpy"] = "0.0"
            elif problem == "preprocessing":
                data["metadata"]["preprocessing"]["data.py"] = "0" * 64
            if "metadata" in data:
                data["metadata_sha256"] = fingerprint(data["metadata"])
            data.pop("bundle_id")
            data["bundle_id"] = fingerprint(data)
        rewrite(artifact / "manifest.json", mutate)
    with pytest.raises((ValueError, KeyError), match="manifest|Artifact|artifact|catalog|contract|provenance"):
        load_bundle(artifact)


@pytest.mark.parametrize("name", ["config.json", "catalogs.json", "lightgbm.txt"])
def test_contract_missing_files(artifact, name):
    (artifact / name).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        load_bundle(artifact)


def test_training_record_is_bound_and_cross_checked(artifact):
    record = {"training_run_id": "synthetic-evidence-test", "training_data_sha256": {"panel.npz": "a" * 64},
              "model_sha256": hashlib.sha256((artifact / "lightgbm.txt").read_bytes()).hexdigest()}
    (artifact / "training_record.json").write_text(json.dumps(record), encoding="utf-8")
    provenance = {"status": "training_recorded", "training_run_id": record["training_run_id"],
                  "training_data_sha256": record["training_data_sha256"], "training_record_file": "training_record.json"}
    write_manifest(artifact, provenance=provenance)
    assert load_bundle(artifact)["manifest"]["provenance"] == provenance
    rewrite(artifact / "training_record.json", lambda data: data.update(training_run_id="wrong-run"))
    # Даже повторная упаковка несовместимого журнала не доказывает совпадение run.
    write_manifest(artifact, provenance=provenance)
    with pytest.raises(ValueError, match="provenance mismatch"):
        load_bundle(artifact)


@pytest.mark.parametrize("problem", ["missing", "modified"])
def test_training_record_missing_or_modified_rejected(artifact, problem):
    record = {"training_run_id": "synthetic-negative-test", "training_data_sha256": {"panel.npz": "b" * 64},
              "model_sha256": hashlib.sha256((artifact / "lightgbm.txt").read_bytes()).hexdigest()}
    write_training_manifest(artifact, record)
    if problem == "missing":
        (artifact / "training_record.json").unlink()
    else:
        rewrite(artifact / "training_record.json", lambda data: data.update(training_run_id="changed"))
    with pytest.raises(ValueError, match="artifact file|hash mismatch"):
        load_bundle(artifact)


def test_startup_default_model_path_is_independent_of_cwd(api, monkeypatch, tmp_path):
    _, engine, _, _, _ = api
    seen = []
    monkeypatch.delenv("MODEL_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    def fake_load(path):
        seen.append(path)
        return engine
    monkeypatch.setattr(Predictor, "load", fake_load)
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
    assert seen == [ROOT / "model"]


@pytest.fixture
def api(monkeypatch):
    catalogs = {"warehouses": ["w"], "articles": ["001"]}
    sales = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=180).strftime("%Y-%m-%d"),
                          "warehouse_name": "w", "article": "001", "quantity": 1.0})
    for name in ("composite_division", "cities_name", "category_lvl_1", "category_lvl_2", "category_lvl_3", "characteristic"):
        sales[name] = "m"
    sales["sales_sum"], sales["discount_sum"] = 1., 0.
    stock = sales[["date", "warehouse_name", "article", "quantity"]].rename(columns={"quantity": "stock"})
    def inference(sales, stock, bundle):
        return pd.DataFrame({"date": pd.date_range(pd.to_datetime(sales.date).max() + pd.Timedelta(days=1), periods=64),
                             "warehouse_name": "w", "article": "001", "quantity": float(sales.quantity.mean())})
    monkeypatch.setattr("app.predictor.predict_64", inference)
    engine = Predictor({"config": {"model_version": "test"}, "catalogs": catalogs, "manifest": {"bundle_id": "a" * 64}})
    with TestClient(create_app(engine)) as client:
        yield client, engine, sales, stock, inference


def post(client, sales, stock):
    return client.post("/predict", files={"sales": ("sales.csv", sales.to_csv(index=False).encode()),
                                          "stock": ("stock.csv", stock.to_csv(index=False).encode())})


def test_cache_identity_replacement_restart_and_mutation_isolation(api):
    client, engine, sales, stock, _ = api
    assert client.get("/diagnostics").json()["cache"] is None
    first = post(client, sales, stock)
    assert first.status_code == 200
    assert first.headers["x-forecast-version"] == "1"
    assert first.headers["x-model-id"] == "a" * 64
    assert first.headers["x-input-sales-sha256"] == hashlib.sha256(sales.to_csv(index=False).encode()).hexdigest()
    exported = engine.get_cached_forecast()
    exported.loc[0, "quantity"] = 999
    exported.attrs["cache_metadata"]["version"] = 999
    assert client.get("/predict/all").content == first.content
    assert client.get("/predict/all").headers["x-forecast-version"] == "1"
    sales["quantity"] = 2.
    second = post(client, sales, stock)
    assert second.status_code == 200 and second.content != first.content
    assert second.headers["x-forecast-version"] == "2"
    assert second.headers["x-input-sales-sha256"] != first.headers["x-input-sales-sha256"]
    assert client.get("/predict/all").content == second.content
    assert client.get("/predict/all?format=json").headers["x-forecast-version"] == "2"
    restarted = Predictor(engine.bundle)
    with TestClient(create_app(restarted)) as fresh:
        assert fresh.get("/predict/all").status_code == 409
        assert fresh.get("/diagnostics").json()["cache"] is None


@pytest.mark.parametrize("failure", [False, True])
def test_actual_concurrent_http_post_exclusion_and_committed_reads(api, monkeypatch, failure):
    client, engine, sales, stock, inference = api
    first = post(client, sales, stock)
    entered, release = Event(), Event()
    def blocked(*args):
        entered.set()
        assert release.wait(10), "Запрос не освобождён тестом"
        if failure:
            raise RuntimeError("injected failure")
        return inference(*args)
    monkeypatch.setattr("app.predictor.predict_64", blocked)
    changed = sales.assign(quantity=2.)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(post, client, changed, stock)
        assert entered.wait(10)
        try:
            assert post(client, sales, stock).status_code == 409
            assert client.get("/predict/all").content == first.content
            assert client.get("/diagnostics").json()["cache"]["version"] == 1
        finally:
            release.set()
        completed = pending.result(timeout=10)
    assert completed.status_code == (500 if failure else 200)
    expected = first if failure else completed
    assert client.get("/predict/all").content == expected.content
    assert client.get("/predict/all").headers["x-forecast-version"] == ("1" if failure else "2")
    monkeypatch.setattr("app.predictor.predict_64", inference)
    assert post(client, sales, stock).status_code == 200  # Блокировка освобождена и после отказа.


def test_invalid_upload_preserves_identity_and_version(api):
    client, _, sales, stock, _ = api
    first = post(client, sales, stock)
    failed = post(client, sales.assign(quantity=-1.), stock)
    assert failed.status_code == 422
    cached = client.get("/predict/all")
    assert cached.content == first.content
    assert cached.headers["x-forecast-version"] == "1"
    assert cached.headers["x-input-sales-sha256"] == first.headers["x-input-sales-sha256"]


@pytest.mark.parametrize("arguments", [["--workers", "2"], ["--workers=2"], ["-w", "2"], ["-w2"]])
def test_multiple_workers_rejected(monkeypatch, arguments):
    monkeypatch.setattr(sys, "argv", ["uvicorn", *arguments])
    with pytest.raises(RuntimeError, match="one worker"):
        enforce_single_worker()


@pytest.mark.parametrize("name", ["WEB_CONCURRENCY", "UVICORN_WORKERS"])
def test_multiple_worker_environment_rejected(monkeypatch, name):
    monkeypatch.setenv(name, "2")
    with pytest.raises(RuntimeError, match="one worker"):
        with TestClient(create_app(Predictor({}))):
            pass
