"""Verify the immutable parent, then issue a separate runtime-v2 model bundle."""
from pathlib import Path
import argparse
import json
import shutil
import sys
import zipfile
import hashlib
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.artifacts import file_hash, fingerprint
from src.runtime import STRATEGIES, dependency_versions, runtime_source_hashes

def migrate(source, destination):
    source, destination = Path(source), Path(destination)
    parent = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in parent["files"].items():
        if name not in {"config.json", "daily.txt", "weekly.txt", "article.txt"} or file_hash(source/name) != digest:
            raise ValueError("Parent artifact hash mismatch")
    for name, digest in parent["source_hashes"].items():
        current = ROOT / name
        if current.exists() and file_hash(current) == digest:
            continue
        # Historical implementations are immutable evidence, not a second serving runtime.
        with zipfile.ZipFile(ROOT / "consolidation/pre_merge_snapshot.zip") as frozen:
            if hashlib.sha256(frozen.read(name)).hexdigest() != digest:
                raise ValueError("Parent archived source provenance mismatch before migration")
    old = json.loads((source / "config.json").read_text(encoding="utf-8"))
    if destination.exists():
        raise ValueError("Destination exists; use a new versioned bundle directory")
    destination.mkdir(parents=True)
    for name in ("daily", "weekly", "article"):
        shutil.copyfile(source/f"{name}.txt", destination/f"{name}.txt")
    config = dict(schema_version=2, model_version="nonton-equal4-rc1", kind="components", horizon=64,
                  strategy="equal4:P1", strategies=STRATEGIES, postprocessing="threshold025",
                  catalogs=old["catalogs"], features=old["metadata"]["features"],
                  history_policy=dict(mode="provided", minimum_days=180),
                  category_encodings=old["ensemble_contract"]["category_encodings"],
                  training_metadata=old["metadata"], numerical_contract="nonton-integration-v1-asof-sha20")
    (destination/"config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = dict(runtime_contract_version=2,
                    files={p.name:file_hash(p) for p in sorted(destination.iterdir())},
                    runtime_sources=runtime_source_hashes(), dependencies=dependency_versions(),
                    catalog_sha256=fingerprint(config["catalogs"]),
                    parent=dict(path=str(source.relative_to(ROOT)),manifest_sha256=file_hash(source/"manifest.json"),
                                config_sha256=file_hash(source/"config.json"), migration="Weights unchanged; runtime extraction; no retraining"))
    manifest["bundle_id"] = fingerprint(manifest)
    (destination/"runtime_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest

if __name__ == "__main__":
    p = argparse.ArgumentParser();p.add_argument("--source",default=str(ROOT/"integration/models/final_experimental"))
    p.add_argument("--output",default=str(ROOT/"bundles/equal4-rc1"));args = p.parse_args()
    print(json.dumps(migrate(args.source,args.output)))
