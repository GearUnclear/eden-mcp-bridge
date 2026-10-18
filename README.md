# Eden MCP Bridge

Connect an MCP client to Arma 3's Eden Editor to build and edit missions.

- **Place infantry groups** with proper Eden group connections, or add a soldier to an existing group.
- **Place crewed vehicles** with their default AI crew, named and facing the right way.
- **Give a group waypoints** with behaviour, speed, formation and combat mode, then read the route back with `describe_group`. Waypoint scripts are not supported.
- **Rotate units** and set their position, height, and playable slots.
- **Test without restarting the game:** preview your mission, return to Eden, and keep editing. Reconnect the MCP client with `reconnect_bridge` if needed.

Based on [diaverso's Arma 3 Eden Editor MCP Server](https://github.com/diaverso/Arma3-Eden-Editor-MCP-Server). [Credits](ATTRIBUTION.md) · [MIT license](LICENSE)

## Install

Requires Windows x64, Arma 3, Python 3.11–3.13, and an MCP client with local stdio support. Run Arma and the client under the same Windows account, without Administrator elevation.

1. Download the **Windows x64 ZIP** from [Releases](https://github.com/GearUnclear/eden-mcp-bridge/releases). Extract it to a permanent folder, such as `C:\tools\eden-mcp-bridge`. Use the ZIP containing the built addon, not GitHub's automatic source archive.
2. Open PowerShell in the extracted `eden-mcp-bridge` folder and install the Python dependencies:

   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r mcp_server\requirements.txt
   ```

   Adjust `-3.13` if you use another supported Python version.

3. Save your mission and **close Arma** for installation. Run this with your actual game path:

   ```powershell
   .\tools\install_addon.ps1 -Arma3Path 'D:\SteamLibrary\steamapps\common\Arma 3'
   ```

   The installer backs up existing bridge files before replacing them.
4. In the Arma launcher, add the installed `@ArmaDevBridge` folder as a local mod and enable it. Disable any older copy of the bridge.
5. Add the configuration below to your MCP client, adjusting the paths. Restart its MCP connection, launch Arma, and open Eden.

### Client configuration

Use absolute paths to the extracted folder. Your client's settings format may differ; this example uses the common `mcpServers` format.

```json
{
  "mcpServers": {
    "arma3-eden": {
      "command": "C:\\tools\\eden-mcp-bridge\\.venv\\Scripts\\python.exe",
      "args": ["-m", "mcp_server"],
      "cwd": "C:\\tools\\eden-mcp-bridge"
    }
  }
}
```

If your client doesn't support `cwd`, set its `PYTHONPATH` environment variable to `C:\tools\eden-mcp-bridge` instead.

Call `get_bridge_status` to check the connection: `connected` and `editor_open` should both be `true`.

## Using it

Ask your client to place a squad, turn units toward a position, or make a unit playable. Preview the mission in Arma, then return to Eden to make changes. The bridge edits in Eden, not during Preview. See [groups, crews and waypoints](docs/groups-and-waypoints.md) for those options.

Only one MCP client can connect at a time. If disconnected, confirm the mod is enabled and Eden is open, then use `reconnect_bridge`. Replacing the addon or DLL still requires closing Arma.

Current release: **1.2.0-rc.1**. [Known limits and test coverage](docs/validation.md) · [Full change list](CHANGELOG.md) · [Report a problem](https://github.com/GearUnclear/eden-mcp-bridge/issues)
