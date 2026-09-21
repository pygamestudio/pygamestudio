"""Web build: package the project (and a copy of the engine) for the browser.

The bundle is a plain folder with a few files:

* ``index.html`` - loads Pyodide (Python compiled to WebAssembly), unpacks
  ``game.zip`` into its file system and starts the game loop;
* ``game.zip`` - the PROTECTED project (assets and scripts encrypted, code
  stripped/obfuscated, the build key in ``resources.cache`` - exactly like the
  desktop build), plus a COPY of the engine and a generated ``web_boot.py``;
* one favicon file for the browser tab.

The engine copy is patched while the archive is written: a browser tab cannot
block on ``Clock.tick()`` and cannot call ``sys.exit()``, so the copy gets an
async ``Game.run_async()`` loop, and ``run()`` is kept as a wrapper for
synchronous callers. **The installed engine is never modified** - every change
lives in the archive, and the project keeps running from the editor/desktop
exactly as before.
"""

import html
import http.server
import json
import os
import platform
import shutil
import subprocess
import threading
import webbrowser
import zipfile
from functools import partial
from pathlib import Path
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
import pygamestudio
from pygamestudio.gui.console.logger import Logger
from pygamestudio.gui.build import obfuscation
from pygamestudio.gui.build import assets as asset_build
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils import assets
from pygamestudio.common.utils.config import get_project_config, update_project_config
from pygamestudio.common.utils.path import RES_PATH

#: Pyodide runtime loaded by the generated page. It is not shown in the
#: window on purpose: change it here (or pass ``pyodide_url`` in the build
#: config) to self-host a copy instead of using the CDN.
DEFAULT_PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/'
#: Where a web build lands inside the output dir.
BUNDLE_SUBDIR = ('build', 'Web')
#: Staging folder of the protection step, inside the bundle dir (removed again
#: once the archive is written); same name the desktop build uses.
PROTECTED_WORK_DIR_NAME = '_protected'
#: Fallback canvas size when a project has none (the editor's own default).
DEFAULT_CANVAS_SIZE = (800, 600)
#: Largest page icon edge; bigger images are scaled down before saving.
FAVICON_MAX_SIZE = 256
#: Name of the engine package inside the bundle and in the zip archive.
ENGINE_PACKAGE = 'pygamestudio'
#: Directories that never belong in the bundle (caches, VCS data, builds).
_IGNORED_DIR_NAMES = {'__pycache__', '.git', '.github', '.vscode', '.idea',
                      'venv', '.venv', 'env', 'node_modules', 'dist', 'build'}
#: Engine package folders the game runtime needs (the editor is left out).
_ENGINE_DIRS = ('api', 'game', 'common')
#: Editor files the runtime imports (the logger is plain Python, no Qt in it).
_ENGINE_EXTRA_FILES = ('gui/__init__.py', 'gui/console/__init__.py', 'gui/console/logger.py')
#: ``common/res`` data only the editor uses (fonts are per project).
_ENGINE_RES_SKIP = ('fonts', 'qss', 'templates', 'audios')
#: File names never copied from the project root.
_PROJECT_SKIP_SUFFIXES = ('.pyc', '.pyo')
#: Engine file replaced by its patched copy in the bundle.
GAME_SOURCE_RELATIVE_PATH = 'api/core/game.py'
_SOURCE_ENCODING = 'utf-8'

#: Textual patches applied to the COPY of api/core/game.py inside the bundle.
#: Each entry must match exactly once, otherwise the build stops: the engine
#: changed and this patch has to be updated.
_GAME_PATCHES = (
    (
        "from pygamestudio.api.config.project import get_project_config\n",
        "from pygamestudio.api.config.project import get_project_config\n"
        "\n"
        "# --- Web build patch: this copy runs on an asyncio loop, see the end of the file. ---\n"
        "import asyncio\n"
        "import time\n"
    ),
    (
        "    def run(self):\n"
        "        \"\"\"Start the game loop. Blocks until the window is closed.\"\"\"\n",
        "    async def run_async(self):\n"
        "        \"\"\"Web build: the async game loop awaited by the page entry point.\n"
        "\n"
        "        Same event dispatch as run(), but a frame never blocks the tab:\n"
        "        the loop awaits asyncio.sleep() instead of Clock.tick() and\n"
        "        returns when the run ends instead of exiting the interpreter.\n"
        "        \"\"\"\n"
    ),
    (
        "            delta_time = self._clock.tick(self._fps) / 1000\n",
        "            delta_time = self._web_frame_delta()\n"
        "            await asyncio.sleep(max(0.0, (1.0 / self._fps) - delta_time))\n"
    ),
    (
        "        pygame.quit()\n"
        "        sys.exit()\n",
        "        pygame.quit()\n"
    ),
    (
        "        else:\n"
        "            caller_frame = inspect.stack()[-1]\n"
        "            caller_file_path = caller_frame.filename\n"
        "            self._project_path = Path(caller_file_path).parent.resolve().as_posix()\n",
        "        else:\n"
        "            # Web build patch: the page executes the bundle through\n"
        "            # Pyodide, so the project root published by web_boot.py\n"
        "            # (PROJECT_PATH) wins; the caller-frame heuristic stays as\n"
        "            # the fallback for direct synchronous use.\n"
        "            project_root = os.environ.get('PROJECT_PATH', '')\n"
        "            if project_root and Path(project_root).is_dir():\n"
        "                self._project_path = Path(project_root).resolve().as_posix()\n"
        "            else:\n"
        "                caller_frame = inspect.stack()[-1]\n"
        "                caller_file_path = caller_frame.filename\n"
        "                self._project_path = Path(caller_file_path).parent.resolve().as_posix()\n"
    ),
)

#: Appended to the COPY of api/core/game.py: helpers for the async loop.
_GAME_PATCH_APPENDIX = '''

# ============================================================================
# Web build patch: this file is a COPY made by PyGameStudio's Web build.
# The installed pygamestudio package was not modified.
# ============================================================================
def _web_frame_delta(self):
    """Seconds since the previous frame.

    A browser tab must stay responsive, so the web loop cannot use
    Clock.tick() (it blocks the main thread): it measures the frame itself and
    run_async() awaits the rest of the frame budget.
    """
    now = time.monotonic()
    last = getattr(self, '_web_last_frame_time', None)
    self._web_last_frame_time = now
    if last is None:
        return 1.0 / self._fps
    return min(now - last, 0.25)


Game._web_frame_delta = _web_frame_delta


def _web_run(self):
    """run() for the web: drive the async loop to completion.

    Synchronous callers keep working; async callers use
    ``await game.run_async()`` (that is what the generated web_boot.py does).
    """
    return asyncio.run(self.run_async())


Game.run = _web_run
'''


class WebBuildError(Exception):
    """A web build that cannot produce a working bundle."""


class WebBuildCancelled(Exception):
    """The user stopped the web build."""


class _WebPreviewRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the bundle folder with the MIME types the page needs."""

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        '.ico': 'image/x-icon',
        '.mjs': 'text/javascript',
        '.zip': 'application/zip',
    }

    def log_message(self, format, *args):
        # The editor has its own log panel; the preview server stays quiet.
        pass


class _WebPreviewServer:
    """Tiny local HTTP server behind the Run button.

    The page must be served over HTTP (a ``file://`` page cannot fetch
    game.zip), so Run starts this server for the bundle folder and opens the
    browser on it. The thread is a daemon: closing the editor stops it.
    """

    def __init__(self):
        self._server = None
        self._thread = None
        self._directory = None
        self._url = ''

    def url_for(self, directory) -> str:
        """Start (or reuse) the server for this folder and return its URL."""
        directory = Path(directory).resolve()
        if self._server is not None and self._directory == directory:
            return self._url

        self.stop()
        handler = partial(_WebPreviewRequestHandler, directory=directory.as_posix())
        self._server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._directory = directory
        self._url = 'http://127.0.0.1:{}/index.html'.format(self._server.server_address[1])
        return self._url

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        self._server = None
        self._thread = None
        self._directory = None
        self._url = ''


class WebAppBuildWindow(QScrollArea):
    def __init__(self, game_manager):
        super().__init__()
        self._game_manager = game_manager
        self._central_widget = QWidget()
        self._app_name_label = QLabel()
        self._app_name_lineedit = QLineEdit()
        self._app_icon_label = QLabel()
        self._app_icon_lineedit = QLineEdit()
        self._app_icon_browse_button = QPushButton()
        self._output_dir_label = QLabel()
        self._output_dir_lineedit = QLineEdit()
        self._output_dir_browse_button = QPushButton()
        self._progress_bar = QProgressBar()
        self._build_button = QPushButton()
        self._run_button = QPushButton()
        self._open_output_dir_button = QPushButton()

        self._build_thread = WebBuildThread(self._game_manager)
        self._preview_server = _WebPreviewServer()
        self._is_building = False

        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self.setWidgetResizable(True)
        self.setWidget(self._central_widget)

        self._app_name_label.setText(T.tr('build.app_name', 'App Name'))
        self._app_name_lineedit.setPlaceholderText(T.tr('build.app_name_placeholder', 'Please enter the app name'))
        self._app_icon_label.setText(T.tr('build.app_icon', 'App Icon'))
        self._app_icon_lineedit.setPlaceholderText(T.tr('build.web_app_icon_placeholder', 'Please choose the image used as the page icon (.png/.ico/.jpg/.jpeg/.bmp/.gif)'))
        self._app_icon_lineedit.setToolTip(T.tr('build.web_app_icon_tooltip', 'This image becomes the browser tab icon (favicon) of the page; it is converted to .ico automatically'))
        self._app_icon_browse_button.setIcon(QIcon(':/images/browse.png'))
        self._output_dir_label.setText(T.tr('build.output_dir', 'Output Dir'))
        self._output_dir_lineedit.setPlaceholderText(T.tr('build.output_dir_placeholder', 'Please choose the output dir'))
        self._output_dir_browse_button.setIcon(QIcon(':/images/browse.png'))
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._build_button.setText(T.tr('build.build', 'Build'))
        self._run_button.setText(T.tr('build.web_run', 'Run in Browser'))
        self._run_button.setEnabled(False)
        self._open_output_dir_button.setText(T.tr('build.open_output_dir', 'Open Output Dir'))
        self._update_button_widths()

    def _set_signal(self):
        self._app_icon_browse_button.clicked.connect(self._browse_app_icon)
        self._output_dir_browse_button.clicked.connect(self._browse_output_dir)
        self._build_button.clicked.connect(self._build)
        self._run_button.clicked.connect(self._run_in_browser)
        self._open_output_dir_button.clicked.connect(self._open_output_dir)

        self._build_thread.stopped_signal.connect(self._on_build_stopped)
        self._build_thread.finished_signal.connect(self._on_build_finished)
        self._build_thread.progress_signal.connect(self._on_progress_updated)

        T.add_observer(self)

    def _set_layout(self):
        app_icon_layout = QHBoxLayout()
        app_icon_layout.addWidget(self._app_icon_lineedit)
        app_icon_layout.addSpacing(5)
        app_icon_layout.addWidget(self._app_icon_browse_button)

        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self._output_dir_lineedit)
        output_dir_layout.addSpacing(5)
        output_dir_layout.addWidget(self._output_dir_browse_button)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self._build_button)
        button_layout.addSpacing(5)
        button_layout.addWidget(self._run_button)
        button_layout.addSpacing(5)
        button_layout.addWidget(self._open_output_dir_button)
        button_layout.addStretch()

        main_g_layout = QGridLayout(self._central_widget)
        main_g_layout.setHorizontalSpacing(10)
        main_g_layout.setVerticalSpacing(10)
        main_g_layout.addWidget(self._app_name_label, 0, 0, 1, 1)
        main_g_layout.addWidget(self._app_name_lineedit, 0, 1)
        main_g_layout.addWidget(self._app_icon_label, 1, 0, 1, 1)
        main_g_layout.addLayout(app_icon_layout, 1, 1)
        main_g_layout.addWidget(self._output_dir_label, 2, 0, 1, 1)
        main_g_layout.addLayout(output_dir_layout, 2, 1)
        main_g_layout.addWidget(self._progress_bar, 3, 0, 1, 2)
        main_g_layout.addLayout(button_layout, 4, 0, 1, 2)
        main_g_layout.setColumnStretch(1, 1)
        main_g_layout.setContentsMargins(5, 5, 5, 0)

    def _set_object_name(self):
        self._build_button.setObjectName('webAppBuildBtn')

    def _update_button_widths(self):
        """Give the buttons one width, wide enough for the longer label."""
        button_width = max(self._build_button.sizeHint().width(),
                           self._run_button.sizeHint().width(),
                           self._open_output_dir_button.sizeHint().width())
        self._build_button.setMinimumWidth(button_width)
        self._run_button.setMinimumWidth(button_width)
        self._open_output_dir_button.setMinimumWidth(button_width)

    def get_ready_for_project(self):
        project_path = Path(self._game_manager.get_project_path())
        project_config = get_project_config()

        # The app name is the page title and the same setting the desktop
        # build uses; it starts from the project folder name.
        try:
            app_name = project_config['build']['app_name']
        except Exception as e:
            app_name = ''
        self._app_name_lineedit.setText(app_name or project_path.name)

        # One app icon for every target: the desktop build uses build.app_icon
        # too, and a new project starts with <project>/image/logo.png.
        try:
            app_icon = project_config['build']['app_icon']
        except Exception as e:
            app_icon = ''
        if not app_icon:
            default_icon = project_path / 'image/logo.png'
            app_icon = default_icon.as_posix() if default_icon.exists() else ''
        self._app_icon_lineedit.setText(app_icon)

        try:
            output_dir = project_config['build']['web']['output_dir']
        except Exception as e:
            output_dir = ''
        self._output_dir_lineedit.setText(output_dir or project_path.as_posix())

    def _browse_app_icon(self):
        icon_path, _ = QFileDialog.getOpenFileName(self, T.tr('build.select_app_icon', 'Select App Icon'), self._game_manager.get_project_path(), 'Format (*png *.ico *.jpg *.jpeg *.bmp *.gif)')
        if icon_path:
            self._app_icon_lineedit.setText(icon_path)

    def _browse_output_dir(self):
        output_dir = QFileDialog.getExistingDirectory(self, T.tr('build.select_output_dir', 'Select Output Dir'))
        if output_dir:
            self._output_dir_lineedit.setText(output_dir)

    def _check_before_build(self):
        if not (Path(self._game_manager.get_project_path()) / 'main.py').exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_main_not_found', 'main.py is not found'))
            return False

        for template_name in ('web_index_template.html', 'web_boot_template.py'):
            if not (RES_PATH / 'templates' / template_name).exists():
                QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_web_template_not_found', 'The web build templates are missing from this installation: {}').format(template_name))
                return False

        if self._app_icon_lineedit.text().strip() and not Path(self._app_icon_lineedit.text().strip()).exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_app_icon_not_exist', 'App icon not exist'))
            return False

        if not self._output_dir_lineedit.text().strip():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_no_output_dir', 'Please choose the output dir'))
            return False

        if not Path(self._output_dir_lineedit.text().strip()).exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_output_dir_not_exist', 'Output dir does not exist'))
            return False

        return True

    def _build(self):
        if self._is_building:
            choice = QMessageBox.question(QApplication.activeWindow(), T.tr('message_box.quesiton_title', 'Confirm'), T.tr('message_box.question_stop_build', 'Sure to stop the building?'))
            if choice == QMessageBox.StandardButton.Yes:
                self._build_button.setEnabled(False)
                self._build_thread.stop()
            return

        is_ok_to_build = self._check_before_build()
        if not is_ok_to_build:
            return

        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._run_button.setEnabled(False)
        self._build_thread.set_build_config(self.get_build_config())
        self._build_thread.start()
        self._is_building = True
        self._build_button.setText(T.tr('build.stop', 'Stop'))

    def _open_output_dir(self):
        if not self._output_dir_lineedit.text().strip():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_no_output_dir', 'Please choose the output dir'))
            return

        output_dir_path = Path(self._output_dir_lineedit.text().strip())
        if not output_dir_path.exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_output_dir_not_exist', 'Output dir does not exist'))
            return

        system = platform.system()
        if system == 'Windows':
            os.startfile(output_dir_path)
        elif system == 'Darwin':
            subprocess.Popen(['open', output_dir_path])
        elif system == 'Linux':
            subprocess.Popen(['xdg-open', output_dir_path])
        else:
            QMessageBox.information(QApplication.activeWindow(), T.tr('message_box.information_title', 'Info'), T.tr('message_box.information_os_content', 'Unsupported Operating System'))

    def _run_in_browser(self):
        """Serve the built folder over HTTP and open it in the browser."""
        bundle_dir = self._build_thread.bundle_dir
        if bundle_dir is None or not Path(bundle_dir).exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_web_bundle_missing', 'The web build output is missing, please build again: {}').format(str(bundle_dir)))
            self._set_run_enabled()
            return

        try:
            url = self._preview_server.url_for(bundle_dir)
        except Exception as e:
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_web_run_failed', 'Could not start the local preview server: {}').format(str(e)))
            return

        Logger.info(T.tr('build.web_preview', 'Web preview: {}').format(url))
        webbrowser.open(url)

    def _set_run_enabled(self):
        """Run is available once a bundle exists on disk."""
        bundle_dir = self._build_thread.bundle_dir
        self._run_button.setEnabled(bundle_dir is not None and Path(bundle_dir).exists())

    def _on_build_stopped(self):
        self._is_building = False
        self._build_button.setEnabled(True)
        self._build_button.setText(T.tr('build.build', 'Build'))
        self._progress_bar.hide()
        self._set_run_enabled()

    def _on_build_finished(self, is_successful):
        self._is_building = False
        self._build_button.setEnabled(True)
        self._build_button.setText(T.tr('build.build', 'Build'))
        self._set_run_enabled()

        if not is_successful:
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_fail_to_build', 'Failed to build the project. Please check the log.'))

    def _on_progress_updated(self, progress):
        self._progress_bar.setValue(progress)

    def get_build_config(self):
        project_path = Path(self._game_manager.get_project_path())
        app_name = self._app_name_lineedit.text().strip() or project_path.name
        app_icon = self._app_icon_lineedit.text().strip()
        output_dir = self._output_dir_lineedit.text().strip() or project_path.as_posix()

        # Stored under build.web so the desktop settings (build.*) survive.
        update_project_config('build.web', {'output_dir': output_dir})
        # The app name and the icon are the same settings the desktop build
        # uses: one app for every target (a new project already ships
        # image/logo.png).
        update_project_config('build.app_name', app_name)
        update_project_config('build.app_icon', app_icon)

        return {'app_name': app_name, 'app_icon': app_icon, 'output_dir': output_dir}

    def retranslate(self):
        self._app_name_label.setText(T.tr('build.app_name', 'App Name'))
        self._app_name_lineedit.setPlaceholderText(T.tr('build.app_name_placeholder', 'Please enter the app name'))
        self._app_icon_label.setText(T.tr('build.app_icon', 'App Icon'))
        self._app_icon_lineedit.setPlaceholderText(T.tr('build.web_app_icon_placeholder', 'Please choose the image used as the page icon (.png/.ico/.jpg/.jpeg/.bmp/.gif)'))
        self._app_icon_lineedit.setToolTip(T.tr('build.web_app_icon_tooltip', 'This image becomes the browser tab icon (favicon) of the page; it is converted to .ico automatically'))
        self._output_dir_label.setText(T.tr('build.output_dir', 'Output Dir'))
        self._output_dir_lineedit.setPlaceholderText(T.tr('build.output_dir_placeholder', 'Please choose the output dir'))
        self._build_button.setText(T.tr('build.build', 'Build'))
        self._run_button.setText(T.tr('build.web_run', 'Run in Browser'))
        self._open_output_dir_button.setText(T.tr('build.open_output_dir', 'Open Output Dir'))
        self._update_button_widths()


class WebBuildThread(QThread):
    stopped_signal = Signal()
    finished_signal = Signal(bool)
    progress_signal = Signal(int)

    def __init__(self, game_manager):
        super().__init__()
        self._game_manager = game_manager
        self._build_config = {}
        self._stop_requested = False
        #: Folder of the last successful build (used by the Run button).
        self.bundle_dir = None

    def set_build_config(self, build_config):
        """Take a snapshot of the build configuration.

        It is filled in by the window on the UI thread, so the worker never
        touches a widget and the values stay stable while the build runs.
        """
        self._build_config = dict(build_config or {})

    def stop(self):
        self._stop_requested = True

    def run(self):
        try:
            self._stop_requested = False

            builder = WebAppBuilder(
                self._game_manager.get_project_path(),
                self._build_config,
                progress=self.progress_signal.emit,
                stop_check=lambda: self._stop_requested
            )
            bundle_dir = builder.build()

            if self._stop_requested:
                Logger.info(T.tr('build.build_stopped', 'Build stopped'))
                self.stopped_signal.emit()
                return

            self.bundle_dir = bundle_dir
            Logger.info(T.tr('build.web_build_output', 'Web build output: {}').format(bundle_dir.as_posix()))
            Logger.info(T.tr('build.web_serve_hint', 'Serve the folder over HTTP to play it, for example: python -m http.server 8000 --directory "{}"').format(bundle_dir.as_posix()))
            self.progress_signal.emit(100)
            self.finished_signal.emit(True)
        except WebBuildCancelled:
            Logger.info(T.tr('build.build_stopped', 'Build stopped'))
            self.stopped_signal.emit()
        except Exception as e:
            Logger.error(str(e))
            self.finished_signal.emit(False)


class WebAppBuilder:
    """Builds the browser bundle (index.html + game.zip).

    No widget dependency (only QImage for the page icon), so the window can
    drive it from a thread and tests can drive it directly. The zip contains
    the protected staging copy of the project (same protection as the desktop
    build), a copy of the engine and the generated web_boot.py; the copy of
    api/core/game.py is patched inside the archive and the installed engine
    file is never written to.
    """

    def __init__(self, project_path, build_config, progress=None, stop_check=None):
        self._project_path = Path(project_path)
        app_name = (build_config.get('app_name') or build_config.get('page_title') or '').strip()
        self._page_title = app_name or self._project_path.name
        self._app_icon = (build_config.get('app_icon') or '').strip()
        output_dir = (build_config.get('output_dir') or '').strip()
        self._output_dir = Path(output_dir) if output_dir else None
        pyodide_url = (build_config.get('pyodide_url') or '').strip() or DEFAULT_PYODIDE_URL
        self._pyodide_url = pyodide_url if pyodide_url.endswith('/') else pyodide_url + '/'
        self._progress_callback = progress
        self._stop_check = stop_check

    # ---------- Public API ----------

    def build(self) -> Path:
        """Create the bundle and return its folder."""
        if self._output_dir is None:
            raise WebBuildError(T.tr('build.web_no_output_dir', 'The web build needs an output dir'))

        self._check_stopped()
        bundle_dir = self._output_dir.joinpath(*BUNDLE_SUBDIR)
        bundle_dir.mkdir(parents=True, exist_ok=True)
        self._progress(2)

        project_dir = self._prepare_protected_project(bundle_dir)
        self._check_stopped()

        index_template = self._read_template('web_index_template.html')
        boot_source = self._read_template('web_boot_template.py')
        self._progress(25)

        game_source_path = Path(pygamestudio.__file__).parent / GAME_SOURCE_RELATIVE_PATH
        if not game_source_path.exists():
            raise WebBuildError(T.tr('build.web_engine_source_missing', 'Cannot find the engine file to copy: {}').format(game_source_path.as_posix()))
        patched_source = self._patch_game_source(game_source_path.read_text(encoding=_SOURCE_ENCODING))
        self._progress(30)

        archive_path = bundle_dir / 'game.zip'
        project_count, engine_count = self._write_archive(archive_path, patched_source, boot_source, project_dir)
        self._progress(85)
        self._check_stopped()

        favicon_links = self._write_favicon(bundle_dir)
        self._progress(90)

        canvas_size = self._read_canvas_size()
        (bundle_dir / 'index.html').write_text(self._render_index(index_template, favicon_links, canvas_size), encoding=_SOURCE_ENCODING)
        self._progress(95)

        # The staging copy has done its job: only the page and the archive stay.
        shutil.rmtree(bundle_dir / PROTECTED_WORK_DIR_NAME, ignore_errors=True)

        if self._uses_physics():
            Logger.warning(T.tr('build.web_physics_unsupported', 'The project uses physics, which the browser cannot run yet (pymunk is not part of Pyodide): those objects will not be simulated in the web build'))

        Logger.info(T.tr('build.web_build_summary', 'Bundled {} project file(s) and {} engine file(s)').format(project_count, engine_count))
        self._check_stopped()
        return bundle_dir

    # ---------- Build steps ----------

    def _prepare_protected_project(self, bundle_dir):
        """Stage, strip, obfuscate and encrypt the project (like the desktop build).

        The project folder itself is never touched: the protection works on the
        staging copy inside the bundle folder, and that copy is what gets
        zipped. Its assets and scripts are encrypted; ``main.py`` stays a
        readable (stripped) file so the page's boot loader can start it, and a
        ``resources.cache`` with the build key ships next to it.
        """
        Logger.info(T.tr('build.protection_running', 'Preparing the project code and assets ...'))
        self._progress(8)
        try:
            prepared = obfuscation.prepare(self._project_path, bundle_dir)
        except asset_build.AssetBuildError as e:
            raise WebBuildError(T.tr('build.assets_failed', 'Encrypting the project assets failed, the build is stopped: {}').format(e))
        except obfuscation.ObfuscationError as e:
            raise WebBuildError(T.tr('build.obfuscation_failed', 'Code obfuscation failed, the build is stopped: {}').format(e))
        except obfuscation.ProtectionError as e:
            raise WebBuildError(T.tr('build.staging_failed', 'The project could not be prepared for the build, the build is stopped: {}').format(e))

        if prepared['obfuscation_summary'] is None:
            Logger.warning(T.tr('build.obfuscation_unavailable', 'pyobfus was not found: the code is stripped but not name-obfuscated'))
        else:
            Logger.info(T.tr('build.obfuscation_enabled', 'Obfuscated {} python file(s), no comment or docstring left').format(prepared['obfuscation_summary']['files']))
        summary = prepared['asset_summary']['summary']
        Logger.info(T.tr('build.assets_encrypted', 'Encrypted {} file(s) ({} KB), project scripts included').format(summary['files'], round(summary['bytes'] / 1024)))
        self._progress(20)
        return Path(prepared['project_dir'])

    def _write_archive(self, archive_path, patched_source, boot_source, project_dir):
        project_count = 0
        engine_count = 0

        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
            for source, arcname in self._project_files(project_dir):
                self._check_stopped()
                archive.write(source, arcname)
                project_count += 1
            self._progress(45)

            for source, arcname in self._engine_files():
                self._check_stopped()
                archive.write(source, arcname)
                engine_count += 1
            self._progress(70)

            archive.writestr(f'{ENGINE_PACKAGE}/{GAME_SOURCE_RELATIVE_PATH}', patched_source)
            archive.writestr('web_boot.py', boot_source)

        return project_count, engine_count

    def _project_files(self, project_dir):
        """(path, archive name) of every file of the protected staging copy."""
        for path in sorted(Path(project_dir).rglob('*')):
            if path.is_dir():
                continue

            relative_path = path.relative_to(project_dir)
            if any(part in _IGNORED_DIR_NAMES for part in relative_path.parts):
                continue
            if path.suffix in _PROJECT_SKIP_SUFFIXES or path.name == '.DS_Store':
                continue

            yield path, relative_path.as_posix()

    def _engine_files(self):
        """(path, archive name) of every engine file the runtime needs."""
        package_dir = Path(pygamestudio.__file__).parent

        for source, arcname in self._engine_extra_files(package_dir):
            yield source, arcname

        for directory_name in _ENGINE_DIRS:
            for path in sorted((package_dir / directory_name).rglob('*')):
                if path.is_dir():
                    continue

                relative_path = path.relative_to(package_dir)
                if any(part in _IGNORED_DIR_NAMES for part in relative_path.parts):
                    continue
                # Editor-only resource data (project fonts are packed with the
                # project itself, not with the engine).
                if relative_path.parts[:2] == ('common', 'res') and len(relative_path.parts) > 2 and relative_path.parts[2] in _ENGINE_RES_SKIP:
                    continue
                if relative_path.name.startswith('resources_rc') or relative_path.suffix == '.qrc':
                    continue
                # The patched copy is written separately.
                if relative_path.as_posix() == GAME_SOURCE_RELATIVE_PATH:
                    continue

                yield path, f'{ENGINE_PACKAGE}/{relative_path.as_posix()}'

    def _engine_extra_files(self, package_dir):
        for extra in (f'{ENGINE_PACKAGE}/__init__.py',) + tuple(f'{ENGINE_PACKAGE}/{name}' for name in _ENGINE_EXTRA_FILES):
            path = package_dir / extra[len(ENGINE_PACKAGE) + 1:]
            if path.exists():
                yield path, extra

    def _patch_game_source(self, source):
        """Apply the async-loop patch to the COPY of game.py (never the original)."""
        for index, (old, new) in enumerate(_GAME_PATCHES):
            if source.count(old) != 1:
                raise WebBuildError(T.tr('build.web_patch_failed', 'The engine file {} no longer matches the web patch (#{}): the web build was stopped and the installed engine was left unchanged').format(GAME_SOURCE_RELATIVE_PATH, index + 1))
            source = source.replace(old, new)
        return source + _GAME_PATCH_APPENDIX

    def _write_favicon(self, bundle_dir):
        """Write the page icon next to index.html and return its <link> tag.

        Exactly one icon file is produced: ``favicon.ico`` when the image can
        be converted to it (an .ico source is copied as it is), otherwise
        ``favicon.png``. Without an app icon the engine's own logo is used, so
        a web build always has one.
        """
        icon_path = Path(self._app_icon) if self._app_icon else RES_PATH / 'images/logo.png'
        if not icon_path.exists():
            if self._app_icon:
                raise WebBuildError(T.tr('build.web_app_icon_not_exist', 'The app icon does not exist: {}').format(icon_path.as_posix()))
            return ''

        image = QImage(icon_path.as_posix())
        if image.isNull():
            if self._app_icon:
                raise WebBuildError(T.tr('build.web_app_icon_invalid', 'The app icon is not a readable image: {}').format(icon_path.as_posix()))
            return ''
        if image.width() > FAVICON_MAX_SIZE or image.height() > FAVICON_MAX_SIZE:
            image = image.scaled(FAVICON_MAX_SIZE, FAVICON_MAX_SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        if icon_path.suffix.lower() == '.ico':
            shutil.copyfile(icon_path, bundle_dir / 'favicon.ico')
            favicon_name = 'favicon.ico'
        elif image.save((bundle_dir / 'favicon.ico').as_posix(), 'ICO'):
            favicon_name = 'favicon.ico'
        elif image.save((bundle_dir / 'favicon.png').as_posix(), 'PNG'):
            favicon_name = 'favicon.png'
            Logger.warning(T.tr('build.web_favicon_png_fallback', 'The icon {} could not be written as .ico: it is used as favicon.png instead').format(icon_path.as_posix()))
        elif self._app_icon:
            raise WebBuildError(T.tr('build.web_app_icon_invalid', 'The app icon is not a readable image: {}').format(icon_path.as_posix()))
        else:
            return ''

        Logger.info(T.tr('build.web_favicon_written', 'The app icon is used as the page favicon: {}').format(favicon_name))
        icon_type = 'image/x-icon' if favicon_name.endswith('.ico') else 'image/png'
        return '<link rel="icon" type="{}" href="{}">'.format(icon_type, favicon_name)

    def _read_canvas_size(self):
        """The canvas size of the project, so the page is right before starting."""
        try:
            project_config = json.loads(assets.read_text(self._project_path / 'project.pygs'))
            size = project_config.get('screen_size') or [project_config.get('screen_width'), project_config.get('screen_height')]
            width, height = int(size[0]), int(size[1])
            if width > 0 and height > 0:
                return width, height
        except Exception as e:
            Logger.warning('Failed to read the screen size from project.pygs: {}'.format(e))
        return DEFAULT_CANVAS_SIZE

    def _render_index(self, template, favicon_links, canvas_size):
        return (template
                .replace('__PYGS_TITLE__', html.escape(self._page_title))
                .replace('__PYGS_FAVICON_LINK__', favicon_links)
                .replace('__PYGS_CANVAS_WIDTH__', str(canvas_size[0]))
                .replace('__PYGS_CANVAS_HEIGHT__', str(canvas_size[1]))
                .replace('__PYGS_PYODIDE_URL__', self._pyodide_url))

    def _read_template(self, name):
        path = RES_PATH / 'templates' / name
        if not path.exists():
            raise WebBuildError(T.tr('build.web_template_missing', 'The web build template is missing: {}').format(path.as_posix()))
        return path.read_text(encoding=_SOURCE_ENCODING)

    def _uses_physics(self):
        """True when any scene of the project enables physics on an object."""
        for path in sorted(self._project_path.rglob('*.scene')):
            try:
                text = path.read_text(encoding=_SOURCE_ENCODING, errors='replace')
            except OSError:
                continue
            if '"physics_enabled": true' in text or '"physics_enabled":true' in text:
                return True
        return False

    def _progress(self, value):
        if self._progress_callback is not None:
            self._progress_callback(value)

    def _check_stopped(self):
        if self._stop_check is not None and self._stop_check():
            raise WebBuildCancelled()
