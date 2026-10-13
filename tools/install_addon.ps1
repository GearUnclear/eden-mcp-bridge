# install_addon.ps1
# Copies the @ArmaDevBridge mod folder to the Arma 3 user mods directory.
#
# Usage:
#   .\tools\install_addon.ps1
#   .\tools\install_addon.ps1 -Arma3Path "D:\SteamLibrary\steamapps\common\Arma 3"

param(
    [string]$Arma3Path = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ModSrc      = Join-Path $ProjectRoot "@ArmaDevBridge"

# ---------------------------------------------------------------------------
# Locate Arma 3
# ---------------------------------------------------------------------------

if (-not $Arma3Path) {
    # Try Steam default locations
    $candidates = @(
        "C:\Program Files (x86)\Steam\steamapps\common\Arma 3",
        "D:\SteamLibrary\steamapps\common\Arma 3",
        "E:\SteamLibrary\steamapps\common\Arma 3",
        "G:\SteamLibrary\steamapps\common\Arma 3"
    )
    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c "arma3.exe")) { $Arma3Path = $c; break }
    }
}

if (-not $Arma3Path -or -not (Test-Path (Join-Path $Arma3Path "arma3.exe"))) {
    Write-Host "Arma 3 not found automatically. Please provide the path:" -ForegroundColor Yellow
    $Arma3Path = Read-Host "Arma 3 installation path"
    if (-not (Test-Path (Join-Path $Arma3Path "arma3.exe"))) {
        Write-Error "arma3.exe not found at $Arma3Path"
    }
}

Write-Host "Arma 3 found at: $Arma3Path" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Check source
# ---------------------------------------------------------------------------

if (-not (Test-Path $ModSrc)) {
    Write-Error "@ArmaDevBridge folder not found at $ModSrc. Run build_pbo.ps1 first."
}

# ---------------------------------------------------------------------------
# Deploy the built files, preserving unrelated mod content and a rollback copy.
# ---------------------------------------------------------------------------

$ModDest = Join-Path $Arma3Path "@ArmaDevBridge"
if (Get-Process -Name arma3,arma3_x64 -ErrorAction SilentlyContinue) {
    throw "Close Arma 3 before installing. Loaded addon/DLL files cannot be updated safely."
}
$DllSrc  = Join-Path $ModSrc "arma3_mcp_bridge.dll"
$PboSrc  = Join-Path $ModSrc "addons\bridge.pbo"
foreach ($source in @($DllSrc, $PboSrc)) {
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing build artifact: $source" }
}
$backupDir = Join-Path $ProjectRoot ("backups\" + (Get-Date -Format "yyyyMMdd-HHmmss-fff"))
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$deployments = @(
    @{ Source = $PboSrc; Target = (Join-Path $ModDest "addons\bridge.pbo"); BackupName = "addon_bridge.pbo" },
    @{ Source = $DllSrc; Target = (Join-Path $ModDest "arma3_mcp_bridge.dll"); BackupName = "mod_bridge.dll" },
    @{ Source = $DllSrc; Target = (Join-Path $Arma3Path "arma3_mcp_bridge.dll"); BackupName = "root_bridge.dll" },
    @{ Source = $DllSrc; Target = (Join-Path $Arma3Path "arma3_mcp_bridge_x64.dll"); BackupName = "root_bridge_x64.dll" }
)
foreach ($item in $deployments) {
    $item.Backup = Join-Path $backupDir $item.BackupName
    $item.Existed = Test-Path -LiteralPath $item.Target
    if ($item.Existed) { Copy-Item -LiteralPath $item.Target -Destination $item.Backup -Force }
}
$deployments | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $backupDir "manifest.json")
$attempted = @()
try {
    foreach ($item in $deployments) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $item.Target) -Force | Out-Null
        $attempted += $item
        Copy-Item -LiteralPath $item.Source -Destination $item.Target -Force
        if ((Get-FileHash -LiteralPath $item.Source).Hash -ne (Get-FileHash -LiteralPath $item.Target).Hash) {
            throw "Installed artifact hash mismatch: $($item.Target)"
        }
    }
} catch {
    foreach ($item in $attempted) {
        if ($item.Existed) { Copy-Item -LiteralPath $item.Backup -Destination $item.Target -Force }
        elseif (Test-Path -LiteralPath $item.Target) { Remove-Item -LiteralPath $item.Target -Force }
    }
    throw
}
Write-Host "Previous bridge files backed up to: $backupDir" -ForegroundColor Cyan

Write-Host "Installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Launch Arma 3 with:" -ForegroundColor Cyan
Write-Host "  -mod=@ArmaDevBridge" -ForegroundColor White
Write-Host ""
Write-Host "Or add it via the Arma 3 Launcher in the 'Mods' tab." -ForegroundColor Cyan
