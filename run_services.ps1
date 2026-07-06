# Start all microservices locally (no Docker)
# Usage: .\run_services.ps1 [start|stop|status]

param([string]$Action = "start")

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Ports = @{gateway=8000; router=8001; executor=8002; policy=8003; model_proxy=8004; stats=8005}
$Pids = @{}

function Get-PidFile { "ai_system_pids.json" }

function Save-Pids {
    $p = @{}
    foreach ($entry in $Pids.GetEnumerator()) {
        $p[$entry.Key] = $entry.Value.Id
    }
    $p | ConvertTo-Json | Set-Content (Get-PidFile)
}

function Load-Pids {
    $f = Get-PidFile
    if (Test-Path $f) {
        $d = Get-Content $f | ConvertFrom-Json
        foreach ($entry in $d.PSObject.Properties) {
            try {
                $proc = Get-Process -Id $entry.Value -ErrorAction Stop
                $Pids[$entry.Name] = $proc
            } catch { }
        }
    }
}

function Start-Services {
    Write-Host "Starting AI Microservices..." -ForegroundColor Cyan
    $Pids.Clear()
    $Services = @(
        @{name="gateway"; port=8000; cmd="uvicorn services.gateway.app:app --host 0.0.0.0 --port 8000"}
        @{name="router"; port=8001; cmd="uvicorn services.router_service.app:app --host 0.0.0.0 --port 8001"}
        @{name="executor"; port=8002; cmd="uvicorn services.executor.app:app --host 0.0.0.0 --port 8002"}
        @{name="policy"; port=8003; cmd="uvicorn services.policy.app:app --host 0.0.0.0 --port 8003"}
        @{name="model_proxy"; port=8004; cmd="uvicorn services.model_proxy.app:app --host 0.0.0.0 --port 8004"}
        @{name="stats"; port=8005; cmd="uvicorn services.stats.app:app --host 0.0.0.0 --port 8005"}
    )

    foreach ($svc in $Services) {
        $proc = Start-Process -WindowStyle Hidden -PassThru -NoNewWindow -FilePath "python" `
            -ArgumentList "-m", $svc.cmd.Split(" ") `
            -WorkingDirectory $ScriptDir
        $Pids[$svc.name] = $proc
        Write-Host "  [$($svc.name)] started on port $($svc.port) (PID: $($proc.Id))" -ForegroundColor Green
    }
    Save-Pids
    Write-Host "`nAll services started. Gateway: http://localhost:8000" -ForegroundColor Cyan
    Write-Host "Health check: http://localhost:8000/health?detail=true" -ForegroundColor Gray
}

function Stop-Services {
    Write-Host "Stopping AI Microservices..." -ForegroundColor Yellow
    Load-Pids
    $Names = @("gateway", "router", "executor", "policy", "model_proxy", "stats")
    foreach ($name in $Names) {
        if ($Pids.ContainsKey($name)) {
            try {
                Stop-Process -Id $Pids[$name].Id -Force -ErrorAction SilentlyContinue
                Write-Host "  [$name] stopped" -ForegroundColor Green
            } catch {
                Write-Host "  [$name] not running" -ForegroundColor Gray
            }
        }
    }
    if (Test-Path (Get-PidFile)) { Remove-Item (Get-PidFile) }
}

function Show-Status {
    Load-Pids
    Write-Host "`nService Status:" -ForegroundColor Cyan
    $Ports.GetEnumerator() | Sort-Object Value | ForEach-Object {
        $name = $_.Key; $port = $_.Value
        $running = $Pids.ContainsKey($name)
        $emoji = if ($running) { "✅" } else { "❌" }
        Write-Host "  $emoji $name :$port $(if($running){'(PID: '+$Pids[$name].Id+')'}else{'(stopped)'})"
    }
}

switch ($Action.ToLower()) {
    "start" { Start-Services }
    "stop"  { Stop-Services }
    "status" { Show-Status }
    default { Write-Host "Usage: .\run_services.ps1 [start|stop|status]" }
}
