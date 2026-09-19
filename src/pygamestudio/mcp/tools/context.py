"""Shared helpers used by every MCP tool module.

The helpers keep the individual tool bodies short and make sure that the same
rules apply everywhere:

* object references (uuid, hierarchy path, or "the selected object"),
* undoable property edits (everything the agent changes can be undone with
  Ctrl+Z in the editor),
* project-relative paths that can never escape the project folder.
"""

from pathlib import Path

from pygamestudio.mcp.bridge import bridge
from pygamestudio.mcp.registry import ToolError, register_resource, text_result

#: Object type constants, imported lazily in object_type_names() to keep this
#: module importable without the GUI stack.
_OBJECT_TYPES = (
    'RECT', 'ELLIPSE', 'POLYGON', 'LINE', 'TEXT', 'IMAGE', 'BUTTON',
    'PARTICLE', 'TEXT_INPUT', 'PROGRESS_BAR', 'SLIDER', 'FRAME_SEQUENCE',
    'TILE_MAP', 'CANVAS',
)

#: Attributes that hold a project file/folder path (relative input is resolved
#: against the project folder, so a model can write './script/player.py').
_PATH_ATTRS = {
    'script_path', 'image_path', 'font_path', 'tileset_path', 'frame_folder',
    'particle_image', 'background_image_path', 'foreground_image_path',
    'track_image_path', 'fill_image_path', 'handle_image_path',
}

#: Attributes that are never part of the scene data / never editable.
_READ_ONLY_ATTRS = {
    'uuid', 'type', 'surface', 'icon', 'script_instance', 'game_manager',
    'selected', 'expanded', '_is_initialized', '_is_for_api', '_game_manager',
}


# ------------------------------------------------------------------ context
def manager():
    """The ``GameManager`` of the open project (raises when none is open)."""
    return bridge.manager


def editor():
    """The main ``Editor`` window, or None when running headless."""
    return bridge.editor_or_none()


def editor_body():
    """The ``EditorBody`` (the window that owns every panel), or None."""
    return bridge.editor_body_or_none()


def project_path():
    """Absolute path of the open project folder."""
    manager_ = manager()
    project = manager_.get_project_path()
    if not project:
        raise ToolError('The editor has no project open.')
    return Path(project)


def project_relative(path):
    """A project-relative posix path for display (falls back to absolute)."""
    try:
        return Path(path).resolve().relative_to(project_path().resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def safe_project_path(relative_path, must_exist=False):
    """Resolve a project-relative path, refusing anything outside the project."""
    if not relative_path or not str(relative_path).strip():
        raise ToolError('A project-relative path is required.')
    root = project_path().resolve()
    candidate = (root / str(relative_path).replace('\\', '/')).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ToolError(
            'The path "{}" is outside the project folder and cannot be touched.'.format(relative_path))
    if must_exist and not candidate.exists():
        raise ToolError('"{}" does not exist in the project.'.format(relative_path))
    return candidate


# ------------------------------------------------------------------ objects
def canvas_object():
    manager_ = manager()
    uuid = manager_.canvas_object_uuid
    if not uuid:
        raise ToolError('The scene has no canvas yet.')
    obj = manager_.get_object(uuid)
    if obj is None:
        raise ToolError('The scene has no canvas yet.')
    return obj


def selected_object():
    """The object the user has selected in the editor (or None)."""
    manager_ = manager()
    selection = manager_.get_selected_objects()
    return selection[0] if selection else None


def resolve_object(ref=None, allow_selection=True):
    """Find an object from a uuid, a hierarchy path, or a unique name.

    ``ref`` may be:

    * a uuid,
    * a path like ``Canvas/Player`` or ``Canvas/Enemy[2]``,
    * a plain name (``Player``) that is unique in the scene,
    * empty/None - then the object selected in the editor is used.
    """
    manager_ = manager()
    if ref is None or str(ref).strip() == '':
        if allow_selection:
            obj = selected_object()
            if obj is not None:
                return obj
        raise ToolError('No object given and nothing is selected in the editor.')
    if not isinstance(ref, str):
        raise ToolError('The object reference must be a string.')

    ref = ref.strip()
    obj = manager_.get_object(ref)
    if obj is not None:
        return obj

    # Hierarchy path: the first part is the root (canvas), the rest are children.
    if '/' in ref:
        parts = ref.strip('/').split('/')
        root_node = manager_.all_object_tree_struct
        root_name = list(root_node.values())[0]['object'].name
        first_name, _first_index = _split_index(parts[0])
        if first_name == root_name:
            parts = parts[1:]
    else:
        parts = None

    if parts is not None:
        node = manager_.all_object_tree_struct
        for part in parts:
            name, index = _split_index(part)
            node = _find_child(node, name, index)
            if node is None:
                raise ToolError('Object not found: {}{}'.format(ref, _suggestions(ref)))
        return list(node.values())[0]['object']

    # Unique name anywhere in the scene.
    matches = [obj for obj in iter_objects() if obj.name == ref]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ToolError(
            'The name "{}" is ambiguous ({} objects). Use a path like "{}".'.format(
                ref, len(matches), object_path(matches[0])))
    raise ToolError('Object not found: {}{}'.format(ref, _suggestions(ref)))


def _suggestions(ref):
    """Names that look close to ``ref``, to help an agent fix its call."""
    leaf = str(ref).strip('/').split('/')[-1].split('[')[0].strip().lower()
    if not leaf:
        return ''
    close = [obj.name for obj in iter_objects() if leaf in obj.name.lower()][:6]
    if not close:
        close = [obj.name for obj in iter_objects()][:6]
    return '. Objects in the scene: {}'.format(', '.join(close)) if close else ''


def _split_index(part):
    part = part.strip()
    if part.endswith(']') and '[' in part:
        name, _, index = part[:-1].partition('[')
        try:
            return name, int(index)
        except ValueError:
            return part, None
    return part, None


def _find_child(node, name, index):
    """Child of ``node`` called ``name`` (at sibling position ``index``)."""
    value = list(node.values())[0]
    for position, child in enumerate(value['children']):
        child_obj = list(child.values())[0]['object']
        if child_obj.name != name:
            continue
        if index is None or index == position:
            return child
    return None


def iter_objects(node=None):
    """Every object of the scene, depth first (the canvas first)."""
    manager_ = manager()
    if not manager_.all_object_tree_struct:
        return []
    found = []

    def walk(object_tree_struct):
        value = list(object_tree_struct.values())[0]
        found.append(value['object'])
        for child in value['children']:
            walk(child)

    walk(manager_.all_object_tree_struct if node is None else node)
    return found


def parent_of(obj):
    return manager().get_parent_object(obj.uuid)


def object_path(obj):
    """Unambiguous hierarchy path of an object ('Canvas/Enemy[2]')."""
    manager_ = manager()
    parts = []
    current = obj
    while current is not None:
        parent = manager_.get_parent_object(current.uuid)
        if parent is None:
            parts.append(current.name)
            break
        siblings = [child.name for child in manager_.get_descendant_objects(parent.uuid, True)]
        if siblings.count(current.name) > 1:
            index = [
                child.uuid for child in manager_.get_descendant_objects(parent.uuid, True)
            ].index(current.uuid)
            parts.append('{}[{}]'.format(current.name, index))
        else:
            parts.append(current.name)
        current = parent
    return '/'.join(reversed(parts))


# ------------------------------------------------------------- scene / data
def json_value(value):
    """Make an attribute value JSON friendly (tuples -> lists, surfaces -> id)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    return str(value)


def object_summary(obj, with_children=False):
    """A compact description of one object (what an agent needs to act)."""
    data = {
        'uuid': obj.uuid,
        'name': obj.name,
        'type': obj.type,
        'path': object_path(obj),
        'x': obj.x,
        'y': obj.y,
        'width': getattr(obj, 'width', None),
        'height': getattr(obj, 'height', None),
        'angle': getattr(obj, 'angle', None),
        'visible': bool(getattr(obj, 'visible', True)),
    }
    script = getattr(obj, 'script_path', '') or ''
    if script:
        data['script_path'] = script
    if with_children:
        manager_ = manager()
        children = manager_.get_descendant_objects(obj.uuid, True)
        data['children'] = [object_summary(child) for child in children]
    return data


def object_details(obj):
    """Every scene property of an object (what the inspector shows + more)."""
    data = object_summary(obj)
    editable = {}
    for attr, value in vars(obj).items():
        if attr in _READ_ONLY_ATTRS or attr.startswith('_'):
            continue
        if attr in ('uuid', 'name', 'type', 'x', 'y', 'width', 'height',
                    'angle', 'visible', 'script_path', 'depth', 'screen_space',
                    'selected', 'expanded', 'icon'):
            continue
        editable[attr] = json_value(value)
    data['properties'] = editable
    data['world_rect'] = dict(zip(('x', 'y', 'width', 'height'), json_value(tuple(obj._get_world_rect()))))
    return data


def scene_tree(node=None, depth=4):
    """Nested overview of the scene (uuids, names, positions)."""
    manager_ = manager()
    if not manager_.all_object_tree_struct:
        raise ToolError('No scene is loaded.')

    def walk(object_tree_struct, level):
        value = list(object_tree_struct.values())[0]
        obj = value['object']
        children = value['children'] if level < depth else []
        summary = object_summary(obj)
        summary['child_count'] = len(value['children'])
        if children:
            summary['children'] = [walk(child, level + 1) for child in children]
        return summary

    return walk(manager_.all_object_tree_struct if node is None else node, 0)


# -------------------------------------------------------------------- edits
def push_property(manager_, obj, attr, value):
    """Set one attribute of an object as an undoable editor change."""
    from pygamestudio.game.core.command import UpdateAttrValueCommand

    if not hasattr(obj, attr):
        raise ToolError('Object "{}" ({}) has no property "{}".'.format(
            obj.name, obj.type, attr))
    if attr in _READ_ONLY_ATTRS or attr in ('uuid', 'type'):
        raise ToolError('"{}" cannot be changed.'.format(attr))

    if attr.endswith('color') and isinstance(value, str):
        value = parse_color(value)
    elif attr in _PATH_ATTRS and isinstance(value, str) and value.strip():
        value = resolve_project_path(value)

    old_value = getattr(obj, attr)
    new_value = coerce_value(attr, old_value, value)
    if (isinstance(old_value, (list, tuple)) and isinstance(new_value, list)
            and len(new_value) == len(old_value) - 1 and attr.endswith('color')):
        # A colour given as [r, g, b] keeps the alpha the object already had.
        new_value = list(new_value) + [list(old_value)[-1]]
    if old_value == new_value:
        return False
    manager_._undo_stack.push(UpdateAttrValueCommand(manager_, obj, attr, old_value, new_value))
    return True


def resolve_project_path(value):
    """'./script/player.py' -> the absolute path inside the project folder.

    Scene objects store script/asset paths resolved against the project, so a
    relative path from a model is turned into one here (absolute input is kept).
    """
    text = str(value).strip().replace('\\', '/')
    if Path(text).is_absolute():
        return text
    return str((project_path() / text).resolve())


def parse_color(value):
    """'#ff0000', 'f00', '255, 0, 0' -> [255, 0, 0] (also accepts 8 digits RGBA)."""
    text = str(value).strip()
    if text.startswith('#'):
        text = text[1:]
    if ',' in text:
        parts = [int(float(part.strip())) for part in text.split(',') if part.strip() != '']
        if len(parts) in (3, 4):
            return parts
        raise ToolError('"{}" is not a colour. Use [r, g, b], [r, g, b, a] or "#rrggbb".'.format(value))
    if len(text) in (3, 4):
        text = ''.join(channel * 2 for channel in text)
    if len(text) == 6:
        text += 'ff'
    if len(text) == 8:
        try:
            channels = [int(text[index:index + 2], 16) for index in range(0, 8, 2)]
        except ValueError:
            raise ToolError('"{}" is not a colour.'.format(value))
        return channels
    raise ToolError('"{}" is not a colour. Use [r, g, b], [r, g, b, a] or "#rrggbb".'.format(value))


def coerce_value(attr, old_value, value):
    """Convert a JSON value to the type the attribute already has."""
    if isinstance(old_value, bool):
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ('true', '1', 'yes', 'on'):
                return True
            if lowered in ('false', '0', 'no', 'off'):
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        if not isinstance(value, bool):
            raise ToolError('"{}" must be true or false.'.format(attr))
        return value

    if isinstance(old_value, (int, float)):
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                raise ToolError('"{}" must be a number.'.format(attr))
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ToolError('"{}" must be a number.'.format(attr))
        if isinstance(old_value, int) and float(value).is_integer():
            return int(value)
        return float(value)

    if isinstance(old_value, str):
        if not isinstance(value, str):
            raise ToolError('"{}" must be text.'.format(attr))
        return value

    if isinstance(old_value, (list, tuple)):
        if isinstance(value, str) and ',' in value:
            value = [item.strip() for item in value.split(',')]
        if not isinstance(value, (list, tuple)):
            raise ToolError('"{}" must be a list like [1, 2, 3].'.format(attr))
        return [_coerce_like(item, item_old) for item, item_old in
                zip(value, list(old_value) or [None] * len(value))] if old_value else list(value)

    if isinstance(old_value, dict):
        if not isinstance(value, dict):
            raise ToolError('"{}" must be an object.'.format(attr))
        return value

    return value


def _coerce_like(value, old_value):
    if isinstance(old_value, bool):
        return bool(value)
    if isinstance(old_value, int) and not isinstance(old_value, bool):
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return value
    if isinstance(old_value, float):
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    return value


def begin_macro(manager_, name):
    manager_._undo_stack.beginMacro(name)


def end_macro(manager_):
    manager_._undo_stack.endMacro()


def undo_state():
    """Undo / redo availability and the label of the next step."""
    manager_ = manager()
    stack = manager_._undo_stack
    return {
        'can_undo': stack.canUndo(),
        'can_redo': stack.canRedo(),
        'undo_text': stack.undoText(),
        'redo_text': stack.redoText(),
    }


# ------------------------------------------------------------------- types
def object_type_names():
    """Object types that can be created (canvas excluded, it always exists)."""
    return [name for name in _OBJECT_TYPES if name != 'CANVAS']


def type_properties():
    """Editable properties per object type, taken from the inspector layouts.

    The inspector is the single source of truth for "which property does this
    object type have", so the tool description can never drift from the UI.
    """
    from pygamestudio.game.object.type import (
        OBJECT_BUTTON, OBJECT_ELLIPSE, OBJECT_FRAME_SEQUENCE, OBJECT_IMAGE,
        OBJECT_LINE, OBJECT_PARTICLE, OBJECT_POLYGON, OBJECT_PROGRESS_BAR,
        OBJECT_RECT, OBJECT_SLIDER, OBJECT_TEXT, OBJECT_TEXT_INPUT,
        OBJECT_TILE_MAP, OBJECT_CANVAS,
    )
    from pygamestudio.gui.inspector.layout.button import INSPECTOR_LAYOUT_BUTTON
    from pygamestudio.gui.inspector.layout.canvas import INSPECTOR_LAYOUT_CANVAS
    from pygamestudio.gui.inspector.layout.ellipse import INSPECTOR_LAYOUT_ELLIPSE
    from pygamestudio.gui.inspector.layout.frame_sequence import INSPECTOR_LAYOUT_FRAME_SEQUENCE
    from pygamestudio.gui.inspector.layout.image import INSPECTOR_LAYOUT_IMAGE
    from pygamestudio.gui.inspector.layout.line import INSPECTOR_LAYOUT_LINE
    from pygamestudio.gui.inspector.layout.particle import INSPECTOR_LAYOUT_PARTICLE
    from pygamestudio.gui.inspector.layout.polygon import INSPECTOR_LAYOUT_POLYGON
    from pygamestudio.gui.inspector.layout.progress_bar import INSPECTOR_LAYOUT_PROGRESS_BAR
    from pygamestudio.gui.inspector.layout.rect import INSPECTOR_LAYOUT_RECT
    from pygamestudio.gui.inspector.layout.slider import INSPECTOR_LAYOUT_SLIDER
    from pygamestudio.gui.inspector.layout.text import INSPECTOR_LAYOUT_TEXT
    from pygamestudio.gui.inspector.layout.text_input import INSPECTOR_LAYOUT_TEXT_INPUT
    from pygamestudio.gui.inspector.layout.tile_map import INSPECTOR_LAYOUT_TILE_MAP
    from pygamestudio.gui.inspector.layout.collision import (
        _COLLISION_ENABLED, _COLLISION_OFFSET, _COLLISION_POINTS, _COLLISION_SIZE,
        _COLLISION_TYPE,
    )
    from pygamestudio.gui.inspector.layout.physics import (
        _PHYSICS_ANGULAR_DAMPING, _PHYSICS_ELASTICITY, _PHYSICS_ENABLED,
        _PHYSICS_FIXED_ROTATION, _PHYSICS_FRICTION, _PHYSICS_GRAVITY_SCALE,
        _PHYSICS_LINEAR_DAMPING, _PHYSICS_MASS, _PHYSICS_SHAPE,
        _PHYSICS_SHAPE_OFFSET, _PHYSICS_SHAPE_POINTS, _PHYSICS_SHAPE_SIZE,
        _PHYSICS_TYPE,
    )

    layouts = {
        OBJECT_RECT: INSPECTOR_LAYOUT_RECT,
        OBJECT_ELLIPSE: INSPECTOR_LAYOUT_ELLIPSE,
        OBJECT_POLYGON: INSPECTOR_LAYOUT_POLYGON,
        OBJECT_LINE: INSPECTOR_LAYOUT_LINE,
        OBJECT_TEXT: INSPECTOR_LAYOUT_TEXT,
        OBJECT_IMAGE: INSPECTOR_LAYOUT_IMAGE,
        OBJECT_BUTTON: INSPECTOR_LAYOUT_BUTTON,
        OBJECT_PARTICLE: INSPECTOR_LAYOUT_PARTICLE,
        OBJECT_TEXT_INPUT: INSPECTOR_LAYOUT_TEXT_INPUT,
        OBJECT_PROGRESS_BAR: INSPECTOR_LAYOUT_PROGRESS_BAR,
        OBJECT_SLIDER: INSPECTOR_LAYOUT_SLIDER,
        OBJECT_FRAME_SEQUENCE: INSPECTOR_LAYOUT_FRAME_SEQUENCE,
        OBJECT_TILE_MAP: INSPECTOR_LAYOUT_TILE_MAP,
        OBJECT_CANVAS: INSPECTOR_LAYOUT_CANVAS,
    }
    # The shared sections are stored as individual row details (their layout
    # builders wrap them with a row name), so name them here the same way.
    shared = {
        'collision_enabled': _COLLISION_ENABLED,
        'collision_type': _COLLISION_TYPE,
        'collision_offset': _COLLISION_OFFSET,
        'collision_size': _COLLISION_SIZE,
        'collision_points': _COLLISION_POINTS,
        'physics_enabled': _PHYSICS_ENABLED,
        'physics_type': _PHYSICS_TYPE,
        'physics_mass': _PHYSICS_MASS,
        'physics_fixed_rotation': _PHYSICS_FIXED_ROTATION,
        'physics_friction': _PHYSICS_FRICTION,
        'physics_elasticity': _PHYSICS_ELASTICITY,
        'physics_gravity_scale': _PHYSICS_GRAVITY_SCALE,
        'physics_linear_damping': _PHYSICS_LINEAR_DAMPING,
        'physics_angular_damping': _PHYSICS_ANGULAR_DAMPING,
        'physics_shape': _PHYSICS_SHAPE,
        'physics_shape_offset': _PHYSICS_SHAPE_OFFSET,
        'physics_shape_size': _PHYSICS_SHAPE_SIZE,
        'physics_shape_points': _PHYSICS_SHAPE_POINTS,
    }

    def attributes_of(layout):
        attrs = []
        for detail in layout.values():
            component = detail.get('component') if isinstance(detail, dict) else None
            if not component:
                continue
            attrs.extend(component.get('attribute', []) or [])
        return attrs

    result = {}
    for object_type, layout in layouts.items():
        attrs = attributes_of(layout)
        if object_type != OBJECT_CANVAS:
            attrs.extend(attributes_of(shared))
        result[object_type] = sorted(set(attrs))
    return result


# --------------------------------------------------------------- resources
@register_resource(
    'pygs://editor/capabilities',
    'Editor capabilities',
    'Markdown overview of everything the editor can do and which MCP tools cover it.',
    'text/markdown')
def _capabilities_resource():
    return _read_capabilities_doc()


def _read_capabilities_doc():
    doc = Path(__file__).resolve().parent.parent / 'CAPABILITIES.md'
    try:
        return doc.read_text(encoding='utf-8')
    except OSError:
        return 'CAPABILITIES.md is not available in this installation.'


@register_resource(
    'pygs://editor/tools',
    'MCP tool list',
    'Every registered tool with its JSON schema.',
    'application/json')
def _tools_resource():
    from pygamestudio.mcp.registry import list_tools
    import json as _json
    return _json.dumps(list_tools(), indent=2, ensure_ascii=False)


def ok(message, **extra):
    """A short human/model readable success answer."""
    if extra:
        import json as _json
        return text_result(message + '\n' + _json.dumps(extra, indent=2, ensure_ascii=False, default=str))
    return text_result(message)
