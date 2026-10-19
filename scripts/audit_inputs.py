"""Read-only input audit using the Python standard library."""
import csv
import argparse
import json
import math
from collections import Counter
from pathlib import Path
from time import perf_counter

SOURCES = Path(r"C:\Users\apollo\Desktop\выборка")
ROOT = Path(__file__).resolve().parents[1]


def audit(path, value_column):
    start = perf_counter()
    dates, warehouses, articles, pairs = Counter(), set(), set(), set()
    invalid = Counter()
    total = 0.0
    minimum, maximum = math.inf, -math.inf
    rows = 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        article_column = "article" if "article" in columns else "char_article"
        for row in reader:
            rows += 1
            dates[row["date"]] += 1
            warehouse, article = row["warehouse_name"], row[article_column]
            warehouses.add(warehouse)
            articles.add(article)
            pairs.add((warehouse, article))
            if not warehouse or not article:
                invalid["empty_key"] += 1
            try:
                value = float(row[value_column])
                if not math.isfinite(value):
                    invalid["nonfinite"] += 1
                    continue
                invalid["negative"] += int(value < 0)
                invalid["zero"] += int(value == 0)
                minimum, maximum = min(minimum, value), max(maximum, value)
                total += value
            except (ValueError, TypeError):
                invalid["nonnumeric"] += 1
    return {
        "path": str(path), "bytes": path.stat().st_size, "columns": columns,
        "rows": rows, "date_min": min(dates), "date_max": max(dates),
        "unique_dates": len(dates), "warehouses": sorted(warehouses),
        "article_count": len(articles), "observed_pairs": len(pairs),
        "cartesian_pairs": len(warehouses) * len(articles),
        "value_column": value_column, "minimum": minimum, "maximum": maximum,
        "sum": total, "counts": dict(invalid),
        "elapsed_seconds": round(perf_counter() - start, 3),
        "limitations": "Первичный потоковый аудит: без проверки дублей ключей и синтаксиса дат.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=SOURCES)
    parser.add_argument('--output', type=Path, default=ROOT/'reports/input_audit.json')
    args = parser.parse_args()
    try:
        result = {
            "sales": audit(args.data_dir / "sales_dataset_hakaton_train.csv", "quantity"),
            "stock": audit(args.data_dir / "stock_dataset_hakaton_train.csv", "stock"),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f'Ошибка аудита: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
