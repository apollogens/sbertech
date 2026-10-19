"""Full-grid measured offline/API parity on identical cleaned history."""
import gc
import io
import json
from pathlib import Path
import sys
from time import perf_counter
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import psutil
from fastapi.testclient import TestClient
from app.main import create_app
from src.data import read_inputs,clean_stock,load_panel,Panel
from src.predict import load_bundle,predict_64,predict_panel
from src.metrics import compute_metrics
from src.submission import validate_submission


def run():
    peak=[0]; stop=threading.Event()
    def monitor():
        process=psutil.Process()
        while not stop.wait(.1):
            peak[0]=max(peak[0],process.memory_info().rss)
    thread=threading.Thread(target=monitor,daemon=True); thread.start()
    data=Path(r"C:\Users\apollo\Desktop\выборка")
    sales,stock=read_inputs(data/"sales_dataset_hakaton_train.csv",data/"stock_dataset_hakaton_train.csv")
    stock=clean_stock(stock)
    bundle=load_bundle()
    t=perf_counter(); offline=predict_64(sales,stock,bundle); offline_time=perf_counter()-t
    out=Path("data/parity"); out.mkdir(parents=True,exist_ok=True)
    sales.to_csv(out/"sales.csv",index=False)
    stock.to_csv(out/"stock.csv",index=False)
    offline.to_csv(out/"offline.csv",index=False,float_format="%.17g")
    files={"sales":("sales.csv",(out/"sales.csv").read_bytes(),"text/csv"),
           "stock":("stock.csv",(out/"stock.csv").read_bytes(),"text/csv")}
    origin=sales.date.max()
    del sales,stock
    gc.collect()
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code==200
        assert client.get("/predict/all").status_code==409
        t=perf_counter(); response=client.post("/predict",files=files); post_time=perf_counter()-t
        assert response.status_code==200, response.text[:500]
        api=pd.read_csv(io.StringIO(response.text),dtype={"date":str,"warehouse_name":str,"article":str})
        validate_submission(api,origin,bundle["catalogs"])
        assert api.iloc[:,:3].equals(offline.iloc[:,:3])
        difference=float(np.max(np.abs(api.quantity.to_numpy()-offline.quantity.to_numpy())))
        assert difference<=1e-7, difference
        t=perf_counter(); repeat=client.post("/predict",files=files); repeated_time=perf_counter()-t
        assert repeat.status_code==200
        assert response.content==repeat.content
        t=perf_counter(); cached=client.get("/predict/all"); get_time=perf_counter()-t
        assert cached.content==response.content
        pair=client.get("/predict",params={"article":bundle["catalogs"]["articles"][0],"warehouse":bundle["catalogs"]["warehouses"][0]})
        assert len(pd.read_csv(io.StringIO(pair.text)))==64
        del response,repeat,cached,files,api
        gc.collect()
        # JSON full grid checks actual serialization, not a stub.
        t=perf_counter(); js=client.get("/predict/all",params={"format":"json"}); json_time=perf_counter()-t
        parsed=js.json()
        assert len(parsed)==len(offline)
        assert abs(parsed[-1]["quantity"]-offline.quantity.iloc[-1])<=1e-7
        del parsed,js
    # Untuned diagnostic: the selected frozen model on a 180-day-only API window.
    panel=load_panel(); origin_index=len(panel.dates)-65
    short=Panel(panel.dates[origin_index-179:origin_index+1],panel.y[origin_index-179:origin_index+1],
                panel.stock[origin_index-179:origin_index+1],panel.catalogs)
    config=bundle["config"]
    if config["kind"]=="lightgbm":
        import lightgbm as lgb
        holdout_bundle=dict(bundle,model=lgb.Booster(model_file="reports/oof/selected_holdout.txt"))
        short_prediction=predict_panel(short,179,holdout_bundle)
    else:
        short_prediction=predict_panel(short,179,bundle)
    metrics=compute_metrics(panel.y[origin_index+1:origin_index+65],short_prediction)
    stop.set();thread.join()
    result={"rows":len(offline),"max_abs_difference":difference,"tolerance":1e-7,
            "repeated_post_byte_identical":True,"offline_seconds":offline_time,"post_seconds":post_time,
            "repeated_post_seconds":repeated_time,"get_csv_seconds":get_time,"get_json_seconds":json_time,
            "peak_process_rss_bytes":peak[0],"holdout_180day_input_metrics":metrics,
            "status":"passed","input_policy":"Full sales history; negative and conflicting stock records removed explicitly"}
    Path("reports/parity_benchmarks.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    run()
