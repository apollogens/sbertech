import numpy as np
import pandas as pd


def snapshot(panel, origin):
    """All history is sliced BEFORE calculating any statistic."""
    y = panel.y[:origin + 1]
    s = panel.stock[:origin + 1]
    n = y.shape[1]
    na = len(panel.catalogs["articles"])
    nw = len(panel.catalogs["warehouses"])
    f = {"warehouse_id": np.repeat(np.arange(nw), na), "article_id": np.tile(np.arange(na), nw)}
    f["last_y"] = y[-1]
    for window in [7, 14, 28, 56, 90, 180]:
        z = y[-window:]
        f[f"mean_{window}"] = z.mean(axis=0)
        f[f"freq_{window}"] = (z > 0).mean(axis=0)
        if window in [28, 180]:
            f[f"std_{window}"] = z.std(axis=0)
            f[f"max_{window}"] = z.max(axis=0)
    f["long_mean"] = y.mean(axis=0)
    f["trend"] = (f["mean_28"] + .05) / (f["mean_180"] + .05)
    positive = y[-180:] > 0
    f["days_since_sale"] = np.where(positive.any(axis=0), np.argmax(positive[::-1], axis=0), 180)
    f["positive_mean"] = y[-180:].sum(axis=0) / np.maximum(1, positive.sum(axis=0))
    recent_s = s[-180:]
    observed = np.isfinite(recent_s)
    age = np.argmax(observed[::-1], axis=0)
    f["stock_age"] = np.where(observed.any(axis=0), age, 180)
    f["last_stock"] = np.where(observed.any(axis=0), recent_s[len(recent_s)-1-age, np.arange(n)], np.nan)
    count = observed.sum(axis=0)
    f["stock_coverage"] = observed.mean(axis=0)
    f["stock_zero_rate"] = (recent_s == 0).sum(axis=0) / np.maximum(1, count)
    f["stock_mean"] = np.nansum(recent_s, axis=0) / np.maximum(1, count)
    for w in [28, 180]:
        matrix = y[-w:].mean(axis=0).reshape(nw, na)
        f[f"article_mean_{w}"] = np.tile(matrix.mean(axis=0), nw)
        f[f"warehouse_mean_{w}"] = np.repeat(matrix.mean(axis=1), na)
    weekdays = panel.dates[:origin+1].dayofweek.to_numpy()
    for dow in range(7):
        f[f"weekday_mean_{dow}"] = y[-56:][weekdays[-56:] == dow].mean(axis=0)
    return pd.DataFrame(f, dtype=np.float32)


def horizon_features(snapshot_frame, origin_date, horizon):
    frame = snapshot_frame.copy()
    day = pd.Timestamp(origin_date) + pd.Timedelta(days=int(horizon))
    frame["horizon"] = np.float32(horizon)
    frame["day_of_week"] = np.float32(day.dayofweek)
    frame["month"] = np.float32(day.month)
    frame["year_sin"] = np.float32(np.sin(2*np.pi*day.dayofyear/365.25))
    frame["year_cos"] = np.float32(np.cos(2*np.pi*day.dayofyear/365.25))
    frame["weekday_mean"] = frame[f"weekday_mean_{day.dayofweek}"]
    return frame


def training_data(panel, cutoff, step=35):
    last = cutoff - 64
    if last < 179:
        raise ValueError("Not enough complete direct training origins")
    origins = sorted(set(range(179, last+1, step)) | {last})
    xs, ys = [], []
    # Fixed stratified horizons keep memory bounded, all labels <= cutoff.
    for origin in origins:
        snap = snapshot(panel, origin)
        for horizon in [1, 7, 14, 21, 28, 42, 56, 64]:
            xs.append(horizon_features(snap, panel.dates[origin], horizon))
            ys.append(panel.y[origin+horizon])
    return pd.concat(xs, ignore_index=True), np.concatenate(ys), origins
