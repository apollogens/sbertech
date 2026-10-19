"""Единая командная строка Nonton: python -m src.cli --help."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def positive_int(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("Требуется положительное целое число")
    return value


def model_options(parser):
    parser.add_argument("--config", type=Path, help="Конфигурация активного release; также FORECAST_CONFIG")
    parser.add_argument("--model-dir", type=Path, help="Явный versioned model bundle")
    parser.add_argument("--strategy", help="nonton-v1, D, W, S, A или equal4:P1")


def selection(args):
    from .runtime import configured_selection

    if args.model_dir is not None:
        return args.model_dir.resolve(), args.strategy
    path, strategy = configured_selection(args.config or os.environ.get("FORECAST_CONFIG"))
    return path, args.strategy or strategy


def selected_bundle(args):
    from .runtime import load_bundle

    path, strategy = selection(args)
    return load_bundle(path, strategy=strategy)


def atomic_csv(frame, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", suffix=".tmp",
                                         dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            frame.to_csv(stream, index=False, float_format="%.17g", lineterminator="\n")
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def predict(args):
    from app.validators import read_csv, validate_history
    from .runtime import predict_64
    from .submission import validate_submission

    bundle = selected_bundle(args)
    sales = validate_history(read_csv(args.sales.read_bytes(), "sales"), "sales", bundle["catalogs"])
    stock = validate_history(read_csv(args.stock.read_bytes(), "stock"), "stock", bundle["catalogs"])
    frame = predict_64(sales, stock, bundle)
    result = validate_submission(frame, sales.date.max(), bundle["catalogs"])
    atomic_csv(frame, args.output)
    result.update(output=str(args.output), sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
                  model_id=bundle["manifest"]["bundle_id"])
    print(json.dumps(result, ensure_ascii=False))


def validate(args):
    import pandas as pd
    from .submission import validate_submission

    bundle = selected_bundle(args)
    frame = pd.read_csv(args.input, dtype={"date": str, "warehouse_name": str, "article": str})
    print(json.dumps(validate_submission(frame, args.origin, bundle["catalogs"]), ensure_ascii=False))


def package(args):
    from .artifacts import file_hash, verify_manifest
    from .runtime import verify_runtime_bundle

    path, strategy = selection(args)
    if args.output.suffix.lower() != ".zip":
        raise ValueError("Архив должен иметь расширение .zip")
    if (path / "runtime_manifest.json").exists():
        config, manifest = verify_runtime_bundle(path)
        from .runtime import normalize_strategy, STRATEGIES
        if normalize_strategy(strategy or config["strategy"]) not in STRATEGIES:
            raise ValueError("Неподдерживаемая стратегия")
        manifest_name = "runtime_manifest.json"
    else:
        if strategy not in (None, "nonton-v1"):
            raise ValueError("Incumbent bundle поддерживает только nonton-v1")
        config = json.loads((path / "config.json").read_text(encoding="utf-8"))
        catalogs = json.loads((path / "catalogs.json").read_text(encoding="utf-8"))
        manifest = verify_manifest(path, config, catalogs)
        manifest_name = "manifest.json"
    files = dict(manifest["files"], **{manifest_name: file_hash(path / manifest_name)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=args.output.parent, suffix=".zip", delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(files):
                source = (path / name).resolve()
                if not source.is_relative_to(path.resolve()):
                    raise ValueError("Недопустимый путь в manifest")
                archive.write(source, name)
        with zipfile.ZipFile(temporary) as archive:
            for name, digest in files.items():
                with archive.open(name) as stream:
                    actual = hashlib.file_digest(stream, "sha256").hexdigest()
                if actual != digest:
                    raise ValueError("Hash изменился при упаковке")
        temporary.replace(args.output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(json.dumps({"output": str(args.output), "bundle_id": manifest["bundle_id"], "files": len(files),
                      "sha256": file_hash(args.output)}, ensure_ascii=False))


def run_script(name, arguments):
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / name), *map(str, arguments)], check=False).returncode


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="command", required=True)
    test = commands.add_parser("test", help="pytest; дополнительные опции после --")
    test.add_argument("pytest_args", nargs=argparse.REMAINDER)
    audit = commands.add_parser("audit", help="Потоковый аудит исходных CSV")
    audit.add_argument("--data-dir", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True)
    train = commands.add_parser("train", help="Обучение incumbent LightGBM по зафиксированному selection")
    train.add_argument("--cache-dir", type=Path, default=ROOT / "cache")
    train.add_argument("--selection", type=Path, default=ROOT / "reports/selection_frozen.json")
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--rounds", type=positive_int)
    backtest = commands.add_parser("backtest", help="Production-like 180-day backtest существующих historical bundles")
    backtest.add_argument("--sales", type=Path)
    backtest.add_argument("--stock", type=Path)
    backtest.add_argument("--output", type=Path)
    backtest.add_argument("--origins", nargs="+")
    score = commands.add_parser("score", help="Исходный официальный scorer без изменения формул")
    score.add_argument("--truth", type=Path, required=True)
    score.add_argument("--submissions", type=Path, nargs="+", required=True)
    score.add_argument("--baseline", type=Path)
    score.add_argument("--method", choices=("rank", "minmax"), default="minmax")
    score.add_argument("--output", type=Path, required=True)
    forecast = commands.add_parser("predict", help="CSV → общий runtime → submission, те же validators, что API")
    model_options(forecast)
    forecast.add_argument("--sales", type=Path, required=True)
    forecast.add_argument("--stock", type=Path, required=True)
    forecast.add_argument("--output", type=Path, required=True)
    validation = commands.add_parser("validate", help="Полная проверка submission grid")
    model_options(validation)
    validation.add_argument("--input", type=Path, required=True)
    validation.add_argument("--origin", required=True)
    packaging = commands.add_parser("package", help="Проверить manifest и создать архив только файлов bundle")
    model_options(packaging)
    packaging.add_argument("--output", type=Path, required=True)
    serve = commands.add_parser("serve", help="API, один worker")
    model_options(serve)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=positive_int, default=8000)
    docker = commands.add_parser("docker", help="Чистая сборка или полная проверка контейнера")
    docker.add_argument("action", choices=("build", "test"))
    docker.add_argument("--image", default="nonton-consolidated")
    docker.add_argument("--bundle", default="model", help="Путь bundle внутри build context")
    docker.add_argument("--strategy", choices=("nonton-v1", "equal4"), default="nonton-v1",
                        help="Reference strategy для проверки контейнера")
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    try:
        if args.command == "test":
            forwarded = args.pytest_args[1:] if args.pytest_args[:1] == ["--"] else args.pytest_args
            paths = ["tests", "reports/qa/check_backend_independent.py"] if not forwarded else forwarded
            return subprocess.run([sys.executable, "-m", "pytest", *paths], cwd=ROOT, check=False).returncode
        if args.command == "audit":
            return run_script("scripts/audit_inputs.py", ["--data-dir", args.data_dir, "--output", args.output])
        if args.command == "train":
            forwarded = ["--cache-dir", args.cache_dir, "--selection", args.selection, "--output-dir", args.output_dir]
            if args.rounds is not None:
                forwarded.extend(["--rounds", args.rounds])
            return run_script("scripts/train_final.py", forwarded)
        if args.command == "backtest":
            forwarded = []
            for name in ("sales", "stock", "output"):
                if getattr(args, name) is not None:
                    forwarded.extend(["--" + name, getattr(args, name)])
            if args.origins:
                forwarded.extend(["--origins", *args.origins])
            return run_script("consolidation/backtest_180.py", forwarded)
        if args.command == "score":
            forwarded = ["--truth", args.truth, "--submissions", *args.submissions,
                         "--method", args.method, "--output", args.output]
            if args.baseline is not None:
                forwarded.extend(["--baseline", args.baseline])
            return run_script("scripts/official_score.py", forwarded)
        if args.command in {"predict", "validate", "package"}:
            {"predict": predict, "validate": validate, "package": package}[args.command](args)
            return 0
        if args.command == "serve":
            import uvicorn
            path, strategy = selection(args)
            os.environ.pop("FORECAST_CONFIG", None)
            os.environ["MODEL_DIR"] = str(path)
            if strategy is not None:
                os.environ["FORECAST_STRATEGY"] = strategy
            else:
                os.environ.pop("FORECAST_STRATEGY", None)
            uvicorn.run("app.main:app", host=args.host, port=args.port, workers=1)
            return 0
        if args.command == "docker":
            if args.action == "build":
                return subprocess.run(["docker", "build", "--no-cache", "--build-arg", f"MODEL_BUNDLE={args.bundle}",
                                       "--tag", args.image, str(ROOT)], check=False).returncode
            return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                                   str(ROOT / "consolidation/docker_verify.ps1"), "-ImageName", args.image,
                                   "-Strategy", args.strategy],
                                  check=False).returncode
        raise ValueError("Неизвестная команда")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"code": "CLI_ERROR", "command": args.command, "detail": str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
