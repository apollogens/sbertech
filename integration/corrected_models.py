"""Cutoff-safe experimental models. No imports from external downloaded projects."""
import hashlib
import json
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd
from src.features import horizon_features
from src.train import PARAMS
from integration.catalog_policy import safe_snapshot
from src.temporal import BUCKETS,weekly_frame

def origins_for(cutoff):
    last=cutoff-64
    if last<179:raise ValueError('Not enough historical origins')
    return sorted(set(range(179,last+1,35))|{last})

def article_snapshot(panel, origin, first=None):
    from src.components import article_snapshot as shared_snapshot
    from integration.catalog_policy import _first_observed
    return shared_snapshot(panel, origin, _first_observed() if first is None else first)

def fit_components(panel,cutoff,rounds=220):
    """Each INNER origin has its own known-ID feature catalog and label subset."""
    data={kind:([],[]) for kind in ['daily','weekly','article']};meta=[]
    for origin in origins_for(cutoff):
        frame,positions=safe_snapshot(panel,origin)
        article,active,_=article_snapshot(panel,origin)
        nw,na=len(active.catalogs['warehouses']),len(active.catalogs['articles'])
        meta.append(dict(origin=str(panel.dates[origin].date()),known_warehouses=nw,known_articles=na,
                         known_pairs=len(positions),max_target_date=str(panel.dates[origin+64].date()),
                         active_catalog_sha256=hashlib.sha256(json.dumps(active.catalogs,sort_keys=True).encode()).hexdigest()))
        for horizon in [1,7,14,21,28,42,56,64]:
            data['daily'][0].append(horizon_features(frame,panel.dates[origin],horizon))
            data['daily'][1].append(panel.y[origin+horizon,positions])
            data['article'][0].append(horizon_features(article,panel.dates[origin],horizon))
            data['article'][1].append(panel.y[origin+horizon,positions].reshape(nw,na).sum(axis=0))
        for start,end in BUCKETS:
            data['weekly'][0].append(weekly_frame(frame,panel.dates[origin],start,end))
            data['weekly'][1].append(panel.y[origin+start:origin+end,positions].sum(axis=0,dtype=float))
    bundles={};times={}
    from time import perf_counter
    for kind,(xs,ys) in data.items():
        t=perf_counter();x=pd.concat(xs,ignore_index=True);y=np.concatenate(ys)
        assert x.warehouse_id.dtype==np.int32 and x.article_id.dtype==np.int32
        model=lgb.train(dict(PARAMS,objective='tweedie',tweedie_variance_power=1.3),
                        lgb.Dataset(x,label=y,categorical_feature=['warehouse_id','article_id']),num_boost_round=rounds)
        bundles[kind]=model;times[kind]=perf_counter()-t
        del x,y
    return bundles,dict(cutoff=str(panel.dates[cutoff].date()),rounds=rounds,seed=PARAMS['seed'],
                        origin_catalogs=meta,train_seconds=times,features={k:m.feature_name() for k,m in bundles.items()},
                        policy='sales-only INNER origin catalog; stable int32 SHA256 encodings; unknown output IDs zero')

def predict_components(panel, origin, models, first_observed=None):
    from src.components import predict_component_frames
    from integration.catalog_policy import _first_observed
    return predict_component_frames(panel, origin, models,
        _first_observed() if first_observed is None else first_observed)

def source_hashes():
    root=Path(__file__).resolve().parents[1]
    names=['integration/corrected_models.py','integration/catalog_policy.py','integration/ensemble_engine.py',
           'scripts/architecture_experiments.py','src/features.py','src/data.py','src/train.py','src/submission.py',
           'src/catalog.py','src/temporal.py','src/components.py','src/ensemble.py','src/runtime.py']
    return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in names}

def save_bundle(models,meta,catalogs,path):
    path=Path(path);path.mkdir(parents=True,exist_ok=True)
    for name,model in models.items():model.save_model(str(path/(name+'.txt')))
    config=dict(schema_version=1,horizon=64,model_version='nonton-integration-experimental-v1',
                production=False,catalogs=catalogs,metadata=meta,source_hashes=source_hashes())
    (path/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.iterdir()) if p.is_file() and p.name!='manifest.json'}
    (path/'manifest.json').write_text(json.dumps(dict(files=files,source_hashes=source_hashes()),indent=2),encoding='utf-8')

def load_experimental_bundle(path):
    path=Path(path);manifest=json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['files'].items():
        if hashlib.sha256((path/name).read_bytes()).hexdigest()!=digest:raise ValueError('Experimental artifact integrity mismatch')
    if manifest['source_hashes']!=source_hashes():raise ValueError('Experimental source integrity mismatch')
    config=json.loads((path/'config.json').read_text(encoding='utf-8'))
    models={n:lgb.Booster(model_file=str(path/(n+'.txt'))) for n in ['daily','weekly','article']}
    if any(m.feature_name()!=config['metadata']['features'][n] for n,m in models.items()):raise ValueError('Experimental feature contract mismatch')
    return models,config
