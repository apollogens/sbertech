"""Origin-local inference catalogs; membership is supplied explicitly by callers."""
import hashlib

import numpy as np
import pandas as pd

from .data import Panel
from .features import snapshot


def stable_codes(values, namespace):
    """Bounded int32 categorical identity, checked only on available IDs.

    Do not cast these codes to float32: doing so can merge distinct categories.
    Hash collision raises rather than resolving with a future-dependent mapping.
    """
    result = np.array([
        int.from_bytes(hashlib.sha256((namespace + "\0" + str(v)).encode("utf-8")).digest()[:8], "big")
        % (2**20 - 1) for v in values
    ], dtype=np.int32)
    if len(set(map(str, values))) != len(values):
        raise ValueError("Duplicate catalog identity")
    if len(np.unique(result)) != len(result):
        raise ValueError("Categorical hash collision among observed IDs")
    return result


def asof_panel(panel, origin, first_observed):
    """Return truncated active Panel and positions in the caller's fixed output grid.

    Membership is first raw sales-row observation, including zero-quantity rows,
    not first positive sale. Both ID dimensions must be known at this INNER origin.
    """
    if not isinstance(origin, (int, np.integer)) or not 0 <= origin < len(panel.dates):
        raise ValueError("origin must be a valid integer panel date position")
    if first_observed is None:
        raise ValueError("Explicit first-observed membership is required")
    first = first_observed
    day = str(panel.dates[origin].date())
    known = first.loc[(first.source == "sales") & (first.first_date <= day)]
    warehouse_set = set(known.loc[known.key_type == "warehouse_name", "key"])
    article_set = set(known.loc[known.key_type == "article", "key"])
    # Canonical order is independent of fixed output ordering and later catalog IDs.
    warehouses = sorted(set(panel.catalogs["warehouses"]) & warehouse_set)
    articles = sorted(set(panel.catalogs["articles"]) & article_set)
    if not warehouses or not articles:
        raise ValueError("No known sales catalog at origin")
    active_pairs = pd.MultiIndex.from_product([warehouses, articles])
    positions = panel.pairs.get_indexer(active_pairs)
    if (positions < 0).any():
        raise ValueError("Known identity absent from output grid")
    active = Panel(
        panel.dates[:origin + 1],
        np.ascontiguousarray(panel.y[:origin + 1, positions]),
        np.ascontiguousarray(panel.stock[:origin + 1, positions]),
        dict(warehouses=warehouses, articles=articles),
    )
    return active, positions


def safe_snapshot(panel, origin, first_observed):
    active, positions = asof_panel(panel, origin, first_observed)
    frame = snapshot(active, len(active.dates) - 1)
    nw, na = len(active.catalogs["warehouses"]), len(active.catalogs["articles"])
    frame["warehouse_id"] = np.repeat(stable_codes(active.catalogs["warehouses"], "warehouse"), na)
    frame["article_id"] = np.tile(stable_codes(active.catalogs["articles"], "article"), nw)
    return frame, positions


def expand_to_output(prediction, positions, width=8789):
    """Known-ID forecasts -> fixed output grid; unknown identities receive zero."""
    prediction = np.asarray(prediction)
    positions = np.asarray(positions, dtype=np.int64)
    if prediction.shape[-1] != len(positions) or len(set(positions)) != len(positions):
        raise ValueError("Prediction/mapping mismatch")
    if ((positions < 0) | (positions >= width)).any():
        raise ValueError("Mapping outside output grid")
    if not np.isfinite(prediction).all() or (prediction < 0).any():
        raise ValueError("Forecast must be finite and nonnegative")
    output = np.zeros((*prediction.shape[:-1], width), dtype=prediction.dtype)
    output[..., positions] = prediction
    return output
