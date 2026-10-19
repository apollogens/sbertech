from pathlib import Path
import hashlib,json,zipfile
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[2];O=R/'integration/release'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
m=json.loads((O/'preservation_manifest.json').read_text(encoding='utf-8'));changed=[x['path'] for x in m['files'] if not (R/x['path']).is_file() or sha(R/x['path'])!=x['sha256']]
npz_changed=[x['path'] for x in m['npz'] if sha(R/x['path'])!=x['sha256']]
zips_changed=[x['path'] for x in m['old_zip'] if sha(R/x['path'])!=x['sha256']]
old=json.loads((R/'reports/remediation/delivery_manifest.json').read_text(encoding='utf-8'))
delivery_bad=[x['path'] for x in old['files'] if sha(R/x['path'])!=x['sha256']]
delivery={'files':len(old['files']),'changed':delivery_bad,'zip_matches':sha(R/old['archive'])==old['archive_sha256']}
(O/'old_delivery_check.json').write_text(json.dumps(delivery,indent=2))
assert not delivery_bad and delivery['zip_matches']
f=pd.read_csv(O/'submission.csv',dtype={'date':str,'warehouse_name':str,'article':str});catalog=json.loads((R/'model/catalogs.json').read_text())
assert list(f)==['date','warehouse_name','article','quantity'];assert len(f)==562496;assert not f.duplicated(['date','warehouse_name','article']).any()
dates=sorted(f.date.unique());assert len(dates)==64;assert list(pd.date_range(dates[0],periods=64).strftime('%Y-%m-%d'))==dates
keys=pd.MultiIndex.from_product([dates,catalog['warehouses'],catalog['articles']],names=list(f)[:3]);assert keys.equals(pd.MultiIndex.from_frame(f.iloc[:,:3]));assert np.isfinite(f.quantity).all() and (f.quantity>=0).all()
result={'preserved_files':len(m['files']),'changed_files':changed,'npz_files':len(m['npz']),'changed_npz':npz_changed,'changed_old_zip':zips_changed,'snapshot_sha256_valid':sha(O/'pre_integration_snapshot.zip')==m['snapshot_sha256'],'submission_independent_validation':'passed','submission_rows':len(f),'submission_first_date':dates[0],'submission_last_date':dates[-1],'submission_sha256':sha(O/'submission.csv')}
(O/'artifact_check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));assert not changed and not npz_changed and not zips_changed
