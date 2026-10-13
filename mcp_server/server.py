"""
Arma 3 Eden Editor MCP Server.

Exposes tools and resources for an MCP client to manipulate
the Arma 3 Eden Editor via a named-pipe bridge DLL.
"""

from mcp.server.fastmcp import FastMCP
from .bridge_client import BridgeClient

# ---------------------------------------------------------------------------
# Server and bridge singletons
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "arma3-eden",
    instructions=(
        "You are connected to the Arma 3 Eden Editor. "
        "Use the available tools to create, move, delete entities, "
        "read mission data, and manage scenario attributes. "
        "Entity types are: 'Object', 'Vehicle', 'Unit', 'Group', 'Trigger', 'Waypoint', 'Logic', 'Marker'. "
        "Sides: 'WEST' (BLUFOR), 'EAST' (OPFOR), 'GUER' (Independent), 'CIV' (Civilian). "
        "Positions are [x, y, z], ATL by default; creation/movement accept explicit ASL, terrain, or water placement modes."
    ),
)

bridge = BridgeClient()

# ---------------------------------------------------------------------------
# Import tool modules so their @mcp.tool() decorators register
# ---------------------------------------------------------------------------

from .tools import entities  # noqa: E402, F401
from .tools import attributes  # noqa: E402, F401
from .tools import selection  # noqa: E402, F401
from .tools import mission  # noqa: E402, F401
from .tools import catalog  # noqa: E402, F401
from .tools import terrain  # noqa: E402, F401
from .tools import wiki     # noqa: E402, F401
