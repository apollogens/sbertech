import numpy as np
from .features import snapshot


def baseline_predict(panel, origin, kind):
    y = panel.y[:origin+1]
    if kind == "zero":
        return np.zeros((64, y.shape[1]), dtype=np.float32)
    if kind == "last":
        return np.tile(y[-1], (64, 1))
    if kind in ["mean28", "mean90"]:
        window = int(kind[4:])
        return np.tile(y[-window:].mean(axis=0), (64,1))
    if kind == "seasonal56":
        snap = snapshot(panel, origin)
        return np.stack([snap[f"weekday_mean_{(panel.dates[origin].dayofweek+h)%7}"].to_numpy() for h in range(1,65)])
    if kind == "tsb":
        # TSB smooths occurrence and positive size separately; no future recursion.
        z = y[-180:]
        p = (z[:28] > 0).mean(axis=0)
        size = z[:28].sum(axis=0) / np.maximum(1, (z[:28] > 0).sum(axis=0))
        for row in z[28:]:
            positive = row > 0
            p = .05 * positive + .95 * p
            size = np.where(positive, .05 * row + .95 * size, size)
        return np.tile(p*size, (64,1)).astype(np.float32)
    raise ValueError(kind)
