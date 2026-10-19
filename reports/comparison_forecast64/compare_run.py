import sys, json, time, importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
ROOT = Path('D:/SberTech')
REPO = BASE / 'forecast-container'
sys.path.insert(0, str(REPO))
import train
from app.models import inverse_target, postprocess_forecast
spec = importlib.util.spec_from_file_location('local_metrics', ROOT/'src/metrics.py')
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)
original = train.evaluate_frame

def capture(model, frame, zero_threshold=0., round_int=False):
    forecast = frame[['date','warehouse_name','article']].copy()
    forecast['quantity'] = postprocess_forecast(inverse_target(model.predict(frame), model.target_transform), zero_threshold, round_int)
    forecast.to_csv(BASE/'rival_holdout.csv', index=False)
    catalog = json.loads((ROOT/'cache/catalogs.json').read_text(encoding='utf-8'))
    with np.load(ROOT/'cache/panel.npz') as d:
        dates = pd.DatetimeIndex(d['dates'])
        origin = dates.get_loc(pd.Timestamp('2026-05-28'))
        truth = d['y'][origin+1:origin+65].astype(float)
    idx = pd.MultiIndex.from_product([dates[origin+1:origin+65],catalog['warehouses'],catalog['articles']], names=['date','warehouse_name','article'])
    prediction = forecast.set_index(['date','warehouse_name','article']).quantity.reindex(idx)
    missing = int(prediction.isna().sum())
    rival = prediction.fillna(0).to_numpy().reshape(truth.shape)
    ours = np.load(ROOT/'reports/oof/lgb_tweedie_z0.25_fold3.npz')['prediction']
    result = {'origin':'2026-05-28','dates':['2026-05-29','2026-07-31'],'rows':len(idx),'rival_rows':len(forecast),'missing_rival_rows_filled_zero':missing,'rival_iterations':model.selected_iterations,'models':{}}
    for name, pred in [('ours',ours),('rival',rival),('zero',np.zeros_like(truth)),('ours_rounded_diagnostic',np.rint(ours))]:
        result['models'][name] = {**metrics.compute_metrics(truth,pred),'smape_include_zero_zero':metrics.smape_include_zero_zero(truth,pred),'zero_fraction':float((pred==0).mean())}
    present = prediction.notna().to_numpy().reshape(truth.shape).all(axis=0)
    result['common_pairs_models'] = {name:{**metrics.compute_metrics(truth[:,present],pred[:,present]),'smape_include_zero_zero':metrics.smape_include_zero_zero(truth[:,present],pred[:,present])} for name,pred in [('ours',ours),('rival',rival)]}
    (BASE/'comparison_metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('INDEPENDENT_COMPARISON '+json.dumps(result),flush=True)
    return original(model,frame,zero_threshold,round_int)

train.evaluate_frame = capture
train.main(['--sales','C:/Users/apollo/Desktop/выборка/sales_dataset_hakaton_train.csv','--stock','C:/Users/apollo/Desktop/выборка/stock_dataset_hakaton_train.csv','--model-type','blend','--round-int','--no-refit','--no-log','--threads','4','--out-dir',str(BASE/'strict_holdout_model')])
