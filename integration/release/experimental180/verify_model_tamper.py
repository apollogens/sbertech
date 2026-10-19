from pathlib import Path
import hashlib,json,shutil,sys,tempfile
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from integration.corrected_models import load_experimental_bundle
OUT=ROOT/'integration/release/experimental180';BUNDLE=ROOT/'integration/models/final_experimental'
with tempfile.TemporaryDirectory(prefix='model-tamper-',dir=OUT) as directory:
 copy=Path(directory)
 assert copy.resolve().is_relative_to(OUT.resolve())
 for p in BUNDLE.iterdir():
  if p.is_file():shutil.copy2(p,copy/p.name)
 target=copy/'daily.txt'
 with target.open('r+b') as stream:
  stream.seek(-1,2);old=stream.read(1);stream.seek(-1,2);stream.write(b'X' if old!=b'X' else b'Y')
 try:load_experimental_bundle(copy)
 except ValueError as error:result={'status':'passed','tampered_model_rejected':str(error),'mutation':'One final byte of copied daily.txt changed; originals untouched'}
 else:raise AssertionError('Tampered model accepted')
(OUT/'model_tamper.json').write_text(json.dumps(result,indent=2));print(result)
