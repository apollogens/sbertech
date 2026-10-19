"""Baseline-only full-grid rolling-origin evaluation."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from src.data import load_panel
from src.baselines import baseline_predict
from src.metrics import evaluate

if __name__=="__main__":
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir',type=Path,default=root/'cache')
    parser.add_argument('--output',type=Path,default=root/'reports/baseline_backtest.csv')
    args=parser.parse_args()
    try:
        panel=load_panel(args.cache_dir); records=[]
        if len(panel.dates)<372:
            raise ValueError('Для трёх полных окон и 180 дней истории требуется минимум 372 дня')
        for fold,origin in enumerate([len(panel.dates)-193,len(panel.dates)-129,len(panel.dates)-65],1):
            truth=panel.y[origin+1:origin+65]
            reference=baseline_predict(panel,origin,"last")
            for kind in ["zero","last","mean28","mean90","seasonal56","tsb"]:
                result=evaluate(truth,baseline_predict(panel,origin,kind),reference)
                records.append({"fold":fold,"model":kind,**result["raw"],"local_minmax_score":result["score"]})
        frame=pd.DataFrame(records)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        frame.to_csv(args.output,index=False)
    except (OSError,ValueError,KeyError) as exc:
        parser.exit(2,f'Ошибка backtest: {exc}\n')
    print(frame.to_string(index=False))
