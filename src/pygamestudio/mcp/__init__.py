"""(No third-party dependency) MCP server for the Pygame Studio editor.

The editor is the "hands": these tools let an MCP client (VS Code Copilot,
Claude Desktop, any agent framework) inspect the open project, create and edit
scene objects, write scripts, run the game and read the console - while the
user watches everything happen in the editor and can undo it with Ctrl+Z.

Quick start (inside the editor: Settings > MCP server, or programmatically)::

    from pygamestudio.mcp import attach, start_server, stop_server

    attach(editor=editor, editor_body=editor_body, game_manager=manager)
    info = start_server()        # {'url': 'http://127.0.0.1:8765/mcp', ...}

The transport is a small HTTP endpoint (Streamable HTTP, POST only) written
with the standard library; ``python -m pygamestudio.mcp`` is a stdio bridge for
clients that can only spawn a process.
"""

from pygamestudio.mcp.bridge import attach, detach
from pygamestudio.mcp.protocol import PROTOCOL_VERSION, SERVER_NAME, SERVER_VERSION
from pygamestudio.mcp.registry import ToolError, call_tool, list_tools
from pygamestudio.mcp.server import (
    DEFAULT_HOST, DEFAULT_PORT, is_running, server_info, start_server, stop_server,
)

# Importing the tools package registers every tool (it is what the server lists).
from pygamestudio.mcp import tools as _tools  # noqa: F401,E402

__all__ = [
    'attach', 'detach', 'start_server', 'stop_server', 'server_info', 'is_running',
    'call_tool', 'list_tools', 'ToolError',
    'DEFAULT_HOST', 'DEFAULT_PORT', 'PROTOCOL_VERSION', 'SERVER_NAME', 'SERVER_VERSION',
]
