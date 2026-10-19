"""Agent F: no fitting; official scalar metrics and independent inference algebra."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import lightgbm as lgb
import numpy as np
import pandas as pd
from src.data import Panel, load_panel
from src.features import horizon_features, snapshot
from scripts import official_score as official
from integration.catalog_policy import asof_panel, safe_snapshot, stable_codes

OUT = ROOT / "integration/review"
METRICS = list(official.METRIC_WEIGHTS)
BUCKETS = [(s, min(s + 7, 65)) for s in range(1, 65, 7)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def score(truth, pred):
    sm = [official.smape_series(a, b) for a, b in zip(truth.T, pred.T)]
    bias = [official.bias_abs_series(a, b) for a, b in zip(truth.T, pred.T)]
    bias = [x for x in bias if x is not None]
    return dict(smape=float(np.mean(sm)), bias=float(np.mean(bias)) if bias else 0.,
                wape=official.wape(truth, pred), rmse=official.rmse(truth, pred),
                rmsle=official.rmsle(truth, pred))


def daily(model, snap, date):
    return np.stack([model.predict(horizon_features(snap, date, h), num_threads=4) for h in range(1, 65)])


def independent_replay(panel, origin, path):
    models = {n: lgb.Booster(model_file=str(path / (n + '.txt'))) for n in ['daily', 'weekly', 'article']}
    active, idx = asof_panel(panel, origin)
    snap, _ = safe_snapshot(panel, origin)
    nw, na = len(active.catalogs['warehouses']), len(active.catalogs['articles'])
    raw = daily(models['daily'], snap, panel.dates[origin])
    totals = []
    for start, end in BUCKETS:
        frame = horizon_features(snap, panel.dates[origin], start)
        frame['bucket_days'] = np.float32(end-start)
        frame['bucket_end'] = np.float32(end-1)
        totals.append(models['weekly'].predict(frame, num_threads=4))
    totals = np.array(totals)
    hist = active.y[-180:].astype(float)
    dows = active.dates[-180:].dayofweek.to_numpy()
    dowweights = []
    for d in range(7):
        z = hist[dows == d]
        prior = z.reshape(len(z), nw, na).mean(axis=(0, 2))
        dowweights.append((z.sum(axis=0) + 4*np.repeat(prior, na))/(len(z)+4))
    dowweights = np.array(dowweights)
    dowweights = np.where(dowweights.sum(axis=0)[None, :] > 0, dowweights, 1.)
    future_dows = pd.date_range(panel.dates[origin]+pd.Timedelta(days=1), periods=64).dayofweek
    outputs = dict(daily=raw)
    coherence = []
    for name, weights in [('weekly', dowweights[future_dows]), ('shape', raw)]:
        p = np.zeros_like(raw)
        for i, (s, e) in enumerate(BUCKETS):
            w = np.maximum(weights[s-1:e-1], 0.)
            denom = w.sum(axis=0)
            shares = np.divide(w, denom, out=np.full_like(w, 1/len(w)), where=denom > 0)
            p[s-1:e-1] = totals[i]*shares
            coherence.append(float(np.max(np.abs(p[s-1:e-1].sum(axis=0)-totals[i]))))
        outputs[name] = p
    stock = active.stock.reshape(-1, nw, na)
    agg = Panel(active.dates, active.y.reshape(-1, nw, na).sum(axis=1),
                np.where(np.isfinite(stock).all(axis=1), np.nansum(stock, axis=1), np.nan),
                dict(warehouses=['all_warehouses'], articles=active.catalogs['articles']))
    af = snapshot(agg, len(agg.dates)-1)
    af['warehouse_id'] = np.repeat(stable_codes(['all_warehouses'], 'aggregate_warehouse'), na)
    af['article_id'] = stable_codes(active.catalogs['articles'], 'article')
    article_total = daily(models['article'], af, panel.dates[origin])
    mass = hist.reshape(-1, nw, na).sum(axis=0)
    prior = mass.sum(axis=1)
    prior = prior/prior.sum() if prior.sum() else np.full(nw, 1/nw)
    smooth = mass + 28*hist.reshape(-1, nw, na).mean(axis=0).sum(axis=0)[None, :]*prior[:, None]
    shares = np.divide(smooth, smooth.sum(axis=0), out=np.broadcast_to(prior[:, None], smooth.shape).copy(), where=smooth.sum(axis=0)>0)
    article = article_total[:, None, :]*shares[None, :, :]
    coherence.append(float(np.max(np.abs(article.sum(axis=1)-article_total))))
    outputs['article'] = article.reshape(64, -1)
    expanded = {}
    for n, p in outputs.items():
        expanded[n] = np.zeros((64, panel.y.shape[1]))
        expanded[n][:, idx] = p
    return expanded, max(coherence)


def policy(x, name):
    if name == 'continuous': return x.copy()
    if name == 'threshold025': return np.where(x < .25, 0., x)
    if name == 'nearest_even': return np.rint(x)
    if name == 'threshold_then_nearest_even': return np.rint(np.where(x < .25, 0., x))
    raise ValueError(name)


def main():
    OUT.mkdir(exist_ok=True)
    table = pd.read_csv(ROOT/'integration/per_origin_metrics.csv')
    protocol = json.loads((ROOT/'integration/executed_protocol.json').read_text(encoding='utf-8'))
    assert len(table) == 215 and table.origin.nunique() == 5 and table.candidate.nunique() == 43
    assert sha(ROOT/'integration/experiment_protocol.md') == protocol['protocol_sha256']
    panel = load_panel(ROOT/'cache')
    metrics, replay, metadata, identities, legacy = [], [], [], [], []
    max_metric_error = 0.
    for date in protocol['origins']:
        origin = panel.dates.get_loc(date)
        truth = panel.y[origin+1:origin+65].astype(float)
        bundle = ROOT/'integration/models'/date
        manifest = json.loads((bundle/'manifest.json').read_text())
        config = json.loads((bundle/'config.json').read_text(encoding='utf-8'))
        for name, digest in manifest['files'].items(): assert sha(bundle/name) == digest
        for name, digest in manifest['source_hashes'].items(): assert sha(ROOT/name) == digest
        expected_origins = sorted(set(range(179, origin-64+1, 35)) | {origin-64})
        records = config['metadata']['origin_catalogs']
        assert [x['origin'] for x in records] == [str(panel.dates[i].date()) for i in expected_origins]
        for record, inner in zip(records, expected_origins):
            active, idx = asof_panel(panel, inner)
            assert record['known_pairs'] == len(idx)
            assert record['known_articles'] == len(active.catalogs['articles'])
            assert record['known_warehouses'] == len(active.catalogs['warehouses'])
            assert record['active_catalog_sha256'] == hashlib.sha256(json.dumps(active.catalogs, sort_keys=True).encode()).hexdigest()
            assert record['max_target_date'] == str(panel.dates[inner+64].date()) <= date
            f, _ = safe_snapshot(panel, inner)
            assert f.article_id.dtype == f.warehouse_id.dtype == np.int32
            metadata.append(dict(outer=date, inner=record['origin'], known_pairs=len(idx), max_target_date=record['max_target_date'], passed=True))
        keys = pd.MultiIndex.from_product([
            pd.date_range(pd.Timestamp(date)+pd.Timedelta(days=1), periods=64).strftime('%Y-%m-%d'),
            panel.catalogs['warehouses'], panel.catalogs['articles']], names=['date','warehouse_name','article']).to_frame(index=False)
        assert len(keys) == 562496 and not keys.duplicated().any()
        key_sha = hashlib.sha256(keys.to_csv(index=False, lineterminator='\n').encode()).hexdigest()
        fresh, coherence = independent_replay(panel, origin, bundle)
        raw = {}
        for name in ['daily','weekly','shape','article']:
            file = ROOT/'integration/predictions'/f'component_{name}_{date}.npz'
            with np.load(file) as z:
                assert str(z['origin']) == date and str(z['key_sha256']) == key_sha
                raw[name] = z['prediction'].copy()
            error = float(np.max(np.abs(fresh[name]-raw[name])))
            assert error < 1e-10
            replay.append(dict(origin=date, candidate='component_'+name, max_abs_error=error, coherence_error=coherence, model_reloaded=True))
        last = np.load(ROOT/f'reports/remediation/predictions/last_{date}.npz')['prediction'].astype(float)
        lastscore = score(truth, last)
        for row in table[table.origin == date].itertuples(index=False):
            file = ROOT/row.prediction_path
            assert sha(file) == row.prediction_sha256
            with np.load(file) as z:
                pred = z['prediction'].copy()
                assert str(z['origin']) == date
                assert str(z['key_sha256']) == row.key_sha256 == key_sha
            assert pred.shape == (64,8789) and np.isfinite(pred).all() and (pred >= 0).all()
            assert hashlib.sha256(pred.tobytes()).hexdigest() == row.array_sha256
            got = score(truth, pred)
            error = max(abs(got[k]-getattr(row,k)) for k in METRICS)
            max_metric_error = max(max_metric_error, error)
            assert error < 1e-10
            actual = truth.sum(axis=0); predicted = pred.sum(axis=0); eligible = actual > 0
            signed = float(np.mean((predicted[eligible]-actual[eligible])/actual[eligible])*100)
            assert abs(signed-row.signed_series_bias) < 1e-10
            assert int(((predicted == 0)&eligible).sum()) == row.zero_total_eligible
            assert int((predicted == 0).sum()) == row.zero_total_all
            assert abs(float(pred.sum())-row.total_volume) < 1e-8
            minmax = sum(official.METRIC_WEIGHTS[k]*min(got[k]/lastscore[k], 1) for k in METRICS)
            assert abs(minmax-row.minmax_last) < 1e-12
            metrics.append(dict(candidate=row.candidate, origin=date, max_abs_metric_error=error, **got, minmax_last=minmax))
            weights = json.loads(row.weights)
            blend = None
            for name in sorted(weights):
                term = weights[name]*policy(fresh[name],row.component_policy)
                blend = term if blend is None else blend+term
            blend = policy(blend,row.output_policy)
            blenderr = float(np.max(np.abs(blend-pred)))
            assert blenderr < 1e-10
            replay.append(dict(origin=date,candidate=row.candidate,max_abs_error=blenderr,coherence_error=coherence,model_reloaded=True))
        for mechanism in protocol['weights']:
            a = np.load(ROOT/f'integration/predictions/{mechanism}_P2_{date}.npz')['prediction']
            b = np.load(ROOT/f'integration/predictions/{mechanism}_P3_{date}.npz')['prediction']
            assert np.array_equal(a,b)
            identities.append(dict(origin=date, mechanism=mechanism, P2_P3_exact_equal=True))
        inc = np.load(ROOT/f'research/predictions/incumbent_{date}.npz')['prediction'].astype(float)
        old = score(truth, inc)
        new = next(r for r in metrics if r['origin']==date and r['candidate']=='D:P1')
        legacy.append(dict(origin=date, role='development' if date!=protocol['origins'][-1] else 'terminal_diagnostic',
                           **{'delta_'+k:new[k]-old[k] for k in METRICS}))
        print(date,'verified',flush=True)
    for name, data in [('metrics',metrics),('replay',replay),('training_catalogs',metadata),('rounding_aliases',identities),('legacy_comparison',legacy)]:
        pd.DataFrame(data).to_csv(OUT/(name+'.csv'),index=False)
    # Rebuild the fixed rank universe and primary quality screen from official metrics.
    signatures = {n:tuple(g[g.origin.isin(protocol['origins'][:4])].sort_values('origin').array_sha256)
                  for n,g in table.groupby('candidate')}
    seen = set(); members = []
    for n in protocol['rank_universe']:
        if signatures[n] not in seen:
            members.append(n); seen.add(signatures[n])
    scoring = json.loads((ROOT/'integration/scoring_universe.json').read_text())
    assert scoring['pools']['main18'] == members
    published_rank = pd.read_csv(ROOT/'integration/rank_sensitivity.csv')
    primary = published_rank[(published_rank.pool=='main18') & (published_rank.tie=='official_argsort') &
                             (published_rank.order=='forward') & (published_rank.smape_definition=='executable')]
    independent_scores = []
    for date in protocol['origins']:
        fold = {r['candidate']:r for r in metrics if r['origin']==date}
        published = table[table.origin==date].set_index('candidate')
        # Exact argsort is sensitive to floating-point ties. Verify published-rank
        # arithmetic on its verified CSV values, and retain scalar-source sensitivity.
        norm = official.normalize_rank({n:{k:float(published.loc[n,k]) for k in METRICS} for n in members})
        scalar_norm = official.normalize_rank({n:{k:fold[n][k] for k in METRICS} for n in members})
        ranks = {n:sum(official.METRIC_WEIGHTS[k]*norm[n][k] for k in METRICS) for n in members}
        for n in members:
            row = primary[(primary.origin==date)&(primary.candidate==n)].iloc[0]
            assert abs(row.score-ranks[n]) < 1e-12
            independent_scores.append(dict(origin=date,candidate=n,rank=ranks[n],
                scalar_rank=sum(official.METRIC_WEIGHTS[k]*scalar_norm[n][k] for k in METRICS),
                rank_delta=ranks[n]-ranks['D:P1'], minmax=fold[n]['minmax_last'],
                minmax_delta=fold[n]['minmax_last']-fold['D:P1']['minmax_last']))
    ranks = pd.DataFrame(independent_scores)
    ranks.to_csv(OUT/'primary_scores.csv',index=False)
    gates = pd.read_csv(ROOT/'integration/quality_gates.csv').set_index('candidate')
    passed = []
    for n in members:
        dev = ranks[(ranks.candidate==n)&ranks.origin.isin(protocol['origins'][:4])]
        periods = [dev[dev.origin.isin(ds)] for ds in [protocol['origins'][:2], protocol['origins'][2:4]]]
        gate = all(p[col].mean()<0 for p in periods for col in ['rank_delta','minmax_delta']) and all(
            (dev[col]<-1e-12).sum()>=3 for col in ['rank_delta','minmax_delta'])
        assert bool(gates.loc[n,'quality_screen']) == gate
        if gate: passed.append(n)
    # Nonnegative half-even rounding and order of operations have distinct semantics.
    from integration.ensemble_engine import postprocess, convex_combine, align_components
    x = np.array([0.,.249,.25,.5,1.5,2.5])
    assert np.array_equal(postprocess(x,'nearest_even'), [0,0,0,0,2,2])
    assert np.array_equal(postprocess(x,'threshold_then_nearest_even'),postprocess(x,'nearest_even'))
    parts = {'a':np.array([.1]),'b':np.array([.3])}
    w = {'a':.5,'b':.5}
    assert convex_combine(parts,w,output_policy='threshold025')[0] == 0
    assert convex_combine(parts,w,component_policy='threshold025')[0] == .15
    keys = pd.DataFrame(dict(date=['2026-01-01']*2,warehouse_name=['w']*2,article=['a','b']))
    frame=keys.copy();frame['quantity']=[1.,2.]
    assert np.array_equal(align_components({'a':frame.iloc[::-1]},keys)['a'],[1,2])
    result=dict(status='passed',fit_count=0,case_forecasts=215,raw_components=20,
                model_reloaded_forecasts=len(replay),training_catalog_checks=len(metadata),
                rounding_alias_checks=len(identities),max_abs_metric_error=max_metric_error,
                primary_rank_checked=len(independent_scores),quality_screen_passed=passed,
                max_abs_replay_error=max(r['max_abs_error'] for r in replay),
                max_abs_coherence_error=max(r['coherence_error'] for r in replay),
                protocol_sha256=protocol['protocol_sha256'],review_scope='code and numerical artifacts; no release/API/Docker claim')
    (OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__ == '__main__': main()
