"""Повторно обучает выбранную архитектуру и записывает проверяемый журнал run."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.artifacts import file_hash, write_training_manifest
from src.data import load_panel
from src.predict import load_bundle
from src.train import train_model
from lightgbm.basic import LightGBMError


def positive_int(value):
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("Количество итераций должно быть положительным")
    return parsed


def run(args):
    started_at = datetime.now(timezone.utc).isoformat()
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    if not isinstance(selection, dict) or not isinstance(selection.get("winner"), str) or not isinstance(selection.get("objectives"), dict):
        raise ValueError("Некорректная структура selection: требуются winner и objectives")
    winner = selection["winner"]
    name, separator, threshold_text = winner.partition("_z")
    if name not in selection["objectives"]:
        raise ValueError("Выбрана baseline архитектура; train_final поддерживает только LightGBM")
    objective = selection["objectives"][name]
    if objective not in ("regression", "tweedie"):
        raise ValueError("Неподдерживаемая целевая функция выбранной архитектуры")
    rounds = args.rounds if args.rounds is not None else selection["rounds"]
    if type(rounds) is not int or rounds < 1:
        raise ValueError("Некорректное число итераций в selection")
    threshold = float(threshold_text) if separator else 0.
    import numpy as np
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("Некорректный zero threshold")
    source_paths = {"panel.npz": args.cache_dir / "panel.npz", "catalogs.json": args.cache_dir / "catalogs.json",
                    "selection.json": args.selection}
    input_hashes = {name: file_hash(path) for name, path in source_paths.items()}
    panel = load_panel(args.cache_dir)
    run_id = "final-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12]
    started = perf_counter()
    bundle = train_model(panel, len(panel.dates) - 1, objective, rounds)
    elapsed = perf_counter() - started
    if {name: file_hash(path) for name, path in source_paths.items()} != input_hashes:
        raise ValueError("Обучающие файлы изменились во время run; публикация отменена")
    bundle["config"]["zero_threshold"] = threshold
    args.output_dir.mkdir(parents=True, exist_ok=True)
    bundle["model"].save_model(str(args.output_dir / "lightgbm.txt"))
    (args.output_dir / "config.json").write_text(json.dumps(bundle["config"], indent=2), encoding="utf-8")
    (args.output_dir / "catalogs.json").write_text(json.dumps(panel.catalogs, indent=2), encoding="utf-8")
    record = {"training_run_id": run_id, "started_at_utc": started_at,
              "completed_at_utc": datetime.now(timezone.utc).isoformat(), "fit_seconds": elapsed,
              "training_data_sha256": input_hashes, "selection": selection,
              "rounds_used": rounds, "training_cutoff": str(panel.dates[-1].date()),
              "training_rows": bundle["config"]["training_rows"],
              "training_source_sha256": {name: file_hash(ROOT / "src" / name)
                                         for name in ("train.py", "features.py", "data.py")},
              "model_sha256": file_hash(args.output_dir / "lightgbm.txt"),
              "invocation": sys.argv,
              "limitation": "Журнал создан текущим run; независимая проверка исполнения и исходных данных проводится отдельно."}
    manifest = write_training_manifest(args.output_dir, record)
    load_bundle(args.output_dir)
    print(json.dumps({"status": "saved", "training_run_id": run_id, "fit_seconds": elapsed,
                      "bundle_id": manifest["bundle_id"], "output_dir": str(args.output_dir)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "cache")
    parser.add_argument("--selection", type=Path, default=ROOT / "reports" / "selection_frozen.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "model")
    parser.add_argument("--rounds", type=positive_int)
    args = parser.parse_args()
    try:
        run(args)
    except (OSError, ValueError, KeyError, TypeError, LightGBMError) as exc:
        parser.exit(2, f"Ошибка обучения финальной модели: {exc}\n")


if __name__ == "__main__":
    main()
