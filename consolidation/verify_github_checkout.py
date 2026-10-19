"""Verify published main from a fresh clone with selective LFS artifacts."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "https://github.com/apollogens/sbertech.git"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def forecast_evidence(destination):
    inputs = ROOT / "integration/release/experimental180"
    input_hashes = {name: digest(inputs / (name + ".csv")) for name in ("sales", "stock")}
    evidence = {}
    for label, reference_name in (("incumbent", "nonton-v1"), ("ensemble", "equal4")):
        output = destination / f"github_verified_{label}.csv"
        reference = (ROOT / "consolidation/regression" / f"{reference_name}.csv").read_bytes().replace(b"\r\n", b"\n")
        actual = output.read_bytes()
        if actual != reference:
            raise ValueError(f"Published {label} forecast differs from reference")
        rows = len(actual.splitlines()) - 1
        if rows != 562496:
            raise ValueError("Published forecast grid row count mismatch")
        evidence[label] = dict(rows=rows, output_sha256=hashlib.sha256(actual).hexdigest(),
                               reference_lf_sha256=hashlib.sha256(reference).hexdigest(),
                               input_sales_sha256=input_hashes["sales"], input_stock_sha256=input_hashes["stock"])
    return evidence


def run():
    destination = Path(tempfile.mkdtemp(prefix="nonton-github-verification-"))
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never", GIT_LFS_SKIP_SMUDGE="1")
    for name in ("PYTHONPATH", "MODEL_DIR", "FORECAST_CONFIG", "FORECAST_STRATEGY"):
        env.pop(name, None)
    operations = []

    def execute(command, label, cwd=destination):
        started = time.perf_counter()
        completed = subprocess.run(command, cwd=cwd, env=env, text=True, encoding="utf-8", errors="replace",
                                   capture_output=True, timeout=900)
        log = ROOT / ".git" / f"github-verification-{label}.log"
        log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise RuntimeError(f"Published clone verification failed at {label}; see {log}")
        operations.append(dict(label=label, elapsed_seconds=time.perf_counter() - started, exit_code=0))
        return completed.stdout

    execute(["git", "clone", "--depth", "1", "--branch", "main", REMOTE, str(destination)], "clone", ROOT)
    revision = execute(["git", "rev-parse", "HEAD"], "revision").strip()
    remote_revision = execute(["git", "ls-remote", "--heads", "origin", "main"], "remote").split()[0]
    expected_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if revision != remote_revision or revision != expected_revision:
        raise ValueError("Published checkout differs from the intended local revision")
    env.pop("GIT_LFS_SKIP_SMUDGE", None)
    selected = "bundles/equal4-rc1/*.txt,reports/remediation/original_release.zip,consolidation/nonton_consolidated_verified.zip"
    execute(["git", "lfs", "pull", "--include=" + selected, "--exclude="], "lfs")
    names = [path.relative_to(ROOT).as_posix() for folder in ("src", "app")
             for path in (ROOT / folder).glob("*.py")]
    assert all((ROOT / name).read_bytes() == (destination / name).read_bytes() for name in names)
    archive = destination / "consolidation/nonton_consolidated_verified.zip"
    with archive.open("rb") as stream:
        archive_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    expected = json.loads((ROOT / "consolidation/release_package.json").read_text(encoding="utf-8"))
    assert archive_sha == expected["archive_sha256"]
    tests = execute([sys.executable, "-X", "utf8", "-m", "src.cli", "test", "--",
                     "tests", "reports/qa/check_backend_independent.py", "-q"], "tests")
    assert "222 passed" in tests
    program = ("from pathlib import Path; from src.runtime import load_bundle; import src.runtime; "
               "assert Path(src.runtime.__file__).is_relative_to(Path.cwd()); "
               "a=load_bundle('model'); b=load_bundle('bundles/equal4-rc1',strategy='equal4:P1'); "
               "assert len(b['models'])==3; print(a['manifest']['bundle_id'],b['manifest']['bundle_id'])")
    models = execute([sys.executable, "-X", "utf8", "-c", program], "models").strip()
    inputs = ROOT / "integration/release/experimental180"
    for label, options in (("incumbent", []), ("ensemble", ["--model-dir", "bundles/equal4-rc1", "--strategy", "equal4:P1"])):
        output = destination / f"github_verified_{label}.csv"
        execute([sys.executable, "-X", "utf8", "-m", "src.cli", "predict", *options,
                 "--sales", str(inputs / "sales.csv"), "--stock", str(inputs / "stock.csv"),
                 "--output", str(output)], label)
        reference = ROOT / ("consolidation/regression/nonton-v1.csv" if label == "incumbent" else "consolidation/regression/equal4.csv")
        assert output.read_bytes() == reference.read_bytes().replace(b"\r\n", b"\n")
    result = dict(status="passed", remote=REMOTE, branch="main", verified_commit=revision,
                  checkout=str(destination), selective_lfs_include=selected,
                  source_files_byte_identical=len(names), tests="222 passed", model_bundle_ids=models.split(),
                  remote_archive_sha256=archive_sha, actual_forecasts_lf_normalized_byte_identical=True,
                  forecasts=forecast_evidence(destination),
                  operations=operations,
                  scope="Fresh remote checkout; existing verified dev interpreter; private CSV supplied from original workspace, not repository. Full historical LFS corpus was not downloaded again.")
    (ROOT / "consolidation/github_publication_verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    run()
