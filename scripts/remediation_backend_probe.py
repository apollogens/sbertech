"""Реальные полноразмерные HTTP запросы к одному локальному uvicorn worker."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter, sleep

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
import psutil
from src.artifacts import file_hash


def run(args):
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    log = (output / "server.log").open("w", encoding="utf-8")
    import os
    env = {**os.environ, "MODEL_DIR": str(args.model_dir.resolve()), "PYTHONUTF8": "1"}
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                "--port", str(args.port), "--workers", "1"], cwd=ROOT, env=env, stdout=log, stderr=log)
    worker = psutil.Process(process.pid)
    peak = [0]
    observed = set()
    def connection():
        return http.client.HTTPConnection("127.0.0.1", args.port, timeout=240)
    def get(path, destination=None):
        conn = connection()
        conn.request("GET", path)
        response = conn.getresponse()
        status, headers = response.status, dict(response.getheaders())
        if destination:
            with destination.open("wb") as stream:
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
            body = None
        else:
            body = response.read()
        conn.close()
        return status, headers, body
    def post(destination, tiny=False):
        boundary = "RemediationEvidenceBoundary20261018"
        parts = []
        for field in ("sales", "stock"):
            path = args.inputs / f"{field}.csv"
            header = (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{field}.csv"\r\n'
                      'Content-Type: text/csv\r\n\r\n').encode()
            parts.append((header, path))
        ending = f"--{boundary}--\r\n".encode()
        size = sum(len(header) + (1 if tiny else path.stat().st_size) + 2 for header, path in parts) + len(ending)
        conn = connection()
        started = perf_counter()
        conn.putrequest("POST", "/predict")
        conn.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
        conn.putheader("Content-Length", str(size))
        conn.endheaders()
        for header, path in parts:
            conn.send(header)
            if tiny:
                conn.send(b"x")
            else:
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        conn.send(chunk)
            conn.send(b"\r\n")
        conn.send(ending)
        response = conn.getresponse()
        status, headers = response.status, dict(response.getheaders())
        with destination.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        conn.close()
        return {"status": status, "headers": headers, "seconds": perf_counter() - started}
    try:
        for attempt in range(120):
            try:
                assert get("/health")[0] == 200
                break
            except (OSError, AssertionError):
                if process.poll() is not None:
                    raise RuntimeError("Uvicorn завершился; см. server.log")
                sleep(.25)
        else:
            raise RuntimeError("Uvicorn не запустился за 30 секунд")
        assert get("/predict/all")[0] == 409
        import threading
        stop = threading.Event()
        def monitor():
            while not stop.wait(.05):
                try:
                    # Windows venv python.exe can be a small launcher whose child
                    # owns the actual interpreter. Include the whole server tree.
                    processes = [worker, *worker.children(recursive=True)]
                    rss = 0
                    for member in processes:
                        try:
                            rss += member.memory_info().rss
                            observed.add(member.pid)
                        except psutil.NoSuchProcess:
                            continue
                    peak[0] = max(peak[0], rss)
                except psutil.NoSuchProcess:
                    return
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        first_path = output / "first.csv"
        first = post(first_path)
        assert first["status"] == 200, first
        assert first["headers"]["x-forecast-version"] == "1"
        expected_hashes = {name: file_hash(args.inputs / f"{name}.csv") for name in ("sales", "stock")}
        for name, digest in expected_hashes.items():
            assert first["headers"][f"x-input-{name}-sha256"] == digest
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(post, output / "second.csv")
            for attempt in range(1200):
                diagnostics = json.loads(get("/diagnostics")[2])
                if diagnostics["post_in_progress"]:
                    break
                if pending.done():
                    raise AssertionError("Не удалось наблюдать выполняющийся полноразмерный POST")
                sleep(.05)
            else:
                raise AssertionError("POST не начал inference за 60 секунд")
            rejected = post(output / "rejected.json", tiny=True)
            assert rejected["status"] == 409
            during = get("/predict/all", output / "during.csv")
            assert during[0] == 200 and during[1]["x-forecast-version"] == "1"
            assert file_hash(output / "during.csv") == file_hash(first_path)
            second = pending.result(timeout=240)
        assert second["status"] == 200 and second["headers"]["x-forecast-version"] == "2"
        assert file_hash(output / "second.csv") == file_hash(first_path)
        failed = post(output / "failed.json", tiny=True)
        assert failed["status"] == 400
        final = get("/predict/all", output / "cached.csv")
        assert final[0] == 200 and final[1]["x-forecast-version"] == "2"
        assert file_hash(output / "cached.csv") == file_hash(first_path)
        offline = pd.read_csv(args.inputs / "offline.csv", dtype={"date": str, "warehouse_name": str, "article": str})
        actual = pd.read_csv(first_path, dtype={"date": str, "warehouse_name": str, "article": str})
        assert actual.iloc[:, :3].equals(offline.iloc[:, :3])
        difference = float(np.max(np.abs(actual.quantity.to_numpy() - offline.quantity.to_numpy())))
        assert difference <= 1e-7, difference
        assert len(actual) == 11 * 799 * 64 and not actual.iloc[:, :3].duplicated().any()
        assert np.isfinite(actual.quantity).all() and (actual.quantity >= 0).all()
        stop.set()
        thread.join()
        result = {"status": "passed", "model_id": first["headers"]["x-model-id"],
                  "rows": len(actual), "date_min": actual.date.min(), "date_max": actual.date.max(),
                  "input_sha256": expected_hashes, "post_seconds": first["seconds"],
                  "replacement_post_seconds": second["seconds"], "concurrent_post_status": rejected["status"],
                  "failed_post_status": failed["status"], "cache_versions": ["1", "2"],
                  "during_get_matches_previous": True, "repeated_post_byte_identical": True,
                  "failed_post_preserves_cache": True, "max_abs_offline_difference": difference,
                  "peak_server_rss_bytes": peak[0],
                  "memory_measurement": "Sum of RSS of the uvicorn launcher and all descendants, sampled every 50 ms; shared pages may be counted more than once",
                  "observed_server_pids": sorted(observed),
                  "network": "local loopback; no external service"}
        (output / "benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, default=ROOT / "data/parity")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/remediation/backend_fullsize")
    parser.add_argument("--port", type=int, default=18091)
    run(parser.parse_args())
