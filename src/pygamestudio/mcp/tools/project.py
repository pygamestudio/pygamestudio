"""Project and file tools: project info, config, files, assets, scripts."""

import shutil
from pathlib import Path

from pygamestudio.mcp.bridge import bridge
from pygamestudio.mcp.registry import ToolError, register_resource, tool
from pygamestudio.mcp.tools.context import (
    json_value, manager, project_path, project_relative, safe_project_path,
)

#: File extensions -> kind, used by list_files and import_file.
_KIND_BY_SUFFIX = {
    '.png': 'image', '.jpg': 'image', '.jpeg': 'image', '.bmp': 'image',
    '.gif': 'image', '.webp': 'image',
    '.wav': 'audio', '.ogg': 'audio', '.mp3': 'audio', '.flac': 'audio',
    '.py': 'script',
    '.scene': 'scene',
    '.json': 'data', '.txt': 'data', '.md': 'data', '.csv': 'data',
    '.pygs': 'config',
}

#: Folders that are never part of the project content.
_IGNORED_DIRS = {'__pycache__', '.git', '.venv', 'build', 'dist', '.idea'}


@tool(
    'get_project_info',
    'Information about the open project: folder, name, screen size, current '
    'scene, main.py presence and counts of scenes/scripts/images/audio.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Project info'},
)
def get_project_info(args):
    manager_ = manager()
    root = project_path()
    from pygamestudio.common.utils.config import get_project_config
    config = get_project_config()

    counts = {'scene': 0, 'script': 0, 'image': 0, 'audio': 0, 'other': 0}
    for path in root.rglob('*'):
        if not path.is_file() or any(part in _IGNORED_DIRS for part in path.parts):
            continue
        counts[_kind_of(path)] = counts.get(_kind_of(path), 0) + 1

    scenes = sorted(p.relative_to(root).as_posix() for p in root.rglob('*.scene'))
    return {
        'project_path': str(root),
        'project_name': root.name,
        'caption': config.get('caption'),
        'screen_width': config.get('screen_width'),
        'screen_height': config.get('screen_height'),
        'current_scene': (manager_.current_scene_file_path or config.get('asset', {}).get('current_scene')),
        'scene_saved': manager_.is_current_scene_saved,
        'has_main_py': (root / 'main.py').exists(),
        'scenes': scenes,
        'file_counts': counts,
        'build': config.get('build'),
    }


@tool(
    'get_project_config',
    'Read project.pygs (the project settings: caption, screen size, start '
    'scene, app name/icon/output dir).',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Project config'},
)
def get_project_config_tool(args):
    from pygamestudio.common.utils.config import get_project_config
    return json_value(get_project_config())


@tool(
    'update_project_config',
    'Change project settings in project.pygs. Keys may be dotted, e.g. '
    '"screen_width", "caption", "build.app_name", "asset.current_scene". '
    'Changes are saved immediately (and are NOT part of the undo stack).',
    {
        'type': 'object',
        'properties': {
            'settings': {
                'type': 'object',
                'description': 'Key/value pairs, e.g. {"screen_width": 960, "caption": "My Game"}.',
                'additionalProperties': True,
            },
        },
        'required': ['settings'],
        'additionalProperties': False,
    },
    annotations={'title': 'Update project settings', 'readOnlyHint': False},
)
def update_project_config(args):
    from pygamestudio.common.utils.config import get_project_config, save_project_config

    settings = args['settings']
    config = get_project_config()
    applied = {}
    for key, value in settings.items():
        parts = str(key).split('.')
        target = config
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value
        applied[key] = value
    _validate_screen_size(config)
    save_project_config(config)

    # The open editor widgets (settings panel, scene view size) follow along.
    manager_ = manager()
    try:
        manager_.scene_loaded_signal.emit()
    except Exception:  # pragma: no cover - signal is best effort
        pass
    return {'updated': applied}


def _validate_screen_size(config):
    for key in ('screen_width', 'screen_height'):
        if key in config:
            try:
                config[key] = int(config[key])
            except (TypeError, ValueError):
                raise ToolError('{} must be an integer.'.format(key))
            if config[key] < 1:
                raise ToolError('{} must be positive.'.format(key))


@tool(
    'get_editor_settings',
    'Read the editor preferences (language, theme) and the MCP server settings.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Editor settings'},
)
def get_editor_settings(args):
    from pygamestudio.common.utils.config import get_editor_config
    return json_value(get_editor_config())


@tool(
    'update_editor_settings',
    'Change editor preferences (language: "en"/"zh_CN", theme: "dark"/"light"). '
    'Saved to the editor config file; the UI changes immediately.',
    {
        'type': 'object',
        'properties': {
            'language': {'type': 'string', 'enum': ['en', 'zh_CN']},
            'theme': {'type': 'string', 'enum': ['dark', 'light']},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Update editor settings'},
)
def update_editor_settings(args):
    from pygamestudio.common.utils.config import get_editor_config, update_editor_config
    from pygamestudio.common.i18n.translator import Translator as T
    from pygamestudio.common.utils.theme import set_editor_theme

    applied = {}
    if args.get('language'):
        update_editor_config('lang', args['language'])
        # toggle_language also retranslates the open windows; load_language only
        # swapped the dictionary, so the UI kept its old labels.
        T.toggle_language(args['language'])
        applied['language'] = args['language']
    if args.get('theme'):
        update_editor_config('theme', args['theme'])
        set_editor_theme(args['theme'])
        # Repaint the panels that carry their own colors: the settings dialog
        # does this over its `theme_toggled` signal, a tool call has no dialog
        # and has to ask the editor body explicitly.
        body = bridge.editor_body_or_none()
        apply_theme = getattr(body, 'apply_editor_theme', None)
        if callable(apply_theme):
            apply_theme(args['theme'])
        applied['theme'] = args['theme']
    if not applied:
        raise ToolError('Nothing to change: pass language and/or theme.')
    return {'updated': applied, 'config': json_value(get_editor_config())}


@tool(
    'list_files',
    'List the files of the project (relative paths). Filter by sub-folder and '
    'by kind to find images, audio, scripts or scenes.',
    {
        'type': 'object',
        'properties': {
            'subfolder': {'type': 'string', 'default': '',
                          'description': 'Only look inside this project-relative folder, e.g. "./images".'},
            'kind': {'type': 'string', 'enum': ['all', 'image', 'audio', 'script', 'scene', 'data'],
                     'default': 'all'},
            'name_contains': {'type': 'string', 'default': '',
                              'description': 'Only paths containing this text (case-insensitive).'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 2000, 'default': 400},
        },
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'List project files'},
)
def list_files(args):
    root = project_path()
    base = root if not args.get('subfolder') else safe_project_path(args['subfolder'])
    if not base.exists():
        raise ToolError('"{}" does not exist.'.format(args.get('subfolder')))

    kind = args.get('kind', 'all')
    needle = args.get('name_contains', '').lower()
    files = []
    for path in sorted(base.rglob('*')):
        if not path.is_file() or any(part in _IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        relative = path.relative_to(root).as_posix()
        if needle and needle not in relative.lower():
            continue
        file_kind = _kind_of(path)
        if kind != 'all' and file_kind != kind:
            continue
        files.append({
            'path': './' + relative,
            'kind': file_kind,
            'size': path.stat().st_size,
        })
        if len(files) >= args['limit']:
            break
    return {'count': len(files), 'files': files}


@tool(
    'read_file',
    'Read a text file of the project (script, scene, json, ...). Binary files '
    'are rejected - use list_files and capture_scene_view for images.',
    {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'description': 'Project-relative path, e.g. "./script/player.py".'},
            'offset': {'type': 'integer', 'minimum': 0, 'default': 0,
                       'description': 'First line to return (0 based).'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 4000, 'default': 600,
                      'description': 'Maximum number of lines to return.'},
        },
        'required': ['path'],
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Read project file'},
)
def read_file(args):
    path = safe_project_path(args['path'], must_exist=True)
    if path.is_dir():
        raise ToolError('"{}" is a folder.'.format(args['path']))
    if _kind_of(path) in ('image', 'audio'):
        raise ToolError('"{}" is a binary file and cannot be read as text.'.format(args['path']))

    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError as e:
        raise ToolError('Could not read {}: {}'.format(args['path'], e))

    lines = text.splitlines()
    offset = int(args.get('offset', 0))
    limit = int(args.get('limit', 600))
    chunk = lines[offset:offset + limit]
    return {
        'path': project_relative(path),
        'total_lines': len(lines),
        'offset': offset,
        'returned_lines': len(chunk),
        'truncated': offset + len(chunk) < len(lines),
        'content': '\n'.join(chunk),
    }


@tool(
    'write_file',
    'Create or overwrite a text file in the project (scripts, scenes, data). '
    'Missing folders are created. Set append=true to add to an existing file.',
    {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'description': 'Project-relative path, e.g. "./script/player.py".'},
            'content': {'type': 'string', 'description': 'The whole text of the file.'},
            'append': {'type': 'boolean', 'default': False,
                       'description': 'Append instead of overwriting.'},
        },
        'required': ['path', 'content'],
        'additionalProperties': False,
    },
    annotations={'title': 'Write project file'},
)
def write_file(args):
    path = safe_project_path(args['path'])
    if path.exists() and path.is_dir():
        raise ToolError('"{}" is a folder.'.format(args['path']))
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = 'a' if args.get('append') else 'w'
    try:
        with open(path, mode, encoding='utf-8', newline='\n') as f:
            f.write(args['content'])
    except OSError as e:
        raise ToolError('Could not write {}: {}'.format(args['path'], e))

    # Let the code editor reload the file when it is showing it.
    body = bridge.editor_body_or_none()
    if body is not None:
        code_editor = getattr(body, '_code_editor_window', None)
        reload_file = getattr(code_editor, 'reload_file', None)
        if callable(reload_file):
            try:
                reload_file(str(path))
            except Exception:  # pragma: no cover - best effort only
                pass
    return {
        'path': project_relative(path),
        'bytes': path.stat().st_size,
        'lines': args['content'].count('\n') + (0 if args['content'].endswith('\n') else 1),
        'appended': bool(args.get('append')),
    }


@tool(
    'create_script',
    'Create an ObjectScript file for a scene object (a .py file with the '
    'ObjectScript class template) and optionally attach it to an object.',
    {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'description': 'Project-relative path, e.g. "./script/player.py".'},
            'attach_to': {'type': 'string', 'description':
                          'Object uuid, path or name to attach the script to (optional).'},
            'overwrite': {'type': 'boolean', 'default': False},
        },
        'required': ['path'],
        'additionalProperties': False,
    },
    annotations={'title': 'Create an object script'},
)
def create_script(args):
    from pygamestudio.common.utils.path import RES_PATH
    from pygamestudio.mcp.tools.objects import update_object_properties

    path = safe_project_path(args['path'])
    if path.exists() and not args.get('overwrite'):
        raise ToolError('"{}" already exists (pass overwrite=true to replace it).'.format(args['path']))
    template = (Path(RES_PATH) / 'templates/object_script_template.py')
    try:
        content = template.read_text(encoding='utf-8')
    except OSError as e:
        raise ToolError('The script template could not be read: {}'.format(e))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')

    attached = None
    if args.get('attach_to'):
        attached = update_object_properties(args['attach_to'], {'script_path': './' + project_relative(path)})
    return {
        'path': project_relative(path),
        'attached_to': attached,
        'note': 'The script was created from the ObjectScript template; add your code to on_start/on_update.',
    }


@tool(
    'delete_file',
    'Delete a file (or a folder with recursive=true) from the project.',
    {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'description': 'Project-relative path.'},
            'recursive': {'type': 'boolean', 'default': False},
        },
        'required': ['path'],
        'additionalProperties': False,
    },
    annotations={'title': 'Delete project file', 'destructiveHint': True},
)
def delete_file(args):
    path = safe_project_path(args['path'], must_exist=True)
    if path == project_path():
        raise ToolError('The project folder itself cannot be deleted.')
    if path.is_dir():
        if not args.get('recursive'):
            raise ToolError('"{}" is a folder: pass recursive=true to delete it.'.format(args['path']))
        shutil.rmtree(path)
    else:
        path.unlink()
    return {'deleted': project_relative(path)}


@tool(
    'move_file',
    'Move or rename a file/folder inside the project.',
    {
        'type': 'object',
        'properties': {
            'source': {'type': 'string', 'description': 'Project-relative path of the file to move.'},
            'target': {'type': 'string', 'description': 'New project-relative path.'},
            'overwrite': {'type': 'boolean', 'default': False},
        },
        'required': ['source', 'target'],
        'additionalProperties': False,
    },
    annotations={'title': 'Move project file'},
)
def move_file(args):
    source = safe_project_path(args['source'], must_exist=True)
    target = safe_project_path(args['target'])
    if target.exists() and not args.get('overwrite'):
        raise ToolError('"{}" already exists.'.format(args['target']))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    return {'moved': [project_relative(source), project_relative(target)]}


@tool(
    'import_file',
    'Copy a file from anywhere on this computer into the project (import an '
    'image, a sound, a font, ...). Target folder defaults to ./images for '
    'pictures, ./audio for sounds and the project root otherwise.',
    {
        'type': 'object',
        'properties': {
            'source_path': {'type': 'string', 'description': 'Absolute path of the file to import.'},
            'target_path': {'type': 'string', 'description':
                            'Project-relative destination (folder or file path). Optional.'},
            'overwrite': {'type': 'boolean', 'default': False},
        },
        'required': ['source_path'],
        'additionalProperties': False,
    },
    annotations={'title': 'Import a file into the project'},
)
def import_file(args):
    source = Path(args['source_path']).expanduser()
    if not source.is_absolute():
        raise ToolError('source_path must be an absolute path.')
    if not source.exists() or not source.is_file():
        raise ToolError('"{}" does not exist.'.format(source))

    kind = _kind_of(source)
    default_folder = {'image': 'images', 'audio': 'audio'}.get(kind, '')
    target_arg = (args.get('target_path') or '').strip()
    if not target_arg:
        target_arg = '{}/{}'.format(default_folder, source.name) if default_folder else source.name

    target = safe_project_path(target_arg)
    if target.is_dir():
        target = target / source.name
    if target.exists() and not args.get('overwrite'):
        raise ToolError('"{}" already exists (pass overwrite=true to replace it).'.format(
            project_relative(target)))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return {'imported': project_relative(target), 'kind': kind, 'size': target.stat().st_size}


def _kind_of(path):
    return _KIND_BY_SUFFIX.get(Path(path).suffix.lower(), 'other')


@register_resource(
    'pygs://project/files',
    'Project file list',
    'Relative paths of every file in the project, grouped by kind.',
    'application/json')
def _files_resource():
    return json_value(list_files({'limit': 2000}))


@register_resource(
    'pygs://project/config',
    'Project config',
    'The content of project.pygs.',
    'application/json')
def _config_resource():
    from pygamestudio.common.utils.config import get_project_config
    return json_value(get_project_config())
