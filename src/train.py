"""Bounded direct LightGBM training: historical labels all known by cutoff."""
import lightgbm as lgb
from .features import training_data


PARAMS = dict(learning_rate=.06, num_leaves=31, min_data_in_leaf=120,
              feature_fraction=.9, lambda_l2=3, max_bin=127,
              seed=20261018, deterministic=True, force_col_wise=True,
              num_threads=4, verbosity=-1)


def train_model(panel, cutoff, objective="regression", rounds=220):
    x, y, origins = training_data(panel, cutoff)
    params = dict(PARAMS, objective=objective)
    if objective == "tweedie":
        params["tweedie_variance_power"] = 1.3
    dataset = lgb.Dataset(x, label=y, categorical_feature=["warehouse_id", "article_id"], free_raw_data=True)
    model = lgb.train(params, dataset, num_boost_round=rounds)
    config = {"schema_version": 1, "model_version": "nonton-v1", "horizon":64,
              "kind":"lightgbm", "features":x.columns.tolist(), "objective":objective,
              "rounds":rounds, "zero_threshold":0., "training_origins": [str(panel.dates[o].date()) for o in origins],
              "training_rows":len(x), "seed":20261018, "parameters":params}
    return {"model":model, "config":config, "catalogs":panel.catalogs}
