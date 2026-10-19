"""Independent backend audit. Run pytest on this file, or --real / --container.

No implementation or model artifacts are modified. --container uses real HTTP
against loopback inside a --network none Docker container.
"""
import concurrent.futures
import hashlib
import io
import json
import platform
import sys
import threading
import time
from pathlib import Path

ROOT = next((p for p in Path(__file__).resolve().parents if (p / "app" / "main.py").is_file()), Path.cwd())
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.predictor import Predictor
from app.validators import InputError, read_csv, validate_history


def histories(warehouses=("w1", "w2"), articles=("001", "002")):
    sales = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=180).strftime("%Y-%m-%d"),
                          "warehouse_name": warehouses[0], "article": articles[0], "quantity": 1.0})
    for column in ("composite_division", "cities_name", "category_lvl_1", "category_lvl_2", "category_lvl_3"):
        sales[column] = "metadata"
    sales["sales_sum"] = 1.0
    sales["discount_sum"] = 0.0
    sales["characteristic"] = "metadata"  # deliberately last for underfull-row fixture
    stock = sales[["date", "warehouse_name", "article", "quantity"]].rename(columns={"quantity": "stock"})
    return sales, stock


def model_stub(sales, stock, bundle):
    dates = pd.date_range(pd.to_datetime(sales.date).max() + pd.Timedelta(days=1), periods=64)
    index = pd.MultiIndex.from_product([dates, bundle["catalogs"]["warehouses"], bundle["catalogs"]["articles"]],
                                      names=["date", "warehouse_name", "article"])
    result = index.to_frame(index=False)
    result["quantity"] = float(sales.quantity.sum())
    return result


def files(sales, stock):
    return {name: (name + ".csv", frame.to_csv(index=False).encode(), "text/csv")
            for name, frame in (("sales", sales), ("stock", stock))}


@pytest.fixture
def backend(monkeypatch):
    monkeypatch.setattr("app.predictor.predict_64", model_stub)
    engine = Predictor({"catalogs": {"warehouses": ["w1", "w2"], "articles": ["001", "002"]},
                        "config": {"model_version": "independent-synthetic"}})
    with TestClient(create_app(engine)) as client:
        yield client, engine


@pytest.mark.parametrize("different", [False, True])
def test_actual_overlapping_posts_and_get_snapshot(backend, monkeypatch, different):
    client, engine = backend
    sales, stock = histories()
    original = client.post("/predict", files=files(sales, stock))
    assert original.status_code == 200
    entered, release = threading.Event(), threading.Event()
    def blocked_model(*args):
        entered.set()
        assert release.wait(15), "Deadlock: test failed to release inference"
        return model_stub(*args)
    monkeypatch.setattr("app.predictor.predict_64", blocked_model)
    changed = sales.copy()
    changed.quantity = 2.0
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        active = pool.submit(client.post, "/predict", files=files(changed, stock))
        try:
            assert entered.wait(15)
            incoming = changed if different else changed.copy()
            rejected = client.post("/predict", files=files(incoming, stock))
            assert rejected.status_code == 409
            assert isinstance(rejected.json()["detail"], str)
            assert rejected.json()["code"] == "REQUEST_ERROR"
            assert client.get("/predict/all").content == original.content
        finally:
            release.set()
        completed = active.result(timeout=15)
    assert completed.status_code == 200
    assert client.get("/predict/all").content == completed.content
    assert completed.content != original.content


def test_validation_failure_preserves_cache(backend):
    client, _ = backend
    sales, stock = histories()
    previous = client.post("/predict", files=files(sales, stock))
    sales.loc[0, "quantity"] = -1
    failed = client.post("/predict", files=files(sales, stock))
    assert failed.status_code == 422
    assert failed.json()["code"] == "VALIDATION_ERROR"
    assert client.get("/predict/all").content == previous.content


def test_separate_worker_and_restart_cache_are_empty(backend):
    client, engine = backend
    sales, stock = histories()
    assert client.post("/predict", files=files(sales, stock)).status_code == 200
    with TestClient(create_app(Predictor(engine.bundle))) as restarted:
        assert restarted.get("/health").json()["model_loaded"] is True
        assert restarted.get("/predict/all").status_code == 409


@pytest.mark.parametrize("payload", [
    b'a,b,c\n1,2\n',  # underfull data row
    b'a,b\n1,2\n3\n',
    b'a,b\n"broken"suffix,2\n',  # invalid characters after closing quote
])
def test_csv_record_structure_rejected(payload):
    with pytest.raises(InputError) as caught:
        read_csv(payload, "sales")
    assert caught.value.status_code == 400


def test_valid_quoted_newline_and_explicit_empty_field():
    frame = read_csv(b'a,b,c\n"quoted\nmetadata",2,\n\n', "sales")
    assert frame.shape == (1, 3)
    assert frame.loc[0, "a"] == "quoted\nmetadata"
    assert frame.loc[0, "c"] == ""


def test_underfull_sales_metadata_is_http400(backend):
    client, _ = backend
    sales, stock = histories()
    lines = sales.to_csv(index=False).splitlines()
    lines[1] = lines[1].rsplit(",", 1)[0]
    payload = {"sales": ("sales.csv", ("\n".join(lines) + "\n").encode()),
               "stock": ("stock.csv", stock.to_csv(index=False).encode())}
    response = client.post("/predict", files=payload)
    assert response.status_code == 400, response.text[:200]
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("name", ["sales", "stock"])
def test_float32_overflow_rejected_before_model(backend, name):
    client, _ = backend
    sales, stock = histories()
    frame, value = (sales, "quantity") if name == "sales" else (stock, "stock")
    frame.loc[0, value] = 1e40
    response = client.post("/predict", files=files(sales, stock))
    assert response.status_code == 422, response.text[:200]
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("name", ["sales", "stock"])
@pytest.mark.parametrize("value", ["1e309", "-Infinity", "NaN", "", " "])
def test_more_nonfinite_numeric_variants(backend, name, value):
    client, _ = backend
    sales, stock = histories()
    frame, column = (sales, "quantity") if name == "sales" else (stock, "stock")
    frame[column] = frame[column].astype(object)
    frame.loc[0, column] = value
    response = client.post("/predict", files=files(sales, stock))
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert response.json()["code"] == "VALIDATION_ERROR"


def real_small_model_tests():
    """Real artifact, full 11x799 output; controlled 180-day histories."""
    engine = Predictor.load(ROOT / "model")
    sales, stock = histories(engine.catalogs["warehouses"], engine.catalogs["articles"])
    cases = {}
    with TestClient(create_app(engine)) as client:
        started = time.perf_counter()
        first = client.post("/predict", files=files(sales, stock))
        cases["post_seconds"] = time.perf_counter() - started
        assert first.status_code == 200, first.text[:500]
        output = pd.read_csv(io.BytesIO(first.content))
        assert output.shape == (562496, 4)
        assert output.date.nunique() == 64
        assert output.date.min() == "2025-06-30" and output.date.max() == "2025-09-01"
        assert not output.duplicated(["date", "warehouse_name", "article"]).any()
        assert np.isfinite(output.quantity).all() and output.quantity.ge(0).all()
        assert client.get("/predict/all").content == first.content
        article, warehouse = engine.catalogs["articles"][0], engine.catalogs["warehouses"][0]
        for query, count in (({"article": article}, 704), ({"warehouse": warehouse}, 51136),
                             ({"article": article, "warehouse": warehouse}, 64)):
            response = client.get("/predict", params=query)
            assert response.status_code == 200
            assert len(pd.read_csv(io.BytesIO(response.content))) == count
        repeated = client.post("/predict", files=files(sales, stock))
        assert repeated.content == first.content
        # Future stock must be invisible: same daily values after cutoff.
        future = stock.copy()
        future.date = pd.date_range("2026-01-01", periods=180).strftime("%Y-%m-%d")
        future.stock = 100000
        future_response = client.post("/predict", files=files(sales, pd.concat([stock, future])))
        assert future_response.content == first.content
        # Both numeric pathways must fail 422 before model / preserve cache.
        overflow = {}
        for name in ("sales", "stock"):
            s, st = sales.copy(), stock.copy()
            frame, column = (s, "quantity") if name == "sales" else (st, "stock")
            frame.loc[0, column] = 1e40
            response = client.post("/predict", files=files(s, st))
            overflow[name] = response.status_code
        cases["overflow_http_statuses"] = overflow
        assert client.get("/predict/all").content == first.content
    cases.update(rows=len(output), model_kind=engine.bundle["config"]["kind"],
                 deterministic_repeated_post=True, future_stock_invariance=True,
                 output_sha256=hashlib.sha256(first.content).hexdigest(), environment=platform.platform())
    print(json.dumps(cases, indent=2))


def container_probe():
    import http.client
    import psutil
    server = psutil.Process(1)
    rss_peak = [server.memory_info().rss]
    stop_monitor = threading.Event()
    def monitor():
        while not stop_monitor.wait(.1):
            rss_peak[0] = max(rss_peak[0], server.memory_info().rss)
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    total_started = time.perf_counter()
    initial_cpu = sum(server.cpu_times()[:2])
    def connection():
        return http.client.HTTPConnection("127.0.0.1", 8000, timeout=3600)
    def get(path, target=None):
        start = time.perf_counter()
        conn = connection(); conn.request("GET", path); response = conn.getresponse()
        if target:
            with Path(target).open("wb") as output:
                while chunk := response.read(1048576):
                    output.write(chunk)
            body = None
        else:
            body = response.read()
        status = response.status; conn.close()
        return status, body, time.perf_counter() - start
    health_status, body, _ = get("/health")
    assert health_status == 200
    result = {"health": json.loads(body), "network_mode": "none", "python": sys.version,
              "platform": platform.platform(), "pre_post_status": get("/predict/all")[0]}
    assert result["pre_post_status"] == 409
    boundary = "IndependentAudit20261018"
    parts = []
    for name in ("sales", "stock"):
        path = Path("/tmp") / (name + ".csv")
        header = (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{name}.csv"\r\nContent-Type: text/csv\r\n\r\n').encode()
        parts.append((header, path))
    ending = f"--{boundary}--\r\n".encode()
    length = sum(len(h) + p.stat().st_size + 2 for h, p in parts) + len(ending)
    def post(target):
        started = time.perf_counter()
        conn = connection(); conn.putrequest("POST", "/predict")
        conn.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        conn.putheader("Content-Length", str(length)); conn.endheaders()
        for header, path in parts:
            conn.send(header)
            with path.open("rb") as source:
                while chunk := source.read(1048576): conn.send(chunk)
            conn.send(b"\r\n")
        conn.send(ending); response = conn.getresponse()
        assert response.status == 200, (response.status, response.read()[:500])
        with Path(target).open("wb") as output:
            while chunk := response.read(1048576): output.write(chunk)
        conn.close()
        return time.perf_counter() - started
    result["post_seconds"] = post("/tmp/audit_post.csv")
    result["repeat_post_seconds"] = post("/tmp/audit_repeat.csv")
    result["get_csv_seconds"] = get("/predict/all", "/tmp/audit_get.csv")[2]
    result["get_json_seconds"] = get("/predict/all?format=json", "/tmp/audit_get.json")[2]
    hashes = [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
              ("/tmp/audit_post.csv", "/tmp/audit_repeat.csv", "/tmp/audit_get.csv")]
    assert len(set(hashes)) == 1
    result["repeat_and_get_byte_identical"] = True
    keys = ["date", "warehouse_name", "article"]
    api = pd.read_csv("/tmp/audit_post.csv", dtype=dict.fromkeys(keys, str))
    offline = pd.read_csv("/tmp/offline.csv", dtype=dict.fromkeys(keys, str))
    assert api[keys].equals(offline[keys])
    assert api.shape == (562496, 4)
    assert not api.duplicated(keys).any()
    difference = float(np.max(np.abs(api.quantity - offline.quantity)))
    assert difference <= 1e-7
    del offline
    json_output = json.loads(Path("/tmp/audit_get.json").read_text())
    assert len(json_output) == len(api)
    json_max_difference = 0.0
    for record, row in zip(json_output, api.itertuples(index=False)):
        assert (record["date"], record["warehouse_name"], record["article"]) == tuple(row[:3])
        assert np.isfinite(record["quantity"]) and record["quantity"] >= 0
        json_max_difference = max(json_max_difference, abs(record["quantity"] - row.quantity))
    assert json_max_difference <= 1e-7
    result.update(rows=len(api), max_abs_difference=difference, tolerance=1e-7,
                  json_rows=len(json_output), json_max_abs_difference=json_max_difference,
                  output_sha256=hashes[0])
    for path, count in (("/predict?article=char_article_0",704),
                        ("/predict?warehouse=warehouse_name_0",51136),
                        ("/predict?article=char_article_0&warehouse=warehouse_name_0",64)):
        status, body, _ = get(path)
        assert status == 200 and len(pd.read_csv(io.BytesIO(body))) == count
    for path, expected in (("/predict",400),("/predict?article=missing",404),
                           ("/predict/all?format=xml",400)):
        status, body, _ = get(path)
        assert status == expected and isinstance(json.loads(body)["detail"], str)
    result["memory_peak_bytes"] = int(Path("/sys/fs/cgroup/memory.peak").read_text())
    stop_monitor.set(); monitor_thread.join()
    result["server_peak_rss_bytes"] = rss_peak[0]
    result["server_cpu_seconds"] = sum(server.cpu_times()[:2]) - initial_cpu
    result["total_probe_wall_seconds"] = time.perf_counter() - total_started
    result["cpu_stat"] = Path("/sys/fs/cgroup/cpu.stat").read_text()
    result["status"] = "passed"
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    if "--real" in sys.argv:
        real_small_model_tests()
    elif "--container" in sys.argv:
        container_probe()
