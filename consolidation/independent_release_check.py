"""Bounded executable QA: hashes, archive preservation, clean environments and CLI."""
from pathlib import Path
import csv
import hashlib
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "consolidation/independent_review_evidence"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run():
    OUT.mkdir(exist_ok=True)
    baseline = json.loads((ROOT / "consolidation/pre_merge_manifest.json").read_text(encoding="utf-8"))
    checks = {}
    names = {f"src/{name}.py" for name in ("data", "features", "baselines", "predict", "submission", "artifacts")}
    names |= {"scripts/official_score.py"}
    protected = []
    for raw, row in baseline["files"].items():
        name = raw.replace("\\", "/")
        if (name in names or name.startswith("model/") or name.endswith(".npz")
                or name.startswith("cache/") or ("/" not in name and name.endswith(".zip"))):
            path = ROOT / raw
            actual = digest(path) if path.is_file() else None
            assert actual == row["sha256"], raw
            protected.append({"path": name, "sha256": actual})
    checks["protected_files"] = {"verified": len(protected), "npz": sum(r["path"].endswith(".npz") for r in protected)}
    (OUT / "protected_files.json").write_text(json.dumps(protected, indent=2), encoding="utf-8")
    ledger = list(csv.DictReader((ROOT / "consolidation/deleted_files_and_reasons.csv").open(encoding="utf-8")))
    with zipfile.ZipFile(ROOT / "consolidation/legacy_source.zip") as archive, \
            zipfile.ZipFile(ROOT / "consolidation/pre_merge_snapshot.zip") as snapshot:
        for row in ledger:
            original = archive if row["path"] in archive.namelist() else snapshot
            assert hashlib.sha256(original.read(row["path"])).hexdigest() == row["original_sha256"]
            assert baseline["files"][str(Path(row["path"]))]["sha256"] == row["original_sha256"]
            if row["action"] == "archive_remove":
                assert not (ROOT / row["path"]).exists()
    checks["cleanup"] = {"archived_originals_verified": len(ledger),
                         "physically_removed": sum(r["action"] == "archive_remove" for r in ledger)}
    with zipfile.ZipFile(ROOT / "consolidation/pre_merge_snapshot.zip") as archive:
        snapshot_names = [name for name in archive.namelist() if not name.endswith("/")]
        assert len(snapshot_names) == baseline["snapshot_members"]
        for name in sorted(names):
            assert hashlib.sha256(archive.read(name)).hexdigest() == baseline["files"][str(Path(name))]["sha256"]
    checks["snapshot"] = {"members": len(snapshot_names), "source_members_verified": len(names)}
    rollback = json.loads((ROOT / "consolidation/rollback_verification.json").read_text(encoding="utf-8"))
    extracted = Path(rollback["extracted_directory"])
    for name in snapshot_names:
        assert (extracted / name).is_file(), name
    checks["rollback_evidence"] = {"extracted_members_present": len(snapshot_names), "recorded_replay": rollback["replay"]}
    for environment in (".venv_runtime", ".venv_consolidated"):
        python = ROOT / environment / "Scripts/python.exe"
        result = subprocess.run([str(python), "-m", "pip", "check"], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        checks[environment + "_pip_check"] = result.stdout.strip()
    dev = ROOT / ".venv_consolidated/Scripts/python.exe"
    for tool, args in (("ruff", ["check", "src", "app", "--output-format", "json"]),
                       ("deptry", [".", "--json-output", str(OUT / "deptry.json")])):
        result = subprocess.run([str(dev), "-m", tool, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        (OUT / (tool + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
        assert result.returncode == 0, tool
        checks[tool] = "passed canonical src/app scope; see pyproject.toml"
    runtime_python = ROOT / ".venv_runtime/Scripts/python.exe"
    submission = OUT / "submission.csv"
    command = [str(runtime_python), "-X", "utf8", "-m", "src.cli", "predict", "--model-dir", str(ROOT / "model"),
               "--sales", str(ROOT / "integration/release/experimental180/sales.csv"),
               "--stock", str(ROOT / "integration/release/experimental180/stock.csv"), "--output", str(submission)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    (OUT / "real_cli.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    reference = ROOT / "consolidation/regression/nonton-v1.csv"
    assert submission.read_bytes() == reference.read_bytes().replace(b"\r\n", b"\n")
    checks["real_cli"] = {"rows": json.loads(result.stdout)["rows"],
                          "reference_byte_identical": False, "reference_normalized_lf_byte_identical": True,
                          "sha256": digest(submission), "reference_sha256": digest(reference),
                          "environment": ".venv_runtime", "serialization_change": "CRLF to explicit LF only"}
    (OUT / "checks.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(checks, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
