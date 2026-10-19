"""Isolated 180-day experimental inference verification; never calls fit."""
from pathlib import Path
import hashlib,json,shutil,sys,tempfile,threading,time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np,pandas as pd,psutil
from integration.experimental_predict import predict_csv
from integration.corrected_models import load_experimental_bundle
from src.data import read_inputs,clean_stock
from src.predict import load_bundle,predict_64
OUT=ROOT/'integration/release/experimental180';BUNDLE=ROOT/'integration/models/final_experimental'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
 assert (BUNDLE/'manifest.json').is_file(),'Final bundle not ready; no inference attempted'
 config=json.loads((BUNDLE/'config.json').read_text(encoding='utf-8'));catalog=config['catalogs'];inputs=json.loads((OUT/'inputs.json').read_text());origin=pd.Timestamp(inputs['cutoff'])
 dates=pd.date_range(origin+pd.Timedelta(days=1),periods=64).strftime('%Y-%m-%d')
 expected=pd.MultiIndex.from_product([dates,catalog['warehouses'],catalog['articles']],names=['date','warehouse_name','article'])
 records=[];peak=[0];stop=threading.Event()
 def monitor():
  p=psutil.Process()
  while not stop.wait(.05):peak[0]=max(peak[0],p.memory_info().rss)
 thread=threading.Thread(target=monitor,daemon=True);thread.start()
 try:
  with patch('integration.catalog_policy._first_observed',side_effect=AssertionError('Historical audit input forbidden')),patch('lightgbm.train',side_effect=AssertionError('Training forbidden during inference')):
   t=time.perf_counter();incumbent=load_bundle(ROOT/'model');load_seconds=time.perf_counter()-t
   sales,stock=read_inputs(OUT/'sales.csv',OUT/'stock.csv');old=predict_64(sales,clean_stock(stock),incumbent);old_seconds=time.perf_counter()-t
   assert pd.MultiIndex.from_frame(old.iloc[:,:3]).equals(expected)
   old.to_csv(OUT/'incumbent_P1.csv',index=False,float_format='%.17g')
   incumbent_record=dict(model='retained_nonton-v1',total_seconds=old_seconds,load_bundle_seconds=load_seconds,rows=len(old),forecast_sha256=sha(OUT/'incumbent_P1.csv'))
   del sales,stock,incumbent,old
   for candidate in ['equal4:P1','D:P1']:
    t=time.perf_counter();frame=predict_csv(BUNDLE,OUT/'sales.csv',OUT/'stock.csv',candidate);seconds=time.perf_counter()-t
    assert list(frame)==['date','warehouse_name','article','quantity'];assert len(frame)==562496
    assert pd.MultiIndex.from_frame(frame.iloc[:,:3]).equals(expected)
    assert np.isfinite(frame.quantity).all() and (frame.quantity>=0).all()
    p=OUT/(candidate.replace(':','_')+'.csv');frame.to_csv(p,index=False,float_format='%.17g')
    saved=pd.read_csv(p,dtype={'date':str,'article':str,'warehouse_name':str});assert pd.MultiIndex.from_frame(saved.iloc[:,:3]).equals(expected);assert np.isfinite(saved.quantity).all()
    t=time.perf_counter();repeat=predict_csv(BUNDLE,OUT/'sales.csv',OUT/'stock.csv',candidate);repeat_seconds=time.perf_counter()-t
    assert frame.equals(repeat)
    records.append(dict(candidate=candidate,seconds=seconds,repeat_seconds=repeat_seconds,rows=len(frame),forecast_sha256=sha(p),deterministic_exact=True,complete_official_grid=True,volume=float(frame.quantity.sum())))
 finally:stop.set();thread.join()
 with tempfile.TemporaryDirectory(prefix='bundle-tamper-',dir=OUT) as directory:
  tampered=Path(directory)
  for p in BUNDLE.iterdir():
   if p.is_file():shutil.copy2(p,tampered/p.name)
  c=json.loads((tampered/'config.json').read_text(encoding='utf-8'));c['ensemble_contract']['weights']['equal4']['daily']=0.5;(tampered/'config.json').write_text(json.dumps(c),encoding='utf-8')
  try:load_experimental_bundle(tampered)
  except ValueError as error:integrity=str(error)
  else:raise AssertionError('Tampered config accepted')
 result=dict(status='passed',production=False,training_called=False,history_days=180,historical_first_observed_forbidden=True,input_provenance=inputs,incumbent_same_input=incumbent_record,forecasts=records,peak_sampled_process_rss_bytes=peak[0],tampered_config_weights_rejected=integrity,bundle_files={p.name:sha(p) for p in sorted(BUNDLE.iterdir()) if p.is_file()},scope='Standalone input-derived features and complete all-three-booster inference with key alignment; no experimental API or Docker parity claim')
 (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':run()
