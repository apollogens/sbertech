"""Shared inference CLI; inputs must satisfy source-quality contract."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.cli import predict

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--sales",required=True,type=Path)
    p.add_argument("--stock",required=True,type=Path)
    p.add_argument("--model",type=Path,default=Path(__file__).resolve().parents[1]/"model")
    p.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[1]/"submission.csv")
    a=p.parse_args()
    try:
        a.model_dir, a.config, a.strategy = a.model, None, None
        predict(a)
    except (OSError,ValueError,KeyError) as exc:
        p.exit(2,f'Ошибка прогнозирования: {exc}\n')
