"""Create a local release archive with a reproducible SHA-256 inventory."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.predict import load_bundle


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'nonton_solution_remediated_verified.zip')
    args=parser.parse_args()
    bundle=load_bundle(ROOT/'model')
    files=[]
    excluded={'delivery_manifest.json','review_archive.json','review_archive_stdout.txt'}
    for folder in ['src','app','model','scripts','tests','docs','reports']:
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix not in {'.zip','.pyc'}
                     and p.name not in excluded and p.name!='.coverage' and p.stat().st_size>0)
    files.extend(ROOT/n for n in ['README.md','Dockerfile','.dockerignore','.gitignore',
                                  'requirements.txt','requirements-dev.txt','requirements.lock',
                                  'submission.csv','submission_baseline.csv'])
    files=sorted(set(files),key=lambda p:p.relative_to(ROOT).as_posix())
    inventory=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in files]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    temporary=args.output.with_suffix(args.output.suffix+'.tmp')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in files:
            archive.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(temporary) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist())==len(inventory)
        for entry in inventory:
            assert hashlib.sha256(archive.read(entry['path'])).hexdigest()==entry['sha256']
            assert digest(ROOT/entry['path'])==entry['sha256'], f"Файл изменился во время упаковки: {entry['path']}"
    temporary.replace(args.output)
    manifest=dict(archive=str(args.output),archive_bytes=args.output.stat().st_size,
                  archive_sha256=digest(args.output),files=inventory,
                  bundle_id=bundle['manifest']['bundle_id'],
                  excluded='Private source CSV, data/cache/venvs/.git, nested ZIP snapshots, binary coverage, empty logs and archive-review sidecars; originals remain on disk',
                  limitation='The archive includes measured outputs and source, but historical reproducibility also needs the original user CSV locally; never uploaded')
    (ROOT/'reports/remediation/delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='files'},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
