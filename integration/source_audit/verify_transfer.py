"""Independent numerical review of transferred general algebra and rounding."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from integration.ensemble_engine import convex_combine, postprocess

SOURCE = Path("C:/Users/apollo/AppData/Local/Temp/forecast-comparison-7371efa0b4b14184a05e39ed9dc127b8/forecast-container/app/models/base.py")
node = next(n for n in ast.parse(SOURCE.read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef) and n.name == "postprocess_forecast")
scope = {"np": np}
exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), scope)
source_post = scope["postprocess_forecast"]
rng = np.random.default_rng(20261019)
x = np.concatenate([np.array([0, np.nextafter(.25, 0), .25, np.nextafter(.25, 1), np.nextafter(.5, 0), .5, np.nextafter(.5, 1), 1.5, 2.5, 1e12]), rng.uniform(0, 1000, 10000)])
for policy, threshold, rounded in [("continuous", 0, False), ("threshold025", .25, False), ("nearest_even", 0, True), ("threshold_then_nearest_even", .25, True)]:
    np.testing.assert_array_equal(postprocess(x, policy), source_post(x, threshold, rounded))
np.testing.assert_array_equal(postprocess(x, "nearest_even"), postprocess(x, "threshold_then_nearest_even"))
daily = np.array([.4, .5, .8, 1.5, 4])
article = np.array([.8, .4, .2, 3.5, 1])
blend = convex_combine({"D": daily, "A": article}, {"D": .7, "A": .3}, output_policy="nearest_even")
np.testing.assert_array_equal(blend, source_post(.7 * daily + .3 * article, 0, True))
assert convex_combine({"D": np.array([.4]), "A": np.array([.8])}, {"D": .7, "A": .3}, output_policy="nearest_even")[0] == 1
assert convex_combine({"D": np.array([.4]), "A": np.array([.8])}, {"D": .7, "A": .3}, component_policy="nearest_even")[0] == .3
for bad in ([np.nan], [np.inf], [-.1]):
    try:
        postprocess(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid value accepted")
result = {"assertions_passed": True, "numpy": np.__version__, "nonnegative_fixture_values": len(x), "four_postprocess_policies_source_parity": True, "P2_equals_P3": True, "source_DA70_matches_round_after_original_scale_blend": True, "files_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT / "integration/ensemble_engine.py", ROOT / "integration/test_ensemble_engine.py", ROOT / "integration/experiment_protocol.md"]}, "limitations": ["The fixed 0.7 D + 0.3 A blend is an adaptation of combination algebra, not the external hurdle predictor", "Second user-downloaded source remains unidentified", "Synthetic comparison does not establish forecast improvement"]}
(Path(__file__).parent / "transfer_review_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
