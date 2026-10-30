"""Which engine files an Android build needs, and how to stage them.

An Android APK ships a *subset* of the installed engine - the same idea the web
build already uses (see ``gui/build/web.py``): the game runtime, never the
editor:

* ``api/``   the public runtime API (Game, scene loader, audio, physics, ...)
* ``game/``  the scene objects and their collision / physics helpers
* ``common/`` i18n dictionaries, the asset container and the path helpers
* ``gui/console/logger.py`` - the runtime imports it through the translator, and
  it is plain Python on purpose (no Qt)

Left out: everything that needs PySide6 (the scene tree manager, the undo
commands, QSettings config, QSS themes, the Qt resource bundle), the platform
bridges (the TapTap PC SDK is a Windows DLL, the Toy bridge is a browser SDK)
and the editor-only resources (the 9.3 MB SIMHEI font, the self-hosted Pyodide
runtime, the editor icons are kept because ``window.py`` uses its logo).

This module is the prototype of the runtime artefact the editor will download
(``VERSION.json`` + payload): keep the selection in one place so the spike and
the real builder cannot drift apart.
"""
import shutil
from pathlib import Path, PurePosixPath

#: Engine package folders the game runtime needs.
RUNTIME_DIRS = ('api', 'game', 'common')
#: Single engine files outside those folders that still have to ship.
RUNTIME_EXTRA_FILES = (
    '__init__.py',
    'gui/__init__.py',
    'gui/console/__init__.py',
    'gui/console/logger.py',
)
#: Files inside the shipped folders that need PySide6 and therefore cannot be
#: imported on a device (they are editor-only, the runtime never touches them).
RUNTIME_SKIP_FILES = (
    'game/core/command.py',        # PySide6.QtGui.QUndoCommand
    'game/core/manager.py',        # Qt scene tree, QFileDialog, QSettings
    'common/utils/config.py',      # platformdirs + QSettings editor config
    'common/utils/theme.py',       # QSS themes
    'common/utils/qr.py',          # QImage / QPainter
    'common/res/resources_rc.py',  # compiled Qt resources
)
#: Folders inside the shipped directories that are editor-only data.
RUNTIME_SKIP_DIRS = (
    ('common', 'res', 'fonts'),      # 9.3 MB SIMHEI.ttf; projects ship their own
    ('common', 'res', 'qss'),        # Qt stylesheets
    ('common', 'res', 'templates'),  # project / editor templates
    ('common', 'res', 'audios'),     # editor click sound
    ('common', 'res', 'pyodide'),    # 14.5 MB browser runtime
    ('common', 'res', 'wheels'),     # browser wheels
    ('common', 'res', 'sdk'),        # Windows SDK binaries
)

#: ``pygamestudio/sdk/__init__.py`` written into a build.
#:
#: The real one imports every bridge; neither works on Android (the TapTap PC
#: SDK is a Windows DLL, the Toy bridge needs ``window.toy`` in a browser page),
#: and a game that does ``from pygamestudio.sdk import toy`` would fail at
#: import time. Shipping an empty namespace keeps such code importable - the
#: guards in game code (``toy.available()``) are then simply False.
SDK_STUB_SOURCE = '''"""studio.sdk - the platform bridges available to this build.

Android has none of them: the TapTap PC SDK is a Windows desktop library and
the Bilibili Toy bridge talks to a browser page. Game code can still import
this namespace; every bridge it expects is missing on purpose.
"""

__all__ = []
'''

#: Version marker of the staged runtime (the editor's real artefact carries far
#: more: python / pygame_ce / cffi / pymunk / p4a / ndk versions, ABI, ...).
VERSION = {
    'format': 2,
    'abi': 'arm64-v8a',
    'python': '3.14',
    'engine': 'pygamestudio',
}


def _is_skipped(relative: PurePosixPath) -> bool:
    if '__pycache__' in relative.parts:
        return True
    if relative.as_posix() in RUNTIME_SKIP_FILES:
        return True
    for prefix in RUNTIME_SKIP_DIRS:
        if relative.parts[:len(prefix)] == prefix:
            return True
    return False


def iter_runtime_files(engine_root):
    """``(absolute path, package-relative posix path)`` of every file to ship.

    ``engine_root`` is the installed ``pygamestudio`` package directory.
    """
    engine_root = Path(engine_root)
    for name in RUNTIME_EXTRA_FILES:
        path = engine_root / name
        if not path.is_file():
            raise SystemExit(f'engine file missing: {path}')
        yield path, PurePosixPath(name)

    for directory in RUNTIME_DIRS:
        base = engine_root / directory
        if not base.is_dir():
            raise SystemExit(f'engine folder missing: {base}')
        for path in sorted(base.rglob('*')):
            if not path.is_file():
                continue
            relative = PurePosixPath(path.relative_to(engine_root).as_posix())
            if _is_skipped(relative):
                continue
            yield path, relative


def stage(engine_root, dest_dir):
    """Copy the runtime subset of the engine into ``dest_dir``.

    The result is a ready-to-import ``pygamestudio`` package: ``dest_dir`` is
    the folder that CONTAINS the package (the app source dir of a p4a build).
    Returns ``{'files': n, 'bytes': n, 'package': path}``.
    """
    engine_root = Path(engine_root)
    dest_dir = Path(dest_dir)
    package_dir = dest_dir / 'pygamestudio'
    if package_dir.exists():
        shutil.rmtree(package_dir)

    files = 0
    size = 0
    for source, relative in iter_runtime_files(engine_root):
        target = package_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files += 1
        size += target.stat().st_size

    (package_dir / 'sdk').mkdir(parents=True, exist_ok=True)
    stub = package_dir / 'sdk' / '__init__.py'
    stub.write_text(SDK_STUB_SOURCE, encoding='utf-8')
    files += 1
    size += stub.stat().st_size

    return {'files': files, 'bytes': size, 'package': package_dir}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description='Stage the engine runtime subset')
    parser.add_argument('engine_root', type=Path, help='.../src/pygamestudio')
    parser.add_argument('dest_dir', type=Path, help='folder that will contain pygamestudio/')
    args = parser.parse_args(argv)

    summary = stage(args.engine_root, args.dest_dir)
    print(f'staged {summary["files"]} file(s), {summary["bytes"] / 1024 / 1024:.1f} MB '
          f'-> {summary["package"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
