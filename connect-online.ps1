$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$gamePython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$tunnelBinary = Join-Path $env:LOCALAPPDATA 'CemITX\tools\cloudflared.exe'
$runtimeFolder = Join-Path $projectRoot 'artifacts'
$connectionFile = Join-Path $runtimeFolder 'online-connection.json'

if (-not (Test-Path -LiteralPath $gamePython)) { throw 'Environnement Python manquant : consultez README.md.' }
if (-not (Test-Path -LiteralPath $tunnelBinary)) { throw "cloudflared manque : $tunnelBinary" }
New-Item -ItemType Directory -Path $runtimeFolder -Force | Out-Null

Push-Location $projectRoot
try {
    $serverReady = $false
    try {
        $gameState = Invoke-RestMethod -Uri 'http://127.0.0.1:5001/api/game' -TimeoutSec 10
        $serverReady = [bool]$gameState.day
    } catch {}
    if (-not $serverReady) {
        $serverProcess = Start-Process -FilePath $gamePython -ArgumentList '-m','waitress','--listen=127.0.0.1:5001','--threads=4','--call','app:create_app' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeFolder 'server-online.stdout.log') -RedirectStandardError (Join-Path $runtimeFolder 'server-online.stderr.log') -PassThru
        $serverProcess.Id | Set-Content -LiteralPath (Join-Path $runtimeFolder 'server-online.pid')
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            if ($serverProcess.HasExited) { throw 'Le serveur Python s’est arrêté. Consultez artifacts/server-online.stderr.log.' }
            try {
                $gameState = Invoke-RestMethod -Uri 'http://127.0.0.1:5001/api/game' -TimeoutSec 5
                if ($gameState.day) { $serverReady = $true; break }
            } catch {}
            Start-Sleep -Milliseconds 500
        }
        if (-not $serverReady) { throw 'Le serveur Python ne répond pas encore. Consultez artifacts/server-online.stderr.log.' }
    }

    $publicOrigin = $null
    if (Test-Path -LiteralPath $connectionFile) {
        $previous = Get-Content -LiteralPath $connectionFile -Raw | ConvertFrom-Json
        $previousTunnel = Get-Process -Id $previous.tunnel_pid -ErrorAction SilentlyContinue
        if ($previousTunnel -and $previousTunnel.ProcessName -eq 'cloudflared') {
            try {
                $publicState = Invoke-RestMethod -Uri ($previous.origin + '/api/game') -TimeoutSec 10
                if ($publicState.day) { $publicOrigin = $previous.origin }
            } catch {}
        }
    }
    if (-not $publicOrigin) {
        $tunnelLog = Join-Path $runtimeFolder ('tunnel-' + [guid]::NewGuid().ToString('N') + '.log')
        $tunnelProcess = Start-Process -FilePath $tunnelBinary -ArgumentList 'tunnel','--no-autoupdate','--url','http://127.0.0.1:5001' -WindowStyle Hidden -RedirectStandardOutput ($tunnelLog + '.stdout') -RedirectStandardError $tunnelLog -PassThru
        for ($attempt = 0; $attempt -lt 90; $attempt++) {
            if ($tunnelProcess.HasExited) { throw "Le tunnel s’est arrêté. Consultez $tunnelLog" }
            if (Test-Path -LiteralPath $tunnelLog) {
                $logText = Get-Content -LiteralPath $tunnelLog -Raw
                if ($logText -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
                    $publicOrigin = $Matches[0]
                    break
                }
            }
            Start-Sleep -Milliseconds 500
        }
        if (-not $publicOrigin) { throw "Le tunnel ne fournit pas d’adresse. Consultez $tunnelLog" }
        @{origin = $publicOrigin; tunnel_pid = $tunnelProcess.Id; log = $tunnelLog} | ConvertTo-Json | Set-Content -LiteralPath $connectionFile
    }

    Write-Output "Connexion de c-mitx à $publicOrigin"
    $publicOrigin | & npx.cmd --yes wrangler@4 secret put GAME_API_ORIGIN
    if ($LASTEXITCODE -ne 0) { throw 'Cloudflare n’a pas enregistré GAME_API_ORIGIN. Vérifiez la connexion Wrangler.' }
    Write-Output 'Connexion configurée : https://c-mitx.etienne-courson37.workers.dev'
    Write-Output 'Gardez cet ordinateur allumé et connecté. Relancez ce script si le tunnel est arrêté.'
} finally {
    Pop-Location
}
