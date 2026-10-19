"""Issue a new runtime identity after reviewed source changes; never change weights."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.artifacts import file_hash, fingerprint
from src.runtime import dependency_versions, runtime_source_hashes, verify_runtime_bundle


def seal(path):
    path = Path(path)
    target = path / "runtime_manifest.json"
    previous = json.loads(target.read_text(encoding="utf-8"))
    identity = previous.pop("bundle_id")
    if fingerprint(previous) != identity:
        raise ValueError("Previous bundle identity is corrupt")
    for name, digest in previous["files"].items():
        if file_hash(path / name) != digest:
            raise ValueError("Artifact changed; source-only resealing forbidden")
    if previous["dependencies"] != dependency_versions():
        raise ValueError("Dependency changes require separate validation")
    sources = runtime_source_hashes()
    if sources == previous["runtime_sources"]:
        return identity
    history = ROOT / "consolidation/runtime_manifest_history"
    history.mkdir(exist_ok=True)
    copy = history / f"{identity}.json"
    if not copy.exists():
        copy.write_bytes(target.read_bytes())
    previous["previous_runtime_bundle_id"] = identity
    previous["runtime_sources"] = sources
    previous["bundle_id"] = fingerprint(previous)
    target.write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding="utf-8")
    verify_runtime_bundle(path)
    return previous["bundle_id"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", nargs="?", default=str(ROOT / "bundles/equal4-rc1"))
    print(seal(parser.parse_args().bundle))
