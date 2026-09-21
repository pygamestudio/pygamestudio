"""MCP tools for the editing panels: block editor, image editor, tile map
editor and audio player - plus ``open_panel`` to bring any panel into view.

These tools drive the SAME widgets the user works in, so every change shows
up immediately in the editor:

* the block editor tools edit the block workspace of the open script - the
  same workspace its own Ctrl+S writes back into the ``.py`` file;
* the image editor tools paint on its canvas and use its own undo stack;
* the tile map tools paint cells and manage layers through the
  ``GameManager``, so they are undoable with the editor's Ctrl+Z;
* the audio player tools open a file and control playback.

Nothing here opens a modal dialog: paths and sizes are arguments, and an
unsaved image is saved (or reported) instead of prompting.
"""

from pathlib import Path

from pygamestudio.mcp.bridge import bridge
from pygamestudio.mcp.registry import ToolError, tool
from pygamestudio.mcp.tools.context import (
    manager, project_relative, resolve_object, safe_project_path,
)

# ------------------------------------------------------------------- panels
#: panel key -> (EditorBody attribute, label, window-showing method)
_PANELS = {
    'scene': ('_scene_widnow', 'Scene', None),
    'code': ('_code_editor_window', 'Code Editor', None),
    'block': ('_block_editor_window', 'Block Editor', None),
    'image': ('_image_editor_window', 'Image Editor', None),
    'tile_map': ('_tile_map_editor_window', 'Tile Map Editor', None),
    'console': ('_console_window', 'Console', None),
    'audio': ('_audio_player_window', 'Audio Player', None),
    'hierarchy': ('_hierarchy_window', 'Hierarchy', None),
    'assets': ('_asset_window', 'Asset', None),
    'inspector': ('_inspector_window', 'Inspector', None),
    'agent': ('_agent_window', 'AI Agent', None),
    'build': ('_build_window', 'Build', '_show_build_window'),
    'project_settings': ('_project_settings_window', 'Project Settings',
                         '_show_project_settings_window'),
    'editor_settings': ('_editor_settings_window', 'Editor Settings',
                        '_show_editor_settings_window'),
}


def _body():
    body = bridge.editor_body_or_none()
    if body is None:
        raise ToolError('The editor window is not available.')
    return body


def _require_panel(attr, label):
    widget = getattr(_body(), attr, None)
    if widget is None:
        raise ToolError('This editor build has no {} panel.'.format(label))
    return widget


def _focus(widget):
    """Bring a docked or detached panel into view. Returns how it was shown."""
    tabs = getattr(widget, '_tab_widget', None)
    if tabs is not None:
        index = tabs.indexOf(widget)
        if index >= 0:
            if hasattr(tabs, 'isTabVisible') and not tabs.isTabVisible(index):
                # hidden from the Window menu: show it again before selecting
                tabs.setTabVisible(index, True)
            tabs.setCurrentWidget(widget)
    raiser = getattr(widget, 'raise_editor', None)
    if callable(raiser):
        raiser()
    else:
        raise_window = getattr(widget, '_raise_window', None)
        if callable(raise_window):
            raise_window()
        else:
            standalone = getattr(widget, '_standalone_window', None)
            is_detached = getattr(widget, 'is_detached', None)
            if standalone is not None and callable(is_detached) and is_detached():
                standalone.show()
                standalone.raise_()
                standalone.activateWindow()
    if getattr(widget, 'is_detached', None) and widget.is_detached():
        return 'detached'
    tabs = getattr(widget, '_tab_widget', None)
    if tabs is not None and tabs.indexOf(widget) >= 0:
        return 'tab' if tabs.currentWidget() is widget else 'other tab'
    return 'visible' if widget.isVisible() else 'hidden'


# =================================================================== panels
@tool(
    'open_panel',
    'Bring one of the editor panels into view: selects its tab (or raises the '
    'floating window when the user detached it) and re-shows a tab hidden '
    'from the Window menu. Does not change any project data. Panels: scene, '
    'code, block, image, tile_map, console, audio, hierarchy, assets, '
    'inspector, agent, build, project_settings, editor_settings.',
    {
        'type': 'object',
        'properties': {
            'panel': {
                'type': 'string',
                'enum': sorted(_PANELS),
                'description': 'Which panel to show.',
            },
        },
        'required': ['panel'],
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Show an editor panel'},
)
def open_panel(args):
    name = args['panel']
    attr, label, show_method = _PANELS[name]
    body = _body()
    widget = getattr(body, attr, None)

    if show_method:
        shower = getattr(body, show_method, None)
        if widget is None or not callable(shower):
            raise ToolError('The {} window is not available in this editor build.'.format(label))
        shower()
        return {'panel': name, 'title': label,
                'visible': bool(widget.isVisible()), 'mode': 'window'}

    if widget is None:
        raise ToolError('This editor build has no {} panel.'.format(label))
    mode = _focus(widget)
    return {'panel': name, 'title': label,
            'visible': bool(widget.isVisible()), 'mode': mode}


# ============================================================= block editor
def _block_window():
    return _require_panel('_block_editor_window', 'Block Editor')


def _block_canvas():
    return _block_window().canvas()


def _block_workspace(canvas):
    workspace = canvas.workspace()
    if not isinstance(workspace.get('stacks'), list):
        workspace['stacks'] = []
    return workspace


def _count_blocks(workspace):
    from pygamestudio.gui.block_editor.model import walk
    return sum(1 for stack in workspace.get('stacks', []) for _ in walk([stack]))


def _block_summary(block):
    from pygamestudio.gui.block_editor.registry import get_definition, label_text
    definition = get_definition(block.get('type'))
    return {
        'id': block.get('id'),
        'type': block.get('type'),
        'label': label_text(definition) if definition else None,
    }


def _find_block(workspace, block_id):
    from pygamestudio.gui.block_editor.model import find_block
    _, _, block = find_block(workspace.get('stacks', []), block_id)
    if block is None:
        raise ToolError(
            'Unknown block id "{}" - call block_editor_get_blocks to list the '
            'blocks of the workspace.'.format(block_id))
    return block


def _coerce_block_value(spec, value):
    """Turn a JSON value into the value the workspace should store."""
    from pygamestudio.gui.block_editor import registry as block_registry

    kind = spec['kind']
    if value is None:
        raise ToolError('A value is required for field "{}".'.format(spec['name']))
    if kind == 'number':
        if isinstance(value, bool):
            raise ToolError('Field "{}" is a number.'.format(spec['name']))
        if isinstance(value, (int, float)):
            number = float(value)
        else:
            try:
                number = float(str(value).strip())
            except ValueError:
                raise ToolError('Field "{}" needs a number, got "{}".'.format(
                    spec['name'], value))
        return int(number) if number.is_integer() else number

    options = block_registry.options_for(kind)
    if options:
        if kind == 'toggle' and isinstance(value, bool):
            value = 'True' if value else 'False'
        codes = [option[0] for option in options]
        if value in codes:
            return value
        lookup = {}
        for option in options:
            lookup[str(option[0]).strip().lower()] = option[0]
            lookup[block_registry.option_text(option).strip().lower()] = option[0]
        found = lookup.get(str(value).strip().lower())
        if found is None:
            sample = ', '.join(options[index][0] for index in range(min(8, len(options))))
            raise ToolError(
                '"{value}" is not a valid value for field "{field}" (kind {kind}). '
                'Examples: {sample}, ... Call block_editor_list_types for the full '
                'list.'.format(value=value, field=spec['name'], kind=kind, sample=sample))
        return found

    if isinstance(value, (str, int, float, bool)):
        return value if not isinstance(value, bool) else str(value)
    return str(value)


@tool(
    'block_editor_open',
    'Open a project script in the Block Editor panel (any object script can '
    'hold blocks; the file is only modified when blocks are saved). Brings '
    'the panel into view. Paths are project relative.',
    {
        'type': 'object',
        'properties': {
            'path': {'type': 'string',
                     'description': 'Script to open, e.g. "./script/player.py".'},
        },
        'required': ['path'],
        'additionalProperties': False,
    },
    annotations={'title': 'Open a script in the block editor'},
)
def block_editor_open(args):
    from pygamestudio.gui.block_editor import storage

    window = _block_window()
    target = safe_project_path(args['path'])
    window.open_file(str(target))
    canvas = window.canvas()
    return {
        'file': project_relative(target),
        'is_block_script': storage.is_block_script(target),
        'modified': canvas.is_modified(),
        'blocks': _count_blocks(_block_workspace(canvas)),
    }


@tool(
    'block_editor_list_types',
    'List the block types of the visual script editor: type id, category, '
    'label, shape and every field (name, kind, default and - for dropdowns - '
    'the accepted values). Use it to pick the ids for block_editor_add_block '
    'and the exact values for block_editor_set_field.',
    {
        'type': 'object',
        'properties': {
            'category': {'type': 'string', 'enum': ['event', 'action', 'physics', 'control'],
                         'description': 'Only the blocks of this category (optional).'},
        },
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Block types of the block editor'},
)
def block_editor_list_types(args):
    from pygamestudio.gui.block_editor import registry as block_registry

    wanted = args.get('category')
    if wanted and block_registry.get_category(wanted) is None:
        raise ToolError('Unknown category "{}". Known: {}.'.format(
            wanted, ', '.join(item['key'] for item in block_registry.CATEGORIES)))

    types = []
    for definition in block_registry.definitions():
        if wanted and definition['category'] != wanted:
            continue
        fields = []
        for spec in definition['fields']:
            entry = {'name': spec['name'], 'kind': spec['kind'],
                     'default': spec['default']}
            options = block_registry.options_for(spec['kind'])
            if options:
                entry['options'] = [
                    {'value': option[0], 'label': block_registry.option_text(option)}
                    for option in options
                ]
            fields.append(entry)
        types.append({
            'type': definition['type'],
            'category': definition['category'],
            'label': block_registry.label_text(definition),
            'shape': definition['shape'],
            'fields': fields,
        })
    return {
        'categories': [{'key': item['key'], 'label': block_registry.category_text(item)}
                       for item in block_registry.CATEGORIES],
        'types': types,
    }


@tool(
    'block_editor_get_blocks',
    'Read the block workspace the block editor currently shows: the file, '
    'whether it has unsaved changes and the nested block stacks (id, type, '
    'label, fields and their body/else children).',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Blocks of the block editor'},
)
def block_editor_get_blocks(args):
    from pygamestudio.gui.block_editor import storage
    from pygamestudio.gui.block_editor.registry import (
        field_value, get_definition, label_text,
    )

    canvas = _block_canvas()
    path = canvas.file_path()
    workspace = _block_workspace(canvas)

    def render(block):
        definition = get_definition(block.get('type'))
        entry = _block_summary(block)
        fields = {}
        if definition is not None:
            for spec in definition['fields']:
                fields[spec['name']] = field_value(block, definition, spec['name'])
        if fields:
            entry['fields'] = fields
        for key in ('body', 'else'):
            if isinstance(block.get(key), list):
                entry[key] = [render(child) for child in block[key]]
        return entry

    return {
        'open': path is not None,
        'file': project_relative(path) if path else None,
        'is_block_script': bool(path) and storage.is_block_script(path),
        'modified': canvas.is_modified(),
        'stacks': [render(stack) for stack in workspace['stacks']],
    }


@tool(
    'block_editor_add_block',
    'Add a block to the workspace the block editor shows. Without "parent" a '
    'new top-level stack is placed on the canvas (x/y optional); with '
    '"parent" the block is inserted into that block\'s "body" or "else" '
    'slot at "index". Returns the new block id. Use block_editor_list_types '
    'for the type ids.',
    {
        'type': 'object',
        'properties': {
            'type': {'type': 'string', 'description': 'Block type id, e.g. "event_start".'},
            'parent': {'type': 'string',
                       'description': 'Block id to nest into (optional).'},
            'slot': {'type': 'string', 'enum': ['body', 'else'], 'default': 'body',
                     'description': 'Which statement list of the parent to use.'},
            'index': {'type': 'integer', 'minimum': 0,
                      'description': 'Position inside the slot (default: append).'},
            'x': {'type': 'number', 'description': 'Canvas x of a new top-level stack.'},
            'y': {'type': 'number', 'description': 'Canvas y of a new top-level stack.'},
        },
        'required': ['type'],
        'additionalProperties': False,
    },
    annotations={'title': 'Add a block'},
)
def block_editor_add_block(args):
    from pygamestudio.gui.block_editor import model as block_model
    from pygamestudio.gui.block_editor.registry import get_definition

    canvas = _block_canvas()
    definition = get_definition(args['type'])
    if definition is None:
        raise ToolError(
            'Unknown block type "{}" - call block_editor_list_types for the '
            'type ids.'.format(args['type']))

    workspace = _block_workspace(canvas)
    parent_id = args.get('parent')

    if parent_id:
        parent = _find_block(workspace, parent_id)
        slot = args.get('slot') or 'body'
        target = parent.get(slot)
        if not isinstance(target, list):
            raise ToolError('The block "{}" has no "{}" slot - use "body" or "else" '
                            'of an event / control block.'.format(parent_id, slot))
        canvas.push_undo()
        block = block_model.new_block(args['type'])
        block_model.insert_block(block, target,
                                 args['index'] if args.get('index') is not None else len(target))
    else:
        x = args.get('x')
        y = args.get('y')
        if x is None:
            x = 40
        if y is None:
            y = 40 + 130 * len(workspace['stacks'])
        canvas.push_undo()
        block = block_model.new_stack(args['type'], x, y)
        workspace['stacks'].append(block)

    canvas.rebuild()
    canvas.schedule_save()
    return {'block': _block_summary(block), 'modified': canvas.is_modified()}


@tool(
    'block_editor_set_field',
    'Change one field of a block in the block editor (the same edit as '
    'clicking the field). Dropdown fields accept the option code or its '
    'label; number fields accept numbers. Undoable in the block editor.',
    {
        'type': 'object',
        'properties': {
            'block': {'type': 'string', 'description': 'Block id.'},
            'field': {'type': 'string', 'description': 'Field name.'},
            'value': {'description': 'New value (string, number, boolean).'},
        },
        'required': ['block', 'field'],
        'additionalProperties': False,
    },
    annotations={'title': 'Set a block field'},
)
def block_editor_set_field(args):
    from pygamestudio.gui.block_editor import registry as block_registry

    canvas = _block_canvas()
    workspace = _block_workspace(canvas)
    block = _find_block(workspace, args['block'])
    definition = block_registry.get_definition(block.get('type'))
    spec = block_registry.field_spec(definition, args['field']) if definition else None
    if spec is None:
        names = [item['name'] for item in (definition or {}).get('fields', [])]
        raise ToolError('The block has no field "{}". Fields: {}.'.format(
            args['field'], ', '.join(names) if names else '(none)'))
    value = _coerce_block_value(spec, args.get('value'))
    canvas.set_field(args['block'], args['field'], value)
    return {'block': args['block'], 'field': args['field'], 'value': value,
            'modified': canvas.is_modified()}


@tool(
    'block_editor_move_block',
    'Move a block (with its subtree) inside the workspace: into the "body" '
    'or "else" slot of another block at "index", or back to the canvas as a '
    'top-level stack when no parent is given.',
    {
        'type': 'object',
        'properties': {
            'block': {'type': 'string', 'description': 'Block id to move.'},
            'parent': {'type': 'string',
                       'description': 'New parent block id (optional: canvas).'},
            'slot': {'type': 'string', 'enum': ['body', 'else'], 'default': 'body'},
            'index': {'type': 'integer', 'minimum': 0,
                      'description': 'Position inside the slot (default: append).'},
        },
        'required': ['block'],
        'additionalProperties': False,
    },
    annotations={'title': 'Move a block'},
)
def block_editor_move_block(args):
    from pygamestudio.gui.block_editor import model as block_model

    canvas = _block_canvas()
    workspace = _block_workspace(canvas)
    block = _find_block(workspace, args['block'])
    parent_id = args.get('parent')

    if parent_id:
        if parent_id == args['block']:
            raise ToolError('A block cannot be moved into itself.')
        parent = _find_block(workspace, parent_id)
        if block_model.is_descendant(block, parent_id):
            raise ToolError('A block cannot be moved into its own subtree.')
        slot = args.get('slot') or 'body'
        target = parent.get(slot)
        if not isinstance(target, list):
            raise ToolError('The block "{}" has no "{}" slot.'.format(parent_id, slot))
    else:
        target = workspace['stacks']

    canvas.push_undo()
    moved, _, _ = block_model.remove_segment(workspace['stacks'], args['block'])
    if target is workspace['stacks'] and 'x' not in moved:
        moved['x'] = 40
        moved['y'] = 40 + 130 * len(workspace['stacks'])
    index = args.get('index')
    block_model.insert_block(moved, target, len(target) if index is None else index)
    canvas.rebuild()
    canvas.schedule_save()
    return {'block': _block_summary(moved), 'modified': canvas.is_modified()}


@tool(
    'block_editor_delete_block',
    'Delete a block and its subtree from the block editor (undoable there).',
    {
        'type': 'object',
        'properties': {
            'block': {'type': 'string', 'description': 'Block id.'},
        },
        'required': ['block'],
        'additionalProperties': False,
    },
    annotations={'title': 'Delete a block'},
)
def block_editor_delete_block(args):
    canvas = _block_canvas()
    workspace = _block_workspace(canvas)
    _find_block(workspace, args['block'])          # raises when unknown
    canvas.delete_block(args['block'])
    return {'deleted': args['block'], 'modified': canvas.is_modified()}


@tool(
    'block_editor_save',
    'Save the block workspace into its script file now (the block editor '
    'also auto-saves, this forces it). Returns the file and the callbacks '
    'the blocks generate.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'title': 'Save the block editor'},
)
def block_editor_save(args):
    from pygamestudio.gui.block_editor.generator import generated_callbacks

    canvas = _block_canvas()
    path = canvas.file_path()
    if not path:
        raise ToolError('The block editor has no file open - call block_editor_open first.')
    canvas.save_now()
    return {
        'saved': project_relative(path),
        'modified': canvas.is_modified(),
        'callbacks': generated_callbacks(canvas.workspace()),
    }


# ============================================================= image editor
def _image_window():
    return _require_panel('_image_editor_window', 'Image Editor')


def _image_canvas():
    return getattr(_image_window(), '_canvas')


def _image_state():
    window = _image_window()
    canvas = _image_canvas()
    current = getattr(window, '_file_path', None)
    color = canvas.current_color()
    width, height = canvas.image_size()
    return {
        'open': canvas.has_image(),
        'file': project_relative(current) if current else None,
        'width': width,
        'height': height,
        'modified': canvas.is_modified(),
        'tool': canvas.tool(),
        'brush_size': canvas.brush_size(),
        'color': [color.red(), color.green(), color.blue(), color.alpha()],
        'zoom': round(canvas.zoom(), 4),
        'can_undo': canvas.can_undo(),
        'can_redo': canvas.can_redo(),
    }


def _flush_pending_image_changes(window, canvas):
    """Never open a dialog: save the pending image, or fail with a hint."""
    if not canvas.is_modified():
        return
    current = getattr(window, '_file_path', None)
    if current is None:
        raise ToolError(
            'The image editor has unsaved changes and no file path yet - save it '
            'first with image_editor_save (pass "path").')
    if not canvas.save(str(current)):
        raise ToolError('Could not save the pending changes of "{}".'.format(current))
    updater = getattr(window, '_update_titles', None)
    if callable(updater):
        updater()


@tool(
    'image_editor_open',
    'Open an image in the Image Editor, or create a new transparent one. '
    'Pass "path" for an existing project image, or "width"/"height" for a '
    'new image (saved later with image_editor_save). Unsaved changes are '
    'saved first when possible (never a dialog).',
    {
        'type': 'object',
        'properties': {
            'path': {'type': 'string',
                     'description': 'Project-relative image, e.g. "./image/hero.png".'},
            'width': {'type': 'integer', 'minimum': 1, 'maximum': 16384,
                      'description': 'Width of a NEW image.'},
            'height': {'type': 'integer', 'minimum': 1, 'maximum': 16384,
                       'description': 'Height of a NEW image.'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Open or create an image'},
)
def image_editor_open(args):
    from PySide6.QtGui import QImage

    window = _image_window()
    canvas = _image_canvas()
    _flush_pending_image_changes(window, canvas)

    if args.get('path'):
        target = safe_project_path(args['path'], must_exist=True)
        if not window._load_image_file(str(target)):
            raise ToolError('"{}" could not be loaded as an image.'.format(args['path']))
        _focus(window)
        return _image_state()

    width = args.get('width')
    height = args.get('height')
    if not width or not height:
        raise ToolError('Pass "path", or "width" and "height" for a new image.')

    image = QImage(int(width), int(height), QImage.Format.Format_ARGB32)
    image.fill(0)                       # fully transparent, like the New dialog
    window._file_path = None
    canvas.set_image(image)
    for name in ('_update_enabled_state', '_update_size_label', '_update_titles'):
        updater = getattr(window, name, None)
        if callable(updater):
            updater()
    canvas.actual_size()
    _focus(window)
    return _image_state()


@tool(
    'image_editor_state',
    'What the Image Editor shows: file, size, drawing tool, brush size, '
    'color, zoom and undo state. Call it before the drawing tools.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Image editor state'},
)
def image_editor_state(args):
    return _image_state()


@tool(
    'image_editor_set_tool',
    'Select the drawing tool of the image editor (same buttons as the '
    'toolbar): pencil, eraser, line, rect, ellipse, fill or picker.',
    {
        'type': 'object',
        'properties': {
            'tool': {'type': 'string',
                     'enum': ['pencil', 'eraser', 'line', 'rect', 'ellipse',
                              'fill', 'picker']},
        },
        'required': ['tool'],
        'additionalProperties': False,
    },
    annotations={'title': 'Select an image editor tool'},
)
def image_editor_set_tool(args):
    window = _image_window()
    canvas = _image_canvas()
    activate = getattr(window, '_activate_tool', None)
    if callable(activate):
        activate(args['tool'])
    else:
        canvas.set_tool(args['tool'])
    return {'tool': canvas.tool()}


@tool(
    'image_editor_set_color',
    'Set the drawing color of the image editor (and optionally the brush '
    'size in pixels). Color is [r, g, b] or [r, g, b, a], 0-255 per channel.',
    {
        'type': 'object',
        'properties': {
            'color': {'type': 'array', 'minItems': 3, 'maxItems': 4,
                      'items': {'type': 'integer', 'minimum': 0, 'maximum': 255},
                      'description': 'New color, e.g. [255, 0, 0].'},
            'brush_size': {'type': 'integer', 'minimum': 1, 'maximum': 512,
                           'description': 'Brush size in pixels (optional).'},
        },
        'required': ['color'],
        'additionalProperties': False,
    },
    annotations={'title': 'Set the image editor color'},
)
def image_editor_set_color(args):
    window = _image_window()
    window.set_color(args['color'])
    if args.get('brush_size') is not None:
        spin = getattr(window, '_brush_spinbox', None)
        if spin is not None:
            spin.setValue(int(args['brush_size']))   # syncs the canvas too
        else:
            _image_canvas().set_brush_size(int(args['brush_size']))
    canvas = _image_canvas()
    color = canvas.current_color()
    return {'color': [color.red(), color.green(), color.blue(), color.alpha()],
            'brush_size': canvas.brush_size()}


@tool(
    'image_editor_draw',
    'Draw a polyline on the image with the current tool (pencil by default, '
    'eraser to erase); each point is [x, y] in image pixels. Use '
    'image_editor_fill for flood fill. One undo step (the image editor\'s '
    'Ctrl+Z).',
    {
        'type': 'object',
        'properties': {
            'points': {'type': 'array', 'minItems': 1,
                       'items': {'type': 'array', 'minItems': 2, 'items': {'type': 'number'}},
                       'description': 'Stroke points: [[x, y], [x, y], ...].'},
            'color': {'type': 'array', 'minItems': 3, 'maxItems': 4,
                      'items': {'type': 'integer', 'minimum': 0, 'maximum': 255},
                      'description': 'Temporary color for this stroke (optional).'},
            'brush_size': {'type': 'integer', 'minimum': 1, 'maximum': 512,
                           'description': 'Temporary brush size for this stroke (optional).'},
        },
        'required': ['points'],
        'additionalProperties': False,
    },
    annotations={'title': 'Draw on the image'},
)
def image_editor_draw(args):
    canvas = _image_canvas()
    if not canvas.has_image():
        raise ToolError('The image editor has no image open - call image_editor_open first.')

    points = []
    for point in args['points']:
        if len(point) < 2:
            raise ToolError('Every point needs [x, y].')
        points.append((int(round(float(point[0]))), int(round(float(point[1])))))

    old_color = canvas.current_color()
    old_brush = canvas.brush_size()
    canvas._push_undo()
    try:
        if args.get('color') is not None:
            canvas.set_color(args['color'])
        if args.get('brush_size') is not None:
            canvas.set_brush_size(int(args['brush_size']))
        previous = points[0]
        canvas._stamp_point(previous, previous)
        for point in points[1:]:
            canvas._stamp_point(previous, point)
            previous = point
    finally:
        canvas.set_color(old_color)
        canvas.set_brush_size(old_brush)
    canvas.update()
    return {'drawn': len(points), 'tool': canvas.tool()}


@tool(
    'image_editor_fill',
    'Flood fill on the image, starting at pixel (x, y) - the same as the '
    'fill tool. Uses the current color unless "color" is given. One undo '
    'step.',
    {
        'type': 'object',
        'properties': {
            'x': {'type': 'integer', 'minimum': 0},
            'y': {'type': 'integer', 'minimum': 0},
            'color': {'type': 'array', 'minItems': 3, 'maxItems': 4,
                      'items': {'type': 'integer', 'minimum': 0, 'maximum': 255},
                      'description': 'Fill color (optional: current color).'},
        },
        'required': ['x', 'y'],
        'additionalProperties': False,
    },
    annotations={'title': 'Fill an area of the image'},
)
def image_editor_fill(args):
    from PySide6.QtGui import QColor

    canvas = _image_canvas()
    if not canvas.has_image():
        raise ToolError('The image editor has no image open - call image_editor_open first.')
    width, height = canvas.image_size()
    x, y = int(args['x']), int(args['y'])
    if not (0 <= x < width and 0 <= y < height):
        raise ToolError('({}, {}) is outside the image ({}x{}).'.format(x, y, width, height))

    color = QColor(*[int(channel) for channel in args['color']]) if args.get('color') is not None \
        else canvas.current_color()
    canvas._push_undo()
    canvas._flood_fill(x, y, color)
    canvas.update()
    return {'filled_at': [x, y]}


@tool(
    'image_editor_transform',
    'Transform the image: flip_h, flip_v, rotate_cw, rotate_ccw or clear '
    '(transparent), plus undo / redo of the image editor itself. Each '
    'transform is one undo step.',
    {
        'type': 'object',
        'properties': {
            'action': {'type': 'string',
                       'enum': ['flip_h', 'flip_v', 'rotate_cw', 'rotate_ccw',
                                'clear', 'undo', 'redo']},
        },
        'required': ['action'],
        'additionalProperties': False,
    },
    annotations={'title': 'Transform the image'},
)
def image_editor_transform(args):
    canvas = _image_canvas()
    if not canvas.has_image():
        raise ToolError('The image editor has no image open - call image_editor_open first.')
    action = args['action']
    {
        'flip_h': canvas.flip_h,
        'flip_v': canvas.flip_v,
        'rotate_cw': canvas.rotate_cw,
        'rotate_ccw': canvas.rotate_ccw,
        'clear': canvas.clear,
        'undo': canvas.undo,
        'redo': canvas.redo,
    }[action]()
    return _image_state()


@tool(
    'image_editor_save',
    'Save the image editor image. Without "path" it is written to the file '
    'it was opened from; with "path" it is a Save As (a missing suffix '
    'becomes .png). The folder must be inside the project.',
    {
        'type': 'object',
        'properties': {
            'path': {'type': 'string',
                     'description': 'Project-relative target of a Save As (optional).'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Save the image'},
)
def image_editor_save(args):
    window = _image_window()
    canvas = _image_canvas()
    if not canvas.has_image():
        raise ToolError('The image editor has no image open - call image_editor_open first.')

    if args.get('path'):
        target = safe_project_path(args['path'])
        if not target.suffix:
            target = target.with_suffix('.png')
    else:
        target = getattr(window, '_file_path', None)
        if target is None:
            raise ToolError('The image has no file path yet - pass "path".')

    if not canvas.save(str(target)):
        raise ToolError('Could not save the image to "{}" (unknown format?).'.format(target))
    window._file_path = Path(target)
    updater = getattr(window, '_update_titles', None)
    if callable(updater):
        updater()
    return {'saved': project_relative(target), 'modified': canvas.is_modified()}


@tool(
    'image_editor_capture',
    'Screenshot of the image editor content as a PNG (what the user sees, '
    'not the scene). "scale" below 1 returns a smaller image.',
    {
        'type': 'object',
        'properties': {
            'scale': {'type': 'number', 'minimum': 0.05, 'maximum': 4, 'default': 1,
                      'description': 'Scale factor of the returned PNG.'},
        },
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Screenshot of the image editor'},
)
def image_editor_capture(args):
    from PySide6.QtCore import QBuffer, QIODevice, Qt as QtCore_Qt

    canvas = _image_canvas()
    if not canvas.has_image():
        raise ToolError('The image editor has no image open - call image_editor_open first.')

    image = canvas.image()
    scale = float(args.get('scale', 1) or 1)
    if abs(scale - 1.0) > 0.001:
        image = image.scaled(max(1, int(image.width() * scale)),
                             max(1, int(image.height() * scale)),
                             QtCore_Qt.AspectRatioMode.IgnoreAspectRatio,
                             QtCore_Qt.TransformationMode.SmoothTransformation)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, 'PNG'):
        raise ToolError('The image could not be encoded as PNG.')
    from pygamestudio.mcp.protocol import image_content
    png = bytes(buffer.data())
    return {'content': [
        {'type': 'text', 'text': 'Image editor capture: {}x{} (file: {})'.format(
            image.width(), image.height(), _image_state()['file'])},
        image_content(png),
    ], 'isError': False}


# ========================================================== tile map editor
def _tile_window():
    return _require_panel('_tile_map_editor_window', 'Tile Map Editor')


def _tile_canvas(window):
    """The canvas of the tile map window ('canvas' is a property there)."""
    canvas = getattr(window, 'canvas', None)
    return canvas() if callable(canvas) else canvas


def _tile_object(required=True):
    window = _tile_window()
    manager_ = manager()
    uuid = window.current_object_uuid()
    obj = manager_.get_object(uuid) if uuid else None
    if obj is None and required:
        raise ToolError(
            'The tile map editor is not bound to a tile map - call '
            'tile_map_editor_open with the uuid or name of a TILE_MAP object '
            'first (create_object can make one).')
    return obj


def _layer_index(obj, value):
    if value is None:
        return obj.get_active_layer_index()
    if isinstance(value, bool):
        raise ToolError('"layer" must be an index or a layer name.')
    if isinstance(value, int):
        index = value
    else:
        text = str(value)
        names = obj.get_layer_names()
        if text in names:
            index = names.index(text)
        elif text.isdigit():
            index = int(text)
        else:
            raise ToolError('No layer named "{}". Layers: {}.'.format(
                text, ', '.join('{} (index {})'.format(name, i)
                                for i, name in enumerate(names))))
    if not (0 <= index < obj.get_layer_count()):
        raise ToolError('Layer index {} is out of range (0-{}).'.format(
            index, obj.get_layer_count() - 1))
    return index


def _validate_tile(obj, tile_id):
    tile_id = int(tile_id)
    if tile_id < -1:
        raise ToolError('A tile id is >= 0, or -1 to erase the cell.')
    count = obj.get_tileset_tile_count()
    if count > 0 and tile_id >= count:
        raise ToolError('Tile {} is outside the tileset ({} tiles, max {}).'.format(
            tile_id, count, count - 1))
    return tile_id


def _commit_tile_paint(window, obj, index, old_tiles):
    """Record a finished paint on a layer as ONE scene-undo step.

    ``commit_tile_map_paint`` snapshots the ACTIVE layer, so a paint that
    targeted another layer switches the active layer for the commit and puts
    the user's layer back afterwards.
    """
    previous = obj.get_active_layer_index()
    obj.set_active_layer_index(index)
    manager().commit_tile_map_paint(obj.uuid, old_tiles)
    obj.set_active_layer_index(previous)
    canvas = _tile_canvas(window)
    refresh = getattr(window, '_refresh_layer_ui', None)
    if callable(refresh):
        refresh()
    canvas.update()


def _tile_state(window, obj):
    layers = []
    for index in range(obj.get_layer_count()):
        tiles = obj.get_layer_tiles(index)
        layers.append({
            'index': index,
            'name': obj.get_layer_name(index),
            'visible': obj.is_layer_visible(index),
            'collision': obj.is_collision_layer(index),
            'tiles_used': sum(1 for tile in tiles if tile >= 0),
        })
    canvas = _tile_canvas(window)
    tileset = obj.get_tileset_path()
    return {
        'open': True,
        'object': {'uuid': obj.uuid, 'name': obj.name},
        'columns': obj.columns,
        'rows': obj.rows,
        'tile_width': obj.tile_width,
        'tile_height': obj.tile_height,
        'tileset_path': tileset or None,
        'tileset_tiles': obj.get_tileset_tile_count(),
        'active_layer': obj.get_active_layer_index(),
        'layers': layers,
        'tool': canvas.tool(),
        'selected_tile': canvas.current_tile(),
        'zoom': round(canvas.zoom(), 4),
    }


@tool(
    'tile_map_editor_open',
    'Bind the Tile Map Editor to a tile map object of the scene (uuid, '
    'hierarchy path or unique name; without an argument the object selected '
    'in the editor is used) and bring the panel into view. Its layers and '
    'cells can then be edited with the tile_map_editor_* tools.',
    {
        'type': 'object',
        'properties': {
            'object': {'type': 'string',
                       'description': 'Tile map object: uuid, "Canvas/Map" or name (optional: selection).'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Open a tile map in the tile map editor'},
)
def tile_map_editor_open(args):
    from pygamestudio.game.object.type import OBJECT_TILE_MAP

    window = _tile_window()
    obj = resolve_object(args.get('object'))
    if getattr(obj, 'type', '') != OBJECT_TILE_MAP:
        raise ToolError(
            '"{}" is a {} object, not a TILE_MAP. Create one with '
            'create_object(type="TILE_MAP") or pick an existing tile map.'.format(
                getattr(obj, 'name', '?'), getattr(obj, 'type', '?')))
    window.set_object(obj.uuid)
    _focus(window)
    return _tile_state(window, obj)


@tool(
    'tile_map_editor_state',
    'What the Tile Map Editor shows: the bound object, grid and tile size, '
    'tileset, every layer (name, visibility, collision, tiles used), the '
    'active layer, tool and selected tile.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Tile map editor state'},
)
def tile_map_editor_state(args):
    window = _tile_window()
    obj = _tile_object(required=False)
    if obj is None:
        return {'open': False,
                'hint': 'Use tile_map_editor_open with a TILE_MAP object first.'}
    return _tile_state(window, obj)


@tool(
    'tile_map_editor_set_tool',
    'Select the tile map editor tool: pencil (paint the selected tile), '
    'erase, fill (flood fill with the selected tile) or pick (read a tile '
    'from the map).',
    {
        'type': 'object',
        'properties': {
            'tool': {'type': 'string', 'enum': ['pencil', 'erase', 'fill', 'pick']},
        },
        'required': ['tool'],
        'additionalProperties': False,
    },
    annotations={'title': 'Select a tile map tool'},
)
def tile_map_editor_set_tool(args):
    window = _tile_window()
    obj = _tile_object()
    window.set_tool(args['tool'])
    return {'tool': _tile_canvas(window).tool(), 'layers': obj.get_layer_count()}


@tool(
    'tile_map_editor_select_tile',
    'Select the tile the pencil/fill paints (a tile id of the tileset; the '
    'editor switches to the pencil like clicking a tile does).',
    {
        'type': 'object',
        'properties': {
            'tile': {'type': 'integer', 'minimum': 0,
                     'description': 'Tile id inside the tileset.'},
        },
        'required': ['tile'],
        'additionalProperties': False,
    },
    annotations={'title': 'Select a tile'},
)
def tile_map_editor_select_tile(args):
    window = _tile_window()
    obj = _tile_object()
    tile_id = _validate_tile(obj, args['tile'])
    picker = getattr(window, '_on_tile_selected', None)
    if callable(picker):
        picker(tile_id)
    else:
        _tile_canvas(window).set_current_tile(tile_id)
    canvas = _tile_canvas(window)
    return {'selected_tile': canvas.current_tile(), 'tool': canvas.tool()}


@tool(
    'tile_map_editor_layer',
    'Manage the tile map layers (all changes are undoable in the scene): '
    'add (optional "name"), remove, rename ("name"), select, set_visible or '
    'set_collision ("value"; the collision layer is unique). "layer" is an '
    'index or a layer name; without it the active layer is used.',
    {
        'type': 'object',
        'properties': {
            'action': {'type': 'string',
                       'enum': ['add', 'remove', 'rename', 'select',
                                'set_visible', 'set_collision']},
            'layer': {'description': 'Layer index or name (optional: active layer).'},
            'name': {'type': 'string',
                     'description': 'Layer name for "add" or "rename".'},
            'value': {'type': 'boolean',
                      'description': 'New flag for set_visible / set_collision.'},
        },
        'required': ['action'],
        'additionalProperties': False,
    },
    annotations={'title': 'Manage tile map layers'},
)
def tile_map_editor_layer(args):
    window = _tile_window()
    obj = _tile_object()
    manager_ = manager()
    action = args['action']

    if action == 'add':
        index = manager_.add_tile_map_layer(obj.uuid, args.get('name'))
        if index < 0:
            raise ToolError('Could not add a layer to "{}".'.format(obj.name))
    elif action == 'remove':
        index = _layer_index(obj, args.get('layer'))
        if not manager_.remove_tile_map_layer(obj.uuid, index):
            raise ToolError('The last layer cannot be removed.')
    elif action == 'rename':
        index = _layer_index(obj, args.get('layer'))
        name = (args.get('name') or '').strip()
        if not name:
            raise ToolError('"name" is required to rename a layer.')
        manager_.set_tile_map_layer_property(obj.uuid, index, 'name', name)
    elif action == 'select':
        index = _layer_index(obj, args.get('layer'))
        obj.set_active_layer_index(index)
        refresh = getattr(window, '_refresh_layer_ui', None)
        if callable(refresh):
            refresh()
    elif action in ('set_visible', 'set_collision'):
        index = _layer_index(obj, args.get('layer'))
        value = args.get('value')
        if value is None:
            raise ToolError('"value" (true/false) is required for {}.'.format(action))
        attr = 'visible' if action == 'set_visible' else 'collision'
        manager_.set_tile_map_layer_property(obj.uuid, index, attr, bool(value))
    else:  # pragma: no cover - the schema enum already rejects this
        raise ToolError('Unknown action "{}".'.format(action))

    return _tile_state(window, obj)


@tool(
    'tile_map_editor_paint',
    'Paint cells of a tile map layer in one undoable step. "cells" is a '
    'list of {"column", "row", "tile"} objects ({"tile"} optional) or '
    '[column, row] / [column, row, tile] arrays; a missing tile id uses '
    '"tile" of the request, falling back to the selected tile. Tile -1 '
    'erases the cell. "layer" is an index or name (default: the active '
    'layer).',
    {
        'type': 'object',
        'properties': {
            'cells': {'type': 'array', 'minItems': 1,
                      'description': 'Cells to paint, e.g. [{"column": 0, "row": 0, "tile": 2}].'},
            'layer': {'description': 'Layer index or name (optional).'},
            'tile': {'type': 'integer', 'minimum': -1,
                     'description': 'Tile for cells without their own tile id (optional).'},
        },
        'required': ['cells'],
        'additionalProperties': False,
    },
    annotations={'title': 'Paint tile map cells'},
)
def tile_map_editor_paint(args):
    window = _tile_window()
    obj = _tile_object()
    canvas = _tile_canvas(window)
    index = _layer_index(obj, args.get('layer'))
    default_tile = args.get('tile')
    default_tile = canvas.current_tile() if default_tile is None else _validate_tile(obj, default_tile)

    old_tiles = list(obj.get_layer_tiles(index))
    painted = 0
    for cell in args['cells']:
        if isinstance(cell, dict):
            column = cell.get('column')
            row = cell.get('row')
            tile = cell.get('tile')
            if tile is None:
                tile = default_tile
        elif isinstance(cell, (list, tuple)) and len(cell) >= 2:
            column, row = cell[0], cell[1]
            tile = cell[2] if len(cell) > 2 else default_tile
        else:
            raise ToolError('Cells must be {"column", "row", "tile"} objects or '
                            '[column, row(, tile)] arrays.')
        if column is None or row is None:
            raise ToolError('Every cell needs a column and a row.')
        column, row = int(column), int(row)
        if not (0 <= column < obj.columns and 0 <= row < obj.rows):
            raise ToolError('Cell ({}, {}) is outside the map ({}x{}).'.format(
                column, row, obj.columns, obj.rows))
        tile = _validate_tile(obj, tile)
        if obj.get_tile(column, row, index) == tile:
            continue
        obj.set_tile(column, row, tile, index)
        painted += 1

    if painted:
        _commit_tile_paint(window, obj, index, old_tiles)
    return {'painted': painted, 'layer': index, 'active_layer': obj.get_active_layer_index()}


@tool(
    'tile_map_editor_fill',
    'Flood fill the tile map from cell (column, row): every connected cell '
    'that holds the same tile id becomes "tile" (or the selected tile). One '
    'undoable step.',
    {
        'type': 'object',
        'properties': {
            'column': {'type': 'integer', 'minimum': 0},
            'row': {'type': 'integer', 'minimum': 0},
            'tile': {'type': 'integer', 'minimum': -1,
                     'description': 'Fill tile (optional: the selected tile).'},
            'layer': {'description': 'Layer index or name (optional).'},
        },
        'required': ['column', 'row'],
        'additionalProperties': False,
    },
    annotations={'title': 'Fill a tile map area'},
)
def tile_map_editor_fill(args):
    window = _tile_window()
    obj = _tile_object()
    canvas = _tile_canvas(window)
    index = _layer_index(obj, args.get('layer'))
    column, row = int(args['column']), int(args['row'])
    if not (0 <= column < obj.columns and 0 <= row < obj.rows):
        raise ToolError('Cell ({}, {}) is outside the map ({}x{}).'.format(
            column, row, obj.columns, obj.rows))
    tile = args.get('tile')
    tile = canvas.current_tile() if tile is None else _validate_tile(obj, tile)

    target = obj.get_tile(column, row, index)
    if target == tile:
        return {'filled': 0, 'layer': index}

    old_tiles = list(obj.get_layer_tiles(index))
    seen = set()
    stack = [(column, row)]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        c, r = current
        if not (0 <= c < obj.columns and 0 <= r < obj.rows):
            continue
        if obj.get_tile(c, r, index) != target:
            continue
        seen.add(current)
        stack.extend(((c - 1, r), (c + 1, r), (c, r - 1), (c, r + 1)))
    for c, r in seen:
        obj.set_tile(c, r, tile, index)

    if seen:
        _commit_tile_paint(window, obj, index, old_tiles)
    return {'filled': len(seen), 'layer': index}


# ============================================================== audio player
def _audio_window():
    return _require_panel('_audio_player_window', 'Audio Player')


def _audio_state(window):
    engine = window._engine
    current = getattr(window, '_current_path', None)
    try:
        playlist_count = len(window._playlist())
    except Exception:  # noqa: BLE001 - the playlist is a nicety
        playlist_count = 0
    return {
        'loaded': engine.is_loaded(),
        'file': project_relative(current) if current else None,
        'state': engine.state(),
        'position_ms': engine.position_ms(),
        'duration_ms': engine.duration_ms(),
        'playlist_count': playlist_count,
    }


@tool(
    'audio_player_open',
    'Open a project audio file in the Audio Player panel and start playing '
    'it ("play" false loads it without playing). Brings the panel into view.',
    {
        'type': 'object',
        'properties': {
            'path': {'type': 'string',
                     'description': 'Project-relative audio file, e.g. "./audio/jump.wav".'},
            'play': {'type': 'boolean', 'default': True,
                     'description': 'Start playing right away.'},
        },
        'required': ['path'],
        'additionalProperties': False,
    },
    annotations={'title': 'Open audio in the audio player'},
)
def audio_player_open(args):
    window = _audio_window()
    target = safe_project_path(args['path'], must_exist=True)
    if not window.open_audio(str(target), raise_window=True):
        raise ToolError('"{}" could not be loaded as audio (unsupported format?).'.format(
            args['path']))
    if args.get('play') is False:
        window._stop_playback()
    return _audio_state(window)


@tool(
    'audio_player_state',
    'What the Audio Player shows: file, playing state, position and duration '
    'in milliseconds, and how many files the previous/next buttons step '
    'through.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Audio player state'},
)
def audio_player_state(args):
    return _audio_state(_audio_window())


@tool(
    'audio_player_control',
    'Control the Audio Player: toggle (play/pause), play, pause, stop, next '
    'or previous (the same folder playlist), or seek to "position_ms".',
    {
        'type': 'object',
        'properties': {
            'action': {'type': 'string',
                       'enum': ['toggle', 'play', 'pause', 'stop', 'next',
                                'previous', 'seek']},
            'position_ms': {'type': 'integer', 'minimum': 0,
                            'description': 'Target position for "seek".'},
        },
        'required': ['action'],
        'additionalProperties': False,
    },
    annotations={'title': 'Control audio playback'},
)
def audio_player_control(args):
    from pygamestudio.gui.audio_player.engine import STATE_PLAYING

    window = _audio_window()
    engine = window._engine
    action = args['action']

    if action == 'toggle':
        window._toggle_play()
    elif action == 'play':
        if engine.state() != STATE_PLAYING:
            window._toggle_play()
    elif action == 'pause':
        if engine.state() == STATE_PLAYING:
            window._toggle_play()
    elif action == 'stop':
        window._stop_playback()
    elif action == 'next':
        window._play_next()
    elif action == 'previous':
        window._play_previous()
    elif action == 'seek':
        position = args.get('position_ms')
        if position is None:
            raise ToolError('"position_ms" is required for seek.')
        duration = engine.duration_ms()
        if duration <= 0:
            raise ToolError('No audio is loaded to seek in - open a file first.')
        fraction = max(0.0, min(1.0, float(position) / duration))
        window._on_seek(fraction)
    else:  # pragma: no cover - the schema enum already rejects this
        raise ToolError('Unknown action "{}".'.format(action))
    return _audio_state(window)
