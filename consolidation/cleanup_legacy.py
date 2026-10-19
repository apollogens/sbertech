"""Archive proven duplicate adapters and replace historical helpers with shared code."""
from pathlib import Path
import ast
import csv
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MERGED = ["integration/catalog_policy.py", "integration/ensemble_engine.py",
          "integration/corrected_models.py", "scripts/architecture_experiments.py"]
ARCHIVED = ["integration/experimental_predict.py", "integration/package_experimental.py",
            "integration/verify_archive.py", "integration/preserve_release.py",
            "integration/release_probe.py", "integration/docker_verify.ps1"]


def replace_functions(text, replacements):
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    for node in sorted((node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name in replacements), key=lambda node: node.lineno, reverse=True):
        lines[node.lineno - 1:node.end_lineno] = [replacements[node.name]]
    return "".join(lines)


def run():
    archive = ROOT / "consolidation/legacy_source.zip"
    if archive.exists():
        raise RuntimeError("Cleanup already archived; do not overwrite")
    rows = []
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in MERGED + ARCHIVED:
            path = ROOT / name
            rows.append(dict(path=name, action="merge" if name in MERGED else "archive_remove",
                             original_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             reason="Canonical src catalog/ensemble/components/temporal" if name in MERGED
                             else "Superseded by unified CLI, runtime packaging and consolidated HTTP/Docker verification",
                             preserved_in="consolidation/legacy_source.zip and pre_merge_snapshot.zip"))
            bundle.write(path, name)
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        for row in rows:
            assert hashlib.sha256(bundle.read(row["path"])).hexdigest() == row["original_sha256"]
    (ROOT / MERGED[0]).write_text('''"""Historical research defaults; serving uses explicit src.catalog membership."""
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
''', encoding="utf-8")
    (ROOT / MERGED[1]).write_text('''"""Historical import compatibility; all ensemble arithmetic lives in src.ensemble."""
from src.ensemble import (align_components as align_components, convex_combine as convex_combine,
                          postprocess as postprocess, key_hash as key_hash)
''', encoding="utf-8")
    path = ROOT / MERGED[2]
    text = path.read_text(encoding="utf-8")
    text = replace_functions(text, {
        "article_snapshot": '''def article_snapshot(panel, origin, first=None):
    from src.components import article_snapshot as shared_snapshot
    from integration.catalog_policy import _first_observed
    return shared_snapshot(panel, origin, _first_observed() if first is None else first)
''',
        "predict_components": '''def predict_components(panel, origin, models, first_observed=None):
    from src.components import predict_component_frames
    from integration.catalog_policy import _first_observed
    return predict_component_frames(panel, origin, models,
        _first_observed() if first_observed is None else first_observed)
'''})
    text = text.replace("from src.data import Panel\n", "").replace("from src.features import snapshot,horizon_features", "from src.features import horizon_features")
    text = text.replace("from src.submission import forecast_frame\n", "")
    text = text.replace("asof_panel,safe_snapshot,stable_codes,expand_to_output", "safe_snapshot")
    text = text.replace("from scripts.architecture_experiments import BUCKETS,weekly_frame,weekday_weights,allocate_buckets,warehouse_shares", "from src.temporal import BUCKETS,weekly_frame")
    path.write_text(text, encoding="utf-8")
    path = ROOT / MERGED[3]
    text = path.read_text(encoding="utf-8")
    names = ("weekly_frame", "weekday_weights", "allocate_buckets", "warehouse_shares")
    text = replace_functions(text, {name: "" for name in names})
    text = text.replace("BUCKETS = [(start, min(start + 7, 65)) for start in range(1, 65, 7)]",
                        "from src.temporal import BUCKETS, weekly_frame, weekday_weights, allocate_buckets, warehouse_shares")
    path.write_text(text, encoding="utf-8")
    for name in ARCHIVED:
        (ROOT / name).unlink()
    with (ROOT / "consolidation/deleted_files_and_reasons.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = dict(archived_removed=len(ARCHIVED), merged_files=len(MERGED),
                   archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                   archive_bytes=archive.stat().st_size)
    (ROOT / "consolidation/cleanup_result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    run()
