"""Extract the immutable baseline into a fresh directory and replay its model."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run():
    manifest = json.loads((ROOT / "consolidation/pre_merge_manifest.json").read_text(encoding="utf-8"))
    archive = ROOT / "consolidation/pre_merge_snapshot.zip"
    assert hashlib.file_digest(archive.open("rb"), "sha256").hexdigest() == manifest["snapshot_sha256"]
    destination = ROOT / "consolidation/rollback_verified_complete"
    if destination.exists():
        raise ValueError("Rollback target already exists; choose a fresh target")
    destination.mkdir()
    count = 0
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError("Unsafe archive path")
            bundle.extract(member, destination)
            if not member.is_dir():
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                record_name = str(Path(member.filename))
                assert digest == manifest["files"][record_name]["sha256"], member.filename
                count += 1
    program = '''
import json,sys
from pathlib import Path
import numpy as np,pandas as pd
from src.predict import load_bundle,predict_64
from src.data import read_inputs
from src.submission import validate_submission
root=Path(sys.argv[1])
sales,stock=read_inputs(root/'integration/release/experimental180/sales.csv',root/'integration/release/experimental180/stock.csv')
bundle=load_bundle('model')
forecast=predict_64(sales,stock,bundle)
validate_submission(forecast,sales.date.max(),bundle['catalogs'])
reference=pd.read_csv(root/'consolidation/regression/nonton-v1.csv',dtype={'date':str,'warehouse_name':str,'article':str})
assert forecast.iloc[:,:3].equals(reference.iloc[:,:3])
diff=float(np.max(np.abs(forecast.quantity-reference.quantity)))
assert diff<1e-12
print(json.dumps({'status':'passed','rows':len(forecast),'max_abs_difference':diff}))
'''
    output = subprocess.check_output([sys.executable, "-X", "utf8", "-c", program, str(ROOT)],
                                     cwd=destination, text=True, encoding="utf-8")
    result = dict(status="passed", extracted_files_verified=count, snapshot_sha256=manifest["snapshot_sha256"],
                  extracted_directory=str(destination), replay=json.loads(output))
    (ROOT / "consolidation/rollback_verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    run()
