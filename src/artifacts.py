"""Версионированный локальный контракт артефактов; SHA-256 не доказывает происхождение."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform

CONTRACT_VERSION = 1
SOURCE_FILES = ("data.py", "features.py", "baselines.py", "predict.py", "submission.py", "artifacts.py")
CANONICALIZATION = "UTF-8 JSON; sort_keys=true; separators=(',',':'); ensure_ascii=false; allow_nan=false; list order preserved"


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def contract_metadata(config, catalogs):
    """Порядок списков сохраняется; category ID равен позиции в списке."""
    versions = {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "lightgbm")}
    versions["python"] = ".".join(platform.python_version().split(".")[:2])
    return {
        "model_format": "lightgbm-text-v4" if config["kind"] == "lightgbm" else "baseline-json-v1",
        "feature_schema": [{"name": name, "dtype": "float32"} for name in config.get("features", [])],
        "category_mapping": {key: [{"identifier": value, "id": i} for i, value in enumerate(catalogs[key])]
                             for key in ("warehouses", "articles")},
        "inference_config": config,
        "preprocessing": {name: file_hash(Path(__file__).parent / name) for name in SOURCE_FILES},
        "dependencies": versions,
    }


def write_manifest(directory, *, provenance=None):
    """Связывает текущие байты. По умолчанию историческое происхождение НЕ подтверждено."""
    directory = Path(directory)
    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    catalogs = json.loads((directory / "catalogs.json").read_text(encoding="utf-8"))
    files = ["config.json", "catalogs.json"] + (["lightgbm.txt"] if config["kind"] == "lightgbm" else [])
    if provenance and provenance.get("status") == "training_recorded":
        files.append("training_record.json")
    metadata = contract_metadata(config, catalogs)
    manifest = {
        "artifact_contract_version": CONTRACT_VERSION,
        "hash_algorithm": "sha256",
        "canonicalization": CANONICALIZATION,
        "files": {name: file_hash(directory / name) for name in files},
        "metadata": metadata,
        "metadata_sha256": fingerprint(metadata),
        "provenance": provenance or {"status": "reconstructed_unverified", "training_run_id": None,
            "limitation": "Хэши фиксируют текущий комплект; исходная связь весов с обучающими данными и кодировками не доказана."},
    }
    manifest["bundle_id"] = fingerprint(manifest)
    temporary = directory / "manifest.json.tmp"
    temporary.write_bytes(canonical_bytes(manifest) + b"\n")
    temporary.replace(directory / "manifest.json")
    return manifest


def write_training_manifest(directory, record):
    """Записывает журнал непосредственно выполненного обучения и связывает с весами."""
    directory = Path(directory)
    if (not record.get("training_run_id") or not record.get("training_data_sha256")
            or record.get("model_sha256") != file_hash(directory / "lightgbm.txt")):
        raise ValueError("Missing or incompatible training run evidence")
    (directory / "training_record.json").write_bytes(canonical_bytes(record) + b"\n")
    return write_manifest(directory, provenance={"status": "training_recorded",
        "training_run_id": record["training_run_id"], "training_data_sha256": record["training_data_sha256"],
        "training_record_file": "training_record.json"})


def verify_manifest(directory, config, catalogs):
    directory = Path(directory)
    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Missing or invalid artifact manifest") from exc
    if (manifest.get("artifact_contract_version") != CONTRACT_VERSION or manifest.get("hash_algorithm") != "sha256"
            or manifest.get("canonicalization") != CANONICALIZATION):
        raise ValueError("Unsupported artifact contract version or hash algorithm")
    identity = dict(manifest)
    bundle_id = identity.pop("bundle_id", None)
    if bundle_id != fingerprint(identity):
        raise ValueError("Artifact manifest identity mismatch")
    provenance = manifest.get("provenance", {})
    if provenance.get("status") not in ("reconstructed_unverified", "training_recorded"):
        raise ValueError("Missing or invalid artifact provenance metadata")
    expected = {"config.json", "catalogs.json"} | ({"lightgbm.txt"} if config["kind"] == "lightgbm" else set())
    if provenance["status"] == "training_recorded":
        if (not provenance.get("training_run_id") or not provenance.get("training_data_sha256")
                or provenance.get("training_record_file") != "training_record.json"):
            raise ValueError("Missing training provenance evidence")
        expected.add("training_record.json")
    if set(manifest.get("files", {})) != expected:
        raise ValueError("Artifact file contract mismatch")
    for name in sorted(expected):
        try:
            actual = file_hash(directory / name)
        except OSError as exc:
            raise ValueError(f"Missing artifact file: {name}") from exc
        if actual != manifest["files"][name]:
            raise ValueError(f"Artifact hash mismatch: {name}")
    metadata = contract_metadata(config, catalogs)
    if manifest.get("metadata") != metadata or manifest.get("metadata_sha256") != fingerprint(metadata):
        raise ValueError("Artifact preprocessing, feature schema, mapping or dependency mismatch")
    if provenance["status"] == "training_recorded":
        record = json.loads((directory / "training_record.json").read_text(encoding="utf-8"))
        if (record.get("training_run_id") != provenance["training_run_id"]
                or record.get("training_data_sha256") != provenance["training_data_sha256"]
                or record.get("model_sha256") != manifest["files"].get("lightgbm.txt")):
            raise ValueError("Training record provenance mismatch")
    return manifest
