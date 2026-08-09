[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [string]$Domain = "",
    [string]$NgrokPath = "ngrok",
    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $env:LOCALAPPDATA "SecondhandAutoposter\runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$ngrokLog = Join-Path $runtimeDir "ngrok.log"
$ngrokErrorLog = Join-Path $runtimeDir "ngrok-error.log"
$appLog = Join-Path $runtimeDir "app.log"
$appErrorLog = Join-Path $runtimeDir "app-error.log"

$ngrokArgs = @(
    "http",
    "http://127.0.0.1:$Port",
    "--inspect=false",
    "--log=stdout",
    "--log-format=json"
)
if ($Domain.Trim()) {
    $ngrokArgs += "--url=$($Domain.Trim())"
}

$ngrok = Start-Process -FilePath $NgrokPath -ArgumentList $ngrokArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput $ngrokLog -RedirectStandardError $ngrokErrorLog
$app = $null
$appExecutablePath = $null
$baselineAppPids = @()
try {
    $publicUrl = $null
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $ngrok.Refresh()
        if ($ngrok.HasExited) {
            $ngrokErrors = @(Get-Content -LiteralPath $ngrokErrorLog -ErrorAction SilentlyContinue)
            $ngrokError = ($ngrokErrors | Where-Object { $_ -match "ERR_NGROK_" } | Select-Object -First 1)
            if (-not $ngrokError) {
                $ngrokError = ($ngrokErrors | Where-Object { $_.Trim() -notin @("", "ERROR:") } | Select-Object -First 1)
            }
            if (-not $ngrokError) {
                $ngrokError = (Get-Content -LiteralPath $ngrokLog -ErrorAction SilentlyContinue | Select-Object -Last 1)
            }
            throw "ngrok exited before creating a tunnel. $ngrokError"
        }

        foreach ($line in (Get-Content -LiteralPath $ngrokLog -ErrorAction SilentlyContinue)) {
            try {
                $event = $line | ConvertFrom-Json
                if ($event.url -like "https://*") {
                    $publicUrl = $event.url
                }
            } catch {
                # Ignore an incomplete log line while ngrok is still writing it.
            }
        }
        if ($publicUrl) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $publicUrl) {
        throw "ngrok did not expose an HTTPS tunnel within 30 seconds. See $ngrokLog"
    }

    $env:APP_ENV = "standalone"
    $env:PUBLIC_BASE_URL = $publicUrl
    $env:CORS_ORIGINS = $publicUrl
    $env:AUTH_TRANSPORT = "bearer"
    $env:DEV_AUTO_LOGIN = "false"
    $env:AUTO_CREATE_TABLES = "false"
    $env:JOB_PROCESS_INLINE = "false"

    $portableExe = Join-Path $root "dist\SecondhandAutoposter.exe"
    if (Test-Path -LiteralPath $portableExe) {
        $appExecutablePath = (Resolve-Path -LiteralPath $portableExe).Path
        $baselineAppPids = @(
            Get-CimInstance Win32_Process |
                Where-Object { $_.ExecutablePath -eq $appExecutablePath } |
                Select-Object -ExpandProperty ProcessId
        )
        $app = Start-Process -FilePath $portableExe -ArgumentList @("--port", $Port, "--no-browser") -PassThru -WindowStyle Hidden -RedirectStandardOutput $appLog -RedirectStandardError $appErrorLog
    } else {
        $python = Join-Path $root ".venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $python)) {
            throw "Build the portable app or create the project environment first."
        }
        $appExecutablePath = (Resolve-Path -LiteralPath $python).Path
        $baselineAppPids = @(
            Get-CimInstance Win32_Process |
                Where-Object { $_.ExecutablePath -eq $appExecutablePath } |
                Select-Object -ExpandProperty ProcessId
        )
        $app = Start-Process -FilePath $python -ArgumentList @("-m", "app.launcher", "--port", $Port, "--no-browser") -WorkingDirectory $root -PassThru -WindowStyle Hidden -RedirectStandardOutput $appLog -RedirectStandardError $appErrorLog
    }

    $health = $null
    for ($attempt = 0; $attempt -lt 180; $attempt++) {
        $app.Refresh()
        if ($app.HasExited) {
            throw "The app exited before becoming healthy. See $appLog"
        }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
            if ($health.status -eq "ok") { break }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $health -or $health.status -ne "ok") {
        throw "The app did not become healthy within 3 minutes. See $appLog"
    }

    $publicHealth = $null
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $publicHealth = Invoke-RestMethod -Uri "$publicUrl/api/health" -TimeoutSec 5
            if ($publicHealth.status -eq "ok") { break }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $publicHealth -or $publicHealth.status -ne "ok") {
        throw "The public HTTPS tunnel did not pass its health check. See $ngrokLog"
    }

    Write-Output "Secondhand Autoposter is available at $publicUrl"
    if ($VerifyOnly) {
        Write-Output "Verified local API, worker startup, and public HTTPS health; stopping test services."
        return
    }
    Write-Output "Press Ctrl+C to stop the app and tunnel."
    Start-Process $publicUrl
    Wait-Process -Id $app.Id
} finally {
    if ($appExecutablePath) {
        $createdAppProcesses = @(
            Get-CimInstance Win32_Process |
                Where-Object {
                    $_.ExecutablePath -eq $appExecutablePath -and
                    $baselineAppPids -notcontains $_.ProcessId
                }
        )
        foreach ($process in $createdAppProcesses) {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        }
    } elseif ($app -and -not $app.HasExited) {
        Stop-Process -Id $app.Id -Force
    }
    if ($ngrok -and -not $ngrok.HasExited) { Stop-Process -Id $ngrok.Id -Force }
}
