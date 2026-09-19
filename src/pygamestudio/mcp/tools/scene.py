"""Scene tools: list/load/save scenes, read the scene tree, find objects."""

from pathlib import Path

from pygamestudio.mcp.bridge import bridge
from pygamestudio.mcp.registry import ToolError, register_resource, tool
from pygamestudio.mcp.tools.context import (
    canvas_object, json_value, manager, object_summary, project_path,
    project_relative, safe_project_path, scene_tree,
)


@tool(
    'list_scenes',
    'List the .scene files of the project and mark the one that is loaded in '
    'the editor and the project start scene.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'List scenes'},
)
def list_scenes(args):
    root = project_path()
    manager_ = manager()
    current = Path(manager_.current_scene_file_path).name if manager_.current_scene_file_path else None
    from pygamestudio.common.utils.config import get_project_config
    start = Path(str(get_project_config().get('asset', {}).get('current_scene') or '')).name
    scenes = []
    for path in sorted(root.rglob('*.scene')):
        scenes.append({
            'path': './' + path.relative_to(root).as_posix(),
            'name': path.stem,
            'is_loaded': path.name == current,
            'is_start_scene': path.name == start,
            'size': path.stat().st_size,
        })
    return {'scenes': scenes, 'loaded_scene': manager_.current_scene_file_path}


@tool(
    'get_current_scene',
    'Information about the scene that is open in the editor: file path, '
    'whether it has unsaved changes and how many objects it holds.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Current scene'},
)
def get_current_scene(args):
    manager_ = manager()
    canvas = canvas_object() if manager_.canvas_object_uuid else None
    objects = scene_tree() if not manager_.is_empty() else None
    return {
        'scene_path': manager_.current_scene_file_path or None,
        'saved': manager_.is_current_scene_saved,
        'canvas': object_summary(canvas) if canvas is not None else None,
        'root': objects,
    }


@tool(
    'new_scene',
    'Replace the open scene with an empty one (a new canvas). Unsaved changes '
    'are discarded - use save_scene first if they matter. The empty scene is '
    'not written to disk until save_scene is called with a path.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'title': 'New empty scene'},
)
def new_scene(args):
    manager_ = manager()
    manager_.load_scene('', silent=True)
    return {'created': True, 'canvas': object_summary(canvas_object())}


@tool(
    'load_scene',
    'Open another .scene file of the project in the editor. Unsaved changes in '
    'the current scene are saved first when it has a file.',
    {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'description': 'Project-relative path, e.g. "./scene/level2.scene".'},
        },
        'required': ['path'],
        'additionalProperties': False,
    },
    annotations={'title': 'Load scene'},
)
def load_scene(args):
    manager_ = manager()
    path = safe_project_path(args['path'], must_exist=True)
    loaded = manager_.load_scene(str(path), silent=True)
    return {
        'loaded': project_relative(path),
        'scene_path': manager_.current_scene_file_path,
        'tree': scene_tree(),
    }


@tool(
    'save_scene',
    'Save the open scene. Without a path it is written to its current file '
    '(pass a path to save a new scene to that file, e.g. "./scene/level2.scene").',
    {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'description': 'Project-relative scene path (optional).'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Save scene', 'idempotentHint': True},
)
def save_scene(args):
    manager_ = manager()
    path = args.get('path')
    if path:
        target = safe_project_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        manager_.save_scene(str(target))
    else:
        if not manager_.current_scene_file_path:
            raise ToolError('This scene has no file yet: pass a path like "./scene/main.scene".')
        manager_.save_scene()
    return {'saved': manager_.current_scene_file_path, 'dirty': not manager_.is_current_scene_saved}


@tool(
    'get_scene_tree',
    'The object tree of the open scene (name, type, uuid, position, size, '
    'visibility, script, children). This is the main overview an agent works '
    'with; pass a deeper `depth` or use get_object for the full properties.',
    {
        'type': 'object',
        'properties': {
            'depth': {'type': 'integer', 'minimum': 1, 'maximum': 12, 'default': 4,
                      'description': 'How many levels of children to include.'},
            'root': {'type': 'string', 'description':
                     'Start at this object (uuid, path or name) instead of the canvas.'},
        },
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Scene tree'},
)
def get_scene_tree(args):
    from pygamestudio.mcp.tools.context import resolve_object
    root = resolve_object(args['root']) if args.get('root') else None
    if root is not None:
        from pygamestudio.mcp.tools.context import manager as _manager
        struct = _manager()._get_object_tree_struct(root.uuid)
        return scene_tree(struct, depth=args['depth'])
    return scene_tree(depth=args['depth'])


@tool(
    'find_objects',
    'Search the open scene for objects by name, type, script or whether they '
    'have a script attached. Returns matching objects with their paths.',
    {
        'type': 'object',
        'properties': {
            'name': {'type': 'string', 'default': '', 'description': 'Part of the name (case-insensitive).'},
            'type': {'type': 'string', 'default': '',
                     'description': 'Object type, e.g. RECT, TEXT, IMAGE, BUTTON, FRAME_SEQUENCE.'},
            'script': {'type': 'string', 'default': '',
                       'description': 'Part of the script_path (case-insensitive).'},
            'with_script': {'type': 'boolean', 'description':
                            'true = only objects with a script, false = only without.'},
            'visible_only': {'type': 'boolean', 'default': False},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 500, 'default': 100},
        },
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Find objects'},
)
def find_objects(args):
    from pygamestudio.mcp.tools.context import iter_objects, object_summary

    name = (args.get('name') or '').lower()
    type_filter = (args.get('type') or '').upper()
    script = (args.get('script') or '').lower()
    matches = []
    for obj in iter_objects():
        if name and name not in obj.name.lower():
            continue
        if type_filter and obj.type != type_filter:
            continue
        script_path = (getattr(obj, 'script_path', '') or '').lower()
        if script and script not in script_path:
            continue
        if args.get('with_script') is not None and bool(script_path) != bool(args['with_script']):
            continue
        if args.get('visible_only') and not getattr(obj, 'visible', True):
            continue
        matches.append(object_summary(obj))
        if len(matches) >= args['limit']:
            break
    return {'count': len(matches), 'objects': matches}


@register_resource(
    'pygs://project/scene-tree',
    'Scene tree',
    'The object tree of the scene that is open in the editor.',
    'application/json')
def _scene_tree_resource():
    return json_value(scene_tree(depth=8))
