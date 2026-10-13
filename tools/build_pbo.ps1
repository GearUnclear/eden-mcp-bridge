# build_pbo.ps1
# Packages the Arma 3 addon using the bundled Python PBO packer.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File "tools\build_pbo.ps1"

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$AddonSrc    = Join-Path $ProjectRoot "arma3_addon\addons\bridge"
$OutDir      = Join-Path $ProjectRoot "@ArmaDevBridge\addons"

# ---------------------------------------------------------------------------
# 1. Locate Python
# ---------------------------------------------------------------------------

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }
Write-Host "Python: $Python" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 2. Locate DLL (built by WSL make)
# ---------------------------------------------------------------------------

$DllSrc = Join-Path $ProjectRoot "bridge_dll\build\wsl\arma3_mcp_bridge.dll"

if (-not (Test-Path $DllSrc)) {
    Write-Warning "DLL not found at $DllSrc. Run this first:"
    throw "Build bridge_dll with make (WSL/MinGW) before packaging; refusing to deploy a missing or stale DLL."
}

# Remove DLL from addon source so it is NOT packed inside the PBO
$DllInAddon = Join-Path $AddonSrc "arma3_mcp_bridge.dll"
if (Test-Path $DllInAddon) { Remove-Item $DllInAddon -Force }

# ---------------------------------------------------------------------------
# 3. Pack the PBO (no DLL inside)
# ---------------------------------------------------------------------------

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "`nPacking PBO with Python packer..." -ForegroundColor Cyan

$PboOut = Join-Path $OutDir "bridge.pbo"
& $Python (Join-Path $PSScriptRoot "pack_pbo.py") $AddonSrc $PboOut

if ($LASTEXITCODE -ne 0) {
    Write-Error "pack_pbo.py failed with exit code $LASTEXITCODE"
}

# ---------------------------------------------------------------------------
# 4. Verify output
# ---------------------------------------------------------------------------

if (Test-Path $PboOut) {
    Write-Host "PBO created: $PboOut" -ForegroundColor Green
} else {
    Write-Warning "PBO not found at $PboOut. Check output above."
}

# Copy DLL to mod ROOT (not addons subfolder) — Arma 3 searches extensions there
$ModRoot = Split-Path $OutDir -Parent
$DllOut  = Join-Path $ModRoot "arma3_mcp_bridge.dll"
if (Test-Path $DllSrc) {
    Copy-Item $DllSrc $DllOut -Force
    Write-Host "DLL copied to mod root: $DllOut" -ForegroundColor Green
}

Write-Host "`nDone! Run install_addon.ps1 to copy to your Arma 3 mods folder." -ForegroundColor Green
