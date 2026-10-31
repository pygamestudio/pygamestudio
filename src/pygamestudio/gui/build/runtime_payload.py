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

The Android build (``gui/build/android.py``) uses this list to stage the engine
inside the project payload, and the CI spike (``tools/android_spike``) loads this
same file by path - one list, so a file the device needs can never be missing
from one of them. Keep the module free of Qt and of engine imports: it has to be
importable from a plain CPython in the build container.
"""
import gzip
import io
import shutil
import tarfile
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
    'common/utils/android_runtime.py',  # editor side: runtime pack + JDK/SDK checks
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
    ('common', 'res', 'android'),    # frozen Android runtime pack (built from a dist)
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

#: pygame submodules a desktop build has but the p4a build does not.
#:
#: p4a's pygame recipe deliberately leaves the optional C extensions out
#: (``freetype``, ``postmidi``, the camera binding), so ``import pygame.freetype``
#: - which a desktop run happily executes - dies on the device with
#: ``ModuleNotFoundError: No module named 'pygame._freetype'``. The engine hit
#: exactly that on its first device run; this list lets the smoke test block the
#: modules and reproduce the device import graph on a developer machine.
ANDROID_MISSING_PYGAME_MODULES = (
    'pygame._freetype', 'pygame.freetype',
    'pygame._camera', 'pygame.camera',
    'pygame.pypm', 'pygame.midi',
    'pygame.system',
)

#: Version marker of the staged runtime (the editor's real artefact carries far
#: more: python / pygame_ce / cffi / pymunk / p4a / ndk versions, ABI, ...).
VERSION = {
    'format': 2,
    'abi': 'arm64-v8a',
    'python': '3.14',
    'engine': 'pygamestudio',
}

#: File p4a's start.c reads to export environment variables to the game.
PAYLOAD_ENV_FILE = 'p4a_env_vars.txt'
#: Written into the payload so the device can import ``_applibs`` (the folder
#: p4a's own packaging code adds); a dist without it still runs, but keeping it
#: makes the payload identical to one p4a would have built.
SITECUSTOMIZE_SOURCE = '''import os.path
import sys

# p4a puts the unpacked native helpers here; the folder may be empty, in which
# case the entry stays in sys.path without breaking anything.
sys.path.append(os.path.join(os.path.dirname(__file__), '_applibs'))
'''


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


def _iter_payload_files(payload_dir):
    """Every file of the payload, plus the folders that contain them."""
    payload_dir = Path(payload_dir)
    files = sorted(path for path in payload_dir.rglob('*')
                   if path.is_file() and '__pycache__' not in path.parts)
    folders = set()
    for path in files:
        for parent in path.relative_to(payload_dir).parents:
            if parent.parts:
                folders.add(parent)
    return files, sorted(folders, key=lambda path: (len(path.parts), path.as_posix()))


def make_payload_tar(payload_dir, target, numeric_version=1, min_sdk=24):
    """Write ``assets/private.tar`` - the app folder the device unpacks.

    This is the file p4a's packaging step would have produced: every project
    file at the tar root, ``.py`` bytcode left alone (the runtime loads object
    scripts by path, so a ``.pyc`` would be invisible to it), the environment
    file ``start.c`` reads and the ``sitecustomize.py`` p4a generates.

    Entries carry a fixed mtime and no owner, so the same input always produces
    the same bytes - an APK that only differs in its timestamp is a nightmare to
    compare.
    """
    payload_dir = Path(payload_dir)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    (payload_dir / PAYLOAD_ENV_FILE).write_text(
        f'P4A_NUMERIC_VERSION={int(numeric_version)}\nP4A_MINSDK={int(min_sdk)}\n',
        encoding='utf-8')
    (payload_dir / 'sitecustomize.py').write_text(SITECUSTOMIZE_SOURCE, encoding='utf-8')

    files, folders = _iter_payload_files(payload_dir)
    with open(target, 'wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w',
                              format=tarfile.USTAR_FORMAT) as archive:
                for folder in folders:
                    info = tarfile.TarInfo(folder.as_posix())
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    info.mtime = 0
                    archive.addfile(info)
                for path in files:
                    data = path.read_bytes()
                    info = tarfile.TarInfo(path.relative_to(payload_dir).as_posix())
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = 0
                    archive.addfile(info, io.BytesIO(data))

    return {'files': len(files),
            'folders': len(folders),
            'bytes': target.stat().st_size}


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
