"""
Entry point: python -m mcp_server

Starts the bridge reconnect loop, then runs the MCP server over stdio.
An MCP client connects via stdio using its server configuration.
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def main() -> None:
    from .server import mcp, bridge

    async with bridge:
        await mcp.run_stdio_async()


asyncio.run(main())
