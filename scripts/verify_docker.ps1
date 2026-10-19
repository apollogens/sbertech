$ErrorActionPreference = 'Stop'
$watch = [Diagnostics.Stopwatch]::StartNew()
docker build --no-cache -t nonton-forecast:verified .
if ($LASTEXITCODE -ne 0) { throw 'Docker build failed' }
$buildSeconds = $watch.Elapsed.TotalSeconds
$imageBytes = docker image inspect nonton-forecast:verified --format '{{.Size}}'
$container = docker run -d --network none --memory=6g --cpus=4 nonton-forecast:verified
if ($LASTEXITCODE -ne 0) { throw 'Docker run failed' }
try {
    docker cp data/parity/sales.csv "${container}:/tmp/sales.csv"
    docker cp data/parity/stock.csv "${container}:/tmp/stock.csv"
    docker cp scripts/container_probe.py "${container}:/tmp/container_probe.py"
    docker exec $container python /tmp/container_probe.py
    if ($LASTEXITCODE -ne 0) { throw 'Container HTTP probe failed' }
    docker cp "${container}:/tmp/container_forecast.csv" reports/container_forecast.csv
    docker cp "${container}:/tmp/container_benchmark.json" reports/container_benchmark.json
    $result = Get-Content reports/container_benchmark.json -Raw | ConvertFrom-Json
    $result | Add-Member -NotePropertyName build_seconds -NotePropertyValue $buildSeconds
    $result | Add-Member -NotePropertyName image_bytes -NotePropertyValue ([long]$imageBytes)
    $result | ConvertTo-Json -Depth 5 | Set-Content reports/container_benchmark.json -Encoding UTF8
} finally {
    docker logs $container
    docker rm -f $container
}
.\.venv\Scripts\python.exe -X utf8 -c "import pandas as pd,numpy as np,json; a=pd.read_csv('data/parity/offline.csv'); b=pd.read_csv('reports/container_forecast.csv'); assert a.iloc[:,:3].equals(b.iloc[:,:3]); d=float(np.max(np.abs(a.quantity-b.quantity))); assert d<=1e-7,d; p='reports/container_benchmark.json'; r=json.load(open(p,encoding='utf-8-sig')); r['max_abs_difference']=d; r['rows']=len(b); json.dump(r,open(p,'w',encoding='utf-8'),indent=2); print(r)"
if ($LASTEXITCODE -ne 0) { throw 'Container parity failed' }
