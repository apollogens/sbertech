"""Fixed first-origin survivor set and prediction mass on unknown IDs; no fit."""
from catalog_selection_audit import ROOT,OUT,score
from src.data import load_panel
import numpy as np
import pandas as pd

def main():
    panel=load_panel(ROOT/'cache'); first=pd.read_csv(OUT/'catalog_first_observed.csv',dtype=str)
    first=first[(first.source=='sales')&(first.key_type=='article')].set_index('key').first_date
    pairs=panel.pairs; articles=pairs.get_level_values(1)
    survive=np.asarray(articles.map(first)<= '2025-09-14')
    rows=[]; unknown=[]
    for path in sorted((ROOT/'research/predictions').glob('*.npz')):
        date=path.stem[-10:]; model=path.stem[:-11]
        with np.load(path) as z: p=z['prediction'].astype(float)
        idx=panel.dates.get_loc(date); y=panel.y[idx+1:idx+65].astype(float)
        rows.append(dict(model=model,origin=date,survivor_pairs=int(survive.sum()),**score(y[:,survive],p[:,survive])))
        unknown_mask=np.asarray(articles.map(first)>date)
        unknown.append(dict(model=model,origin=date,unknown_pairs=int(unknown_mask.sum()),
            positive_forecast_cells=int((p[:,unknown_mask]>0).sum()),predicted_units=float(p[:,unknown_mask].sum()),
            true_units=float(y[:,unknown_mask].sum())))
    pd.DataFrame(rows).to_csv(OUT/'catalog_common_survivor_metrics.csv',index=False)
    pd.DataFrame(unknown).to_csv(OUT/'catalog_unknown_prediction_mass.csv',index=False)
    print('Common surviving set:',int(survive.sum()),'pairs;',len(rows),'forecasts')

if __name__=='__main__': main()
