# Requires PowerShell
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Always run from this script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# 1) Create / activate venv
$Python = (Get-Command python -ErrorAction SilentlyContinue) ?? (Get-Command python3 -ErrorAction SilentlyContinue)
if (-not $Python) { Write-Error "python not found in PATH" }

if (-not (Test-Path "$ScriptDir/venv")) {
  Write-Host "Creating virtual environment..."
  & $Python.Source -m venv "$ScriptDir/venv" | Out-Null
}

$VenvPython = Join-Path $ScriptDir "venv/Scripts/python.exe"
if (-not (Test-Path $VenvPython)) { Write-Error "venv python not found at $VenvPython" }

# 2) Upgrade pip toolchain
& $VenvPython -m pip install --upgrade pip setuptools wheel --disable-pip-version-check --no-input

# 3) Install requirements (prebuilt wheels preferred)
& $VenvPython -m pip install --prefer-binary -r "$ScriptDir/requirements.txt" --disable-pip-version-check --no-input

# 4) Generate gRPC Python files
& $VenvPython -m grpc_tools.protoc -I "$ScriptDir/proto" --python_out="$ScriptDir/proto" --grpc_python_out="$ScriptDir/proto" "$ScriptDir/proto/onvif.proto"
Write-Host "gRPC Python files generated."

# 5) Run server
& $VenvPython "$ScriptDir/grpc_server.py"

