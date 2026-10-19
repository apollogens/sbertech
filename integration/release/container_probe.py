"""Loopback HTTP acceptance inside a network-isolated release container."""
from pathlib import Path
import hashlib,http.client,json,time,sys
OUT=Path('/tmp/release')
def conn():return http.client.HTTPConnection('127.0.0.1',8000,timeout=3600)
def get(url):
 c=conn();t=time.perf_counter();c.request('GET',url);r=c.getresponse();data=r.read();elapsed=time.perf_counter()-t;c.close();return r.status,data,elapsed
for i in range(120):
 try:
  status,data,_=get('/health')
  if status==200:break
 except OSError:pass
 time.sleep(.5)
else:raise RuntimeError('No health')
if '--restart' in sys.argv:
 assert get('/predict/all')[0]==409
 (OUT/'restart.json').write_text(json.dumps({'health':json.loads(data),'empty_cache_after_restart':True,'status':'passed'},indent=2));sys.exit()
assert get('/predict/all')[0]==409
boundary='NontonIntegrationBoundary';parts=[]
for field in ['sales','stock']:
 p=Path('/tmp')/(field+'.csv');header=(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{field}.csv"\r\nContent-Type: text/csv\r\n\r\n').encode();parts.append((header,p))
end=f'--{boundary}--\r\n'.encode();length=sum(len(h)+p.stat().st_size+2 for h,p in parts)+len(end)
c=conn();t=time.perf_counter();c.putrequest('POST','/predict');c.putheader('Content-Type',f'multipart/form-data; boundary={boundary}');c.putheader('Content-Length',str(length));c.endheaders()
for h,p in parts:
 c.send(h)
 with p.open('rb') as f:
  while chunk:=f.read(1048576):c.send(chunk)
 c.send(b'\r\n')
c.send(end);r=c.getresponse();assert r.status==200,(r.status,r.read()[:500]);raw=r.read();post=time.perf_counter()-t;c.close();(OUT/'container_forecast.csv').write_bytes(raw)
status,cached,get_s=get('/predict/all');assert status==200 and raw==cached
status,pair,pair_s=get('/predict?article=char_article_0&warehouse=warehouse_name_0');assert status==200 and len(pair.splitlines())==65
status,js,json_s=get('/predict/all?format=json');assert status==200 and len(json.loads(js))==562496
import pandas as pd,numpy as np
actual=pd.read_csv(OUT/'container_forecast.csv');expected=pd.read_csv(OUT/'submission.csv');assert actual.iloc[:,:3].equals(expected.iloc[:,:3]);diff=float(np.max(np.abs(actual.quantity-expected.quantity)));assert diff<=1e-7
peak=Path('/sys/fs/cgroup/memory.peak');result={'status':'passed','rows':len(actual),'health':json.loads(data),'post_seconds':post,'get_csv_seconds':get_s,'get_filtered_seconds':pair_s,'get_json_seconds':json_s,'offline_container_max_abs_difference':diff,'container_csv_sha256':hashlib.sha256(raw).hexdigest(),'cgroup_memory_peak_bytes':int(peak.read_text()),'cpu_max':Path('/sys/fs/cgroup/cpu.max').read_text().strip(),'memory_max':Path('/sys/fs/cgroup/memory.max').read_text().strip(),'network_mode':'none'}
(OUT/'container_benchmark.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
