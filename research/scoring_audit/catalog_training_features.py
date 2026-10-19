"""Historical catalog sensitivity at every direct training origin; does not fit."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src.data import Panel,load_panel
from src.features import snapshot
OUT=Path(__file__).resolve().parent

def main():
    p=load_panel(ROOT/'cache'); f=pd.read_csv(OUT/'catalog_first_observed.csv',dtype=str)
    dates=['2025-09-14','2025-11-17','2026-01-20','2026-03-25','2026-05-28']
    rows=[]; changes=[]
    for cutoff in dates:
        idx=p.dates.get_loc(cutoff)
        origins=sorted(set(range(179,idx-64+1,35))|{idx-64})
        for i in origins:
            date=str(p.dates[i].date())
            known=f[(f.source=='sales')&(f.first_date<=date)]
            kw=known[known.key_type=='warehouse_name'].key.tolist()
            ka=known[known.key_type=='article'].key.tolist()
            use=np.array([w*799+a for w,name in enumerate(p.catalogs['warehouses']) for a,key in enumerate(p.catalogs['articles']) if name in kw and key in ka])
            rows.append(dict(cutoff=cutoff,training_origin=date,known_warehouses=len(kw),known_articles=len(ka),known_pairs=len(use),future_catalog_pairs=8789-len(use)))
            q=Panel(p.dates,p.y[:,use],p.stock[:,use],dict(warehouses=[w for w in p.catalogs['warehouses'] if w in kw],articles=[a for a in p.catalogs['articles'] if a in ka]))
            a=snapshot(p,i).iloc[use].reset_index(drop=True); b=snapshot(q,i)
            for col in a:
                av=a[col].to_numpy(); bv=b[col].to_numpy()
                mask=~np.isclose(av,bv,rtol=1e-5,atol=1e-4,equal_nan=True)
                if mask.any():
                    changes.append(dict(cutoff=cutoff,training_origin=date,feature=col,compared_pairs=len(use),changed_pairs=int(mask.sum()),max_abs_change=float(np.nanmax(np.abs(av-bv)))))
    pd.DataFrame(rows).to_csv(OUT/'catalog_training_origin_summary.csv',index=False)
    pd.DataFrame(changes).to_csv(OUT/'catalog_training_feature_sensitivity.csv',index=False)
    print(pd.DataFrame(rows).groupby('cutoff')[['known_warehouses','known_articles','future_catalog_pairs']].agg(['min','max']).to_string())

if __name__=='__main__': main()
