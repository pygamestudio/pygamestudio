"""Editor level MCP tools: status, undo/redo, console output, scene screenshots."""

from pygamestudio.mcp.bridge import bridge
from pygamestudio.mcp.registry import ToolError, register_resource, tool
from pygamestudio.mcp.tools.context import (
    json_value, manager, object_type_names, project_path, project_relative,
    safe_project_path, type_properties, undo_state,
)


@tool(
    'editor_status',
    'Report whether the editor is running with a project open, which scene is '
    'loaded, what is selected and whether the game is running. Call this first: '
    'every other tool needs the editor to have a project open.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Editor status'},
)
def editor_status(args):
    manager_ = bridge.game_manager_or_none()
    if manager_ is None:
        return {
            'attached': False,
            'hint': 'No Pygame Studio editor is attached. Open a project in the '
                    'editor, or make sure the MCP server was started from it.',
        }

    data = {
        'attached': True,
        'project_ready': bridge.is_project_ready,
        'project_path': manager_.get_project_path(),
        'project_name': project_path().name if manager_.get_project_path() else None,
        'scene_path': manager_.current_scene_file_path or None,
        'scene_saved': manager_.is_current_scene_saved,
        'has_scene': not manager_.is_empty(),
        'selected_objects': [
            {'uuid': obj.uuid, 'name': obj.name, 'type': obj.type}
            for obj in manager_.get_selected_objects()
        ],
        'undo': undo_state(),
    }
    editor_ = bridge.editor_or_none()
    if editor_ is not None:
        data['editor_window_visible'] = bool(editor_.isVisible())
    return data


@tool(
    'undo',
    'Undo the last change in the editor (same as pressing Ctrl+Z). Every MCP '
    'edit is one undo step, so this also reverts what the agent just did.',
    {
        'type': 'object',
        'properties': {
            'steps': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 1,
                      'description': 'How many steps to undo.'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Undo'},
)
def undo(args):
    manager_ = manager()
    stack = manager_._undo_stack
    done = 0
    for _ in range(args['steps']):
        if not stack.canUndo():
            break
        stack.undo()
        done += 1
    return {'undone': done, 'undo': undo_state()}


@tool(
    'redo',
    'Redo changes that were undone (same as Ctrl+Y).',
    {
        'type': 'object',
        'properties': {
            'steps': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 1,
                      'description': 'How many steps to redo.'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Redo'},
)
def redo(args):
    manager_ = manager()
    stack = manager_._undo_stack
    done = 0
    for _ in range(args['steps']):
        if not stack.canRedo():
            break
        stack.redo()
        done += 1
    return {'redone': done, 'undo': undo_state()}


@tool(
    'log_to_console',
    'Write a line to the editor console so the user can follow what the agent '
    'is doing (shows up in the Console panel).',
    {
        'type': 'object',
        'properties': {
            'message': {'type': 'string', 'description': 'Text to print.'},
            'level': {'type': 'string', 'enum': ['info', 'warning', 'error'],
                      'default': 'info'},
        },
        'required': ['message'],
        'additionalProperties': False,
    },
    annotations={'title': 'Log to the editor console'},
)
def log_to_console(args):
    from pygamestudio.gui.console.logger import Logger
    level = args.get('level', 'info')
    getattr(Logger, level if level in ('info', 'warning', 'error') else 'info')(args['message'])
    return 'logged'


@tool(
    'object_types',
    'List the scene object types that can be created and, for each one, the '
    'properties that can be set on it (the same list the inspector shows). '
    'Use this before create_object/update_object to get the exact property names.',
    {
        'type': 'object',
        'properties': {
            'type': {'type': 'string', 'description': 'Only this object type (optional).'},
        },
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Object types and properties'},
)
def object_types(args):
    wanted = (args.get('type') or '').upper()
    properties = type_properties()
    common = ['name', 'x', 'y', 'width', 'height', 'angle', 'visible', 'color',
              'script_path', 'scale_x', 'scale_y', 'collision_enabled',
              'collision_type', 'collision_offset_x', 'collision_offset_y',
              'collision_width', 'collision_height', 'collision_points']
    result = {
        'creatable_types': object_type_names(),
        'common_properties': sorted(set(common)),
        'type_specific_properties': properties,
        'notes': [
            'Positions (x, y) are relative to the parent object; width/height set the size.',
            'script_path is project relative, e.g. "./script/player.py".',
            'color is [r, g, b] or [r, g, b, a] with 0-255 per channel.',
            'collision_* properties only matter when collision_enabled is true.',
        ],
    }
    if wanted:
        if wanted not in properties:
            raise ToolError('Unknown type "{}". Known: {}'.format(
                wanted, ', '.join(object_type_names())))
        result = {'type': wanted, 'properties': properties[wanted]}
    return result


@tool(
    'capture_scene_view',
    'Take a PNG screenshot of the editor scene view (what the user sees in the '
    'Scene panel) and return it as an image. Use it to check how the scene '
    'looks after a change. Coordinates are in scene (= canvas) units.',
    {
        'type': 'object',
        'properties': {
            'x': {'type': 'number', 'description': 'Left edge of the region (default: canvas left).'},
            'y': {'type': 'number', 'description': 'Top edge of the region (default: canvas top).'},
            'width': {'type': 'number', 'description': 'Region width (default: canvas width).'},
            'height': {'type': 'number', 'description': 'Region height (default: canvas height).'},
            'scale': {'type': 'number', 'minimum': 0.1, 'maximum': 2, 'default': 1,
                      'description': 'Scale factor of the returned image (0.5 = half size, cheaper for the model).'},
        },
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Screenshot of the scene view'},
)
def capture_scene_view(args):
    body = bridge.editor_body_or_none()
    if body is None:
        raise ToolError('The editor window is not available, so the scene cannot be captured.')

    try:
        from PySide6.QtCore import QPoint, Qt, QBuffer, QIODevice
        from PySide6.QtGui import QImage, QRegion
    except ImportError as e:
        raise ToolError('Qt is not available: {}'.format(e))

    scene_window = getattr(body, '_scene_widnow', None)
    pygame_screen = getattr(scene_window, '_pygame_screen', None)
    if pygame_screen is None:
        raise ToolError('The scene view is not available in this editor build.')

    manager_ = manager()
    canvas = manager_.get_object(manager_.canvas_object_uuid) if manager_.canvas_object_uuid else None
    canvas_width = int(canvas.width) if canvas is not None else 800
    canvas_height = int(canvas.height) if canvas is not None else 600

    x = float(args.get('x', 0))
    y = float(args.get('y', 0))
    width = float(args.get('width', canvas_width))
    height = float(args.get('height', canvas_height))
    if width <= 0 or height <= 0:
        raise ToolError('The capture region must have a positive size.')

    ox, oy = pygame_screen.scene_offset()
    image = QImage(int(width), int(height), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    # render() needs integers; the scene view maps scene (x, y) to widget (x + ox, y + oy).
    pygame_screen.render(image, QPoint(0, 0),
                         QRegion(int(round(x)) + ox, int(round(y)) + oy, int(width), int(height)))

    scale = float(args.get('scale', 1) or 1)
    if abs(scale - 1.0) > 0.001:
        from PySide6.QtCore import Qt as _Qt
        image = image.scaled(max(1, int(width * scale)), max(1, int(height * scale)),
                             _Qt.AspectRatioMode.IgnoreAspectRatio,
                             _Qt.TransformationMode.SmoothTransformation)

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, 'PNG'):
        raise ToolError('The screenshot could not be encoded as PNG.')
    from pygamestudio.mcp.protocol import image_content
    png = bytes(buffer.data())
    return {'content': [
        {'type': 'text', 'text': 'Scene view capture: x={} y={} w={} h={} scale={} (canvas {}x{})'.format(
            int(x), int(y), int(width), int(height), scale, canvas_width, canvas_height)},
        image_content(png),
    ], 'isError': False}


@tool(
    'list_editor_panels',
    'List the editor panels (scene, code editor, console, inspector, ...) and '
    'which one is currently visible, so an agent can talk about the same UI the '
    'user sees.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Editor panels'},
)
def list_editor_panels(args):
    body = bridge.editor_body_or_none()
    if body is None:
        raise ToolError('The editor window is not available.')

    panels = []
    for attr, label in (
            ('_scene_widnow', 'Scene'),
            ('_code_editor_window', 'Code Editor'),
            ('_block_editor_window', 'Block Editor'),
            ('_image_editor_window', 'Image Editor'),
            ('_tile_map_editor_window', 'Tile Map Editor'),
            ('_console_window', 'Console'),
            ('_audio_player_window', 'Audio Player'),
            ('_hierarchy_window', 'Hierarchy'),
            ('_asset_window', 'Asset'),
            ('_inspector_window', 'Inspector'),
            ('_build_window', 'Build')):
        widget = getattr(body, attr, None)
        if widget is None:
            continue
        tab_widget = getattr(widget, '_tab_widget', None)
        docked = tab_widget is not None and tab_widget.indexOf(widget) >= 0
        panels.append({
            'name': label,
            'visible': bool(widget.isVisible()),
            'current': bool(docked and tab_widget.currentWidget() is widget),
            'tab': tab_widget.tabText(tab_widget.indexOf(widget)) if docked else None,
        })
    return {'panels': panels}


@register_resource(
    'pygs://project/info',
    'Project info',
    'Project folder, config, current scene and the object count.',
    'application/json')
def _project_info_resource():
    manager_ = manager()
    return json_value({
        'project_path': manager_.get_project_path(),
        'project_name': project_path().name,
        'scene_path': manager_.current_scene_file_path,
        'scene_saved': manager_.is_current_scene_saved,
        'canvas': {
            'width': getattr(manager_.get_object(manager_.canvas_object_uuid), 'width', None),
            'height': getattr(manager_.get_object(manager_.canvas_object_uuid), 'height', None),
        } if manager_.canvas_object_uuid else None,
    })


@tool(
    'open_in_code_editor',
    'Open a project file in the editor code editor (optionally at a line) so '
    'the user can see it. Does not change anything on disk.',
    {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'description': 'Project-relative path, e.g. "./script/player.py".'},
            'line': {'type': 'integer', 'minimum': 1, 'default': 1},
        },
        'required': ['path'],
        'additionalProperties': False,
    },
    annotations={'title': 'Open file in the code editor'},
)
def open_in_code_editor(args):
    file_path = safe_project_path(args['path'], must_exist=True)
    body = bridge.editor_body_or_none()
    if body is None:
        raise ToolError('The editor window is not available.')
    editor_window = getattr(body, '_code_editor_window', None)
    if editor_window is None:
        raise ToolError('The code editor is not available in this editor build.')
    editor_window.open_file_at_line(str(file_path), int(args.get('line', 1)))
    return 'opened {} in the code editor'.format(project_relative(file_path))
