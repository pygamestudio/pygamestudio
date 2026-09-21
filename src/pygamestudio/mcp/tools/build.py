"""Build tools: package the project into a desktop app or a web (browser)
app. Both use the Build window of the running editor (its two tabs)."""

import os
import platform
import subprocess
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


def _web_build_body(required=True):
    """The web-app build panel of the editor.

    Layout: EditorBody -> BuildWindow -> BuildWindowBody -> WebAppBuildWindow.
    """
    body = bridge.editor_body_or_none()
    build_window = getattr(body, '_build_window', None)
    web_body = getattr(getattr(build_window, '_build_window_body', None),
                       '_web_app_build_window', None)
    if web_body is None and required:
        raise ToolError('The build window is not available in this editor session.')
    return web_body


def _open_folder(folder):
    """Open a folder in the system file manager."""
    folder = Path(folder)
    system = platform.system()
    if system == 'Windows':
        os.startfile(folder)
    elif system == 'Darwin':
        subprocess.Popen(['open', folder.as_posix()])
    else:
        subprocess.Popen(['xdg-open', folder.as_posix()])


@tool(
    'get_build_settings',
    'The build settings of the project: the desktop-app values (app name, '
    'icon, output dir, clean cache) and the web-app values (build.web: output '
    'dir; name and icon are shared with the desktop build). Also reports '
    'whether a build is running in either tab, its progress and the folder of '
    'the last web build.',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Build settings'},
)
def get_build_settings(args):
    from pygamestudio.common.utils.config import get_project_config
    data = {
        'config': get_project_config().get('build'),
        'project_path': str(project_path()),
        'has_main_py': (project_path() / 'main.py').exists(),
    }
    body = _build_body(required=False)
    if body is not None:
        data['is_building'] = bool(getattr(body, '_is_building', False))
        progress_bar = getattr(body, '_progress_bar', None)
        data['progress'] = progress_bar.value() if progress_bar is not None else None
    web_body = _web_build_body(required=False)
    if web_body is not None:
        data['web_is_building'] = bool(getattr(web_body, '_is_building', False))
        web_progress_bar = getattr(web_body, '_progress_bar', None)
        data['web_progress'] = web_progress_bar.value() if web_progress_bar is not None else None
        bundle_dir = getattr(getattr(web_body, '_build_thread', None), 'bundle_dir', None)
        data['web_bundle_dir'] = Path(bundle_dir).as_posix() if bundle_dir else None
    return data


@tool(
    'start_build',
    'Package the project into a standalone desktop app with PyInstaller (same '
    'as the Build button in the desktop-app tab of the Build window). This '
    'takes a while: the build runs in the background, poll get_build_settings '
    'and read get_console_logs for the log, open_output_dir points at the result.',
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
    'start_web_build',
    'Package the project for the browser (same as the Build button in the '
    'Web App tab of the Build window): the result is a folder with index.html '
    'and game.zip that plays the game through Pyodide and pygame-ce, and it '
    'starts by itself once loaded. The project code/assets are protected like '
    'in the desktop build (the installed engine is never modified) and the '
    'result lands in <output_dir>/build/Web. The build runs in the background: '
    'poll get_build_settings (web_is_building / web_progress), read '
    'get_console_logs, then open_output_dir with target="web".',
    {
        'type': 'object',
        'properties': {
            'app_name': {'type': 'string', 'description': 'Page title / app name (default: the project folder name).'},
            'app_icon': {'type': 'string', 'description': 'Absolute path of the favicon image (.png/.ico/.jpg/.bmp/.gif; optional).'},
            'output_dir': {'type': 'string', 'description': 'Absolute path of an existing output folder (default: the project folder).'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Build a web app'},
)
def start_web_build(args):
    body = _web_build_body()
    if getattr(body, '_is_building', False):
        raise ToolError('A web build is already running (use stop_build to stop it).')
    if not (project_path() / 'main.py').exists():
        raise ToolError('main.py is not in the project root - the project cannot be built.')

    output_dir = (args.get('output_dir') or '').strip()
    if output_dir:
        output_dir_path = Path(output_dir).expanduser()
        if not output_dir_path.is_absolute():
            raise ToolError('output_dir must be an absolute path.')
        if not output_dir_path.exists() or not output_dir_path.is_dir():
            raise ToolError('The output folder "{}" does not exist.'.format(output_dir_path))
        output_dir = output_dir_path.as_posix()

    app_name = (args.get('app_name') or '').strip()
    app_icon = (args.get('app_icon') or '').strip()
    if app_icon and not Path(app_icon).exists():
        raise ToolError('The app icon "{}" does not exist.'.format(app_icon))

    # Mirror the arguments into the web panel (its own defaults stay in place
    # for everything that was not given) - get_build_config saves them.
    if app_name:
        body._app_name_lineedit.setText(app_name)
    if app_icon:
        body._app_icon_lineedit.setText(app_icon)
    if output_dir:
        body._output_dir_lineedit.setText(output_dir)

    body._progress_bar.setValue(0)
    body._progress_bar.show()
    body._run_button.setEnabled(False)
    build_config = body.get_build_config()
    body._build_thread.set_build_config(build_config)
    body._build_thread.start()
    body._is_building = True
    body._build_button.setText('Stop')

    return {
        'started': True,
        'config': build_config,
        'bundle_dir': (Path(build_config['output_dir']) / 'build' / 'Web').as_posix(),
        'note': 'Poll get_build_settings (web_is_building / web_progress); the log appears in the console.',
    }


@tool(
    'stop_build',
    'Stop the running build - whichever tab is building (desktop app or web app).',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'title': 'Stop the build', 'destructiveHint': True},
)
def stop_build(args):
    stopped = []
    for target, body in (('desktop', _build_body(required=False)),
                         ('web', _web_build_body(required=False))):
        if body is not None and getattr(body, '_is_building', False):
            body._build_thread.stop()
            stopped.append(target)
    if not stopped:
        return {'stopped': False, 'reason': 'no build is running'}
    return {'stopped': True, 'targets': stopped}


@tool(
    'open_output_dir',
    'Open a build output folder in the system file manager: the desktop app '
    'output (target "desktop", default) or the web bundle folder '
    '(<output>/build/Web) once a web build was made (target "web").',
    {
        'type': 'object',
        'properties': {
            'target': {'type': 'string', 'enum': ['desktop', 'web'], 'default': 'desktop',
                       'description': 'Which build output to open.'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Open the output folder'},
)
def open_output_dir(args):
    target = args.get('target') or 'desktop'
    if target == 'web':
        body = _web_build_body()
        output_dir = (body._output_dir_lineedit.text() or '').strip() or str(project_path())
        bundle_dir = Path(output_dir) / 'build' / 'Web'
        folder = bundle_dir if bundle_dir.exists() else Path(output_dir)
        if not folder.exists():
            raise ToolError('The output folder "{}" does not exist yet.'.format(folder))
        _open_folder(folder)
        return {'opened': folder.as_posix(), 'target': 'web'}

    body = _build_body()
    output_dir = (body._output_dir_lineedit.text() or '').strip()
    if not output_dir:
        raise ToolError('No output folder is configured yet.')
    body._open_output_dir()
    return {'opened': output_dir, 'target': 'desktop'}
