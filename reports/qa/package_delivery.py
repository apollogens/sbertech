"""Package the audited tree locally, retaining the original delivery untouched."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/qa'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run():
    target=ROOT/'nonton_solution_qa_verified.zip'
    initial=json.loads((OUT/'initial_manifest.json').read_text())
    assert sha(ROOT/'nonton_solution.zip')==initial['nonton_solution.zip']['sha256']
    excluded={'container_forecast.csv','submission_verified.csv','archive_contents.json','delivery_manifest.json'}
    paths=[]
    for folder in ['src','app','scripts','tests','docs','model','reports']:
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in excluded and not p.name.startswith('.coverage'))
    paths += [ROOT/name for name in ['README.md','Dockerfile','.dockerignore','.gitignore','requirements.txt','requirements-dev.txt','requirements.lock','submission.csv','submission_baseline.csv']]
    paths=sorted(set(paths))
    manifest={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths}
    (OUT/'archive_contents.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    paths.append(OUT/'archive_contents.json')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in paths:archive.write(path,path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist())==len(set(archive.namelist()))
        for name,entry in manifest.items():assert hashlib.sha256(archive.read(name)).hexdigest()==entry['sha256'],name
    result={'archive':str(target.relative_to(ROOT)),'bytes':target.stat().st_size,'sha256':sha(target),
            'files':len(paths),'crc_and_content_hashes_verified':True,
            'original_archive_preserved':True,'original_submission_sha256':sha(ROOT/'submission.csv'),
            'verified_submission_sha256':sha(OUT/'submission_verified.csv'),
            'production_model_sha256':sha(ROOT/'model/lightgbm.txt'),
            'source_tree_sha256':json.loads((OUT/'revision.json').read_text())['final_source_tree_sha256'],
            'scope':'Local archive; raw sales/stock, venv, caches and duplicate forecast CSV are excluded. OOF evidence and QA reports are included.'}
    (OUT/'delivery_manifest.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':run()
