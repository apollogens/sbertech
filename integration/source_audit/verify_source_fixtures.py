"""Read inspected source AST only; never import upstream setup/train/pickle artifacts."""
from __future__ import annotations

import ast
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = Path("C:/Users/apollo/AppData/Local/Temp/forecast-comparison-7371efa0b4b14184a05e39ed9dc127b8")
PACKAGE = SOURCE / "forecast-container"


def git(directory, *args):
    return subprocess.check_output(["git", "-C", str(directory), *args], text=True, encoding="utf-8").strip()


def function(relative, name, cls=None):
    tree = ast.parse((PACKAGE / relative).read_text(encoding="utf-8"))
    nodes = tree.body
    if cls:
        nodes = next(n for n in nodes if isinstance(n, ast.ClassDef) and n.name == cls).body
    node = next(n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node], type_ignores=[])
    ast.fix_missing_locations(module)
    scope = {"np": np, "inverse_target": inverse_target} if name != "inverse_target" else {"np": np}
    exec(compile(module, str(PACKAGE / relative), "exec"), scope)
    return scope[name]


inverse_target = function("app/models/base.py", "inverse_target")
postprocess = function("app/models/base.py", "postprocess_forecast")
blend_predict = function("app/models/blend_model.py", "predict", "BlendForecastModel")
hurdle_predict = function("app/models/hurdle_model.py", "predict", "HurdleForecastModel")
values = np.array([-2, 0, .01, np.nextafter(.25, 0), .25, np.nextafter(.25, 1), np.nextafter(.5, 0), .5, np.nextafter(.5, 1), 1.5, 2.5, 3.5, 1e12])
rounded = postprocess(values, .25, True)
expected = np.rint(np.where(np.maximum(values, 0) < .25, 0, np.maximum(values, 0)))
np.testing.assert_array_equal(rounded, expected)
np.testing.assert_array_equal(postprocess(np.array([.25]), .25, False), [.25])
np.testing.assert_array_equal(postprocess(np.array([.5, 1.5, 2.5, 3.5]), 0, True), [0, 2, 2, 4])
np.testing.assert_array_equal(postprocess(values, .25, True), rounded)
nonfinite = postprocess(np.array([np.nan, np.inf, -np.inf]), 0, True)
assert np.isnan(nonfinite[0]) and np.isposinf(nonfinite[1]) and nonfinite[2] == 0


class Booster:
    def __init__(self, output):
        self.output = np.asarray(output, dtype=float)

    def predict(self, *args, **kwargs):
        return self.output


stub_hurdle = SimpleNamespace(classifier=Booster([.49, .5, .9]), regressor=Booster([10, 10, 10]), _encode=lambda x, fit: x, _best_iterations={"classifier": None, "regressor": None}, params={})
gated = hurdle_predict(stub_hurdle, None)
np.testing.assert_array_equal(gated, [0, 10, 10])
stub_blend = SimpleNamespace(hurdle=SimpleNamespace(classifier=True, target_transform="none", predict=lambda x: np.array([0, 2, 4])), lgbm=SimpleNamespace(booster=True, target_transform="log1p", predict=lambda x: np.log1p([1, 3, 5])), weight_hurdle=.3)
combined = blend_predict(stub_blend, None)
np.testing.assert_allclose(combined, [.7, 2.7, 4.7], atol=1e-14)
after = postprocess(np.array([.5 * .4 + .5 * .8]), 0, True)
before = .5 * postprocess(np.array([.4]), 0, True) + .5 * postprocess(np.array([.8]), 0, True)
assert after[0] == 1 and before[0] == .5

# Earlier research clones are audited as supplemental evidence, not identified
# as the two unknown user downloads. Execute selected inspected nodes only.
m5_root = ROOT / "research/sources/M5-methods"
m5_file = m5_root / "Code of Winning Methods/A1/3. code/3. predict/3-1. Final ensemble.py"
m5_tree = ast.parse(m5_file.read_text(encoding="utf-8"))
m5_assignments = [node for node in m5_tree.body if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and ((node.targets[0].id.startswith("sub") and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "set_index") or node.targets[0].id == "final_sub")]
assert len(m5_assignments) == 7
m5_scope = {"ids": pd.DataFrame({"id": ["a", "b"]})}
for number in range(1, 7):
    m5_scope[f"sub{number}"] = pd.DataFrame({"id": ["b", "a"], "F1": [2 * number, number]})
exec(compile(ast.Module(body=m5_assignments, type_ignores=[]), str(m5_file), "exec"), m5_scope)
np.testing.assert_array_equal(m5_scope["final_sub"].F1.values, [3.5, 7.])

favorita_root = ROOT / "research/sources/Favorita-LenzDu"
favorita_file = favorita_root / "Utils.py"
favorita_node = next(node for node in ast.parse(favorita_file.read_text(encoding="utf-8")).body if isinstance(node, ast.FunctionDef) and node.name == "make_submission")
favorita_scope = {"np": np, "pd": pd}
exec(compile(ast.Module(body=[favorita_node], type_ignores=[]), str(favorita_file), "exec"), favorita_scope)
original_read_csv = pd.read_csv
output = io.StringIO()
try:
    pd.read_csv = lambda *args, **kwargs: pd.DataFrame({"id": range(16), "store_nbr": [1] * 16, "item_nbr": [2] * 16, "date": pd.date_range("2017-08-16", periods=16)})
    favorita_scope["make_submission"](pd.MultiIndex.from_tuples([(1, 2)]), np.log1p(np.array([[.123456, 1200.] + [0.] * 14])), output)
finally:
    pd.read_csv = original_read_csv
assert "0.1235" in output.getvalue() and "1000.0000" in output.getvalue()

tracked = git(SOURCE, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
licenses = [p for p in tracked if any(x in Path(p).name.lower() for x in ("license", "licence", "copying", "notice"))]
files = ["app/models/base.py", "app/models/blend_model.py", "app/models/hurdle_model.py", "app/models/lightgbm_model.py", "app/features.py", "app/predictor.py", "train.py", "evaluate.py", "requirements.txt", "model/config.json", "README.md"]
hashes = {p: hashlib.sha256((PACKAGE / p).read_bytes()).hexdigest() for p in files}
archive_inventory = {}
for p in [ROOT / "nonton_solution.zip", ROOT / "nonton_solution_qa_verified.zip", ROOT / "nonton_solution_remediated_verified.zip", Path("C:/Users/apollo/Desktop/выборка/hakaton.zip")]:
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
    archive_inventory[str(p)] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "entries": len(names), "source_indicators": [n for n in names if any(x in n.lower() for x in (".git/", "license", "readme", "requirements", "models.py", "blend", "round"))][:30]}

result = {"date": "2026-10-19", "numpy_version": np.__version__, "source": str(SOURCE), "remote": git(SOURCE, "remote", "get-url", "origin"), "commit": git(SOURCE, "rev-parse", "HEAD"), "tracked_license_candidates": licenses, "source_hashes": hashes, "fixture_assertions_passed": True, "rounding": {"input": values.tolist(), "threshold_025_then_rint": rounded.tolist(), "half_even": postprocess(np.array([.5, 1.5, 2.5, 3.5]), 0, True).tolist(), "nonfinite_result": ["NaN", "+Infinity", 0]}, "hurdle_probability": [.49, .5, .9], "hurdle_magnitude": [10, 10, 10], "hurdle_prediction": gated.tolist(), "blend_prediction": combined.tolist(), "order_fixture": {"round_after_mean": after.tolist(), "mean_after_round": before.tolist()}, "archives": archive_inventory, "limitations": ["Only one relevant local Nonton external repository identified; no assertion that M5/Favorita are the two requested user downloads", "Only selected inspected numeric AST functions executed with synthetic stubs; no upstream training, setup, pickle loading or full serving replay"]}
result["tracked_source_tree_clean"] = not bool(git(SOURCE, "diff", "--name-only", "HEAD"))
assert result["tracked_source_tree_clean"]
result["supplemental_research_clones"] = {
    "M5": {"commit": git(m5_root, "rev-parse", "HEAD"), "remote": git(m5_root, "remote", "get-url", "origin"), "file": str(m5_file.relative_to(ROOT)), "sha256": hashlib.sha256(m5_file.read_bytes()).hexdigest(), "fixture_F1_after_key_alignment": m5_scope["final_sub"].F1.tolist()},
    "Favorita": {"commit": git(favorita_root, "rev-parse", "HEAD"), "remote": git(favorita_root, "remote", "get-url", "origin"), "file": str(favorita_file.relative_to(ROOT)), "sha256": hashlib.sha256(favorita_file.read_bytes()).hexdigest(), "fixture_csv_prefix": output.getvalue().splitlines()[:3], "license_sha256": hashlib.sha256((favorita_root / "LICENSE").read_bytes()).hexdigest()}
}
(OUT / "source_fixture_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
print(json.dumps({"fixture_assertions_passed": True, "source_commit": result["commit"], "numpy_version": np.__version__, "tracked_license_candidates": licenses, "archive_entries": {p: x["entries"] for p, x in archive_inventory.items()}}, ensure_ascii=False))
