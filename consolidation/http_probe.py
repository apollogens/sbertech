"""Real HTTP checks; standard library transport, streaming multipart upload."""
from pathlib import Path
import argparse
import hashlib
import http.client
import json
import time


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)

    def get(url):
        connection = http.client.HTTPConnection("127.0.0.1", args.port, timeout=3600)
        started = time.perf_counter()
        connection.request("GET", url)
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        return response.status, payload, time.perf_counter() - started

    health = None
    for _ in range(120):
        try:
            status, payload, _ = get("/health")
            if status == 200:
                health = json.loads(payload)
                break
        except OSError:
            pass
        time.sleep(.5)
    if health is None:
        raise RuntimeError("API startup failed")
    assert get("/predict/all")[0] == 409
    if args.restart:
        result = dict(status="passed", health=health, empty_cache_after_restart=True)
        (args.output / "restart.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    def post():
        boundary = "NontonConsolidationBoundary"
        parts = []
        for name, path in (("sales", args.sales), ("stock", args.stock)):
            header = (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                      f'filename="{name}.csv"\r\nContent-Type: text/csv\r\n\r\n').encode()
            parts.append((header, path))
        end = f"--{boundary}--\r\n".encode()
        length = sum(len(header) + path.stat().st_size + 2 for header, path in parts) + len(end)
        connection = http.client.HTTPConnection("127.0.0.1", args.port, timeout=3600)
        started = time.perf_counter()
        connection.putrequest("POST", "/predict")
        connection.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        connection.putheader("Content-Length", str(length))
        connection.endheaders()
        for header, path in parts:
            connection.send(header)
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    connection.send(chunk)
            connection.send(b"\r\n")
        connection.send(end)
        response = connection.getresponse()
        raw = response.read()
        assert response.status == 200, (response.status, raw[:500])
        connection.close()
        return raw, time.perf_counter() - started

    raw, post_seconds = post()
    (args.output / "forecast.csv").write_bytes(raw)
    repeated, repeat_seconds = post()
    assert repeated == raw
    status, cached, get_seconds = get("/predict/all")
    assert status == 200 and cached == raw
    status, filtered, filter_seconds = get("/predict?article=char_article_0&warehouse=warehouse_name_0")
    assert status == 200 and len(filtered.splitlines()) == 65
    status, payload, json_seconds = get("/predict/all?format=json")
    assert status == 200 and len(json.loads(payload)) == 562496
    connection = http.client.HTTPConnection("127.0.0.1", args.port, timeout=3600)
    connection.request("POST", "/predict", b"", {"Content-Type": "multipart/form-data; boundary=bad"})
    response = connection.getresponse()
    response.read()
    assert response.status == 422
    connection.close()
    assert get("/predict/all")[1] == raw
    import numpy as np
    import pandas as pd
    actual = pd.read_csv(args.output / "forecast.csv", dtype={"date": str, "warehouse_name": str, "article": str})
    expected = pd.read_csv(args.reference, dtype={"date": str, "warehouse_name": str, "article": str})
    assert len(actual) == 562496 and actual.iloc[:, :3].equals(expected.iloc[:, :3])
    assert not actual.iloc[:, :3].duplicated().any()
    assert np.isfinite(actual.quantity).all() and actual.quantity.ge(0).all()
    difference = float(np.max(np.abs(actual.quantity - expected.quantity)))
    assert difference < 1e-12
    result = dict(status="passed", rows=len(actual), health=health, post_seconds=post_seconds,
                  repeat_post_seconds=repeat_seconds, get_csv_seconds=get_seconds,
                  get_filtered_seconds=filter_seconds, get_json_seconds=json_seconds,
                  offline_api_max_abs_difference=difference, repeat_byte_identical=True,
                  failure_preserves_cache=True, forecast_sha256=hashlib.sha256(raw).hexdigest())
    for name, path in (("cgroup_peak_rss_bytes", "/sys/fs/cgroup/memory.peak"),
                       ("memory_limit", "/sys/fs/cgroup/memory.max"), ("cpu_limit", "/sys/fs/cgroup/cpu.max")):
        if Path(path).exists():
            result[name] = Path(path).read_text().strip()
    (args.output / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--output", type=Path, default=Path("/tmp/release"))
    parser.add_argument("--sales", type=Path, default=Path("/tmp/sales.csv"))
    parser.add_argument("--stock", type=Path, default=Path("/tmp/stock.csv"))
    parser.add_argument("--reference", type=Path, default=Path("/tmp/release/reference.csv"))
    parser.add_argument("--restart", action="store_true")
    print(json.dumps(run(parser.parse_args()), indent=2))
