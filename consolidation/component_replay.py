"""Isolated frozen/current real-weight raw component replay; no training."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, required=True)
parser.add_argument("--inputs", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--old", action="store_true")
args = parser.parse_args()
sys.path.insert(0, str(args.root.resolve()))

import numpy as np
import pandas as pd

from src.data import build_panel, clean_stock, read_inputs

sales, stock = read_inputs(args.inputs / "sales.csv", args.inputs / "stock.csv")
sales["date"] = pd.to_datetime(sales.date).dt.strftime("%Y-%m-%d")
rows = []
for column in ("warehouse_name", "article"):
    rows.extend(dict(source="sales", key_type=column, key=str(key), first_date=str(day))
                for key, day in sales.groupby(column).date.min().items())
first = pd.DataFrame(rows)

if args.old:
    from integration.corrected_models import load_experimental_bundle, predict_components

    models, config = load_experimental_bundle(args.root / "integration/models/final_experimental")
    panel = build_panel(sales, clean_stock(stock), catalogs=config["catalogs"])
    frames = predict_components(panel, len(panel.dates) - 1, models, first_observed=first)
else:
    from src.components import predict_component_frames
    from src.runtime import load_bundle

    bundle = load_bundle(args.root / "bundles/equal4-rc1", "equal4:P1")
    panel = build_panel(sales, clean_stock(stock), catalogs=bundle["catalogs"])
    frames = predict_component_frames(panel, len(panel.dates) - 1, bundle["models"], first)

assert len(panel.dates) == 180
values = {}
for name, frame in frames.items():
    assert frame.shape == (562496, 4)
    values[name] = frame.quantity.to_numpy()
    values[name + "_key_sha256"] = hashlib.sha256(
        frame.iloc[:, :3].to_csv(index=False, lineterminator="\n").encode("utf-8")
    ).hexdigest()
values["input_sales_sha256"] = hashlib.sha256((args.inputs / "sales.csv").read_bytes()).hexdigest()
values["input_stock_sha256"] = hashlib.sha256((args.inputs / "stock.csv").read_bytes()).hexdigest()
np.savez_compressed(args.output, **values)
print(json.dumps(dict(mode="old" if args.old else "canonical", components=list(frames), rows=562496)))
