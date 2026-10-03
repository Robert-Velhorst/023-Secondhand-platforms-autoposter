[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [string]$Domain = "",
    [string]$NgrokPath = "ngrok",
    [switch]$VerifyOnly,
    [switch]$FromSource,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$portableExe = Join-Path $root "dist\SecondhandAutoposter.exe"
$python = Join-Path $root ".venv\Scripts\python.exe"
$launchArgs = @("--ngrok", "--port", $Port, "--ngrok-path", $NgrokPath)
if ($Domain) { $launchArgs += @("--ngrok-domain", $Domain) }
if ($VerifyOnly) { $launchArgs += "--verify-only" }
if ($NoBrowser -or $VerifyOnly) { $launchArgs += "--no-browser" }

# The application owns its socket, data lock, ngrok, and worker. Do not start a
# tunnel or select processes by executable name in this wrapper. Native argument
# arrays preserve paths with spaces; the caller's environment is never modified.
Push-Location -LiteralPath $root
try {
    if (-not $FromSource -and (Test-Path -LiteralPath $portableExe)) {
        & $portableExe @launchArgs
    } elseif (Test-Path -LiteralPath $python) {
        & $python -m app.launcher @launchArgs
    } else {
        throw "Build the current portable app or create the project Python environment first."
    }
    if ($LASTEXITCODE -ne 0) {
        throw "The managed ngrok launcher failed (exit $LASTEXITCODE). No readiness success is claimed."
    }
} finally {
    Pop-Location
}
