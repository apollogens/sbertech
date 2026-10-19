"""Inspect staged publication without printing potential secret values."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run():
    names = [name for name in subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0") if name]
    patterns = [re.compile(pattern) for pattern in (
        rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})",
        rb"AKIA[A-Z0-9]{16}", rb"sk-(?:proj-)?[A-Za-z0-9_-]{35,}",
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    )]
    findings = []
    forbidden = []
    text_suffixes = {".py", ".md", ".txt", ".json", ".toml", ".yaml", ".yml", ".ps1", ".lock"}
    for name in names:
        path = ROOT / name
        parts = Path(name).parts
        if (any(part.startswith(".venv") or part in {"__pycache__", ".git", ".pytest_cache"} for part in parts)
                or name.startswith(("data/", "cache/", "research/sources/"))
                or (len(parts) > 2 and name.startswith(("consolidation/rollback_", "consolidation/package_extracted")))
                or path.name in {"sales.csv", "stock.csv", "sales_dataset_hakaton_train.csv", "stock_dataset_hakaton_train.csv", ".env"}):
            forbidden.append(name)
        if path.suffix in text_suffixes and path.stat().st_size < 10_000_000:
            content = path.read_bytes()
            for pattern in patterns:
                match = pattern.search(content)
                if match:
                    findings.append(dict(path=name, line=content[:match.start()].count(b"\n") + 1))
    entries = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=ROOT).decode().split("\0")
    objects = []
    for entry in entries:
        if entry:
            metadata, name = entry.split("\t", 1)
            mode, oid, stage = metadata.split()
            if mode == "160000" or stage != "0":
                raise ValueError("Unexpected gitlink or unmerged index")
            objects.append((name, oid))
    checked = subprocess.check_output(["git", "cat-file", "--batch-check=%(objectname) %(objectsize)"],
                                      cwd=ROOT, input=("\n".join(oid for _, oid in objects) + "\n").encode()).decode().splitlines()
    oversized = [name for (name, _), line in zip(objects, checked) if int(line.split()[1]) > 100 * 1024**2]
    frozen = ROOT / "consolidation/nonton_consolidated_verified.zip"
    receipt = json.loads((ROOT / "consolidation/release_package.json").read_text(encoding="utf-8"))
    with frozen.open("rb") as stream:
        frozen_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    assert frozen_sha == receipt["archive_sha256"]
    source_names = [name for name in names if name.startswith(("src/", "app/")) and name.endswith(".py")]
    source_diffs = []
    with zipfile.ZipFile(frozen) as archive:
        for name in source_names:
            content = (ROOT / name).read_bytes()
            indexed = subprocess.check_output(["git", "show", ":" + name], cwd=ROOT)
            if content != archive.read(name) or content != indexed:
                source_diffs.append(name)
        assert (ROOT / "tests/test_api.py").read_bytes() == archive.read("tests/test_api.py")
    result = dict(status="passed" if not any((findings, forbidden, oversized, source_diffs)) else "failed",
                  staged_files=len(names), secret_pattern_findings=findings, forbidden_staged_paths=forbidden,
                  normal_git_blobs_over_100mib=oversized, changed_runtime_sources=source_diffs,
                  frozen_release_sha256=frozen_sha, source_files_byte_identical=len(source_names),
                  secret_scan_scope="High-confidence token/private-key patterns in text files under10MB; not a guarantee against all secrets")
    (ROOT / "consolidation/github_publication_preflight.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    run()
