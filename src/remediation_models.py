"""Experimental two-part expected-volume challenger, isolated from serving."""
import lightgbm as lgb
import numpy as np
import pandas as pd
from .features import training_data, snapshot, horizon_features
from .train import PARAMS


def fit_two_part(panel, cutoff, rounds=220):
    x, y, origins = training_data(panel, cutoff)
    positive = y > 0
    if not positive.any() or positive.all():
        raise ValueError('Two-part experiment requires both binary classes')
    kwargs = dict(categorical_feature=['warehouse_id', 'article_id'], free_raw_data=True)
    occurrence = lgb.train(dict(PARAMS, objective='binary'),
                           lgb.Dataset(x, label=positive.astype(float), **kwargs), num_boost_round=rounds)
    magnitude = lgb.train(dict(PARAMS, objective='gamma'),
                          lgb.Dataset(x.loc[positive], label=y[positive], **kwargs), num_boost_round=rounds)
    return dict(occurrence=occurrence, magnitude=magnitude, features=x.columns.tolist(),
                training_rows=len(y), positive_training_rows=int(positive.sum()),
                origins=[str(panel.dates[o].date()) for o in origins])


def predict_two_part(panel, origin, fitted):
    snap = snapshot(panel, origin)
    probabilities, magnitudes = [], []
    for start in range(1, 65, 8):
        frame = pd.concat([horizon_features(snap, panel.dates[origin], h) for h in range(start, start+8)], ignore_index=True)
        if frame.columns.tolist() != fitted['features']:
            raise ValueError('Experimental feature order mismatch')
        probabilities.append(fitted['occurrence'].predict(frame, num_threads=4).reshape(8, -1))
        magnitudes.append(fitted['magnitude'].predict(frame, num_threads=4).reshape(8, -1))
    p, m = np.concatenate(probabilities), np.concatenate(magnitudes)
    if not np.isfinite(p).all() or not np.isfinite(m).all() or (p<0).any() or (p>1).any() or (m<=0).any():
        raise ValueError('Invalid two-part predictions')
    return p*m, p, m
