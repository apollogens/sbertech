"""Fit an isolated deployable research bundle; never writes model/ or app/."""
from pathlib import Path
import sys
import json
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.data import load_panel
from integration.corrected_models import fit_components,save_bundle

if __name__=='__main__':
    panel=load_panel(ROOT/'cache');start=perf_counter()
    models,metadata=fit_components(panel,len(panel.dates)-1)
    save_bundle(models,metadata,panel.catalogs,ROOT/'integration/models/final_experimental')
    (ROOT/'integration/final_experimental_training.json').write_text(json.dumps(dict(metadata=metadata,seconds=perf_counter()-start,production=False),indent=2),encoding='utf-8')
    print('Experimental final bundle saved; production untouched',flush=True)
