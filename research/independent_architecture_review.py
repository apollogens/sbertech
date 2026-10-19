"""Independent artifact/scorer audit and saved-weight replay; no training."""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import lightgbm as lgb
import numpy as np
import pandas as pd
from src.data import Panel,load_panel
from src.features import snapshot
from src.predict import predict_panel
from scripts import official_score as official
from scripts.architecture_experiments import (BUCKETS,weekly_frame,weekday_weights,
    warehouse_shares,article_panel,allocate_buckets)


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def score(y,p):
    # Official scalar series functions avoid compute_all_metrics' quadratic ID scans.
    sm=[official.smape_series(a,b) for a,b in zip(y.T,p.T)]
    biases=[official.bias_abs_series(a,b) for a,b in zip(y.T,p.T)]
    biases=[v for v in biases if v is not None]
    return dict(smape=float(np.mean(sm)),bias=float(np.mean(biases)) if biases else 0.,
        wape=official.wape(y,p),rmse=official.rmse(y,p),rmsle=official.rmsle(y,p))


def main():
    directory=ROOT/'research'
    protocol=json.loads((directory/'experiment_protocol.json').read_text(encoding='utf-8'))
    results=pd.read_csv(directory/'experiment_results.csv')
    expected={'incumbent'}|{m+s for m in protocol['candidates'] for s in ['', '_z0.25']}
    assert len(results)==35 and not results.duplicated(['model','origin']).any()
    assert set(results.model)==expected and set(results.origin)==set(protocol['origins'])
    panel=load_panel(ROOT/'cache')
    checks=[]; replay=[]; leakage=[]; hashchecks=[]
    for _,row in results.iterrows():
        with np.load(ROOT/row.prediction_path) as z:
            p=z['prediction']; saved_origin=str(z['origin'])
        assert saved_origin==row.origin
        assert p.shape==(64,8789) and np.isfinite(p).all() and (p>=0).all()
        assert digest(ROOT/row.prediction_path)==row.prediction_sha256
        idx=panel.dates.get_loc(row.origin)
        y=panel.y[idx+1:idx+65].astype(float)
        measured=score(y,p)
        diffs={m:abs(measured[m]-row[m]) for m in measured}
        assert max(diffs.values())<1e-9,diffs
        if row.model.endswith('_z0.25'):
            with np.load(directory/'predictions'/f'{row.model[:-6]}_{row.origin}.npz') as z:
                assert np.array_equal(p,np.where(z['prediction']<.25,0,z['prediction']))
        if row.model=='incumbent':
            with np.load(ROOT/f'reports/remediation/predictions/current_tweedie_z0.25_{row.origin}.npz') as z:
                assert np.array_equal(p,z['prediction'])
        checks.append(dict(model=row.model,origin=row.origin,max_metric_error=max(diffs.values())))
    for date in protocol['origins']:
        idx=panel.dates.get_loc(date)
        # Extreme future mutations preserve every historical feature/allocation.
        changed=Panel(panel.dates,panel.y.copy(),panel.stock.copy(),panel.catalogs)
        changed.y[idx+1:]=1234567
        changed.stock[idx+1:]=7654321
        pd.testing.assert_frame_equal(snapshot(panel,idx),snapshot(changed,idx))
        pd.testing.assert_frame_equal(snapshot(article_panel(panel),idx),snapshot(article_panel(changed),idx))
        assert np.array_equal(weekday_weights(panel,idx),weekday_weights(changed,idx))
        assert np.array_equal(warehouse_shares(panel,idx),warehouse_shares(changed,idx))
        shares=warehouse_shares(panel,idx)
        assert np.allclose(shares.sum(0),1,atol=1e-14) and (shares>=0).all()
        origin_indices=sorted(set(range(179,idx-64+1,35))|{idx-64})
        assert max(o+64 for o in origin_indices)<=idx
        metadata=json.loads(results[(results.origin==date)&(results.model=='weekly_allocation')].iloc[0].metadata)
        assert metadata['origins']==[str(panel.dates[o].date()) for o in origin_indices]
        article_metadata=json.loads(results[(results.origin==date)&(results.model=='article_topdown')].iloc[0].metadata)
        assert article_metadata['training_origins']==metadata['origins']
        leakage.append(dict(origin=date,future_mutation_invariant=True,
            latest_training_target=str(panel.dates[max(o+64 for o in origin_indices)].date()),
            latest_origin=str(panel.dates[max(origin_indices)].date())))
        # All five saved weights re-evaluated; no fitting and no dependence on saved predictions.
        weekly=lgb.Booster(model_file=str(directory/'predictions'/f'weekly_{date}.txt'))
        snap=snapshot(panel,idx)
        totals=np.stack([weekly.predict(weekly_frame(snap,panel.dates[idx],s,e),num_threads=4) for s,e in BUCKETS])
        dows=pd.date_range(panel.dates[idx]+pd.Timedelta(days=1),periods=64).dayofweek.to_numpy()
        with np.load(ROOT/f'reports/remediation/predictions/tweedie_raw_{date}.npz') as z:
            raw=z['prediction']
        reconstructed={'weekly_allocation':allocate_buckets(totals,weekday_weights(panel,idx)[dows]),
                       'weekly_direct_shape':allocate_buckets(totals,raw)}
        agg=article_panel(panel)
        article=lgb.Booster(model_file=str(directory/'predictions'/f'article_{date}.txt'))
        aggregate=predict_panel(agg,idx,dict(model=article,config=article_metadata,catalogs=agg.catalogs))
        reconstructed['article_topdown']=(aggregate[:,None,:]*shares[None,:,:]).reshape(64,-1)
        for name,p in reconstructed.items():
            with np.load(directory/'predictions'/f'{name}_{date}.npz') as z:
                error=float(np.max(np.abs(p-z['prediction'])))
            assert error<1e-10,(name,date,error)
            if name.startswith('weekly'):
                coherent_error=max(float(np.max(np.abs(p[s-1:e-1].sum(0)-totals[i]))) for i,(s,e) in enumerate(BUCKETS))
            else:
                coherent_error=float(np.max(np.abs(p.reshape(64,*shares.shape).sum(1)-aggregate)))
            assert coherent_error<1e-10
            replay.append(dict(model=name,origin=date,saved_weight_max_error=error,coherence_max_error=coherent_error))
        del changed
    for reference in ['delivery_manifest.json','review_baseline_hashes.json','initial_manifest.json']:
        entries=json.loads((ROOT/'reports/remediation'/reference).read_text(encoding='utf-8'))
        if isinstance(entries,dict):
            entries=entries['files']
        for entry in entries:
            p=ROOT/entry['path']
            if reference=='delivery_manifest.json':
                assert p.is_file(),str(p)
            if p.is_file():
                hashchecks.append(dict(reference=reference,path=entry['path'],matches=digest(p)==entry['sha256']))
    # Edge fixture calls the actual merge/scorer too, including zero-truth exclusion.
    def frame(a):
        return pd.DataFrame(dict(date=np.repeat(['2020-01-01','2020-01-02'],3),
            warehouse_name='w',article=np.tile(['a','b','c'],2),quantity=a.ravel()))
    y=np.array([[10.,10.,0.],[10.,10.,0.]])
    p=np.array([[0.,12.,2.],[0.,12.,2.]])
    fixture=official.compute_all_metrics(frame(y),frame(p))
    assert all(abs(fixture[m]-score(y,p)[m])<1e-10 for m in fixture)
    pd.DataFrame(checks).to_csv(directory/'diagnostics/architecture_metric_review.csv',index=False)
    pd.DataFrame(replay).to_csv(directory/'diagnostics/architecture_weight_replay.csv',index=False)
    pd.DataFrame(hashchecks).to_csv(directory/'diagnostics/release_hash_comparison.csv',index=False)
    measured_new=results[results.model!='incumbent']
    assert measured_new.train_seconds.max()<1200
    assert measured_new.process_peak_rss_bytes.max()<10_000_000_000
    delivery=[c for c in hashchecks if c['reference']=='delivery_manifest.json']
    assert delivery and all(c['matches'] for c in delivery),[c for c in delivery if not c['matches']]
    delivery_manifest=json.loads((ROOT/'reports/remediation/delivery_manifest.json').read_text(encoding='utf-8'))
    archive=Path(delivery_manifest['archive'])
    assert digest(archive)==delivery_manifest['archive_sha256']
    summary=dict(no_training=True,forecasts_verified=len(checks),saved_weight_replays=len(replay),
        final_delivery_files_matched=len(delivery),
        release_archive_sha256=digest(archive),
        max_fit_seconds=float(measured_new.train_seconds.max()),
        max_sampled_process_rss_bytes=int(measured_new.process_peak_rss_bytes.max()),
        max_metric_error=max(c['max_metric_error'] for c in checks),
        max_prediction_replay_error=max(c['saved_weight_max_error'] for c in replay),
        max_coherence_error=max(c['coherence_max_error'] for c in replay),
        future_mutation_checks=leakage,official_merge_fixture=fixture,
        protocol_sha256=digest(directory/'experiment_protocol.json'),
        old_reference_hash_mismatches=[c for c in hashchecks if not c['matches']],
        limitations=['saved raw-shape model provenance inherited from old audit',
            'old-reference mismatches are reported, not evidence of new-run mutation',
            'budget is not automatically enforced by experiment script',
            'weekly_direct_shape excludes upstream raw model fit/predict cost',
            'incumbent reuse timing zero is not measured inference',
            'source/metadata training cutoff inspection plus future-mutation check, no duplicate fit'])
    (directory/'diagnostics/independent_architecture_review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
