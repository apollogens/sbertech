from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from src.predict import load_bundle
from src.submission import validate_submission

if __name__=="__main__":
    p=argparse.ArgumentParser()
    root=Path(__file__).resolve().parents[1]
    p.add_argument("--input",default=root/"submission.csv")
    p.add_argument("--model",default=root/"model")
    p.add_argument("--origin",default="2026-07-31")
    a=p.parse_args()
    try:
        frame=pd.read_csv(a.input,dtype={"date":str,"article":str,"warehouse_name":str})
        print(validate_submission(frame,a.origin,load_bundle(a.model)["catalogs"]))
    except (OSError,ValueError,KeyError) as exc:
        p.exit(2,f'Ошибка проверки submission: {exc}\n')
