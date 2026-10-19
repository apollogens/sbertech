"""Historical temporal and hierarchical allocation with unchanged arithmetic."""
import numpy as np

from .features import horizon_features

BUCKETS = [(start, min(start + 7, 65)) for start in range(1, 65, 7)]


def weekly_frame(snap, date, start, end):
    frame = horizon_features(snap, date, start)
    frame['bucket_days'] = np.float32(end - start)
    frame['bucket_end'] = np.float32(end - 1)
    return frame


def weekday_weights(panel, origin):
    """Shrink series weekday means toward warehouse profiles, using past only."""
    hist = panel.y[max(0, origin - 179):origin + 1].astype(float)
    dows = panel.dates[max(0, origin - 179):origin + 1].dayofweek.to_numpy()
    nw, na = len(panel.catalogs['warehouses']), len(panel.catalogs['articles'])
    values = []
    for dow in range(7):
        daily = hist[dows == dow]
        pooled = daily.reshape(len(daily), nw, na).mean(axis=(0, 2))
        values.append((daily.sum(axis=0) + 4 * np.repeat(pooled, na)) / (len(daily) + 4))
    values = np.asarray(values)
    return np.where(values.sum(axis=0)[None, :] > 0, values, 1.)


def allocate_buckets(totals, weights):
    prediction = np.zeros_like(weights, dtype=float)
    for i, (start, end) in enumerate(BUCKETS):
        w = np.maximum(weights[start - 1:end - 1], 0.)
        denom = w.sum(axis=0)
        shares = np.divide(w, denom, out=np.full_like(w, 1 / len(w)), where=denom > 0)
        prediction[start - 1:end - 1] = totals[i] * shares
    return prediction


def warehouse_shares(panel, origin):
    nw, na = len(panel.catalogs['warehouses']), len(panel.catalogs['articles'])
    hist = panel.y[max(0, origin - 179):origin + 1].astype(float).reshape(-1, nw, na)
    mass = hist.sum(axis=0)
    prior = mass.sum(axis=1)
    prior = prior / prior.sum() if prior.sum() else np.full(nw, 1 / nw)
    # 28 pseudo-days of article activity, allocated by historical warehouse mass.
    smooth = mass + (28 * hist.mean(axis=0).sum(axis=0))[None, :] * prior[:, None]
    return np.divide(smooth, smooth.sum(axis=0), out=np.broadcast_to(prior[:, None], smooth.shape).copy(), where=smooth.sum(axis=0) > 0)
