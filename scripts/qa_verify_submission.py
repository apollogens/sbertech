"""Fresh real artifact inference, two-run determinism and preserved output parity."""
from pathlib import Path
import json
import sys
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from src.data import load_panel
from src.predict import load_bundle,predict_panel
from src.submission import forecast_frame,write_submission,validate_submission


def run():
    start=perf_counter();panel=load_panel();bundle=load_bundle()
    assert panel.catalogs==bundle['catalogs']
    origin=len(panel.dates)-1
    pred=predict_panel(panel,origin,bundle)
    repeat=predict_panel(panel,origin,bundle)
    np.testing.assert_array_equal(pred,repeat)
    frame=forecast_frame(pred,panel.dates[origin],panel.catalogs)
    target=Path('reports/qa/submission_verified.csv')
    write_submission(frame,target,panel.dates[origin],panel.catalogs)
    actual=pd.read_csv(target,dtype={'date':str,'warehouse_name':str,'article':str})
    original=pd.read_csv('submission.csv',dtype={'date':str,'warehouse_name':str,'article':str})
    assert actual.iloc[:,:3].equals(original.iloc[:,:3])
    difference=float(np.abs(actual.quantity-original.quantity).max())
    assert difference<=1e-7
    result={**validate_submission(actual,panel.dates[origin],panel.catalogs),
            'repeat_prediction_bitwise_equal':True,'original_submission_max_abs_difference':difference,
            'tolerance':1e-7,'output':str(target),'seconds':perf_counter()-start}
    Path('reports/qa/fresh_inference.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':run()
