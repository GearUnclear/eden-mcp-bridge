#!/usr/bin/env bash
# build_dll_wsl.sh
# Compila arma3_mcp_bridge.dll desde WSL usando MinGW-w64 y la copia al addon.
#
# Uso (desde WSL, en cualquier directorio):
#   bash /mnt/c/path/to/eden-mcp-bridge/tools/build_dll_wsl.sh
#
# O desde Windows (PowerShell):
#   wsl bash "/mnt/c/path/to/eden-mcp-bridge/tools/build_dll_wsl.sh"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DLL_DIR="$PROJECT_ROOT/bridge_dll"
ADDON_DIR="$PROJECT_ROOT/arma3_addon/addons/bridge"

echo "=== ArmaDevBridge DLL Build (WSL / MinGW-w64) ==="
echo "Project : $PROJECT_ROOT"
echo "Compiler: $(x86_64-w64-mingw32-g++-posix --version | head -1)"
echo ""

cd "$DLL_DIR"
make install

echo ""
echo "=== Build complete ==="
echo "DLL location: $ADDON_DIR/arma3_mcp_bridge.dll"
echo ""
echo "Next step: run tools/build_pbo.ps1 in PowerShell to pack the addon."
