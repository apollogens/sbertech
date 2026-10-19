param(
    [string]$ImageName = 'nonton:consolidated-v1',
    [ValidateSet('nonton-v1','equal4')][string]$Strategy = 'nonton-v1'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $PSScriptRoot "docker_$Strategy"
New-Item -ItemType Directory -Force -Path $out | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "regression/$Strategy.csv") -Destination (Join-Path $out 'reference.csv')
$name = 'nonton-consolidated-' + $Strategy + '-' + (Get-Date -Format 'yyyyMMddHHmmss')
docker image inspect $ImageName | Out-File -Encoding utf8 (Join-Path $out 'image.json')
if ($LASTEXITCODE -ne 0) { throw 'Missing Docker image' }
try {
    docker run -d --name $name --network none --cpus 4 --memory 6g --mount "type=bind,source=$out,target=/tmp/release" $ImageName | Out-File (Join-Path $out 'container_id.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Docker run failed' }
    docker cp (Join-Path $root 'integration/release/experimental180/sales.csv') "${name}:/tmp/sales.csv"
    if ($LASTEXITCODE -ne 0) { throw 'Copy sales failed' }
    docker cp (Join-Path $root 'integration/release/experimental180/stock.csv') "${name}:/tmp/stock.csv"
    if ($LASTEXITCODE -ne 0) { throw 'Copy stock failed' }
    docker cp (Join-Path $PSScriptRoot 'http_probe.py') "${name}:/tmp/http_probe.py"
    if ($LASTEXITCODE -ne 0) { throw 'Copy probe failed' }
    docker inspect $name | Out-File -Encoding utf8 (Join-Path $out 'container_inspect.json')
    docker exec $name python /tmp/http_probe.py | Out-File -Encoding utf8 (Join-Path $out 'probe.log')
    if ($LASTEXITCODE -ne 0) { throw 'Real HTTP probe failed' }
    docker exec $name python -m pip check | Out-File -Encoding utf8 (Join-Path $out 'pip_check.log')
    if ($LASTEXITCODE -ne 0) { throw 'Container pip check failed' }
    docker exec $name python -m pip list --format=json | Out-File -Encoding utf8 (Join-Path $out 'packages.json')
    docker restart $name | Out-File -Encoding utf8 (Join-Path $out 'restart.log')
    if ($LASTEXITCODE -ne 0) { throw 'Restart failed' }
    docker exec $name python /tmp/http_probe.py --restart | Out-File -Append -Encoding utf8 (Join-Path $out 'restart.log')
    if ($LASTEXITCODE -ne 0) { throw 'Restart probe failed' }
} finally {
    $ErrorActionPreference = 'Continue'
    docker logs $name 2>&1 | Out-File -Encoding utf8 (Join-Path $out 'container.log')
    docker stop $name | Out-File (Join-Path $out 'stop.log')
}
