"""Immutable pre-consolidation snapshot and streaming SHA-256 inventory."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'consolidation'
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):digest.update(block)
    return digest.hexdigest()
def run():
    OUT.mkdir(exist_ok=True);manifest=OUT/'pre_merge_manifest.json';archive=OUT/'pre_merge_snapshot.zip'
    if manifest.exists() or archive.exists():raise RuntimeError('Pre-merge snapshot already exists; do not overwrite')
    records={};saved=[];skip={'.git','.venv','.venv_stats','.venv_consolidated','__pycache__','.pytest_cache','consolidation','data'}
    for directory,dirs,names in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in skip and not d.startswith('extracted_experimental_')]
        for name in names:
            path=Path(directory)/name;relative=path.relative_to(ROOT)
            if path.suffix=='.pyc':continue
            # Preserve all source, model, metadata and scientific arrays; large generated CSV/ZIP stay immutable in place.
            keep=path.suffix in {'.py','.md','.json','.txt','.lock','.toml','.ps1','.npz','.csv','.zip'} or len(relative.parts)==1
            if not keep:continue
            records[str(relative)]={'bytes':path.stat().st_size,'sha256':sha(path)}
            if path.suffix!='.zip' and (path.suffix!='.csv' or path.stat().st_size<5_000_000 or len(relative.parts)==1):saved.append(path)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in saved:z.write(path,str(path.relative_to(ROOT)))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    result=dict(snapshot=str(archive),snapshot_sha256=sha(archive),snapshot_members=len(saved),files=records,
                git_status=subprocess.run(['git','status','--short'],cwd=ROOT,capture_output=True,text=True).stdout,
                git_revision=subprocess.run(['git','rev-parse','--verify','HEAD'],cwd=ROOT,capture_output=True,text=True).stdout.strip() or None,
                python=sys.version,note='Large existing generated CSV/ZIP and raw data remain in place; existing immutable archives provide older releases. No raw input is deleted.')
    manifest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(snapshot_members=len(saved),inventoried=len(records),snapshot_sha256=result['snapshot_sha256'])))
if __name__=='__main__':run()
