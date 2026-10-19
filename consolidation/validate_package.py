"""Extract release into a fresh directory, test it and run both actual bundles."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "consolidation"


def run():
    archive = OUT / "nonton_consolidated_verified.zip"
    receipt = json.loads((OUT / "release_package.json").read_text(encoding="utf-8"))
    assert hashlib.file_digest(archive.open("rb"), "sha256").hexdigest() == receipt["archive_sha256"]
    destination = OUT / "package_extracted_verified"
    if destination.exists():
        raise ValueError("Use a fresh extraction directory")
    destination.mkdir()
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if not (destination / name).resolve().is_relative_to(destination.resolve()):
                raise ValueError("Unsafe archive path")
        bundle.extractall(destination)
    manifest = json.loads((destination / "consolidation/release_manifest.json").read_text(encoding="utf-8"))
    for name, record in manifest["files"].items():
        with (destination / name).open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == record["sha256"], name
    env = dict(os.environ)
    for name in ("PYTHONPATH", "FORECAST_CONFIG", "MODEL_DIR", "FORECAST_STRATEGY"):
        env.pop(name, None)
    (destination / "consolidation/package_checks").mkdir()
    result = dict(status="passed", archive_sha256=receipt["archive_sha256"],
                  extraction=str(destination), files_verified=len(manifest["files"]), operations=[])

    def execute(arguments, label):
        started = time.perf_counter()
        command = [sys.executable, "-X", "utf8", *arguments]
        completed = subprocess.run(command, cwd=destination, env=env, capture_output=True,
                                   text=True, encoding="utf-8", timeout=600)
        (OUT / f"package_validation_{label}.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise RuntimeError(f"Extracted release {label} failed: {completed.stderr[-1500:]}")
        result["operations"].append(dict(label=label, returncode=completed.returncode,
                                         elapsed_seconds=time.perf_counter() - started,
                                         output_tail=completed.stdout[-250:]))

    execute(["-c", "import src.runtime,app.main,pathlib; root=pathlib.Path.cwd(); assert pathlib.Path(src.runtime.__file__).is_relative_to(root); assert pathlib.Path(app.main.__file__).is_relative_to(root); print(root)"], "import_isolation")
    execute(["-m", "src.cli", "test", "--", "-q", "tests", "reports/qa/check_backend_independent.py"], "tests")
    inputs = ROOT / "integration/release/experimental180"
    for label, args in (("nonton-v1", []), ("equal4", ["--model-dir", "bundles/equal4-rc1", "--strategy", "equal4:P1"])):
        output = destination / "consolidation/package_checks" / f"{label}.csv"
        execute(["-m", "src.cli", "predict", *args, "--sales", str(inputs / "sales.csv"),
                 "--stock", str(inputs / "stock.csv"), "--output", str(output)], label)
        reference = (ROOT / "consolidation/regression" / f"{label}.csv").read_bytes().replace(b"\r\n", b"\n")
        assert output.read_bytes() == reference, f"{label} extracted forecast differs after newline normalization"
    result["forecast_csv_lf_normalized_byte_identical"] = True
    (OUT / "package_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    run()
