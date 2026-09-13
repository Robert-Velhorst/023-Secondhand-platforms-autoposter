[CmdletBinding()]
param(
    [string]$Python = ".\.venv-build\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$requestedPython = if ([IO.Path]::IsPathRooted($Python)) { $Python } else { Join-Path $root $Python }
if (-not (Test-Path -LiteralPath $requestedPython)) {
    $uvPython = Get-ChildItem -LiteralPath (Join-Path $env:APPDATA "uv\python") -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "cpython-3.13*-windows-x86_64-none" } |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if (-not $uvPython) {
        throw "Python 3.13 is required to create the Windows packaging environment."
    }
    & (Join-Path $uvPython.FullName "python.exe") -m venv (Join-Path $root ".venv-build")
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.13 is required to create the Windows packaging environment."
    }
}
$pythonPath = (Resolve-Path -LiteralPath $requestedPython).Path

& $pythonPath -m pip install -r (Join-Path $root "requirements-build.txt")
& $pythonPath -m PyInstaller --noconfirm --clean (Join-Path $root "packaging\autoposter.spec")
if ($LASTEXITCODE -ne 0) {
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
