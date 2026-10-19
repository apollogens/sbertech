"""Независимая нормировка пересчитанных Reviewer C метрик исходным scorer."""
from pathlib import Path
import hashlib
import importlib.util
import json
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KEYS = ["smape", "wape", "rmse", "bias", "rmsle"]


def run():
    module = importlib.util.spec_from_file_location("original_score", ROOT / "scripts/official_score.py")
    original = importlib.util.module_from_spec(module)
    module.loader.exec_module(original)
    source = HERE / "reviewer_c_metrics.csv"
    data = pd.read_csv(source)
    data = data[data.source.isin(["remediation", "architecture"])].copy()
    data["model"] = data.model.replace({"current_tweedie_z0.25": "incumbent"})
    for (_, _), repeated in data.groupby(["model", "origin"]):
        if len(repeated) > 1:
            assert repeated.canonical_float64_sha256.nunique() == 1
            assert np.allclose(repeated[KEYS + ["smape_text"]].values, repeated[KEYS + ["smape_text"]].values[0], atol=1e-13, rtol=0)
    architecture = sorted(data[data.source == "architecture"].model.unique())
    data = data.drop_duplicates(["model", "origin"])
    assert len(data) == 23 * 5
    pools = {"union23": sorted(data.model.unique()), "architecture7": architecture,
             "focus4": sorted(["incumbent", "weekly_allocation_z0.25", "weekly_direct_shape_z0.25", "article_topdown_z0.25"])}
    rows = []
    for origin, block in data.groupby("origin"):
        block = block.set_index("model")
        for definition in ["executable", "written"]:
            raw = block[KEYS].copy()
            if definition == "written":
                raw["smape"] = block.smape_text
            baseline = raw.loc["last"].to_dict()
            for pool, members in pools.items():
                for order, names in [("forward", sorted(members)), ("reverse", sorted(members, reverse=True))]:
                    metrics = {name: raw.loc[name].to_dict() for name in names}
                    for method, normalized in [("rank", original.normalize_rank(metrics)),
                                               ("minmax_last", original.normalize_minmax(metrics, baseline))]:
                        scores = {name: sum(original.METRIC_WEIGHTS[k] * val[k] for k in KEYS) for name, val in normalized.items()}
                        for name in names:
                            rows.append({"origin": origin, "role": block.loc[name, "role"], "pool": pool,
                                         "pool_size": len(names), "order": order, "smape_definition": definition,
                                         "method": method, "model": name, "score": scores[name],
                                         "incumbent_score": scores["incumbent"],
                                         "delta_vs_incumbent": scores[name] - scores["incumbent"],
                                         **{k + "_norm": normalized[name][k] for k in KEYS}})
    result = pd.DataFrame(rows)
    result.to_csv(HERE / "reviewer_a_score_crosscheck.csv", index=False)
    development = result[result.role == "development"]
    means = development.groupby(["pool", "order", "smape_definition", "method", "model"])["score"].mean().reset_index()
    means.to_csv(HERE / "reviewer_a_score_development_means.csv", index=False)
    winners = means.loc[means.groupby(["pool", "order", "smape_definition", "method"])["score"].idxmin()]
    winners.to_csv(HERE / "reviewer_a_score_winners.csv", index=False)
    # Только ПОСЛЕ независимого вычисления — сверка с результатами root.
    root = pd.read_csv(HERE / "weighted_rank_sensitivity.csv")
    root = root[root.tie_policy == "official_argsort"]
    join_keys = ["origin", "pool", "order", "smape_definition", "model"]
    compared = result[result.method == "rank"].merge(root, on=join_keys, suffixes=("_A", "_root"), validate="one_to_one")
    assert len(compared) == len(result[result.method == "rank"])
    max_error = (compared.score_A - compared.score_root).abs().max()
    assert max_error < 1e-13
    root_minmax = pd.read_csv(HERE / "minmax_sensitivity.csv")
    root_minmax = root_minmax[root_minmax.baseline == "last"]
    compared_minmax = result[result.method == "minmax_last"].merge(
        root_minmax, on=["origin", "smape_definition", "model"],
        suffixes=("_A", "_root"), validate="many_to_one")
    assert len(compared_minmax) == 680
    max_minmax_error = (compared_minmax.score_A - compared_minmax.score_root).abs().max()
    assert max_minmax_error < 1e-13
    summary = {"status": "PASS", "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
               "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "rows": len(result), "independently_computed_rank_rows_matched": len(compared),
               "max_root_rank_difference": float(max_error),
               "independently_computed_minmax_rows_matched": len(compared_minmax),
               "max_root_minmax_difference": float(max_minmax_error),
               "winners": winners.to_dict(orient="records")}
    (HERE / "reviewer_a_rank_crosscheck.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(winners.to_string(index=False))
    print("Max root rank error:", max_error)
    print("Max root minmax error:", max_minmax_error)


if __name__ == "__main__":
    run()
