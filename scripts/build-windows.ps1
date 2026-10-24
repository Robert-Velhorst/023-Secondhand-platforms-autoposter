[CmdletBinding()]
param(
    [string]$Python = ".\.venv-build\Scripts\python.exe",
    [string]$BootstrapPython = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
function Assert-StableBuildPython([string]$Executable) {
    & $Executable -I -c 'import sys, sysconfig; expected = (3, 15, 1); actual = sys.version_info[:3]; platform = sysconfig.get_platform(); sys.exit(0 if actual == expected and platform == "win-amd64" else "Windows packaging requires CPython 3.15.1 for win-amd64; found %s on %s" % (actual, platform))'
    if ($LASTEXITCODE -ne 0) {
        throw "Select CPython 3.15.1 win-amd64; the existing environment was not replaced."
    }
}
$requestedPython = if ([IO.Path]::IsPathRooted($Python)) { $Python } else { Join-Path $root $Python }
if (-not (Test-Path -LiteralPath $requestedPython)) {
    if ($Python -ne ".\.venv-build\Scripts\python.exe") {
        throw "The requested Python executable does not exist: $requestedPython"
    }
    if (-not $BootstrapPython) {
        $uvPython = Get-ChildItem -LiteralPath (Join-Path $env:APPDATA "uv\python") -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq "cpython-3.15.1-windows-x86_64-none" } |
            Select-Object -First 1
        if (-not $uvPython) {
            throw "Supply -BootstrapPython with the path to CPython 3.15.1 win-amd64."
        }
        $BootstrapPython = Join-Path $uvPython.FullName "python.exe"
    }
    Assert-StableBuildPython $BootstrapPython
    & $BootstrapPython -m venv (Join-Path $root ".venv-build")
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create the Python 3.15.1 Windows packaging environment."
    }
}
$pythonPath = (Resolve-Path -LiteralPath $requestedPython).Path
Assert-StableBuildPython $pythonPath

& $pythonPath -I (Join-Path $root "scripts/setup_sqlite_runtime.py")
if ($LASTEXITCODE -ne 0) {
    throw "Project-local SQLite provisioning failed; no executable was built."
}

& $pythonPath -m pip install --require-hashes -r (Join-Path $root "requirements-build.lock.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Windows build dependency installation failed integrity verification."
}
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = (Join-Path $root "runtime_bootstrap") + [IO.Path]::PathSeparator + $root
    & $pythonPath -m PyInstaller --noconfirm --clean (Join-Path $root "packaging\autoposter.spec")
    $buildExit = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $previousPythonPath
}
if ($buildExit -ne 0) {
    throw "Windows executable build failed."
}

$executable = Join-Path $root "dist\SecondhandAutoposter.exe"
if (-not (Test-Path -LiteralPath $executable)) {
    throw "Expected executable was not produced: $executable"
}

$hash = (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$executable.sha256" -Value "$hash  SecondhandAutoposter.exe" -Encoding ascii
Write-Output "Built $executable"
Write-Output "SHA256 $hash"
