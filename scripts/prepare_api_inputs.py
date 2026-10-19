"""Explicit source repair; original CSVs stay untouched."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data import read_inputs, clean_stock

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--sales", default=r"C:\Users\apollo\Desktop\выборка\sales_dataset_hakaton_train.csv")
    p.add_argument("--stock", default=r"C:\Users\apollo\Desktop\выборка\stock_dataset_hakaton_train.csv")
    p.add_argument("--output-dir", default="data/api_clean")
    args = p.parse_args()
    sales, stock = read_inputs(args.sales, args.stock)
    cleaned = clean_stock(stock)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    sales.to_csv(out / "sales.csv", index=False)
    cleaned.to_csv(out / "stock.csv", index=False)
    print(f"sales={len(sales)} stock_raw={len(stock)} stock_clean={len(cleaned)}")
