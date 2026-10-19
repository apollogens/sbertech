"""Independent tiny-fit temporal and expected-volume checks; no release writes."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.data import Panel
from src.features import training_data
from src.remediation_models import fit_two_part, predict_two_part

rng = np.random.default_rng(9357)
y = (rng.random((410, 4)) < .27) * rng.uniform(.1, 2.5, (410, 4))
stock = rng.uniform(0, 12, (410, 4)).astype(np.float32)
panel = Panel(pd.date_range('2024-01-01', periods=410), y.astype(np.float32), stock,
              {'warehouses': ['w1','w2'], 'articles': ['a1','a2']})
cutoff = 345
altered = Panel(panel.dates, panel.y.copy(), panel.stock.copy(), panel.catalogs)
altered.y[cutoff+1:] = 99999
altered.stock[cutoff+1:] = 77777
x, labels, origins = training_data(panel, cutoff)
xx, yy, oo = training_data(altered, cutoff)
pd.testing.assert_frame_equal(x, xx)
np.testing.assert_array_equal(labels, yy)
assert origins == oo and max(origins)+64 <= cutoff
a, b = fit_two_part(panel, cutoff, rounds=2), fit_two_part(altered, cutoff, rounds=2)
assert a['occurrence'].model_to_string() == b['occurrence'].model_to_string()
assert a['magnitude'].model_to_string() == b['magnitude'].model_to_string()
pred, prob, mag = predict_two_part(panel, cutoff, a)
z, zp, zm = predict_two_part(altered, cutoff, a)
np.testing.assert_array_equal(pred, z)
np.testing.assert_array_equal(pred, prob*mag)
assert np.isfinite(pred).all() and (pred>=0).all()
assert ((prob>=0)&(prob<=1)).all() and (mag>0).all()
assert a['training_rows'] == len(labels) and a['positive_training_rows'] == int((labels>0).sum())
classes = []
for value in (0., 1.):
    constant = Panel(panel.dates, np.full_like(panel.y, value), panel.stock, panel.catalogs)
    try:
        fit_two_part(constant, cutoff, rounds=2)
    except ValueError as exc:
        assert 'both binary classes' in str(exc)
        classes.append(value)
    else:
        raise AssertionError('Degenerate binary labels accepted')
result = dict(status='passed', tiny_fits=4, trees_per_model=2, training_rows=len(labels),
              positive_training_rows=int((labels>0).sum()),
              labels_known_by_cutoff=True, altered_future_identical_weights=True,
              altered_future_identical_prediction=True, product_identity_exact=True,
              gamma_positive_only_code_review=True, rejected_constant_training_targets=classes,
              note='Проверка корректности; не доказательство качества или calibration')
(ROOT/'reports/remediation/review_two_part_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
