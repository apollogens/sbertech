import sys, json, os, asyncio, time, threading
from pathlib import Path
import pandas as pd
import numpy as np
BASE=Path(__file__).resolve().parent
REPO=BASE/'forecast-container'
sys.path.insert(0,str(REPO))
os.environ['MODEL_DIR']=str(REPO/'model')
from app.validators import SALES_REQUIRED_COLS, validate_sales_csv, validate_stock_csv
from app.predictor import Predictor
from app.main import app
from fastapi.testclient import TestClient

dates=pd.date_range('2026-01-01',periods=180)
sales=pd.DataFrame([{**{c:'x' for c in SALES_REQUIRED_COLS},'date':str(d.date()),'warehouse_name':w,'article':a,'quantity':1.,'sales_sum':1.,'discount_sum':0.} for d in dates for w,a in [('warehouse_name_0','char_article_0'),('warehouse_name_1','char_article_1')]])
stock=sales[['date','warehouse_name','article']].assign(stock=2.)
result={}
for label,value in [('text','oops'),('nan',np.nan),('infinity',np.inf)]:
    broken=sales.copy(); broken.loc[0,'quantity']=value
    result['sales_'+label+'_validation']=validate_sales_csv(broken)
broken=stock.copy();broken.loc[0,'stock']='oops'
result['stock_text_validation']=validate_stock_csv(broken)
broken=sales.copy();broken.loc[0,'article']=None
result['missing_article_validation']=validate_sales_csv(broken)
engine=Predictor(REPO/'model').load()
forecast=engine.predict(sales,stock)
result['grid']={'actual_rows':len(forecast),'cartesian_rows':2*2*64}
engine.get_cached_forecast().iloc[0,3]=999999.
result['cache_mutable']=bool(engine.get_cached_forecast().iloc[0,3]==999999.)
with TestClient(app) as client:
    broken=sales.copy();broken.loc[0,'quantity']='oops'
    response=client.post('/predict',files={'sales':('sales.csv',broken.to_csv(index=False),'text/csv'),'stock':('stock.csv',stock.to_csv(index=False),'text/csv')})
    result['http_invalid_quantity_status']=response.status_code
    result['http_invalid_quantity_rows']=len(pd.read_csv(__import__('io').StringIO(response.text))) if response.status_code==200 else None

# ASGI responsiveness: make synchronous inference wait one second, then request health.
from app import main
original=main.predictor.predict
started=threading.Event()
def slow_predict(*args,**kwargs):
    started.set();time.sleep(1.0)
    return forecast
main.predictor.predict=slow_predict
import httpx
async def responsiveness():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        post=asyncio.create_task(client.post('/predict',files={'sales':('sales.csv',sales.to_csv(index=False)),'stock':('stock.csv',stock.to_csv(index=False))}))
        begin=time.perf_counter()
        await asyncio.sleep(.05)
        timer_delay=time.perf_counter()-begin
        await client.get('/health')
        await post
        return timer_delay
result['event_loop_50ms_timer_actual_seconds_with_1s_inference']=asyncio.run(responsiveness())
main.predictor.predict=original
(BASE/'rival_probes.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
