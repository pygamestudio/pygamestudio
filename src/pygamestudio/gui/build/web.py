"""Web build: package the project (and a copy of the engine) for the browser.

The bundle is a plain folder with a few files:

* ``index.html`` - loads Pyodide (Python compiled to WebAssembly), unpacks
  ``game.zip`` into its file system and starts the game loop;
* ``game.zip`` - the PROTECTED project (assets and scripts encrypted, code
  stripped of comments/docstrings, the build key in ``resources.cache`` -
  exactly like the desktop build), plus a COPY of the engine and a generated
  ``web_boot.py``;
* one favicon file for the browser tab;
* ``pymunk-*.whl`` - only when the project uses physics: the Pyodide wheel of
  pymunk (shipped with the engine), installed by the page from its own folder
  so the browser simulates the physics without downloading anything.

The engine copy is patched while the archive is written: a browser tab cannot
block on ``Clock.tick()`` and cannot call ``sys.exit()``, so the copy gets an
async ``Game.run_async()`` loop, and ``run()`` is kept as a wrapper for
synchronous callers. **The installed engine is never modified** - every change
lives in the archive, and the project keeps running from the editor/desktop
exactly as before.

The publishing platform decides the packaging (see the dropdown in the build
window). "None" produces the bundle described above; **Bilibili Toy** only
accepts whitelisted file suffixes, so there the containers are renamed to
``.data`` (``game.data``, ``python_stdlib.data``, the wheels), the runtime's
loader and lock file are patched to match, and the page also loads the Toy JS
SDK - the Python side of it lives in ``pygamestudio/sdk/toy``.
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
from pygamestudio.gui.build import protection
from pygamestudio.gui.build import assets as asset_build
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils import assets
from pygamestudio.common.utils import qr
from pygamestudio.common.utils.config import (get_project_config,
                                              save_project_config,
                                              update_project_config)
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.common.utils.system import get_lan_ip

#: Pyodide runtime the generated page falls back to when the engine's bundled
#: copy is missing (it normally ships in ``common/res/pyodide`` and is loaded
#: from the page's own folder). Pass ``pyodide_url`` in the build config to
#: point the page at another copy (the CDN, or your own server).
DEFAULT_PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/'
#: Folder in ``common/res`` with the self-hosted Pyodide runtime: the core
#: files plus the wheels the page loads (pygame-ce; cffi and pycparser when
#: the project uses physics). Must belong to the DEFAULT_PYODIDE_URL version -
#: update both together. The build copies it next to the page.
PYODIDE_DIR_NAME = 'pyodide'
#: ``pyodide_url`` written into the page when the bundled runtime is used.
LOCAL_PYODIDE_URL = './{}/'.format(PYODIDE_DIR_NAME)
#: Where a web build lands inside the output dir.
BUNDLE_SUBDIR = ('build', 'Web')
#: Suffix of the folder the package is assembled in before it replaces the
#: previous bundle (a failed build never leaves a half-written package).
BUNDLE_STAGING_SUFFIX = '.building'
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
#: ``sdk`` holds the platform bridges: copied so ``import`` never
#: breaks in the browser, where every call reports "Windows only".
_ENGINE_DIRS = ('api', 'game', 'common', 'sdk')
#: Bridges that never belong in a web bundle: the TapTap PC SDK is a Windows
#: desktop library (ctypes + a DLL) and the browser has no use for it. The
#: page only keeps the bridges that work there (Bilibili Toy).
_ENGINE_WEB_SKIP_DIRS = (('sdk', 'taptap'),)
#: Single engine files the page never shows (the TapTap pick only exists in the
#: desktop tab of the build window).
_ENGINE_WEB_SKIP_FILES = ('common/res/images/taptap_logo.png',)
#: ``sdk/__init__.py`` written into the bundle: the real one imports every
#: bridge, which would fail when the desktop-only package is left out.
_WEB_SDK_INIT_SOURCE = '''"""studio.sdk - the platform bridges available to this web build.

The TapTap PC bridge is a Windows desktop library and is not part of a browser
bundle; ``toy`` talks to the Bilibili Toy JS SDK the page loads when the bundle
is packaged for that platform (``toy.available()`` is False everywhere else).
"""

from . import toy

__all__ = ['toy']
'''
#: Editor files the runtime imports (the logger is plain Python, no Qt in it).
_ENGINE_EXTRA_FILES = ('gui/__init__.py', 'gui/console/__init__.py', 'gui/console/logger.py')
#: ``common/res`` data only the desktop/editor side uses (fonts are per
#: project; the TapTap SDK binaries are Windows desktop data). The physics
#: wheels and the self-hosted Pyodide runtime ship NEXT TO the bundle, never
#: inside the archive.
_ENGINE_RES_SKIP = ('fonts', 'qss', 'templates', 'audios', 'wheels', 'pyodide', 'sdk')
#: Folder in ``common/res`` holding the Pyodide wheels of the engine.
WHEELS_DIR_NAME = 'wheels'
#: Boot template placeholder holding the pymunk install source ('' = none).
PYMUNK_SOURCE_PLACEHOLDER = '__PYGS_PYMUNK_SOURCE__'
#: Install source used when the shipped pymunk wheel is missing (PyPI name).
PYMUNK_PACKAGE_NAME = 'pymunk'
#: Platform picker value for a plain (no platform) bundle.
NO_PLATFORM_ID = ''
#: Platform picker value for a Bilibili Toy bundle.
TOY_PLATFORM_ID = 'bilibili_toy'
#: File suffixes the Bilibili Toy platform publishes - everything else is
#: silently dropped by the upload, so a Toy bundle only contains these.
TOY_ALLOWED_SUFFIXES = frozenset((
    # page, script, data
    '.html', '.htm', '.css', '.js', '.json', '.wasm',
    '.data', '.md', '.csv', '.tsv',
    # images, fonts
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico',
    '.woff2', '.woff', '.ttf', '.eot',
    # audio, video
    '.mp3', '.wav', '.ogg', '.m4a', '.mp4', '.webm',
    # engine resources
    '.atlas', '.ani', '.part', '.nani', '.unityweb',
))
#: Containers the platform filters (``.zip``, ``.whl``) ship as ``.data``.
TOY_GAME_ARCHIVE_NAME = 'game.data'
TOY_STDLIB_ARCHIVE_NAME = 'python_stdlib.data'
#: Literal rewrites that keep the runtime able to parse its renamed wheels:
#: the distribution turns a wheel URL back into package name/version with
#: ``/^.*?([^\/]*)\.whl$/`` and rebuilds the file name with ``+".whl"``.
TOY_WHEEL_NAME_PATCHES = (
    (r'/^.*?([^\/]*)\.whl$/', r'/^.*?([^\/]*)\.(whl|data)$/'),
    ('r.join("-")+".whl"', 'r.join("-")+"."+e[2]'),
)
#: The platform SDK script (provides ``window.toy``); only a Toy page loads it.
TOY_SDK_SCRIPT = '<script src="//s1.hdslb.com/bfs/seed/toy/app/sdk/toy-sdk.js"></script>'
#: Patch of ``pyodide/_package_loader.py`` inside the shipped standard library:
#: the package loader decides the archive format and the wheel handling from
#: the file extension, which the Toy build had to change to ``.data``. Each
#: entry must match exactly once, otherwise the build stops.
_TOY_LOADER_PATCHES = (
    (
        "        buffer._into_file(f)\n"
        "        shutil.unpack_archive(f.name, extract_path, format)\n"
        "\n"
        "        suffix = Path(f.name).suffix\n"
        "        if suffix == \".whl\":\n",
        "        buffer._into_file(f)\n"
        "        # Toy build patch: the platform only serves whitelisted suffixes,\n"
        "        # so the wheels arrive renamed to .data - they are still zips and\n"
        "        # are installed exactly like a wheel.\n"
        "        suffix = \".whl\" if filename.endswith(\".data\") else Path(f.name).suffix\n"
        "        shutil.unpack_archive(f.name, extract_path, format or \"zip\")\n"
        "\n"
        "        if suffix == \".whl\":\n",
    ),
)
#: Module of the standard library that carries the package loader patch.
_TOY_LOADER_MODULE = 'pyodide/_package_loader.py'
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
        "        the loop waits for the display's next animation frame instead\n"
        "        of Clock.tick() and returns when the run ends instead of\n"
        "        exiting the interpreter.\n"
        "        \"\"\"\n"
    ),
    (
        "            delta_time = self._clock.tick(self._fps) / 1000\n",
        "            delta_time = self._web_frame_delta()\n"
        "            await self._web_wait_frame()\n"
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
    run_async() waits for the next display frame (see _web_wait_frame).
    """
    now = time.monotonic()
    last = getattr(self, '_web_last_frame_time', None)
    self._web_last_frame_time = now
    if last is None:
        return 1.0 / self._fps
    return min(now - last, 0.25)


Game._web_frame_delta = _web_frame_delta


#: animation-frame timestamps sampled to learn the display's refresh rate
_WEB_TICK_SAMPLES = 16


async def _web_next_frame():
    """Await the browser's next animation frame; returns its timestamp.

    Animation frames fire on the display's vertical sync, so waiting for one
    is what keeps the update cadence locked to the monitor.
    """
    import js
    from pyodide.ffi import create_once_callable

    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def _ready(timestamp=None):
        if not future.done():
            future.set_result(timestamp)

    js.requestAnimationFrame(create_once_callable(_ready))
    return await future


def _web_track_display(self, timestamp):
    """Learn the display frame period (seconds) from frame timestamps."""
    if timestamp is None or getattr(self, '_web_display_period', None) is not None:
        return
    ticks = getattr(self, '_web_ticks', None)
    if ticks is None:
        ticks = self._web_ticks = []
    if ticks and timestamp <= ticks[-1]:
        return
    ticks.append(timestamp)
    if len(ticks) > _WEB_TICK_SAMPLES:
        del ticks[0]
    if len(ticks) >= 5:
        deltas = sorted(second - first for first, second in zip(ticks, ticks[1:]))
        middle = deltas[len(deltas) // 2] / 1000.0
        if 0.002 <= middle <= 0.1:
            self._web_display_period = middle


Game._web_track_display = _web_track_display


async def _web_wait_frame(self):
    """Wait for the display: every update lands on the vsync grid.

    Waiting a whole number of animation frames keeps the update cadence
    locked to the monitor instead of drifting against it - the old
    time-budget sleep made frames land at random phases, and the picture
    juddered even at 60+ fps. The game's ``_fps`` target is honored by
    waiting more frames per update on a faster display (60 fps on a 120 Hz
    screen = two animation frames per update). A hidden tab stops firing
    animation frames, which pauses the game - standard for web games.
    """
    fps = getattr(self, '_fps', None) or 60.0
    target = 1.0 / float(fps)
    period = getattr(self, '_web_display_period', None)
    ticks = 1 if period is None else max(1, int(round(target / period)))
    for _ in range(ticks):
        try:
            timestamp = await _web_next_frame()
        except Exception:
            await asyncio.sleep(target)         # no animation frames here
            return
        self._web_track_display(timestamp)


Game._web_wait_frame = _web_wait_frame


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
        '.whl': 'application/octet-stream',
        '.zip': 'application/zip',
    }

    def log_message(self, format, *args):
        # The editor has its own log panel; the preview server stays quiet.
        pass


class _WebPreviewServer:
    """Tiny local HTTP server behind the Run button.

    The page must be served over HTTP (a ``file://`` page cannot fetch
    game.zip), so Run starts this server for the bundle folder and opens the
    browser on it. It listens on every interface (``0.0.0.0``) so a phone on
    the same network can open the page too - that is the address the QR button
    hands out - while the desktop browser keeps using the loopback one. The
    thread is a daemon: closing the editor stops it.
    """

    def __init__(self):
        self._server = None
        self._thread = None
        self._directory = None
        self._url = ''
        self._lan_url = ''

    def url_for(self, directory) -> str:
        """Start (or reuse) the server for this folder and return its URL."""
        self._start(directory)
        return self._url

    def lan_url_for(self, directory) -> str:
        """The same page as a phone on the same network opens it.

        Falls back to the loopback address when no LAN address can be found
        (no network, firewall-only setups).
        """
        self._start(directory)
        return self._lan_url or self._url

    def _start(self, directory):
        directory = Path(directory).resolve()
        if self._server is not None and self._directory == directory:
            return

        self.stop()
        handler = partial(_WebPreviewRequestHandler, directory=directory.as_posix())
        # 0.0.0.0 = every interface: the loopback as well as the LAN address a
        # phone uses.
        self._server = http.server.ThreadingHTTPServer(('0.0.0.0', 0), handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._directory = directory
        port = self._server.server_address[1]
        self._url = 'http://127.0.0.1:{}/index.html'.format(port)
        self._lan_url = 'http://{}:{}/index.html'.format(get_lan_ip() or '127.0.0.1', port)

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        self._server = None
        self._thread = None
        self._directory = None
        self._url = ''
        self._lan_url = ''


class _QrPopup(QWidget):
    """Floating panel with the QR code of the phone preview address.

    It is a tooltip-type window: it never takes focus or activates the editor,
    so hovering the QR button does not disturb whatever the user is typing.
    """

    def __init__(self):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._title_label = QLabel()
        self._image_label = QLabel()
        self._url_label = QLabel()
        self._url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._url_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._url_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.addWidget(self._title_label)
        layout.addWidget(self._image_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._url_label)
        self.setStyleSheet(
            'QWidget { background: #ffffff; color: #202020; '
            'border: 1px solid #9aa0a6; } '
            'QLabel { border: none; }')
        self._title_label.setStyleSheet('font-weight: 600;')

    def set_title(self, text):
        self._title_label.setText(text)
        self._title_label.setVisible(bool(text))

    def set_content(self, image, text):
        """Show ``image`` (None = no code) above ``text``."""
        if image is None or image.isNull():
            self._image_label.clear()
            self._image_label.hide()
        else:
            pixmap = QPixmap.fromImage(image)
            self._image_label.setPixmap(pixmap)
            self._image_label.show()
        self._url_label.setText(text)
        self._url_label.setVisible(bool(text))
        self.adjustSize()


class WebAppBuildWindow(QScrollArea):
    #: The app icon and name are one setting shared with the desktop build tab
    #: (build.app_icon / build.app_name); the build window saves them and
    #: mirrors them.
    app_icon_changed_signal = Signal(str)
    app_name_changed_signal = Signal(str)
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
        #: Hovering this icon shows the QR code a phone scans to open the same
        #: preview page (the server listens on every interface for it).
        self._qr_button = QPushButton()
        self._qr_popup = None
        #: Last printed phone address, so hovering does not flood the console.
        self._qr_logged_url = None
        #: Publishing-platform picker (bottom-right, like the desktop tab):
        #: the pick decides how the bundle is packaged (Bilibili Toy renames
        #: the containers to whitelisted suffixes and loads the Toy SDK).
        self._platform_label = QLabel()
        self._platform_combobox = QComboBox()

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
        self._qr_button.setIcon(QIcon(':/images/qr_code.png'))
        self._qr_button.setIconSize(QSize(18, 18))
        self._qr_button.setFixedSize(QSize(26, 26))
        self._qr_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._qr_button.setToolTip(T.tr(
            'build.web_qr_tooltip',
            'Hover to show a QR code - scan it with your phone to try the game'))
        self._platform_label.setText(T.tr('build.platform_label', 'Publishing Platform:'))
        self._set_platform_combobox_texts()
        self._set_platform_tooltip()
        self._update_button_widths()

    def _set_signal(self):
        self._app_name_lineedit.editingFinished.connect(self._on_app_name_edited)
        self._app_icon_browse_button.clicked.connect(self._browse_app_icon)
        self._app_icon_lineedit.editingFinished.connect(self._on_app_icon_edited)
        self._output_dir_browse_button.clicked.connect(self._browse_output_dir)
        self._build_button.clicked.connect(self._build)
        self._run_button.clicked.connect(self._run_in_browser)
        self._open_output_dir_button.clicked.connect(self._open_output_dir)
        # The QR code appears while the pointer rests on the icon, so it is a
        # hover (event filter) rather than a click.
        self._qr_button.installEventFilter(self)
        self._platform_combobox.activated.connect(self._on_platform_activated)

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
        button_layout.addSpacing(1)
        button_layout.addWidget(self._run_button)
        button_layout.addSpacing(1)
        button_layout.addWidget(self._open_output_dir_button)
        button_layout.addSpacing(1)
        button_layout.addWidget(self._qr_button)
        button_layout.addStretch()
        # Bottom-right corner: label + publishing-platform picker.
        button_layout.addWidget(self._platform_label)
        button_layout.addWidget(self._platform_combobox)

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

    # ------------------------------------------------------- publishing platform
    def _set_platform_tooltip(self):
        """Tooltip of the picker: "Publish to <platform>", none for 无平台."""
        platform_id = self.get_platform()
        if platform_id == TOY_PLATFORM_ID:
            tooltip = T.tr('build.publish_to_toy', 'Publish to Bilibili Toy')
        else:
            tooltip = ''
        self._platform_combobox.setToolTip(tooltip)

    def _set_platform_combobox_texts(self):
        """(Re)fill the dropdown: 无平台 and Bilibili Toy, each with its icon."""
        selected = self._platform_combobox.currentData()
        self._platform_combobox.blockSignals(True)
        self._platform_combobox.clear()
        self._platform_combobox.addItem(QIcon(':/images/ban.png'),
                                        T.tr('build.no_platform', 'None'), '')
        self._platform_combobox.addItem(QIcon(':/images/bilibili_toy.png'),
                                        T.tr('build.bilibili_toy', 'Bilibili Toy'),
                                        'bilibili_toy')
        index = self._platform_combobox.findData(selected)
        self._platform_combobox.setCurrentIndex(index if index >= 0 else 0)
        self._platform_combobox.blockSignals(False)
        self._set_platform_tooltip()

    def set_platform_selected(self, platform_id):
        """Set the picker from outside without re-saving the config."""
        self._platform_combobox.blockSignals(True)
        index = self._platform_combobox.findData(str(platform_id or ''))
        # An unknown id falls back to "无平台": the normal web bundle.
        self._platform_combobox.setCurrentIndex(index if index >= 0 else 0)
        self._platform_combobox.blockSignals(False)
        self._set_platform_tooltip()

    def get_platform(self):
        """The chosen web publishing platform id ('' while "无" is picked)."""
        return str(self._platform_combobox.currentData() or '')

    def _on_platform_activated(self, index):
        """Remember the pick right away (build.web.platform in project.pygs)."""
        self._save_web_config(platform=self.get_platform())
        self._set_platform_tooltip()

    def _save_web_config(self, output_dir=None, platform=None):
        """Write the web build settings into build.web, keeping other keys."""
        project_config = get_project_config()
        web_config = project_config.setdefault('build', {}).setdefault('web', {})
        if output_dir is not None:
            web_config['output_dir'] = output_dir
        if platform is not None:
            web_config['platform'] = platform
        save_project_config(project_config)

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

        web_config = project_config.get('build', {}).get('web') or {}
        self.set_platform_selected(str(web_config.get('platform') or ''))

    def _browse_app_icon(self):
        icon_path, _ = QFileDialog.getOpenFileName(self, T.tr('build.select_app_icon', 'Select App Icon'), self._game_manager.get_project_path(), 'Format (*png *.ico *.jpg *.jpeg *.bmp *.gif)')
        if icon_path:
            self._app_icon_lineedit.setText(icon_path)
            self._on_app_icon_edited()

    def _on_app_icon_edited(self):
        """Report the pick right away so it is saved even without a build.

        ``build.app_icon`` is shared with the desktop build tab, so the build
        window stores the path at once and shows it in both tabs. Otherwise a
        pick was lost as soon as the app was closed without building (or the
        other tab built with its still empty field).
        """
        self.app_icon_changed_signal.emit(self._app_icon_lineedit.text().strip())

    def set_app_icon(self, icon_path):
        """Show an app icon chosen in the other build tab (no new pick)."""
        icon_path = str(icon_path or '')
        if self._app_icon_lineedit.text() != icon_path:
            self._app_icon_lineedit.setText(icon_path)

    def _on_app_name_edited(self):
        """Report the name right away: build.app_name is shared by both tabs."""
        self.app_name_changed_signal.emit(self._app_name_lineedit.text().strip())

    def set_app_name(self, app_name):
        """Show an app name chosen in the other build tab (no new edit)."""
        app_name = str(app_name or '')
        if self._app_name_lineedit.text() != app_name:
            self._app_name_lineedit.setText(app_name)

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

    # ------------------------------------------------------------ phone QR code
    def eventFilter(self, watched, event):
        """Show the phone QR code while the pointer rests on its button."""
        if watched is self._qr_button:
            if event.type() == QEvent.Type.Enter:
                self._show_qr_popup()
            elif event.type() in (QEvent.Type.Leave, QEvent.Type.Hide):
                self._hide_qr_popup()
        return super().eventFilter(watched, event)

    def _current_bundle_dir(self):
        """The built bundle folder: the last build, else <output>/build/Web."""
        bundle_dir = self._build_thread.bundle_dir
        if bundle_dir is not None and Path(bundle_dir).exists():
            return Path(bundle_dir)
        output_dir = self._output_dir_lineedit.text().strip()
        if output_dir:
            candidate = Path(output_dir).joinpath(*BUNDLE_SUBDIR)
            if candidate.exists():
                return candidate
        return None

    def _ensure_qr_popup(self):
        if self._qr_popup is None:
            self._qr_popup = _QrPopup()
        return self._qr_popup

    def _show_qr_popup(self):
        """Show the QR code of the address a phone on this network opens."""
        popup = self._ensure_qr_popup()
        popup.set_title(T.tr('build.web_qr_title', 'Scan with your phone to play'))

        bundle_dir = self._current_bundle_dir()
        if bundle_dir is None:
            popup.set_content(None, T.tr(
                'build.web_qr_no_build',
                'Build the web app first - the QR code links to the preview server'))
            self._place_qr_popup(popup)
            popup.show()
            return

        try:
            url = self._preview_server.lan_url_for(bundle_dir)
            image = qr.to_qimage(url, scale=5)
        except Exception as error:
            popup.set_content(None, T.tr(
                'build.web_qr_failed',
                'Could not start the phone preview server: {}').format(error))
            self._place_qr_popup(popup)
            popup.show()
            return

        if self._qr_logged_url != url:
            Logger.info(T.tr('build.web_preview_lan', 'Phone preview (same network): {}').format(url))
            self._qr_logged_url = url
        popup.set_content(image, url)
        self._place_qr_popup(popup)
        popup.show()

    def _place_qr_popup(self, popup):
        """Sit the panel above the button, kept inside the screen."""
        anchor = self._qr_button.mapToGlobal(self._qr_button.rect().topRight())
        size = popup.sizeHint()
        x = anchor.x() - size.width()
        y = anchor.y() - size.height() - 8
        screen = self._qr_button.screen()
        if screen is not None:
            available = screen.availableGeometry()
            x = max(available.left() + 4, min(x, available.right() - size.width() - 4))
            y = max(available.top() + 4, min(y, available.bottom() - size.height() - 4))
        popup.move(int(x), int(y))

    def _hide_qr_popup(self):
        if self._qr_popup is not None:
            self._qr_popup.hide()

    def closeEvent(self, event):
        """Drop the floating QR panel together with the window."""
        if self._qr_popup is not None:
            self._qr_popup.hide()
            self._qr_popup.deleteLater()
            self._qr_popup = None
        super().closeEvent(event)

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
        platform_id = self.get_platform()

        # Stored under build.web so the desktop settings (build.*) survive;
        # the merge keeps keys this dialog does not know.
        self._save_web_config(output_dir=output_dir, platform=platform_id)
        # The app name and the icon are the same settings the desktop build
        # uses: one app for every target (a new project already ships
        # image/logo.png).
        update_project_config('build.app_name', app_name)
        update_project_config('build.app_icon', app_icon)

        return {'app_name': app_name, 'app_icon': app_icon,
                'output_dir': output_dir, 'platform': platform_id}

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
        self._qr_button.setToolTip(T.tr(
            'build.web_qr_tooltip',
            'Hover to show a QR code - scan it with your phone to try the game'))
        self._platform_label.setText(T.tr('build.platform_label', 'Publishing Platform:'))
        self._set_platform_combobox_texts()
        self._set_platform_tooltip()
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
        platform_id = str(build_config.get('platform') or '').strip()
        self._platform = platform_id if platform_id in ('', TOY_PLATFORM_ID) else ''
        self._is_toy = self._platform == TOY_PLATFORM_ID
        output_dir = (build_config.get('output_dir') or '').strip()
        self._output_dir = Path(output_dir) if output_dir else None
        # The runtime the page loads: an explicit pyodide_url wins (nothing is
        # copied); otherwise the copy shipped in common/res/pyodide is bundled
        # next to the page so the game starts without downloading anything;
        # without that folder the page falls back to the CDN.
        pyodide_url = (build_config.get('pyodide_url') or '').strip()
        self._bundle_pyodide = False
        #: Loader file the page imports; the bundled copy ships as .js (see
        #: _rename_runtime_modules) so every static server serves it with a
        #: JavaScript MIME type.
        self._pyodide_entry = 'pyodide.mjs'
        if pyodide_url:
            self._pyodide_url = pyodide_url if pyodide_url.endswith('/') else pyodide_url + '/'
        elif (self._bundled_pyodide_dir() / 'pyodide.mjs').is_file():
            self._pyodide_url = LOCAL_PYODIDE_URL
            self._bundle_pyodide = True
        else:
            self._pyodide_url = DEFAULT_PYODIDE_URL
            Logger.warning(T.tr('build.web_runtime_cdn_fallback', 'The engine resources are missing the bundled browser runtime ({}): the page will load Pyodide from the CDN instead').format(self._bundled_pyodide_dir().as_posix()))
        self._progress_callback = progress
        self._stop_check = stop_check

    # ---------- Public API ----------

    def build(self) -> Path:
        """Create the bundle and return its folder.

        The package is assembled in a sibling folder and swapped in only when
        it is complete: the previous bundle is always replaced (a stale wheel,
        runtime file or asset never survives), and a build that fails or is
        stopped leaves the last good bundle untouched.
        """
        if self._output_dir is None:
            raise WebBuildError(T.tr('build.web_no_output_dir', 'The web build needs an output dir'))

        self._check_stopped()
        bundle_dir = self._output_dir.joinpath(*BUNDLE_SUBDIR)
        staging_dir = bundle_dir.with_name(bundle_dir.name + BUNDLE_STAGING_SUFFIX)
        # A staging folder left behind by a crash is not part of any build.
        shutil.rmtree(staging_dir, ignore_errors=True)
        staging_dir.mkdir(parents=True, exist_ok=True)
        self._progress(2)

        try:
            self._assemble(staging_dir)
        except BaseException:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise

        self._replace_bundle(staging_dir, bundle_dir)
        return bundle_dir

    def _assemble(self, bundle_dir):
        """Write the whole bundle into ``bundle_dir`` (the staging folder)."""
        self._check_stopped()
        project_dir = self._prepare_protected_project(bundle_dir)
        self._check_stopped()

        index_template = self._read_template('web_index_template.html')
        boot_source = self._read_template('web_boot_template.py').replace(
            PYMUNK_SOURCE_PLACEHOLDER, self._prepare_physics(bundle_dir))
        self._progress(25)

        game_source_path = Path(pygamestudio.__file__).parent / GAME_SOURCE_RELATIVE_PATH
        if not game_source_path.exists():
            raise WebBuildError(T.tr('build.web_engine_source_missing', 'Cannot find the engine file to copy: {}').format(game_source_path.as_posix()))
        patched_source = self._patch_game_source(game_source_path.read_text(encoding=_SOURCE_ENCODING))
        self._progress(30)

        archive_name = TOY_GAME_ARCHIVE_NAME if self._is_toy else 'game.zip'
        archive_path = bundle_dir / archive_name
        project_count, engine_count = self._write_archive(archive_path, patched_source, boot_source, project_dir)
        self._progress(85)
        self._check_stopped()

        favicon_links = self._write_favicon(bundle_dir)
        self._prepare_runtime(bundle_dir)
        self._progress(90)

        canvas_size = self._read_canvas_size()
        (bundle_dir / 'index.html').write_text(self._render_index(index_template, favicon_links, canvas_size, archive_name), encoding=_SOURCE_ENCODING)
        if self._is_toy:
            self._apply_toy_package(bundle_dir)
        self._progress(95)

        # The staging copy has done its job: only the page and the archive stay.
        shutil.rmtree(bundle_dir / PROTECTED_WORK_DIR_NAME, ignore_errors=True)

        if self._is_toy:
            # Checked last: the staging copy holds the very suffixes the
            # platform filters, and it is gone by now.
            self._check_toy_whitelist(bundle_dir)

        Logger.info(T.tr('build.web_build_summary', 'Bundled {} project file(s) and {} engine file(s)').format(project_count, engine_count))
        self._check_stopped()
        return bundle_dir

    # ---------- Build steps ----------

    def _replace_bundle(self, staging_dir, bundle_dir):
        """Swap the finished package in, dropping everything that was there.

        A file the page still holds (an open browser tab, a static server) can
        make the removal fail on Windows; the step then retries what it can and
        stops the build, because a leftover file would ship next to the new
        bundle (an old ``pymunk`` wheel, a removed asset, an obsolete runtime).
        """
        self._check_stopped()
        if bundle_dir.exists():
            try:
                shutil.rmtree(bundle_dir)
            except OSError as error:
                shutil.rmtree(bundle_dir, ignore_errors=True)
                if bundle_dir.exists():
                    raise WebBuildError(T.tr('build.web_clear_failed', 'The previous web build could not be removed ({}): {}. Close the page or the server using it and build again').format(bundle_dir.as_posix(), error))
            Logger.info(T.tr('build.web_previous_removed', 'Replaced the previous web build: {}').format(bundle_dir.as_posix()))
        bundle_dir.parent.mkdir(parents=True, exist_ok=True)
        staging_dir.replace(bundle_dir)

    def _prepare_protected_project(self, bundle_dir):
        """Stage, strip and encrypt the project (like the desktop build).

        The project folder itself is never touched: the protection works on the
        staging copy inside the bundle folder, and that copy is what gets
        zipped. Its assets and scripts are encrypted; ``main.py`` stays a
        readable (stripped) file so the page's boot loader can start it, and a
        ``resources.cache`` with the build key ships next to it.
        """
        Logger.info(T.tr('build.protection_running', 'Preparing the project code and assets ...'))
        self._progress(8)
        try:
            prepared = protection.prepare(self._project_path, bundle_dir)
        except asset_build.AssetBuildError as e:
            raise WebBuildError(T.tr('build.assets_failed', 'Encrypting the project assets failed, the build is stopped: {}').format(e))
        except protection.StripError as e:
            raise WebBuildError(T.tr('build.code_strip_failed', 'Preparing the project code failed, the build is stopped: {}').format(e))
        except protection.ProtectionError as e:
            raise WebBuildError(T.tr('build.staging_failed', 'The project could not be prepared for the build, the build is stopped: {}').format(e))

        Logger.info(T.tr('build.code_prepared', 'Prepared {} python file(s), comments and docstrings removed').format(prepared['strip_summary']['files']))
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
            # The real sdk/__init__.py imports the desktop-only bridges too.
            archive.writestr(f'{ENGINE_PACKAGE}/sdk/__init__.py', _WEB_SDK_INIT_SOURCE)
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
                # Desktop-only platform bridges (written separately as well).
                if relative_path.parts[:2] in _ENGINE_WEB_SKIP_DIRS:
                    continue
                if relative_path.as_posix() in _ENGINE_WEB_SKIP_FILES:
                    continue
                if relative_path.as_posix() == 'sdk/__init__.py':
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

    def _render_index(self, template, favicon_links, canvas_size, archive_name='game.zip'):
        return (template
                .replace('__PYGS_TITLE__', html.escape(self._page_title))
                .replace('__PYGS_FAVICON_LINK__', favicon_links)
                .replace('__PYGS_CANVAS_WIDTH__', str(canvas_size[0]))
                .replace('__PYGS_CANVAS_HEIGHT__', str(canvas_size[1]))
                .replace('__PYGS_GAME_ARCHIVE__', archive_name)
                .replace('__PYGS_TOY_SDK_SCRIPT__', TOY_SDK_SCRIPT if self._is_toy else '')
                .replace('__PYGS_PYODIDE_URL__', self._pyodide_url)
                .replace('__PYGS_PYODIDE_ENTRY__', self._pyodide_entry))

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

    def _prepare_physics(self, bundle_dir):
        """Ship pymunk with the bundle when the project uses physics.

        :return: the install source for the boot template - the shipped wheel
            file name (installed from the page's own folder), the plain
            package name when that wheel is missing (PyPI fallback), or ''
            when the project has no physics (nothing is written).
        """
        if not self._uses_physics():
            return ''

        if self._is_toy and not self._bundle_pyodide:
            # The renamed wheel is unpacked by the PATCHED runtime of the
            # bundle; a remote runtime has the stock loader, so let micropip
            # fetch the real wheel instead (that page needs the network for
            # its runtime anyway).
            Logger.warning(T.tr('build.web_toy_physics_cdn', 'A Bilibili Toy package with physics needs the bundled browser runtime ({}): the page will download pymunk from PyPI instead').format(self._bundled_pyodide_dir().as_posix()))
            return PYMUNK_PACKAGE_NAME

        wheel_path = self._find_pymunk_wheel()
        if wheel_path is None:
            Logger.warning(T.tr('build.web_physics_pypi_fallback', 'The project uses physics but the shipped pymunk wheel is missing from the engine resources ({}): the page will download pymunk from PyPI instead').format(self._wheels_dir().as_posix()))
            return PYMUNK_PACKAGE_NAME

        # A Toy bundle keeps only whitelisted suffixes: .whl is filtered out,
        # so the same wheel ships as .data (the boot accepts both).
        target_name = wheel_path.name
        if self._is_toy:
            target_name = wheel_path.name[:-4] + '.data'
        shutil.copyfile(wheel_path, bundle_dir / target_name)
        Logger.info(T.tr('build.web_physics_bundled', 'The project uses physics: pymunk ships next to the page and the browser runs the simulation'))
        return target_name

    def _bundled_pyodide_dir(self):
        """Folder with the self-hosted Pyodide runtime shipped with the engine."""
        return RES_PATH / PYODIDE_DIR_NAME

    def _prepare_runtime(self, bundle_dir):
        """Copy the shipped Pyodide runtime next to the page.

        The page then starts Python and loads the game packages from its own
        folder, so the game startup downloads nothing. No-op when the build
        points at an explicit ``pyodide_url`` or the engine copy is missing
        (the page falls back to the CDN in that case).
        """
        if not self._bundle_pyodide:
            return

        target_dir = bundle_dir / PYODIDE_DIR_NAME
        target_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(self._bundled_pyodide_dir().iterdir()):
            if path.is_file():
                shutil.copyfile(path, target_dir / path.name)

        self._rename_runtime_modules(target_dir)

        Logger.info(T.tr('build.web_runtime_bundled', 'The browser runtime (Pyodide and pygame-ce) ships next to the page: the game loads everything locally'))

    def _rename_runtime_modules(self, target_dir):
        """Ship the two Pyodide module files as .js with their reference patched.

        Simple static servers (Python's own ``http.server`` included, on older
        Python versions) serve ``.mjs`` as ``text/plain`` and the browser then
        refuses the module script. The files are plain ES modules, so the
        bundle carries them as ``.js`` - a name every server maps to a
        JavaScript MIME type - and the loader's internal reference to
        ``pyodide.asm.mjs`` is rewritten to match. Keeps the original names
        when a future distribution changes that reference.
        """
        entry = target_dir / 'pyodide.mjs'
        glue = target_dir / 'pyodide.asm.mjs'
        if not (entry.is_file() and glue.is_file()):
            return

        entry_source = entry.read_text(encoding=_SOURCE_ENCODING)
        if entry_source.count('pyodide.asm.mjs') != 1:
            return

        (target_dir / 'pyodide.js').write_text(
            entry_source.replace('pyodide.asm.mjs', 'pyodide.asm.js'), encoding=_SOURCE_ENCODING)
        glue_source = glue.read_text(encoding=_SOURCE_ENCODING)
        (target_dir / 'pyodide.asm.js').write_text(
            glue_source.replace('pyodide.asm.mjs', 'pyodide.asm.js'), encoding=_SOURCE_ENCODING)
        entry.unlink()
        glue.unlink()
        self._pyodide_entry = 'pyodide.js'

    def _apply_toy_package(self, bundle_dir):
        """Turn the bundle into a Bilibili Toy package.

        The platform silently drops every file whose suffix is outside its
        whitelist, and ``.zip``/``.whl`` are not part of it. The two containers
        the page loads at startup - the game archive and the Python standard
        library - are therefore shipped as ``.data``, the wheels next to the
        runtime (pygame-ce and its dependencies) as well, and every loader
        reference is patched to match. A final self-check refuses to publish a
        bundle that still contains a filtered suffix.
        """
        runtime_dir = bundle_dir.joinpath(PYODIDE_DIR_NAME)

        stdlib = runtime_dir / 'python_stdlib.zip'
        if stdlib.is_file():
            self._patch_toy_stdlib_loader(stdlib)
            stdlib.replace(runtime_dir / TOY_STDLIB_ARCHIVE_NAME)

        renamed = {}
        for folder in (runtime_dir, bundle_dir):
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob('*.whl')):
                target = path.with_name(path.name[:-len('.whl')] + '.data')
                path.replace(target)
                renamed[path.name] = target.name

        if renamed:
            self._patch_toy_wheel_references(runtime_dir, renamed)
        self._patch_toy_stdlib_reference(runtime_dir)

        for path in sorted(runtime_dir.glob('*.mjs')):
            path.unlink()

        Logger.info(T.tr('build.web_toy_packaged', 'Packaged for Bilibili Toy: containers ship as .data and the platform SDK is loaded by the page'))

    def _patch_toy_stdlib_loader(self, stdlib_path):
        """Teach the packaged standard library that wheels may be ``.data``.

        Pyodide installs a package by unpacking the fetched file and decides
        the archive format (and the wheel metadata step) from its extension.
        The Toy build renames the wheels, so the loader is patched too -
        otherwise every package install fails with "Unknown archive format".
        The archive is rewritten in place with the same entries and
        compression; only that one module changes.
        """
        with zipfile.ZipFile(stdlib_path) as source:
            entries = [(info, source.read(info.filename)) for info in source.infolist()]

        patched_module = None
        for info, data in entries:
            if info.filename != _TOY_LOADER_MODULE:
                continue
            text = data.decode(_SOURCE_ENCODING)
            for old, new in _TOY_LOADER_PATCHES:
                if text.count(old) != 1:
                    raise WebBuildError(T.tr('build.web_toy_loader_patch_failed', 'The packaged browser runtime no longer matches the Bilibili Toy patch ({}): the build was stopped').format(_TOY_LOADER_MODULE))
                text = text.replace(old, new)
            patched_module = text.encode(_SOURCE_ENCODING)

        if patched_module is None:
            raise WebBuildError(T.tr('build.web_toy_loader_patch_failed', 'The packaged browser runtime no longer matches the Bilibili Toy patch ({}): the build was stopped').format(_TOY_LOADER_MODULE))

        temporary = stdlib_path.with_suffix('.tmp')
        with zipfile.ZipFile(temporary, 'w') as target:
            for info, data in entries:
                if info.filename == _TOY_LOADER_MODULE:
                    data = patched_module
                target.writestr(info, data)
        temporary.replace(stdlib_path)

    def _patch_toy_stdlib_reference(self, runtime_dir):
        """Point the runtime entry at the renamed standard library archive."""
        for name in ('pyodide.js', 'pyodide.mjs'):
            path = runtime_dir / name
            if not path.is_file():
                continue
            source = path.read_text(encoding=_SOURCE_ENCODING)
            if 'python_stdlib.zip' not in source:
                continue
            path.write_text(source.replace('python_stdlib.zip', TOY_STDLIB_ARCHIVE_NAME), encoding=_SOURCE_ENCODING)
            return

    def _patch_toy_wheel_references(self, runtime_dir, renamed):
        """Teach the runtime that its wheels now end in ``.data``.

        ``pyodide-lock.json`` carries the file name the loader fetches, and the
        distribution parses that name back into package name and version with a
        hardcoded ``\\.whl`` pattern - both sides are updated so the renamed
        files resolve exactly like before.
        """
        lock_path = runtime_dir / 'pyodide-lock.json'
        if lock_path.is_file():
            source = lock_path.read_text(encoding=_SOURCE_ENCODING)
            for old, new in renamed.items():
                source = source.replace(old, new)
            lock_path.write_text(source, encoding=_SOURCE_ENCODING)

        for name in ('pyodide.asm.js', 'pyodide.asm.mjs'):
            path = runtime_dir / name
            if not path.is_file():
                continue
            source = path.read_text(encoding=_SOURCE_ENCODING)
            patched = source
            for old, new in TOY_WHEEL_NAME_PATCHES:
                patched = patched.replace(old, new)
            if patched == source:
                Logger.warning(T.tr('build.web_toy_wheel_patch_skipped', 'The browser runtime did not expose the wheel name pattern: physics wheels may not load on this platform ({})').format(path.name))
                continue
            path.write_text(patched, encoding=_SOURCE_ENCODING)
            return

    def _check_toy_whitelist(self, bundle_dir):
        """Fail the build when a file the platform would silently drop is left."""
        blocked = []
        for path in sorted(bundle_dir.rglob('*')):
            if not path.is_file():
                continue
            if path.suffix.lower() not in TOY_ALLOWED_SUFFIXES:
                blocked.append(path.relative_to(bundle_dir).as_posix())
        if not blocked:
            return
        shown = ', '.join(blocked[:5])
        if len(blocked) > 5:
            shown += ' ...'
        raise WebBuildError(T.tr('build.web_toy_blocked_files', 'These files are not supported by Bilibili Toy and would be dropped, the build is stopped: {}').format(shown))

    def _wheels_dir(self):
        """Folder with the Pyodide wheels shipped with the engine."""
        return RES_PATH / WHEELS_DIR_NAME

    def _find_pymunk_wheel(self):
        """The Pyodide (WASM) wheel of pymunk shipped with the engine, if any."""
        directory = self._wheels_dir()
        if not directory.is_dir():
            return None
        for path in sorted(directory.glob('pymunk-*.whl')):
            name = path.name.lower()
            if 'wasm32' in name or 'pyemscripten' in name or 'pyodide' in name:
                return path
        return None

    def _progress(self, value):
        if self._progress_callback is not None:
            self._progress_callback(value)

    def _check_stopped(self):
        if self._stop_check is not None and self._stop_check():
            raise WebBuildCancelled()
