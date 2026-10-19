"""Create a verified standalone source/runtime archive; retain rollback separately."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "consolidation"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def candidates():
    names = set()
    for folder in ("src", "app", "config", "model", "bundles/equal4-rc1", "tests", "scripts"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                names.add(path.relative_to(ROOT).as_posix())
    for pattern in ("requirements*.txt", "requirements*.lock"):
        names.update(path.name for path in ROOT.glob(pattern))
    names.update(["README.md", "Dockerfile", ".dockerignore", ".gitignore", "pyproject.toml",
                  "reports/qa/check_backend_independent.py", "reports/remediation/original_release.zip",
                  "reports/selection_frozen.json"])
    for path in OUT.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".ps1", ".md", ".json", ".csv", ".log", ".npz"}:
            continue
        relative = path.relative_to(OUT)
        if any(part.startswith(("rollback_", "runtime_manifest_history", "extracted", "package_extracted", "release_extracted"))
               for part in relative.parts[:-1]):
            continue
        if path.name in {"release_manifest.json", "release_package.json", "package_validation.json",
                         "package_build.log", "package_validation.log", "independent_package_review.json"}:
            continue
        if path.suffix == ".csv" and path.stat().st_size > 5_000_000 and path.name != "submission.csv":
            continue
        names.add(path.relative_to(ROOT).as_posix())
    names.add("consolidation/legacy_source.zip")
    return sorted(names)


def run():
    paths = candidates()
    files = {name: dict(sha256=sha(ROOT / name), bytes=(ROOT / name).stat().st_size) for name in paths}
    manifest = dict(release="nonton-consolidated-v1", active_bundle="model", active_strategy="nonton-v1",
                    selectable_bundle="bundles/equal4-rc1", selectable_strategy="equal4:P1",
                    files=files, rollback=dict(archive="pre_merge_snapshot.zip", manifest="pre_merge_manifest.json",
                    sha256=json.loads((OUT / "pre_merge_manifest.json").read_text(encoding="utf-8"))["snapshot_sha256"],
                    packaging="Separate immutable rollback archive; not embedded in runtime release"),
                    excluded="Raw datasets, cache, envs, external checkouts, large historical weights/ZIPs and generated extraction folders remain outside this runtime/source package.")
    target = OUT / "release_manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    paths.append("consolidation/release_manifest.json")
    archive = OUT / "nonton_consolidated_verified.zip"
    temporary = OUT / "nonton_consolidated_verified.zip.tmp"
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name in paths:
            bundle.write(ROOT / name, name)
    with zipfile.ZipFile(temporary) as bundle:
        assert bundle.testzip() is None
        for name, record in files.items():
            with bundle.open(name) as stream:
                assert hashlib.file_digest(stream, "sha256").hexdigest() == record["sha256"], name
        assert bundle.read("consolidation/release_manifest.json") == target.read_bytes()
    temporary.replace(archive)
    result = dict(status="passed", archive=str(archive), archive_sha256=sha(archive), archive_bytes=archive.stat().st_size,
                  members=len(paths), manifest_sha256=sha(target), all_members_verified=True)
    (OUT / "release_package.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    run()
