# Third-party notices

The original bridge and server are credited in [ATTRIBUTION.md](ATTRIBUTION.md). Project source is distributed under MIT, based on the upstream README's declaration.

The Windows DLL is built with MinGW-w64/GCC and statically linked compiler/runtime components. Their notices and applicable GCC Runtime Library Exception are preserved in `docs/third-party/` in this distribution. These components retain their respective terms; the project MIT license does not replace them.

Python and Python dependencies are installed separately. `mcp_server/requirements.txt` identifies direct dependencies (MCP Python SDK, Pydantic, AnyIO, and pywin32); their packages and transitive dependencies retain their own licenses. No Python interpreter or site-packages directory is bundled.

Arma 3, game/mod assets, and Bohemia Interactive documentation are not included. The optional wiki tools require a separately supplied local dataset; obtain and use reference content under its applicable terms.
