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
              'collision_width', 'collision_height', 'collision_points',
              'physics_enabled', 'physics_type', 'physics_mass',
              'physics_friction', 'physics_elasticity', 'physics_gravity_scale',
              'physics_fixed_rotation', 'physics_linear_damping',
              'physics_angular_damping', 'physics_shape_type',
              'physics_shape_offset_x', 'physics_shape_offset_y',
              'physics_shape_width', 'physics_shape_height',
              'physics_shape_points']
    result = {
        'creatable_types': object_type_names(),
        'common_properties': sorted(set(common)),
        'type_specific_properties': properties,
        'notes': [
            'Positions (x, y) are relative to the parent object; width/height set the size.',
            'script_path is project relative, e.g. "./script/player.py".',
            'color is [r, g, b] or [r, g, b, a] with 0-255 per channel.',
            'collision_* properties only matter when collision_enabled is true.',
            'physics_* properties only matter when physics_enabled is true; the rigid '
            'body uses its own shape (physics_shape_type/size/offset/points, '
            'independent from the collision shape), and physics_type is static, '
            'dynamic or kinematic.',
            'A TEXT object clips its text to width/height: after changing text or '
            'font_size call fit_object_size, or pass "auto_size": true to '
            'create_object / update_object, so labels are not cut off.',
        ],
    }
    if wanted:
        if wanted not in properties:
            raise ToolError('Unknown type "{}". Known: {}'.format(
                wanted, ', '.join(object_type_names())))
        result = {'type': wanted, 'properties': properties[wanted]}
    return result


def _canvas_size():
    """Canvas size of the open scene (the default capture region)."""
    manager_ = manager()
    canvas = manager_.get_object(manager_.canvas_object_uuid) if manager_.canvas_object_uuid else None
    return (int(canvas.width) if canvas is not None else 800,
            int(canvas.height) if canvas is not None else 600)


def _render_scene_view_image(x, y, width, height, scale=1.0):
    """Render a region of the editor scene view into a QImage.

    The image is transparent where the scene draws nothing, exactly like the
    PNG ``capture_scene_view`` returns.
    """
    body = bridge.editor_body_or_none()
    if body is None:
        raise ToolError('The editor window is not available, so the scene cannot be captured.')

    try:
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtGui import QImage, QRegion
    except ImportError as e:
        raise ToolError('Qt is not available: {}'.format(e))

    scene_window = getattr(body, '_scene_widnow', None)
    pygame_screen = getattr(scene_window, '_pygame_screen', None)
    if pygame_screen is None:
        raise ToolError('The scene view is not available in this editor build.')

    if width <= 0 or height <= 0:
        raise ToolError('The capture region must have a positive size.')

    ox, oy = pygame_screen.scene_offset()
    image = QImage(int(width), int(height), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    # render() needs integers; the scene view maps scene (x, y) to widget (x + ox, y + oy).
    pygame_screen.render(image, QPoint(0, 0),
                         QRegion(int(round(x)) + ox, int(round(y)) + oy, int(width), int(height)))

    if abs(scale - 1.0) > 0.001:
        image = image.scaled(max(1, int(width * scale)), max(1, int(height * scale)),
                             Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    return image


@tool(
    'capture_scene_view',
    'Take a PNG screenshot of the editor scene view (what the user sees in the '
    'Scene panel) and return it as an image. Use it to check how the scene '
    'looks after a change; a model that cannot see pictures can call '
    'analyze_image for a text description of the same view. Coordinates are '
    'in scene (= canvas) units.',
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
    from PySide6.QtCore import QBuffer, QIODevice

    canvas_width, canvas_height = _canvas_size()
    x = float(args.get('x', 0))
    y = float(args.get('y', 0))
    width = float(args.get('width', canvas_width))
    height = float(args.get('height', canvas_height))
    scale = float(args.get('scale', 1) or 1)
    image = _render_scene_view_image(x, y, width, height, scale)

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


#: analyze_image: sample grid (cells across x down) and the longest side in
#: pixels the picture is scaled down to before its pixels are inspected.
_ANALYSIS_GRID_COLS = 16
_ANALYSIS_GRID_ROWS = 9
_ANALYSIS_MAX_SIDE = 240
#: Colour buckets: channel values round to this step, so "the same colour"
#: stays together in screenshots with subtle shading.
_COLOR_STEP = 32


def _quantize_channel(value):
    return min(255, (value + _COLOR_STEP // 2) // _COLOR_STEP * _COLOR_STEP)


def _color_bucket(color):
    """Quantized colour of one pixel (None = transparent)."""
    if color.alpha() < 32:
        return None
    return (_quantize_channel(color.red()),
            _quantize_channel(color.green()),
            _quantize_channel(color.blue()))


def _bucket_hex(bucket):
    if bucket is None:
        return 'transparent'
    return '#{:02x}{:02x}{:02x}'.format(*bucket)


def _describe_image(image, source):
    """Text description of a QImage for models that cannot see pictures.

    Reports the background colour, where the content sits (bounding box and
    margins), the main non-background colours with their boxes, brightness
    and a coarse colour grid - enough for a text model to reason about what
    is on screen without ever receiving the picture itself.
    """
    from PySide6.QtCore import Qt

    origin_width, origin_height = image.width(), image.height()
    if origin_width <= 0 or origin_height <= 0:
        raise ToolError('The image is empty.')

    # Inspect a small copy: pixel access stays cheap and the statistics barely
    # change (a 1080p screenshot and its 240 px thumbnail tell the same story).
    sample = image
    longest = max(origin_width, origin_height)
    if longest > _ANALYSIS_MAX_SIDE:
        factor = _ANALYSIS_MAX_SIDE / float(longest)
        sample = image.scaled(max(1, int(origin_width * factor)),
                              max(1, int(origin_height * factor)),
                              Qt.AspectRatioMode.IgnoreAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
    width, height = sample.width(), sample.height()
    to_origin = origin_width / float(width)

    cols = max(1, min(_ANALYSIS_GRID_COLS, width))
    rows = max(1, min(_ANALYSIS_GRID_ROWS, height))
    cells = [[{} for _ in range(cols)] for _ in range(rows)]

    histogram = {}          # bucket -> [count, min_x, min_y, max_x, max_y]
    buckets = []            # every pixel's bucket, in row order
    brightness_sum, brightness_count = 0.0, 0
    brightness_min, brightness_max = 1.0, 0.0
    for y in range(height):
        for x in range(width):
            color = sample.pixelColor(x, y)
            bucket = _color_bucket(color)
            buckets.append(bucket)
            entry = histogram.get(bucket)
            if entry is None:
                histogram[bucket] = entry = [0, x, y, x, y]
            entry[0] += 1
            entry[1] = min(entry[1], x)
            entry[2] = min(entry[2], y)
            entry[3] = max(entry[3], x)
            entry[4] = max(entry[4], y)
            cell = cells[y * rows // height][x * cols // width]
            cell[bucket] = cell.get(bucket, 0) + 1
            if bucket is not None:
                luminance = (0.2126 * color.red() + 0.7152 * color.green()
                             + 0.0722 * color.blue()) / 255.0
                brightness_sum += luminance
                brightness_count += 1
                brightness_min = min(brightness_min, luminance)
                brightness_max = max(brightness_max, luminance)

    total = width * height
    background = max(histogram, key=lambda bucket: histogram[bucket][0])
    background_share = histogram[background][0] / float(total)

    def is_content(bucket):
        if bucket == background:
            return False
        if background is None:
            return bucket is not None
        if bucket is None:
            return True
        return max(abs(bucket[index] - background[index]) for index in range(3)) > 48

    content_count = 0
    left = top = 10 ** 9
    right = bottom = -1
    for index, bucket in enumerate(buckets):
        if is_content(bucket):
            content_count += 1
            x, y = index % width, index // width
            left, top = min(left, x), min(top, y)
            right, bottom = max(right, x), max(bottom, y)
    content_share = content_count / float(total)

    def bbox_in_origin(x0, y0, x1, y1):
        return [int(round(x0 * to_origin)), int(round(y0 * to_origin)),
                int(round((x1 - x0 + 1) * to_origin)), int(round((y1 - y0 + 1) * to_origin))]

    result = {
        'source': source,
        'size': [origin_width, origin_height],
        'background': {'color': _bucket_hex(background),
                       'share': round(background_share, 3)},
        'content': {'share': round(content_share, 3)},
        'main_colors': [],
        'brightness': None,
        'distinct_colors': len([bucket for bucket in histogram if bucket is not None]),
        'grid': {
            'cols': cols,
            'rows': rows,
            'cell_pixels': [int(round(origin_width / cols)), int(round(origin_height / rows))],
            'note': 'Each cell shows its dominant non-background colour (hex, no "#"); "." is pure background.',
            'cells': [],
        },
        'notes': [],
    }
    if content_count:
        result['content']['bbox_xywh'] = bbox_in_origin(left, top, right, bottom)
        result['content']['margins_percent'] = {
            'left': int(round(left / float(width) * 100)),
            'right': int(round((width - 1 - right) / float(width) * 100)),
            'top': int(round(top / float(height) * 100)),
            'bottom': int(round((height - 1 - bottom) / float(height) * 100)),
        }
    else:
        result['content']['bbox_xywh'] = None

    main = sorted((bucket for bucket in histogram if is_content(bucket)),
                  key=lambda bucket: histogram[bucket][0], reverse=True)
    for bucket in main[:8]:
        count, min_x, min_y, max_x, max_y = histogram[bucket]
        result['main_colors'].append({
            'color': _bucket_hex(bucket),
            'share': round(count / float(total), 3),
            'bbox_xywh': bbox_in_origin(min_x, min_y, max_x, max_y) if bucket is not None else None,
        })

    if brightness_count:
        result['brightness'] = {
            'mean': round(brightness_sum / brightness_count, 3),
            'min': round(brightness_min, 3),
            'max': round(brightness_max, 3),
        }

    for row_cells in cells:
        row_text = []
        for cell in row_cells:
            cell_total = sum(cell.values())
            content_pixels = sum(count for bucket, count in cell.items()
                                 if is_content(bucket))
            if not cell_total or content_pixels / float(cell_total) < 0.05:
                row_text.append('.')
                continue
            dominant = max((bucket for bucket in cell if is_content(bucket)),
                           key=lambda bucket: cell[bucket])
            row_text.append(_bucket_hex(dominant)[1:])
        result['grid']['cells'].append(' '.join(row_text))

    notes = result['notes']
    if content_share < 0.005:
        notes.append('Almost nothing is drawn besides the background (content {:.1%}).'
                     .format(content_share))
    if background_share > 0.99:
        notes.append('The picture is one flat colour - the scene may be empty or not rendered yet.')
    if brightness_count and brightness_sum / brightness_count < 0.06:
        notes.append('The picture is nearly black (mean brightness {:.0%}).'
                     .format(brightness_sum / brightness_count))
    if brightness_count and brightness_sum / brightness_count > 0.96 and content_share < 0.02:
        notes.append('The picture is nearly white and almost empty.')
    return result


@tool(
    'analyze_image',
    'Describe a picture as text for models that cannot see images: background '
    'colour and share, content coverage/position/margins, the main colours '
    'with their bounding boxes, brightness and a small colour grid. Without '
    '"path" it analyzes a fresh capture of the editor scene view (the same '
    'picture capture_scene_view returns); with "path" any project image. Use '
    'it to verify a scene really shows what it should - labels visible, '
    'sprites inside the screen, the right colours - instead of guessing.',
    {
        'type': 'object',
        'properties': {
            'path': {'type': 'string',
                     'description': 'Project-relative image file, e.g. "./images/player.png" '
                                    '(default: capture the scene view).'},
        },
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Describe an image as text'},
)
def analyze_image(args):
    from PySide6.QtGui import QImage

    path = args.get('path')
    if path:
        target = safe_project_path(path, must_exist=True)
        image = QImage(str(target))
        if image.isNull():
            raise ToolError('"{}" could not be read as an image.'.format(path))
        return _describe_image(image, project_relative(target))

    canvas_width, canvas_height = _canvas_size()
    image = _render_scene_view_image(0, 0, canvas_width, canvas_height)
    return _describe_image(image, 'scene view')


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
            ('_animation_editor_window', 'Animation Editor'),
            ('_audio_editor_window', 'Audio Editor'),
            ('_hierarchy_window', 'Hierarchy'),
            ('_asset_window', 'Asset'),
            ('_inspector_window', 'Inspector'),
            ('_agent_window', 'AI Agent'),
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
