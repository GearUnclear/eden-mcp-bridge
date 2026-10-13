# Eden MCP Bridge

A local MCP server for creating and inspecting Arma 3 missions in the Eden Editor. It connects an MCP client to Eden through a Python server, a Windows x64 extension, and an SQF editor addon.

**Based on [diaverso/Arma3-Eden-Editor-MCP-Server](https://github.com/diaverso/Arma3-Eden-Editor-MCP-Server).** Credit for the original project and bridge architecture belongs to diaverso and its contributors. This independently maintained distribution adds correctness fixes, transport hardening, clearer results, and regression coverage. See [ATTRIBUTION.md](ATTRIBUTION.md).

**Current release: 1.2.0-rc.1.** This is a release candidate: 74 offline checks and focused live editor tests have passed, while broader save/reload and Preview acceptance remains incomplete. Read [validation and limitations](docs/validation.md) before relying on unattended mission changes.

## What it does

- Create, move, delete, list, and inspect Eden entities.
- Merge complete same-side infantry groups through native editor connections.
- Read and write editor attributes with engine acceptance and effective-value readback.
- Search the loaded object catalogue, including installed mods, and query terrain, roads, nearby map objects, and named locations.
- Request scenario saves and editor undo with explicit confirmation limits.
- Read bounded pages of mission objects and discover configured attribute properties.

It is a **local editor tool**, not a dedicated-server controller or protected multiplayer integration. Only one MCP client can own the game bridge at a time.

## What this release fixes

These changes address defects found in the inherited implementation and the subsequent repair work. They are not claims about every version of the upstream project.

| Shortcoming | Result in this distribution |
| --- | --- |
| Quoted numeric IDs and inconsistent conversion could resolve the wrong entity. | Native numeric wire values, full-string numeric validation, and native identity/kind checks; malformed or fractional IDs reject. |
| Runtime grouping did not establish persistent Eden connections. | Native Group connections, complete-group preflight, and membership/leader/link readback. A missing native return can no longer produce null success fields. Save/reload persistence still needs broader testing. |
| Catalogue side labels and filter numbers disagreed. | Correct config affiliation, named filters, raw `config_side`, and cache versioning. WEST is config side 1; EAST is 0. |
| Fragile bulk reads could time out or mishandle empty values. | Bounded pages, per-field errors, stage diagnostics, response-size limits, robust JSON encoding, and a missing-response guard without replay. The historical timeout's exact cause was not conclusively reproduced. |
| Player-slot aliases were unsupported and attribute discovery was unclear. | `isPlayer` → `ControlSP`, `isPlayable` → `ControlMP`, `variable` → `Name`, and config-backed property discovery. |
| Attribute writes always reported success. | Explicit engine acceptance, effective readback, rejection/unverified outcomes, and bounded numeric precision tolerance. |
| The save handler saved inventory instead of the scenario. | Native scenario-save request and Save As guidance; no false claim that a file reached disk. |
| Undo was a successful no-op. | Native Undo with observed-event or unconfirmed results; global editor-history scope is explicit. |
| Altitude heuristics silently changed placement. | Explicit ATL, ASL, terrain, and water modes; actual position readback; corrected marker creation and precision-aware trigger/position checks. |

Transport changes also replace compiled incoming SQF with data-only parsing, restrict the named pipe to the current Windows user, reject remote pipe clients, and prevent stale requests from being replayed after reconnect. There is no arbitrary SQF execution tool. These protections do not replace review of commands issued by your MCP client.

## Install on Windows

Requirements: Windows x64, Arma 3 with Eden, Python 3.11–3.13, and an MCP client supporting local stdio servers. The tested Python version is 3.13. Run the game and client as the **same normal Windows user**, without Administrator elevation.

1. Download `eden-mcp-bridge-1.2.0-rc.1-windows-x64.zip` from [Releases](https://github.com/GearUnclear/eden-mcp-bridge/releases). Extract it into a permanent folder, such as `C:\tools\eden-mcp-bridge`. The package includes source, the built addon/DLL, installer, and documentation. A Git clone or GitHub's automatic source ZIP requires the build step below.
2. Open PowerShell in the extracted folder and prepare the Python environment:

   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r mcp_server\requirements.txt
   ```

3. Save your mission and **close Arma 3**. Install the packaged addon, using your actual game path:

   ```powershell
   .\tools\install_addon.ps1 -Arma3Path 'D:\SteamLibrary\steamapps\common\Arma 3'
   ```

   The installer backs up existing bridge files under `backups/`, verifies copied hashes, and attempts rollback on failure. It installs the PBO under `@ArmaDevBridge/addons`, the DLL in the mod root, and both DLL filenames in the game root. It refuses to update a running game.
4. Add the `@ArmaDevBridge` local mod in the Arma launcher, or launch with `-mod=@ArmaDevBridge`. Enable only one copy of this bridge addon. Existing bridge installations use the same addon and pipe names, so they must not run side by side.
5. Configure your MCP client as described next, restart its server connection, launch Arma, and open Eden. Call `get_bridge_status` first; expect `connected=true`, `editor_open=true`, and version `1.2.0-rc.1`.

The release includes `SHA256SUMS.txt` for checking the download with `Get-FileHash`. The DLL is not code-signed. Do not bypass security software warnings; build from source if your environment does not permit the package.

## Connect an MCP client

Use your client's local **stdio** configuration. Supply absolute paths; `cwd` is the repository/extracted package root, not `mcp_server/`. The following common JSON shape is also in [.mcp.json.example](.mcp.json.example); clients may use a different settings format.

```json
{
  "mcpServers": {
    "arma3-eden": {
      "command": "C:\\tools\\eden-mcp-bridge\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server"],
      "cwd": "C:\\tools\\eden-mcp-bridge",
      "env": {
        "ARMA3_BRIDGE_PIPE": "\\\\.\\pipe\\arma3_mcp_bridge",
        "ARMA3_BRIDGE_TIMEOUT": "30"
      }
    }
  }
}
```

If your client does not support `cwd`, set `PYTHONPATH` to the same absolute package root in its environment. Copying `.mcp.json.example` alone does not configure every client. Restart the MCP server after changing Python source or settings; restart Arma after changing its PBO/DLL.

## First session

Use a disposable scenario for your first checks:

1. Call `get_bridge_status`, then `get_mission_info`.
2. Call `get_placeable_categories` before selecting catalogue filters. Search with `search_placeable_objects(search="B_Soldier_F", filter_side="WEST")` and use a returned classname.
3. Call `get_terrain_info(positions=[[3000,3000]])`. Choose coordinates on land in your current terrain; the example is not a safe location on every map.
4. Create a unit with `create_entity(params={"entity_type":"Unit","classname":"B_Soldier_F","position":[3000,3000,0],"side":"WEST","placement_mode":"ATL"})`. Use the returned entity ID in later calls, never an ID copied from another scenario.
5. Inspect `get_all_editor_objects(page=0,page_size=30)` and `get_supported_attributes(entity_id=YOUR_ID)`.
6. To set a playable slot, use `set_attribute(params={"entity_id":YOUR_ID,"attribute":"isPlayable","value":true})`. Check both `engine_accepted` and `verified`, then inspect the slot in Eden.

The examples show tool arguments, not commands to paste into a shell. Unknown classnames/properties and invalid types should return errors. Check state before retrying any failed mutation: a native command may have changed some editor state before a later error.

## Result and placement rules

- **Writes:** `ok`/`engine_accepted` indicate acceptance. `verified` means immediate readback matched within documented numeric precision; it does not establish saved persistence.
- **Save:** `save_mission(params={})` requests a scenario save. It deliberately returns `ok=false` and `persistence_verified=false`; complete Save As if needed, inspect the file, and reopen it to verify. Changing the display name through this tool is unsupported.
- **Undo:** acts on Eden's global history, including manual edits. An observed `OnUndo` event does not identify what changed. Inspect the result; do not retry blindly.
- **Placement:** ATL is height above terrain; ASL is height above sea level. `terrain` snaps to terrain plus the supplied Z offset. `water` uses sea level plus Z and rejects land. Two coordinates imply Z=0. There is no roof/obstacle snapping.
- **Grouping:** include every member of each participating group; the selected leader must already lead the destination group. Mixed sides, vehicles/mounted crew, partial groups, and source routes/external links are not supported by the merge path.
- **Reads:** object pages have a maximum page size of 100. Bulk attributes may be partial when configured properties do not apply; inspect `errors`. Pages are not atomic snapshots.
- **Strings:** request CR/LF and other control characters except tab reject rather than being silently removed. Use single-line Init text or edit multiline content in Eden.

## Build and test

For a source checkout, install the Python dependencies above. In WSL Ubuntu, install a build toolchain (for example `make` and `g++-mingw-w64-x86-64`), then run from `bridge_dll/`:

```bash
make all
```

The compiler expected by the Makefile is `x86_64-w64-mingw32-g++-posix`. Back in PowerShell at the repository root:

```powershell
.\tools\build_pbo.ps1
.\.venv\Scripts\python.exe tools\run_offline_checks.py --transport
```

Packaging does not install the addon. The test runner uses an explicit allowlist and a unique test pipe, so it does not connect to a running mission. Do not use generic test discovery: `tools/test_pipe.py` is a live diagnostic. Offline tests do not compile or execute SQF in Arma. See [docs/validation.md](docs/validation.md) for the live results and remaining acceptance cases.

## Troubleshooting and limits

| Symptom | Check |
| --- | --- |
| Bridge disconnected | Confirm the addon is enabled, Eden is open, paths point to this package, and game/client use the same normal Windows account. |
| Pipe busy / Windows error 231 | Disconnect the other MCP client; the bridge supports one owner. `reconnect_bridge` releases only this client's handle. |
| Tool timeout | Check bridge status and the Arma RPT for `[ArmaDevBridge]` command/stage entries. Inspect state before retrying a mutation; reduce read page size. |
| Old version or missing tool | Restart the MCP server for Python changes and Arma for addon/DLL changes. Check for duplicate loaded bridge mods. |
| Attribute unavailable | Discover candidates, then perform a focused read; mod/UI conditions can make a configured property unavailable. |
| Wiki lookup finds nothing | The optional local `mcp_server/wiki/*.md` dataset is not distributed. These two tools need separately supplied, appropriately licensed reference files. |

The named-save/reload cycle, full 14-person squad persistence, Preview/load/new-scenario recovery, source-route and mounted-crew rejection, roof placement, remaining entity kinds, and the original modded stress scenario still need broader live acceptance. No end-to-end performance improvement is claimed. The dependency file pins direct dependencies; transitive dependencies are not fully locked. Keep mission backups and review changes in Eden.

Bulk squad construction, routes, filtered/delta reads, and reusable mission recipes are future work, not features delivered here. See [ROADMAP.md](ROADMAP.md). Report reproducible problems through [Issues](https://github.com/GearUnclear/eden-mcp-bridge/issues), including version, terrain/mods, tool arguments, result, and relevant RPT lines with private paths removed.

## License and credit

MIT, consistent with the upstream README's license declaration. See [LICENSE](LICENSE), [ATTRIBUTION.md](ATTRIBUTION.md), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This project is not affiliated with or endorsed by Bohemia Interactive or the upstream maintainers. Arma 3 and other game/mod content remain the property of their respective owners and are not included.
