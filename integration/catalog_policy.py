"""Historical research defaults; serving uses explicit src.catalog membership."""
from functools import lru_cache
from pathlib import Path
import pandas as pd
from src.catalog import stable_codes as stable_codes, expand_to_output as expand_to_output
from src.catalog import asof_panel as _asof_panel, safe_snapshot as _safe_snapshot

FIRST_OBSERVED = Path(__file__).parent / "catalog_audit" / "first_observed.csv"

@lru_cache(maxsize=1)
def _first_observed():
    return pd.read_csv(FIRST_OBSERVED, dtype=str)

def asof_panel(panel, origin, first_observed=None):
    return _asof_panel(panel, origin, _first_observed() if first_observed is None else first_observed)

def safe_snapshot(panel, origin, first_observed=None):
    return _safe_snapshot(panel, origin, _first_observed() if first_observed is None else first_observed)
