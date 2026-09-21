"""MCP tool modules - importing this package registers every tool.

Each module groups the tools of one area of the editor:

``editor``   status, undo/redo, console output, scene screenshots, panels
``project``  project info/config, files, assets, scripts
``scene``    scene files, the object tree, searching objects
``objects``  creating/updating/deleting/duplicating/moving/selecting objects
``runtime``  running and stopping the game, reading the console
``panels``   block editor, image editor, tile map editor, audio player
``build``    packaging the project into a desktop app

See ``CAPABILITIES.md`` for the full map of editor features to tools.
"""

from pygamestudio.mcp.tools import (  # noqa: F401  (import for the side effect)
    build,
    editor,
    objects,
    panels,
    project,
    runtime,
    scene,
)
