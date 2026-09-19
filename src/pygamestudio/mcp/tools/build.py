"""Build tools: package the project into a desktop app (the Build window)."""

from pathlib import Path

from pygamestudio.mcp.bridge import bridge
from pygamestudio.mcp.registry import ToolError, tool
from pygamestudio.mcp.tools.context import manager, project_path, project_relative


def _build_body(required=True):
    """The desktop-app build panel of the editor.

    Layout: EditorBody -> BuildWindow -> BuildWindowBody -> DesktopAppBuildWindow.
    """
    body = bridge.editor_body_or_none()
    build_window = getattr(body, '_build_window', None)
    desktop_body = getattr(getattr(build_window, '_build_window_body', None),
                           '_desktop_app_build_window', None)
    if desktop_body is None and required:
        raise ToolError('The build window is not available in this editor session.')
    return desktop_body


@tool(
    'get_build_settings',
    'The desktop-app build settings of the project (app name, icon, output '
    'dir, clean cache) plus whether a build is running and its progress.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Build settings'},
)
def get_build_settings(args):
    from pygamestudio.common.utils.config import get_project_config
    body = _build_body(required=False)
    data = {
        'config': get_project_config().get('build'),
        'project_path': str(project_path()),
        'has_main_py': (project_path() / 'main.py').exists(),
    }
    if body is not None:
        data['is_building'] = bool(getattr(body, '_is_building', False))
        progress_bar = getattr(body, '_progress_bar', None)
        data['progress'] = progress_bar.value() if progress_bar is not None else None
    return data


@tool(
    'start_build',
    'Package the project into a standalone desktop app with PyInstaller (same '
    'as the Build button in the Build window). This takes a while: the build '
    'runs in the background, poll get_build_settings and read get_console_logs '
    'for the log, open_output_dir points at the result.',
    {
        'type': 'object',
        'properties': {
            'app_name': {'type': 'string', 'description': 'Name of the executable (e.g. "MyGame").'},
            'app_icon': {'type': 'string', 'description': 'Absolute path of a .png/.ico/.icns icon (optional).'},
            'output_dir': {'type': 'string', 'description': 'Absolute path of an existing output folder.'},
            'clean_cache': {'type': 'boolean', 'default': False,
                            'description': 'Clear the PyInstaller cache before building.'},
        },
        'required': ['output_dir'],
        'additionalProperties': False,
    },
    annotations={'title': 'Build a desktop app'},
)
def start_build(args):
    body = _build_body()
    if getattr(body, '_is_building', False):
        raise ToolError('A build is already running (use stop_build to stop it).')

    output_dir = Path(args['output_dir']).expanduser()
    if not output_dir.is_absolute():
        raise ToolError('output_dir must be an absolute path.')
    if not output_dir.exists() or not output_dir.is_dir():
        raise ToolError('The output folder "{}" does not exist.'.format(output_dir))

    app_icon = (args.get('app_icon') or '').strip()
    if app_icon and not Path(app_icon).exists():
        raise ToolError('The app icon "{}" does not exist.'.format(app_icon))

    if not (project_path() / 'main.py').exists():
        raise ToolError('main.py is not in the project root - the project cannot be built.')

    try:
        import importlib.util
        has_pyinstaller = importlib.util.find_spec('PyInstaller') is not None
    except (ImportError, ValueError):
        has_pyinstaller = False
    if not has_pyinstaller:
        raise ToolError('PyInstaller is not installed in the editor environment.')
    if not (project_path() / 'main.py').exists():
        raise ToolError('main.py is not in the project root.')

    from pygamestudio.common.utils.config import get_project_config, save_project_config

    config = get_project_config()
    build_config = config.setdefault('build', {})
    if args.get('app_name'):
        build_config['app_name'] = args['app_name']
    build_config['app_icon'] = app_icon
    build_config['output_dir'] = str(output_dir)
    build_config['clean_cache'] = bool(args.get('clean_cache', False))
    save_project_config(config)

    # Mirror the values into the build window widgets, then start its thread.
    body._app_name_lineedit.setText(str(build_config.get('app_name', '')))
    body._app_icon_lineedit.setText(build_config['app_icon'])
    body._output_dir_lineedit.setText(build_config['output_dir'])
    body._clean_cache_checkbox.setChecked(build_config['clean_cache'])

    body._progress_bar.setValue(0)
    body._progress_bar.show()
    body._build_thread.set_build_config(body.get_build_config())
    body._build_thread.start()
    body._is_building = True
    body._build_button.setText('Stop')

    return {
        'started': True,
        'config': build_config,
        'note': 'Poll get_build_settings for progress; the log appears in the console.',
    }


@tool(
    'stop_build',
    'Stop the running desktop-app build.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'title': 'Stop the build', 'destructiveHint': True},
)
def stop_build(args):
    body = _build_body()
    if not getattr(body, '_is_building', False):
        return {'stopped': False, 'reason': 'no build is running'}
    body._build_thread.stop()
    return {'stopped': True}


@tool(
    'open_output_dir',
    'Open the build output folder of the project in the system file manager.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'title': 'Open the output folder'},
)
def open_output_dir(args):
    body = _build_body()
    output_dir = (body._output_dir_lineedit.text() or '').strip()
    if not output_dir:
        raise ToolError('No output folder is configured yet.')
    body._open_output_dir()
    return {'opened': output_dir}
