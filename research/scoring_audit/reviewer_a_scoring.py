"""Независимые fixtures исходного scorer, без обучения и production mutations."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import platform
import re
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(r"C:\Users\apollo\Desktop\выборка\markdown hakaton.md")
SCORER = ROOT / "scripts/official_score.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    spec = importlib.util.spec_from_file_location("reviewer_a_original", SCORER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    source = SCORER.read_text(encoding="utf-8-sig")
    original = SPEC.read_text(encoding="utf-8-sig")
    block = re.search(r"```python\s*\n(.*?)\n```", original, re.S).group(1)
    text_equal = source.strip().replace("\r\n", "\n") == block.strip().replace("\r\n", "\n")
    ast_equal = ast.dump(ast.parse(source)) == ast.dump(ast.parse(block))
    assert text_equal and ast_equal
    keys = list(mod.METRIC_WEIGHTS)
    constant = lambda x: dict.fromkeys(keys, x)
    score = lambda row: sum(mod.METRIC_WEIGHTS[k] * row[k] for k in keys)
    ties = mod.normalize_rank({"A": constant(1), "B": constant(1)})
    reverse_ties = mod.normalize_rank({"B": constant(1), "A": constant(1)})
    assert ties["A"]["smape"] == 0 and ties["B"]["smape"] == 1
    assert reverse_ties["A"]["smape"] == 1
    assert mod.normalize_rank({"A": constant(1)})["A"] == constant(0)
    assert mod.normalize_rank({}) == {}
    minmax = mod.normalize_minmax({"fixture": dict(zip(keys, [1, 4, 0, 1, 1]))},
                                  dict(zip(keys, [2, 2, 0, 0, 2])))
    assert minmax["fixture"] == dict(zip(keys, [.5, 1, 0, 1, .5]))
    assert abs(score(minmax["fixture"]) - .575) < 1e-15
    truth = pd.DataFrame({"date": pd.to_datetime(["2020-01-01", "2020-01-02"] * 3),
                          "warehouse_name": ["w"] * 6, "article": ["a", "a", "b", "b", "c", "c"],
                          "quantity": [10., 10., 10., 10., 0., 0.]})
    pred = truth.copy()
    pred["quantity"] = [0., 0., 12., 12., 2., 2.]
    fixture = mod.compute_all_metrics(truth, pred)
    assert np.allclose(list(fixture.values()), [139.3939393939394, 70., 6., 60., 1.5258612614218898], rtol=0, atol=1e-13)
    y = np.array([0., 0., 0., 1.])
    p = np.zeros(4)
    executable_smape = mod.smape_series(y, p)
    written_smape = np.divide(200 * abs(y-p), abs(y)+abs(p), out=np.zeros(4), where=(abs(y)+abs(p)) > 0).mean()
    assert executable_smape == 200. and written_smape == 50.
    zero_truth = mod.compute_all_metrics(truth.assign(quantity=0.), pred.assign(quantity=1.))
    assert zero_truth["wape"] == zero_truth["bias"] == 0.
    # Два tradeoff-кандидата: нет Pareto dominance, но ниже weighted minmax.
    incumbent, challenger = constant(1.), constant(1.)
    challenger["smape"], challenger["wape"] = .8, 1.1
    weighted = mod.normalize_minmax({"incumbent": incumbent, "challenger": challenger}, constant(2.))
    assert score(weighted["challenger"]) < score(weighted["incumbent"])
    # CLI с реальными CSV фиксирует fallback minmax без baseline → rank.
    with tempfile.TemporaryDirectory(prefix="nonton_reviewer_a_") as temp:
        folder = Path(temp)
        truth.to_csv(folder / "truth.csv", index=False)
        pred.to_csv(folder / "A.csv", index=False)
        pred.to_csv(folder / "B.csv", index=False)
        result = subprocess.run([sys.executable, str(SCORER), "--truth", str(folder / "truth.csv"),
                                 "--submissions", str(folder / "A.csv"), str(folder / "B.csv"),
                                 "--output", str(folder / "scores.csv")], capture_output=True,
                                encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
        assert result.returncode == 0, result.stderr
        cli = pd.read_csv(folder / "scores.csv")
        assert cli["score"].tolist() == [0., 1.]
    files = [SCORER, SPEC, ROOT / "src/metrics.py", ROOT / "reports/qa/metrics_parity.md",
             ROOT / "reports/qa/reviewer_metrics.md", ROOT / "reports/model_selection.md", Path(__file__)]
    output = {"evaluation_date_moscow": "2026-10-19", "python": platform.python_version(), "numpy": np.__version__,
              "pandas": pd.__version__, "source_hashes": {str(f): sha(f) for f in files},
              "spec_code_text_equal": text_equal, "spec_code_ast_equal": ast_equal,
              "normalized_code_sha256": hashlib.sha256(source.strip().replace("\r\n", "\n").encode()).hexdigest(),
              "weights": mod.METRIC_WEIGHTS, "three_series_fixture": fixture,
              "zero_truth_positive_prediction": zero_truth,
              "smape_fixture": {"truth": y.tolist(), "pred": p.tolist(), "executable": executable_smape, "written": written_smape},
              "ties_AB": ties, "ties_BA": reverse_ties, "minmax_fixture": minmax,
              "minmax_fixture_score": score(minmax["fixture"]),
              "non_pareto_weighted_counterexample": {n: score(v) for n, v in weighted.items()},
              "cli_default_without_baseline": cli.to_dict(orient="records"), "status": "PASS"}
    path = Path(__file__).with_name("reviewer_a_scoring.json")
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "output": str(path), "source_hashes": output["source_hashes"]}, ensure_ascii=False))


if __name__ == "__main__":
    run()
