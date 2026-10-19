"""Executed INSIDE --network none container; HTTP data submitted over loopback."""
import http.client
import json
from pathlib import Path
from time import perf_counter,sleep


def connection():
    return http.client.HTTPConnection("127.0.0.1",8000,timeout=3600)


for attempt in range(60):
    try:
        conn=connection(); conn.request("GET","/health"); response=conn.getresponse()
        assert response.status==200
        health=json.loads(response.read());conn.close();break
    except (OSError,AssertionError):
        if attempt==59:raise
        sleep(.5)

boundary="NontonDeterministicBoundary20261018"
parts=[]
for field in ["sales","stock"]:
    path=Path(f"/tmp/{field}.csv")
    header=(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{field}.csv\"\r\nContent-Type: text/csv\r\n\r\n").encode()
    parts.append((header,path))
ending=f"--{boundary}--\r\n".encode()
length=sum(len(header)+path.stat().st_size+2 for header,path in parts)+len(ending)
conn=connection();conn.putrequest("POST","/predict")
conn.putheader("Content-Type",f"multipart/form-data; boundary={boundary}")
conn.putheader("Content-Length",str(length));conn.endheaders()
t=perf_counter()
for header,path in parts:
    conn.send(header)
    with path.open("rb") as stream:
        while chunk:=stream.read(1024*1024):conn.send(chunk)
    conn.send(b"\r\n")
conn.send(ending);response=conn.getresponse()
assert response.status==200,(response.status,response.read()[:500])
with Path("/tmp/container_forecast.csv").open("wb") as stream:
    while chunk:=response.read(1024*1024):stream.write(chunk)
post_time=perf_counter()-t;conn.close()
conn=connection();conn.request("GET","/predict?article=char_article_0&warehouse=warehouse_name_0")
response=conn.getresponse();assert response.status==200
assert len(response.read().splitlines())==65
conn.close()
memory_peak=Path("/sys/fs/cgroup/memory.peak")
result={"health":health,"post_seconds":post_time,"network_mode":"none",
        "cgroup_memory_peak_bytes":int(memory_peak.read_text()) if memory_peak.exists() else None,
        "status":"passed"}
Path("/tmp/container_benchmark.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
