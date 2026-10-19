"""Фиксирует текущий комплект; не объявляет старое обучение доказанным."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.artifacts import write_manifest
from src.predict import load_bundle
from lightgbm.basic import LightGBMError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "model")
    args = parser.parse_args()
    try:
        if (args.model_dir / "manifest.json").exists():
            manifest = load_bundle(args.model_dir)["manifest"]
        else:
            manifest = write_manifest(args.model_dir)
            load_bundle(args.model_dir)
    except (ValueError, KeyError, OSError, TypeError, LightGBMError) as exc:
        parser.exit(2, f"Ошибка упаковки модели: {exc}\n")
    print(f"Комплект проверен: {manifest['bundle_id']}; provenance={manifest['provenance']['status']}")


if __name__ == "__main__":
    main()
