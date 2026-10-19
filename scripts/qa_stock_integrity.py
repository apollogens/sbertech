"""Independent bounded-memory raw stock reconstruction against the saved panel."""
from pathlib import Path
import hashlib
import json
import sys
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from src.data import load_panel


def run():
    start=perf_counter(); panel=load_panel(); out=Path('reports/qa')
    source=Path(r'C:\Users\apollo\Desktop\выборка\stock_dataset_hakaton_train.csv')
    historical=json.loads(Path('reports/input_audit.json').read_text())['stock']
    days=pd.date_range(historical['date_min'],historical['date_max'])
    width=len(panel.pairs); shape=(len(days),width)
    rawmin=np.full(shape,np.inf);rawmax=np.full(shape,-np.inf)
    cleanmin=np.full(shape,np.inf);cleanmax=np.full(shape,-np.inf)
    count=np.zeros(shape,dtype=np.int32)
    rows=negative=zero=0; total=0.
    for chunk in pd.read_csv(source,dtype={'date':str,'warehouse_name':str,'article':str},chunksize=150000):
        assert chunk.date.str.fullmatch(r'\d{4}-\d{2}-\d{2}').all()
        dates=pd.to_datetime(chunk.date,format='%Y-%m-%d',errors='raise')
        di=days.get_indexer(dates)
        pi=panel.pairs.get_indexer(pd.MultiIndex.from_frame(chunk[['warehouse_name','article']]))
        assert (di>=0).all() and (pi>=0).all()
        values=pd.to_numeric(chunk.stock,errors='raise').to_numpy(dtype=float)
        assert np.isfinite(values).all()
        rows+=len(values);negative+=int((values<0).sum());zero+=int((values==0).sum());total+=values.sum()
        np.add.at(count,(di,pi),1)
        np.minimum.at(rawmin,(di,pi),values);np.maximum.at(rawmax,(di,pi),values)
        keep=values>=0
        np.minimum.at(cleanmin,(di[keep],pi[keep]),values[keep]);np.maximum.at(cleanmax,(di[keep],pi[keep]),values[keep])
    observed=count>0; clean=np.isfinite(cleanmin)&(cleanmin==cleanmax)
    dates_index=days.get_indexer(panel.dates);assert (dates_index>=0).all()
    independent=np.where(clean,cleanmin,np.nan)[dates_index].astype(np.float32)
    np.testing.assert_array_equal(independent,panel.stock)
    with source.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
    initial=json.loads(Path('reports/input_manifest.json').read_text())
    assert digest==initial[str(source)]['sha256']
    result={'raw_rows':rows,'negative_rows':negative,'zero_rows':zero,'sum':float(total),
            'raw_unique_keys':int(observed.sum()),'duplicate_key_rows':int((count-np.minimum(count,1)).sum()),
            'raw_conflicting_keys':int((observed&(rawmin!=rawmax)).sum()),
            'clean_unique_keys':int(clean.sum()),'conflicts_after_negative_removal':int((np.isfinite(cleanmin)&(cleanmin!=cleanmax)).sum()),
            'observed_pairs':int(observed.any(axis=0).sum()),'calendar_days':len(days),'date_min':str(days[0].date()),'date_max':str(days[-1].date()),
            'panel_stock_bitwise_equal':True,'raw_source_sha256':digest,'seconds':perf_counter()-start}
    (out/'stock_integrity.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':run()
