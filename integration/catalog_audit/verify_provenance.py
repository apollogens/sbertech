"""Recompute first observed IDs from raw sources; never fits a model."""
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.data import load_panel
from integration.catalog_policy import asof_panel, stable_codes


def main():
    out = Path(__file__).parent
    audit = json.loads((ROOT / "reports/input_audit.json").read_text(encoding="utf-8"))
    rows, inputs = [], []
    for source in ("sales", "stock"):
        path = Path(audit[source]["path"])
        frame = pd.read_csv(path, usecols=["date", "warehouse_name", "article"], dtype=str)
        with path.open("rb") as stream:
            sha = hashlib.file_digest(stream, "sha256").hexdigest()
        inputs.append(dict(source=source, path=str(path), rows=len(frame), sha256=sha))
        for col in ("warehouse_name", "article"):
            rows.extend(dict(source=source, key_type=col, key=k, first_date=d)
                        for k, d in frame.groupby(col).date.min().items())
    first = pd.DataFrame(rows)
    first.to_csv(out / "first_observed.csv", index=False)
    prior = pd.read_csv(ROOT / "research/scoring_audit/catalog_first_observed.csv", dtype=str)
    prior = prior[prior.key_type != "pair"]
    columns = ["source", "key_type", "key", "first_date"]
    same = first.sort_values(columns).reset_index(drop=True).equals(
        prior[columns].sort_values(columns).reset_index(drop=True))
    panel = load_panel(ROOT / "cache")
    outer_dates = json.loads((ROOT / "research/experiment_protocol.json").read_text(encoding="utf-8"))["origins"]
    dates = set(outer_dates)
    for day in outer_dates:
        cutoff = panel.dates.get_loc(day)
        dates.update(str(panel.dates[i].date()) for i in sorted(set(range(179, cutoff - 64 + 1, 35)) | {cutoff - 64}))
    summaries = []
    for day in sorted(dates):
        active, positions = asof_panel(panel, panel.dates.get_loc(day), first)
        stable_codes(active.catalogs["warehouses"], "warehouse")
        stable_codes(active.catalogs["articles"], "article")
        row = dict(origin=day, role="outer" if day in outer_dates else "inner",
                   known_warehouses=len(active.catalogs["warehouses"]),
                   known_articles=len(active.catalogs["articles"]), known_pairs=len(positions),
                   unknown_output_pairs=panel.y.shape[1] - len(positions))
        for key, col in (("warehouses", "warehouse_name"), ("articles", "article")):
            stock_known = set(first.loc[(first.source == "stock") & (first.key_type == col) & (first.first_date <= day), "key"])
            row["stock_only_" + key] = len(stock_known - set(active.catalogs[key]))
        summaries.append(row)
    pd.DataFrame(summaries).to_csv(out / "origins.csv", index=False)
    result = dict(inputs=inputs, prior_first_observed_matches=same, distinct_origins=len(dates),
                  fixed_output_pairs=panel.y.shape[1], known_id_hash_collisions=0, fits_performed=0)
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
