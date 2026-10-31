"""Build tools: package the project into a desktop app, a web (browser) app or
an Android APK. All three use the Build window of the running editor (its
three tabs)."""

import os
import platform
import subprocess
from pathlib import Path

from pygamestudio.mcp.bridge import bridge
from pygamestudio.mcp.registry import ToolError, autosave_scene, tool
from pygamestudio.mcp.tools.context import manager, project_path, project_relative

#: Publishing platforms of the web tab; the values come from
#: ``gui.build.web`` (none = a plain bundle, bilibili_toy = Toy packaged).
_WEB_PLATFORMS = ('', 'bilibili_toy')
#: Build types of the Android tab (``gui.build.android.BUILD_TYPES``).
_ANDROID_BUILD_TYPES = ('debug', 'release')


def _scene_build_warnings():
    """Warn when the latest scene edits cannot be on disk (no .scene file).

    A build stages the files of the project folder, so the scene has to be
    saved first. Every tool call already autosaves a scene the agent changed;
    this also flushes edits the user has not saved yet, so the package shows
    exactly what the editor shows. A scene without a file cannot be saved
    without asking for a path - that case is reported as a warning.
    """
    if autosave_scene(force=True) == 'unsaved':
        return ['The current scene has no .scene file yet, so the build uses the '
                'files already on disk - save it with save_scene to include your '
                'latest changes.']
    return []


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


def _android_build_body(required=True):
    """The Android build panel of the editor.

    Layout: EditorBody -> BuildWindow -> BuildWindowBody -> AndroidAppBuildWindow.
    """
    body = bridge.editor_body_or_none()
    build_window = getattr(body, '_build_window', None)
    android_body = getattr(getattr(build_window, '_build_window_body', None),
                           '_android_app_build_window', None)
    if android_body is None and required:
        raise ToolError('The build window is not available in this editor session.')
    return android_body


def _android_public_config(config):
    """The Android build config without the two passwords."""
    return {key: value for key, value in config.items()
            if key not in ('store_password', 'key_password')}


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
    'icon, output dir, publishing platform), the web-app values (build.web: '
    'output dir and publishing platform; name and icon are shared with the '
    'desktop build) and the Android values (build.android_*: package, version '
    'name/code, orientation, build type, keystore + alias; the two passwords '
    'live in the editor settings and are never returned). Two separate '
    'platform picks exist: the desktop one is '
    'build.platform - "" = 无平台 (no platform), "taptap" = TapTap (older '
    'projects may still carry the legacy build.taptap flag - the desktop tab '
    'migrates it); the web one is build.web.platform - "" = 无平台 and '
    '"bilibili_toy" = Bilibili Toy. Also reports whether a build is running in '
    'any tab, its progress, the folder of the last web build and the JDK/SDK '
    'the Android tab would use (plus what is missing, if anything).',
    {
        'type': 'object',
        'properties': {},
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Build settings'},
)
def get_build_settings(args):
    from pygamestudio.common.utils.config import get_project_config
    project_config = get_project_config()
    data = {
        'config': project_config.get('build'),
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
        data['web_platform'] = ((project_config.get('build') or {}).get('web') or {}).get('platform', '')

    android_body = _android_build_body(required=False)
    if android_body is not None:
        data['android_is_building'] = bool(getattr(android_body, '_is_building', False))
        android_progress_bar = getattr(android_body, '_progress_bar', None)
        data['android_progress'] = (android_progress_bar.value()
                                    if android_progress_bar is not None else None)
        android_config = _android_public_config(android_body.get_build_config())
        data['android_config'] = android_config
        apk_path = getattr(getattr(android_body, '_build_thread', None), 'apk_path', None)
        data['android_apk'] = Path(apk_path).as_posix() if apk_path else None
        data['android_toolchain'] = _android_toolchain_report(android_config)
    return data


def _android_toolchain_report(android_config):
    """What the Android build needs and whether it is there (no dialogs)."""
    from pygamestudio.common.utils import android_runtime
    report = {'ok': False, 'problems': []}
    try:
        metadata = android_runtime.find_pack()['metadata']
        report['runtime_pack'] = '{} {}'.format(metadata.get('name', 'runtime'),
                                                metadata.get('version', '?'))
    except Exception as error:                      # noqa: BLE001 - report, never raise
        report['problems'].append('editor build: {}'.format(error))
    try:
        toolchain = android_runtime.check_toolchain(android_config.get('jdk') or '',
                                                    android_config.get('sdk') or '')
        report['jdk'] = toolchain['jdk']
        report['sdk'] = toolchain['sdk']
        report['build_tools'] = toolchain['build_tools']
        report['problems'].extend(toolchain['problems'])
        report['ok'] = toolchain['ok'] and not report['problems']
    except Exception as error:                      # noqa: BLE001 - report, never raise
        report['problems'].append(str(error))
    return report


@tool(
    'start_build',
    'Package the project into a standalone desktop app with PyInstaller (same '
    'as the Build button in the desktop-app tab of the Build window; the '
    'PyInstaller cache is always cleared first). This takes a while: the build '
    'runs in the background, poll get_build_settings and read get_console_logs '
    'for the log, open_output_dir points at the result. Use platform to set '
    'where the build is published: "" = 无平台 (no platform), "taptap" = '
    'TapTap - only then the TapTap PC SDK is included in the package (config '
    'key build.platform; the game passes its TapTap client id / public key to '
    'studio.sdk.taptap.pc.init() in its own code). The shipped code stays '
    'protected: comments and docstrings are '
    'stripped and the project modules and assets are encrypted, main.py stays '
    'readable and importing the project modules from it keeps working. Names '
    'are never renamed, so third party SDKs keep working.',
    {
        'type': 'object',
        'properties': {
            'app_name': {'type': 'string', 'description': 'Name of the executable (e.g. "MyGame").'},
            'app_icon': {'type': 'string', 'description': 'Absolute path of a .png/.ico/.icns icon (optional).'},
            'output_dir': {'type': 'string', 'description': 'Absolute path of an existing output folder.'},
            'platform': {'type': 'string', 'enum': ['', 'taptap'],
                         'description': 'Publishing platform: "" = 无平台 (no platform), "taptap" = '
                                        'TapTap (the package includes the TapTap PC SDK). Defaults to '
                                        'the saved pick (build.platform).'},
        },
        'required': ['output_dir'],
        'additionalProperties': False,
    },
    annotations={'title': 'Build a desktop app'},
)
def start_build(args):
    platform_id = args.get('platform')
    if platform_id is not None and platform_id not in ('', 'taptap'):
        raise ToolError('Unknown platform "{}" - use "" (无平台) or "taptap".'.format(platform_id))

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
    if platform_id is not None:
        build_config['platform'] = platform_id
    save_project_config(config)

    # Mirror the values into the build window widgets, then start its thread.
    body._app_name_lineedit.setText(str(build_config.get('app_name', '')))
    body._app_icon_lineedit.setText(build_config['app_icon'])
    body._output_dir_lineedit.setText(build_config['output_dir'])
    body.set_platform_selected(build_config.get('platform', ''))

    # The build stages the project folder: flush scene edits made through the
    # MCP tools first, otherwise the package carries the old .scene files.
    warnings = _scene_build_warnings()

    body._progress_bar.setValue(0)
    body._progress_bar.show()
    body._build_thread.set_build_config(body.get_build_config())
    body._build_thread.start()
    body._is_building = True
    body._build_button.setText('Stop')

    return {
        'started': True,
        'config': build_config,
        'warnings': warnings,
        'note': 'Poll get_build_settings for progress; the log appears in the console.',
    }


@tool(
    'start_web_build',
    'Package the project for the browser (same as the Build button in the '
    'Web App tab of the Build window): the result is a folder with index.html '
    'and game.zip that plays the game through Pyodide and pygame-ce (a '
    'project that uses physics also gets the pymunk wheel next to the page, '
    'so nothing is fetched from PyPI at runtime), and it starts by itself '
    'once loaded. The browser plays all audio with its own codecs and the '
    'game loop follows the display\'s animation frame (a hidden tab pauses '
    'the game; sound begins with the first click/tap/key, browser autoplay '
    'rule). The previous <output_dir>/build/Web folder is always cleared '
    'first, so the package never carries a stale file. platform picks how the '
    'bundle is packaged: "" = 无平台 (plain index.html + game.zip) or '
    '"bilibili_toy" = Bilibili Toy (that platform drops every file whose '
    'suffix is not whitelisted, so the containers ship as .data - game.data, '
    'python_stdlib.data, the wheels - the page also loads the Toy JS SDK and '
    'the game talks to it through studio.sdk.toy). The TapTap PC SDK is '
    'desktop-only and is never part of a web bundle. The project code/assets '
    'are protected like in the desktop build (the installed engine is never '
    'modified) and the result lands in <output_dir>/build/Web. The build runs '
    'in the background: poll get_build_settings (web_is_building / '
    'web_progress), read get_console_logs, then open_output_dir with '
    'target="web".',
    {
        'type': 'object',
        'properties': {
            'app_name': {'type': 'string', 'description': 'Page title / app name (default: the project folder name).'},
            'app_icon': {'type': 'string', 'description': 'Absolute path of the favicon image (.png/.ico/.jpg/.bmp/.gif; optional).'},
            'output_dir': {'type': 'string', 'description': 'Absolute path of an existing output folder (default: the project folder).'},
            'platform': {'type': 'string', 'enum': list(_WEB_PLATFORMS),
                         'description': 'Publishing platform: "" = 无平台 (plain bundle), '
                                        '"bilibili_toy" = Bilibili Toy (.data containers + Toy JS '
                                        'SDK). Defaults to the saved pick (build.web.platform).'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Build a web app'},
)
def start_web_build(args):
    platform_id = args.get('platform')
    if platform_id is not None and platform_id not in _WEB_PLATFORMS:
        raise ToolError('Unknown platform "{}" - use "" (无平台) or "bilibili_toy".'.format(platform_id))

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
    if platform_id is not None:
        body.set_platform_selected(platform_id)

    body._progress_bar.setValue(0)
    body._progress_bar.show()
    body._run_button.setEnabled(False)
    warnings = _scene_build_warnings()
    build_config = body.get_build_config()
    body._build_thread.set_build_config(build_config)
    body._build_thread.start()
    body._is_building = True
    body._build_button.setText('Stop')

    return {
        'started': True,
        'config': build_config,
        'bundle_dir': (Path(build_config['output_dir']) / 'build' / 'Web').as_posix(),
        'platform': build_config.get('platform', ''),
        'warnings': warnings,
        'note': 'The previous bundle was cleared; poll get_build_settings (web_is_building / web_progress); the log appears in the console.',
    }


@tool(
    'start_android_build',
    'Package the project into an Android APK (same as the Build button of the '
    'Android App tab): the editor writes a fresh dist from the bundled runtime '
    'pack, compiles it with the JDK + Android SDK set in Editor Settings > '
    'Android Build (aapt2 -> javac -> d8 -> zipalign -> apksigner) and copies '
    'the result to <output_dir>/build/Android/<app name>-debug.apk or '
    '-release.apk. Nothing is downloaded: no Gradle, no AGP. build_type '
    '"debug" signs with a generated debug key; "release" signs with the '
    'keystore + alias configured in the tab and the passwords stored in the '
    'editor settings (they cannot be passed here). The project is protected '
    'like the other builds. This takes a few seconds; it runs in the '
    'background - poll get_build_settings (android_is_building / '
    'android_progress) and read get_console_logs; check android_toolchain '
    'first when the JDK/SDK paths are empty.',
    {
        'type': 'object',
        'properties': {
            'output_dir': {'type': 'string',
                           'description': 'Absolute path of an existing output folder '
                                          '(default: the project folder).'},
            'app_name': {'type': 'string', 'description': 'Launcher name and APK file name.'},
            'app_icon': {'type': 'string', 'description': 'Absolute path of a square .png icon (optional).'},
            'build_type': {'type': 'string', 'enum': list(_ANDROID_BUILD_TYPES),
                           'description': 'debug (debug key) or release (the configured '
                                          'keystore). Defaults to the saved pick.'},
            'package': {'type': 'string',
                        'description': 'Application id, e.g. "org.pygamestudio.mygame" '
                                       '(default: derived from the app name).'},
            'version_name': {'type': 'string', 'description': 'e.g. "1.0.0".'},
            'version_code': {'type': 'integer', 'minimum': 1,
                             'description': 'Version code the store compares (1, 2, ...).'},
            'orientation': {'type': 'string',
                            'enum': ['landscape', 'portrait', 'sensor_landscape',
                                     'sensor_portrait', 'full_sensor'],
                            'description': 'Screen orientation. sensor_* follow the device, '
                                           'full_sensor flips with it.'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Build an Android APK'},
)
def start_android_build(args):
    from pygamestudio.common.utils import android_runtime
    from pygamestudio.gui.build import android_dist

    body = _android_build_body()
    if getattr(body, '_is_building', False):
        raise ToolError('An Android build is already running (use stop_build to stop it).')
    if not (project_path() / 'main.py').exists():
        raise ToolError('main.py is not in the project root - the project cannot be built.')

    build_type = args.get('build_type')
    if build_type is not None and build_type not in _ANDROID_BUILD_TYPES:
        raise ToolError('build_type must be "debug" or "release".')
    orientation = args.get('orientation')
    if orientation is not None and orientation not in android_dist.ORIENTATIONS:
        raise ToolError('Unknown orientation "{}" - use one of {}.'
                        .format(orientation, ', '.join(android_dist.ORIENTATIONS)))

    output_dir = (args.get('output_dir') or '').strip()
    if output_dir:
        output_path = Path(output_dir).expanduser()
        if not output_path.is_absolute():
            raise ToolError('output_dir must be an absolute path.')
        if not output_path.exists() or not output_path.is_dir():
            raise ToolError('The output folder "{}" does not exist.'.format(output_path))
    else:
        output_path = project_path()

    app_icon = (args.get('app_icon') or '').strip()
    if app_icon and not Path(app_icon).exists():
        raise ToolError('The app icon "{}" does not exist.'.format(app_icon))

    package = (args.get('package') or '').strip()
    if package and not android_dist.is_valid_package(package):
        raise ToolError('"{}" is not a valid package name - two or more lowercase '
                        'segments, e.g. org.pygamestudio.mygame.'.format(package))

    # Mirror the arguments into the tab so the panel shows what is being built;
    # get_build_config() then saves the project-side values (name, icon,
    # package, orientation, ...) exactly like a click would.
    body.set_app_name((args.get('app_name') or '').strip() or body._app_name_lineedit.text())
    if app_icon:
        body.set_app_icon(app_icon)
    body._output_dir_lineedit.setText(output_path.as_posix())
    if package:
        body._package_lineedit.setText(package)
    if args.get('version_name'):
        body._version_name_lineedit.setText(str(args['version_name']))
    if args.get('version_code'):
        body._version_code_lineedit.setText(str(args['version_code']))
    if build_type:
        index = body._build_type_combobox.findData(build_type)
        body._build_type_combobox.setCurrentIndex(max(0, index))
    if orientation:
        index = body._orientation_combobox.findData(orientation)
        body._orientation_combobox.setCurrentIndex(max(0, index))
    body._update_signing_enabled()

    build_config = body.get_build_config()

    # The tab saves these on the widget signals (editingFinished / activated),
    # which a tool call never triggers - write them here so the panel, the
    # project file and the next build agree.
    from pygamestudio.common.utils.config import get_project_config, save_project_config
    project_config = get_project_config()
    saved_build = project_config.setdefault('build', {})
    saved_build['app_name'] = build_config['app_name']
    saved_build['app_icon'] = build_config['app_icon']
    saved_build['output_dir'] = build_config['output_dir']
    saved_build['android_package'] = build_config['package']
    saved_build['android_version_name'] = build_config['version_name']
    try:
        saved_build['android_version_code'] = int(build_config['version_code'])
    except (TypeError, ValueError):
        saved_build['android_version_code'] = 1
    saved_build['android_orientation'] = build_config['orientation']
    saved_build['android_build_type'] = build_config['build_type']
    save_project_config(project_config)

    if build_config['build_type'] == 'release':
        if not build_config.get('keystore') or not Path(build_config['keystore']).is_file():
            raise ToolError('A release build needs a keystore: set build.android_keystore '
                            '(and build.android_key_alias) in the project, or build "debug".')
        if not build_config.get('key_alias'):
            raise ToolError('A release build needs build.android_key_alias (the key alias).')

    # Fail here rather than inside the thread: the reasons are actionable and
    # the panel only shows them in the console.
    try:
        android_runtime.find_pack()
    except Exception as error:                      # noqa: BLE001 - report as a tool error
        raise ToolError('The Android runtime pack is missing from the editor: {}'.format(error))
    toolchain = _android_toolchain_report(build_config)
    if not toolchain.get('ok'):
        raise ToolError('The Android build cannot start: {}. Fill the JDK and Android SDK '
                        'paths in Editor Settings > Android Build.'
                        .format(', '.join(str(problem) for problem in toolchain['problems'])
                                or 'unknown reason'))

    body._progress_bar.setValue(0)
    body._progress_bar.show()
    warnings = _scene_build_warnings()
    body._build_thread.set_build_config(build_config)
    body._build_thread.start()
    body._is_building = True
    body._build_button.setText('Stop')

    app_file_name = body._build_thread.output_file_name(build_config['app_name'],
                                                        build_config['build_type'] == 'release')
    return {
        'started': True,
        'config': _android_public_config(build_config),
        'apk': (output_path / 'build' / 'Android' / app_file_name).as_posix(),
        'toolchain': toolchain,
        'warnings': warnings,
        'note': 'Poll get_build_settings (android_is_building / android_progress); the log '
                'appears in the console.',
    }


@tool(
    'stop_build',
    'Stop the running build - whichever tab is building (desktop app, web app '
    'or Android APK).',
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
                         ('web', _web_build_body(required=False)),
                         ('android', _android_build_body(required=False))):
        if body is not None and getattr(body, '_is_building', False):
            body._build_thread.stop()
            stopped.append(target)
    if not stopped:
        return {'stopped': False, 'reason': 'no build is running'}
    return {'stopped': True, 'targets': stopped}


@tool(
    'open_output_dir',
    'Open a build output folder in the system file manager: the desktop app '
    'output (target "desktop", default), the web bundle folder '
    '(<output>/build/Web) once a web build was made (target "web") or the APK '
    'folder (<output>/build/Android) of an Android build (target "android").',
    {
        'type': 'object',
        'properties': {
            'target': {'type': 'string', 'enum': ['desktop', 'web', 'android'], 'default': 'desktop',
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

    if target == 'android':
        body = _android_build_body()
        output_dir = (body._output_dir_lineedit.text() or '').strip() or str(project_path())
        apk_dir = Path(output_dir) / 'build' / 'Android'
        folder = apk_dir if apk_dir.exists() else Path(output_dir)
        if not folder.exists():
            raise ToolError('The output folder "{}" does not exist yet.'.format(folder))
        _open_folder(folder)
        return {'opened': folder.as_posix(), 'target': 'android'}

    body = _build_body()
    output_dir = (body._output_dir_lineedit.text() or '').strip()
    if not output_dir:
        raise ToolError('No output folder is configured yet.')
    body._open_output_dir()
    return {'opened': output_dir, 'target': 'desktop'}
