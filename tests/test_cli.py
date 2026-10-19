"""Unified CLI with real baseline artifacts and CSV output, without fitting."""

import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pandas as pd
import pytest

from src import cli
from src.artifacts import file_hash, write_manifest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def files(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text(json.dumps({"kind": "baseline", "baseline": "mean28", "schema_version": 1,
                                                  "horizon": 64, "model_version": "cli-test", "zero_threshold": .25}))
    (model / "catalogs.json").write_text(json.dumps({"warehouses": ["w"], "articles": ["a"]}))
    write_manifest(model)
    dates = pd.date_range("2024-01-01", periods=180).strftime("%Y-%m-%d")
    sales = pd.DataFrame({"date": dates, "warehouse_name": "w", "article": "a", "quantity": 1.})
    for column in ("composite_division", "cities_name", "category_lvl_1", "category_lvl_2", "category_lvl_3", "characteristic"):
        sales[column] = "x"
    sales["sales_sum"] = 1.
    sales["discount_sum"] = 0.
    sales.to_csv(tmp_path / "sales.csv", index=False)
    sales[["date", "warehouse_name", "article"]].assign(stock=2.).to_csv(tmp_path / "stock.csv", index=False)
    return tmp_path, model


def command(*arguments, cwd):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run([sys.executable, "-X", "utf8", "-m", "src.cli", *map(str, arguments)], cwd=cwd,
                          env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)


@pytest.mark.parametrize("name", ["test", "audit", "train", "backtest", "score", "predict", "validate", "package", "serve", "docker"])
def test_subcommand_help_and_unknown_option(tmp_path, name):
    assert command(name, "--help", cwd=tmp_path).returncode == 0
    assert command(name, "--unknown-option", cwd=tmp_path).returncode == 2


def test_real_predict_validate_and_determinism_foreign_cwd(files):
    folder, model = files
    outputs = [folder / "one.csv", folder / "two.csv"]
    for output in outputs:
        result = command("predict", "--model-dir", model, "--sales", folder / "sales.csv",
                         "--stock", folder / "stock.csv", "--output", output, cwd=folder)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["rows"] == 64
    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    result = command("validate", "--model-dir", model, "--input", outputs[0], "--origin", "2024-06-28", cwd=folder)
    assert result.returncode == 0, result.stderr
    frame = pd.read_csv(outputs[0])
    assert frame.quantity.eq(1.).all()


def test_invalid_request_does_not_overwrite_output(files):
    folder, model = files
    output = folder / "keep.csv"
    output.write_text("previous valid output")
    sales = pd.read_csv(folder / "sales.csv")
    sales.loc[0, "quantity"] = -1
    sales.to_csv(folder / "sales.csv", index=False)
    result = command("predict", "--model-dir", model, "--sales", folder / "sales.csv", "--stock", folder / "stock.csv",
                     "--output", output, cwd=folder)
    assert result.returncode == 2
    # API InputError is converted to the same structured CLI error boundary.
    assert "Traceback" not in result.stderr
    assert output.read_text() == "previous valid output"


def test_package_contains_only_verified_bundle_files(files):
    folder, model = files
    (model / "unrelated-debug.csv").write_text("not an artifact")
    output = folder / "bundle.zip"
    result = command("package", "--model-dir", model, "--output", output, cwd=folder)
    assert result.returncode == 0, result.stderr
    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == {"config.json", "catalogs.json", "manifest.json"}
        for name in archive.namelist():
            assert archive.read(name) == (model / name).read_bytes()
    assert json.loads(result.stdout)["sha256"] == file_hash(output)
    (model / "catalogs.json").write_text("{}")
    result = command("package", "--model-dir", model, "--output", folder / "corrupt.zip", cwd=folder)
    assert result.returncode == 2 and not (folder / "corrupt.zip").exists()


def test_config_selection_and_zero_rounds(files):
    folder, _ = files
    config = folder / "release.json"
    config.write_text(json.dumps({"schema_version": 1, "active_bundle": "model", "active_strategy": "nonton-v1"}))
    result = command("predict", "--config", config, "--sales", folder / "sales.csv", "--stock", folder / "stock.csv",
                     "--output", folder / "configured.csv", cwd=folder)
    assert result.returncode == 0, result.stderr
    assert command("train", "--rounds", "0", "--output-dir", folder / "never", cwd=folder).returncode == 2
    assert not (folder / "never").exists()


def test_real_audit_and_official_score(files):
    folder, _ = files
    (folder / "sales.csv").rename(folder / "sales_dataset_hakaton_train.csv")
    (folder / "stock.csv").rename(folder / "stock_dataset_hakaton_train.csv")
    audit = command("audit", "--data-dir", folder, "--output", folder / "audit.json", cwd=folder)
    assert audit.returncode == 0, audit.stderr
    assert json.loads((folder / "audit.json").read_text(encoding="utf-8"))["sales"]["rows"] == 180
    forecast = pd.DataFrame({"date": ["2024-07-01"], "warehouse_name": ["w"], "article": ["a"], "quantity": [1.]})
    forecast.to_csv(folder / "truth.csv", index=False)
    forecast.to_csv(folder / "candidate.csv", index=False)
    score = command("score", "--truth", folder / "truth.csv", "--submissions", folder / "candidate.csv",
                    "--method", "rank", "--output", folder / "score.csv", cwd=folder)
    assert score.returncode == 0, score.stderr
    assert (folder / "score.csv").exists()


def test_help_imports_no_training_module(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    code = "import src.cli, sys; assert 'src.train' not in sys.modules; assert 'integration.corrected_models' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code], env=env, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_backtest_arguments_and_failure_exit_propagation(monkeypatch, tmp_path):
    calls = []

    def run(name, arguments):
        calls.append((name, list(map(str, arguments))))
        return 7

    monkeypatch.setattr(cli, "run_script", run)
    assert cli.main(["backtest", "--sales", "sales.csv", "--stock", "stock.csv", "--output", str(tmp_path),
                     "--origins", "2025-09-14", "2025-11-17"]) == 7
    assert calls == [("consolidation/backtest_180.py", ["--sales", "sales.csv", "--stock", "stock.csv", "--output",
                                                       str(tmp_path), "--origins", "2025-09-14", "2025-11-17"])]


def test_serve_explicit_model_overrides_config_environment(monkeypatch, tmp_path):
    import uvicorn

    monkeypatch.setenv("FORECAST_CONFIG", str(tmp_path / "missing-environment-config"))
    monkeypatch.setenv("MODEL_DIR", "old-model")
    monkeypatch.setenv("FORECAST_STRATEGY", "old-strategy")
    calls = []

    def run(app, **kwargs):
        calls.append((app, kwargs, os.environ.get("MODEL_DIR"), os.environ.get("FORECAST_STRATEGY"),
                      os.environ.get("FORECAST_CONFIG")))

    monkeypatch.setattr(uvicorn, "run", run)
    assert cli.main(["serve", "--model-dir", str(tmp_path / "selected"), "--strategy", "D",
                     "--config", str(tmp_path / "missing-flag-config"), "--port", "8123"]) == 0
    assert calls == [("app.main:app", {"host": "127.0.0.1", "port": 8123, "workers": 1},
                      str((tmp_path / "selected").resolve()), "D", None)]


def test_docker_candidate_selects_correct_reference(monkeypatch):
    from types import SimpleNamespace
    calls = []

    def run(argv, check):
        calls.append(argv)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli.subprocess, "run", run)
    assert cli.main(["docker", "test", "--image", "candidate:qa", "--strategy", "equal4"]) == 0
    assert calls[0][-4:] == ["-ImageName", "candidate:qa", "-Strategy", "equal4"]
