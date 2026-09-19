# Pygame Studio MCP server

The editor as an MCP server: it lets an AI client (VS Code Copilot, Claude
Desktop, any agent framework) inspect the project you have open, build scenes,
write scripts, run the game and read its output - while you watch it happen in
the editor and can undo every step with `Ctrl+Z`.

Hand-written on purpose: **no third-party dependency** (the official MCP SDK
needs Python 3.10+, Pygame Studio still ships 3.9). The protocol layer
(`protocol.py`) implements JSON-RPC 2.0 + the MCP methods `initialize`,
`tools/list`, `tools/call`, `resources/list`, `resources/read` and `ping`.

## Layout

| File | Purpose |
| --- | --- |
| `protocol.py` | JSON-RPC 2.0 message parsing, MCP constants, content blocks |
| `registry.py` | tool/resource registry, small JSON-schema validation, dispatch |
| `bridge.py` | hands calls from the server thread to the Qt main thread (and back) |
| `server.py` | HTTP transport (Streamable HTTP, `POST /mcp`) on `127.0.0.1` |
| `stdio.py` | stdio bridge for clients that can only spawn a process |
| `__main__.py` | `pygs mcp` command line (bridge by default, `--serve` for the server) |
| `tools/` | the tools, one module per area of the editor |
| `CAPABILITIES.md` | every editor feature mapped to the tools that cover it |

## Turn it on

Inside the editor: **File > Editor Settings > MCP server**, tick *Enable MCP
server*, pick a port (8765 by default) and copy the token. The settings are
stored in the editor config (`editor.pygs`), so the server starts with the
editor the next time.

Programmatically (what the editor does):

```python
import pygamestudio.mcp as mcp

mcp.attach(editor=editor, editor_body=editor_body, game_manager=manager)
mcp.start_server(port=8765, token='...')     # -> {'url': 'http://127.0.0.1:8765/mcp', ...}
```

## Connect a client

**VS Code (Copilot Chat)** - `.vscode/mcp.json` in the folder you keep the
project in:

```json
{
  "servers": {
    "pygamestudio": {
      "type": "http",
      "url": "http://127.0.0.1:8765/mcp",
      "headers": { "Authorization": "Bearer <the token from the editor settings>" }
    }
  }
}
```

**Clients that only speak stdio** (Claude Desktop, older tools) - let the bridge
forward to the running editor:

```json
{
  "mcpServers": {
    "pygamestudio": {
      "command": "pygs",
      "args": ["mcp"]
    }
  }
}
```

`pygs mcp` reads the port and token from the editor settings, so nothing has to
be repeated. It also takes `--url` / `--token` for an explicit endpoint.

**Check it by hand**

```bash
curl http://127.0.0.1:8765/mcp                     # health + tool count
python -m pygamestudio.mcp --serve --port 0        # stand-alone server (no editor attached)
```

## How a call travels

```
MCP client -> POST /mcp -> HTTP thread -> JSON-RPC -> tool registry
           -> bridge queue -> Qt main thread (QTimer pump) -> GameManager
           -> result back to the HTTP thread -> JSON-RPC response
```

* Every tool body runs **on the Qt main thread**, so touching the scene, the
  widgets or the undo stack is safe. `bridge.call_in_main_thread()` detects when
  the caller already is the main thread (tests, a future in-editor agent) and
  runs inline instead of dead-locking.
* A call that waits longer than 60 s (a modal dialog is open in the editor) is
  reported as a tool error, and the abandoned job is dropped so it cannot mutate
  the scene later.
* Without an attached editor the server still answers `initialize`,
  `tools/list` and the file/project tools that do not need the UI; the rest say
  "no project is open".

## Safety

* The socket binds **127.0.0.1 only**; no remote access.
* Every request must carry the token once one is configured
  (`Authorization: Bearer ...` or `?token=...`).
* File tools are confined to the project folder - `../outside.txt` is refused.
* Scene changes are undoable (`QUndoStack`); a batch tool call is one undo step.
* Tools never open modal dialogs: scene saving/loading uses their silent paths.

## Tests

`d:\tmp\mcp_check` (outside the repo) contains a full end-to-end harness: it
starts the server against a real `GameManager`, plays the MCP client from a
worker thread while the Qt event loop runs, and checks the JSON-RPC handshake,
the tool schemas, every tool category, the error paths and the resources.
