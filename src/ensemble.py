"""Independent, key-aligned convex forecasts and explicit postprocessing."""
import hashlib
import json
import numpy as np
import pandas as pd
KEYS = ['date', 'warehouse_name', 'article']

def forecast_identity(origin, catalogs, horizon=64):
    catalog_bytes = json.dumps(catalogs, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return {'origin': str(pd.Timestamp(origin).date()), 'horizon': horizon, 'catalog_sha256': hashlib.sha256(catalog_bytes).hexdigest()}

def expected_grid(origin, catalogs, horizon=64):
    """Materialize a complete identity contract independently of model output."""
    if not isinstance(horizon, (int, np.integer)) or horizon <= 0:
        raise ValueError('Expected positive integer horizon')
    for name in ('warehouses', 'articles'):
        values = catalogs[name]
        if not values or any((not isinstance(value, str) or not value.strip() for value in values)) or len(set(values)) != len(values):
            raise ValueError('Invalid output catalog')
    dates = pd.date_range(pd.Timestamp(origin) + pd.Timedelta(days=1), periods=horizon)
    return pd.MultiIndex.from_product([dates.strftime('%Y-%m-%d'), catalogs['warehouses'], catalogs['articles']], names=KEYS).to_frame(index=False)

def postprocess(values, policy='continuous'):
    x = np.asarray(values, dtype=np.float64)
    if not np.isfinite(x).all() or (x < 0).any():
        raise ValueError('Expected finite nonnegative component predictions')
    if policy == 'continuous':
        return x.copy()
    if policy == 'threshold025':
        return np.where(x < 0.25, 0.0, x)
    if policy == 'nearest_even':
        return np.rint(x)
    if policy == 'threshold_then_nearest_even':
        return np.rint(np.where(x < 0.25, 0.0, x))
    raise ValueError('Unknown postprocessing policy')

def align_components(components, expected_keys, expected_identity=None):
    """Validate full named grids and align by identity, not assumed array order."""
    if not components:
        raise ValueError('At least one component required')
    keys = expected_keys[KEYS].copy()
    if keys.isna().any().any() or keys.duplicated().any():
        raise ValueError('Invalid expected keys')
    grid = pd.MultiIndex.from_frame(keys)
    aligned = {}
    for name, frame in components.items():
        if expected_identity is not None:
            identity = frame.attrs.get('forecast_identity', {})
            if any((identity.get(key) != value for key, value in expected_identity.items())):
                raise ValueError('Incompatible component identity')
        if list(frame.columns) != KEYS + ['quantity'] or len(frame) != len(keys):
            raise ValueError('Invalid component schema or coverage')
        if frame[KEYS].isna().any().any():
            raise ValueError('Missing component identity')
        index = pd.MultiIndex.from_frame(frame[KEYS])
        if index.has_duplicates or not grid.isin(index).all():
            raise ValueError('Incompatible component keys')
        values = pd.Series(frame.quantity.to_numpy(), index=index).reindex(grid).to_numpy(dtype=float)
        aligned[name] = postprocess(values)
    return aligned

def convex_combine(aligned, weights, component_policy='continuous', output_policy='continuous'):
    if set(aligned) != set(weights):
        raise ValueError('Component/weight names mismatch')
    w = np.array([weights[n] for n in sorted(weights)], dtype=float)
    if not np.isfinite(w).all() or (w < 0).any() or (not np.isclose(w.sum(), 1.0, rtol=0, atol=1e-12)):
        raise ValueError('Weights must be finite, nonnegative and sum to one')
    result = None
    for name in sorted(weights):
        value = postprocess(aligned[name], component_policy)
        if result is not None and value.shape != result.shape:
            raise ValueError('Component shape mismatch')
        value = value * weights[name]
        result = value if result is None else result + value
    return postprocess(result, output_policy)

def key_hash(keys):
    return hashlib.sha256(keys[KEYS].to_csv(index=False, lineterminator='\n').encode('utf-8')).hexdigest()
