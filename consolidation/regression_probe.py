"""Real 180-day inference compared with immutable pre-consolidation CSVs."""
from pathlib import Path
import json
import sys
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from src.runtime import load_bundle,predict_64
from src.data import read_inputs,clean_stock
from src.artifacts import file_hash
from src.submission import validate_submission

def run():
    out=ROOT/'consolidation/regression';out.mkdir(parents=True,exist_ok=True)
    inputs=ROOT/'integration/release/experimental180'
    sales,stock=read_inputs(inputs/'sales.csv',inputs/'stock.csv');stock=clean_stock(stock)
    results=[]
    for name,path,strategy,reference in [('nonton-v1',ROOT/'model',None,'incumbent_P1.csv'),
                                       ('equal4',ROOT/'bundles/equal4-rc1','equal4:P1','equal4_P1.csv')]:
        start=perf_counter();bundle=load_bundle(path,strategy=strategy);loaded=perf_counter()-start
        start=perf_counter();frame=predict_64(sales,stock,bundle);seconds=perf_counter()-start
        validate_submission(frame,sales.date.max(),bundle['catalogs'])
        target=out/(name+'.csv');frame.to_csv(target,index=False,float_format='%.17g')
        before=pd.read_csv(inputs/reference,dtype={'date':str,'warehouse_name':str,'article':str})
        assert frame.iloc[:,:3].equals(before.iloc[:,:3])
        difference=float(np.max(np.abs(frame.quantity-before.quantity)))
        assert difference<1e-12,difference
        results.append(dict(strategy=name,rows=len(frame),load_seconds=loaded,inference_seconds=seconds,
                            max_abs_difference=difference,csv_byte_identical=file_hash(target)==file_hash(inputs/reference),
                            sha256=file_hash(target),loaded_models=list(bundle.get('models',{'daily':None}))))
        del bundle,frame
    (out/'result.json').write_text(json.dumps(dict(status='passed',history_days=180,results=results),indent=2),encoding='utf-8')
    print(json.dumps(results))
if __name__=='__main__':run()
