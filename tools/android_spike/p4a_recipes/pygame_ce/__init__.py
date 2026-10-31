"""p4a recipe: pygame-ce.

pygame-ce keeps pygame's legacy build system and ships the same
``buildconfig/Setup.Android.SDL2.in`` template, so p4a's own pygame recipe
(which writes that Setup file and sets the SDL2 cross-compile env) is reused -
only the source, the recipe name and three workarounds change.

The package still installs as ``pygame`` (``site_packages_name``), which is what
``import pygame`` in the engine resolves to.

Accepted by buildozer as ``pygame_ce`` inside ``requirements``.

Why the workarounds (each one was a separate CI failure):

1. ``hostpython_prerequisites`` - the sdist ships ``.pyx`` sources, so
   ``setup.py build_ext`` aborts with "You need cython" unless Cython is
   importable from the interpreter driving the cross build.
2. ``install_python_package`` override - pygame's setup.py only works when it is
   *started as a script*; pip drives it through the PEP 517 backend (exec,
   different argv) and the build dies at whatever it touches next. Installing
   from a wheel built on the command line keeps the path that already works.
3. the two patches in ``prebuild_arch`` - see their docstrings.

Do *not* reach for ``setup_extra_args`` here: p4a appends it to
``setup.py build_ext`` as well as to ``pip install``, so pip-only flags such as
``--no-build-isolation`` make setup.py fail with "option not recognized".
"""

import ast
import re
import shutil
from pathlib import Path

from pythonforandroid.recipes.pygame import Pygame2Recipe

try:
    from pythonforandroid.logger import info
except ImportError:                                   # pragma: no cover - p4a always has it
    def info(message):
        print(message)

#: Replacement for the sdist's PEP 517 metadata, see _use_setuptools_backend().
#: Cython has to be listed here as well: pip builds the wheel in an isolated
#: environment (the image's Python 3.14), which therefore needs its own copy.
_BUILD_SYSTEM = '''[build-system]
requires = ["setuptools>=61", "wheel", "Cython>=3.1"]
build-backend = "setuptools.build_meta"

'''

#: Marker so the setup.py patch is applied at most once.
_PATH_HACK_MARKER = '__pygs_setup_path__'
_PATH_HACK = (f'import os as _os, sys as _sys  # {_PATH_HACK_MARKER}\n'
              '_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))\n')


class PygameCERecipe(Pygame2Recipe):
    name = 'pygame_ce'
    version = '2.5.8'
    site_packages_name = 'pygame'
    # PyPI's stable "source" alias - no hash needed, and it survives version bumps.
    url = ('https://files.pythonhosted.org/packages/source/p/pygame-ce/'
           'pygame_ce-{version}.tar.gz')
    # Cython 3.1 is what has wheels for the Python 3.14 host interpreter.
    hostpython_prerequisites = ['Cython>=3.0,<3.2']
    # p4a's pygame recipe leaves the optional C extensions out. Adding the
    # library recipes here (freetype is also pulled in by sdl2_ttf) is what lets
    # pygame's own buildconfig compile ``pygame._freetype``.
    depends = ['sdl2', 'sdl2_image', 'sdl2_mixer', 'sdl2_ttf', 'setuptools',
               'jpeg', 'png', 'freetype']

    def get_recipe_env(self, arch):
        """Add freetype's include directory to the cross build.

        The ``Setup`` file written by ``prebuild_arch`` links ``-lfreetype``
        (p4a installs the library into the dist's ``libs/<arch>``), but the
        headers are only in the freetype build tree, so ``#include <ft2build.h>``
        needs this ``-I``. freetype is built in place, so both possible header
        layouts are probed; if neither is there the module stays out instead of
        failing the build.
        """
        env = super().get_recipe_env(arch)
        try:
            freetype = self.get_recipe('freetype', self.ctx)
            freetype_dir = Path(freetype.get_build_dir(arch.arch))
        except Exception as error:                    # noqa: BLE001 - optional
            info(f'{self.name}: no freetype recipe ({error}), _freetype will be skipped')
            return env

        include_dir = _freetype_include_dir(freetype_dir)
        if include_dir is None:
            info(f'{self.name}: no ft2build.h under {freetype_dir.as_posix()}, '
                 f'_freetype will be skipped')
            return env

        for key in ('CFLAGS', 'CPPFLAGS'):
            flag = f'-I{include_dir.as_posix()}'
            if flag not in env.get(key, ''):
                env[key] = (env.get(key, '') + ' ' + flag).strip()
        info(f'{self.name}: freetype headers at {include_dir.as_posix()} (for _freetype)')
        return env

    def prebuild_arch(self, arch):
        # Writes the legacy ``Setup`` file pygame's setup.py consumes.
        super().prebuild_arch(arch)

        build_dir = Path(self.get_build_dir(arch.arch))
        _enable_freetype(build_dir)
        _use_setuptools_backend(build_dir)
        _make_source_dir_importable(build_dir)

    def install_python_package(self, arch, name=None, env=None, is_dir=True):
        """Install the built package without letting pip run setup.py again.

        p4a's default is ``pip install .``, which hands setup.py to a PEP 517
        backend: pygame's setup.py assumes it runs as a script (it rewrites its
        own sys.argv and imports sibling directories) and fails there. Build the
        wheel from the command line - the same way p4a's ``build_ext`` step
        already runs - and unpack it into the target site-packages.
        """
        import sh
        import zipfile

        from pythonforandroid.logger import shprint
        try:
            from pythonforandroid.util import current_directory
        except ImportError:                       # older p4a releases
            from pythonforandroid.toolchain import current_directory

        recipe_env = self.get_recipe_env(arch)
        hostpython = sh.Command(getattr(self, 'real_hostpython_location', None) or self.ctx.hostpython)
        build_dir = Path(self.get_build_dir(arch.arch))
        target_dir = Path(self.ctx.get_python_install_dir(arch.arch))
        wheel_dir = build_dir / '_pygs_wheel'
        wheel_dir.mkdir(exist_ok=True)

        wheels = []
        try:
            with current_directory(build_dir.as_posix()):
                shprint(hostpython, 'setup.py', 'bdist_wheel',
                        '--dist-dir', wheel_dir.as_posix(), _env=recipe_env)
            wheels = sorted(wheel_dir.glob('*.whl'))
        except Exception as error:                # noqa: BLE001 - fall back below
            info(f'{self.name}: bdist_wheel failed ({error}), copying the build tree instead')

        if wheels:
            with zipfile.ZipFile(wheels[-1]) as wheel:
                wheel.extractall(target_dir)
            return

        # Fallback for a hostpython without the bdist_wheel command: a plain
        # ``setup.py build`` and a copy of the produced package tree.
        with current_directory(build_dir.as_posix()):
            shprint(hostpython, 'setup.py', 'build', _env=recipe_env)

        lib_dirs = sorted(build_dir.glob('build/lib*'))
        if not lib_dirs:
            raise RuntimeError(f'{self.name}: setup.py build produced no build/lib* directory')
        for entry in lib_dirs[-1].iterdir():
            destination = target_dir / entry.name
            if entry.is_dir():
                shutil.copytree(entry, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(entry, destination)


def _enable_freetype(build_dir):
    """Uncomment ``_freetype`` in the Setup p4a generated - and in its template.

    ``buildconfig/Setup.Android.SDL2.in`` ships the module commented out
    ("optional freetype module"), which is *the* reason p4a's pygame has no
    ``_freetype``: no amount of dependency detection can enable a line that is a
    comment. The same template links ``-lharfbuzz``, which p4a only builds when
    harfbuzz is in the requirements, so the FREETYPE variable drops it.

    Both files are patched: p4a writes ``Setup`` from the template, and a later
    ``setup.py`` run regenerates it from the template again when it is missing.
    Every decision is logged with ``info`` - the CI copies those lines into
    ``inspect.log``, so a silent "module missing" can be told apart from "the
    patch never ran".
    """
    build_dir = Path(build_dir)
    patched_files = []
    enabled = False
    for relative in (('buildconfig', 'Setup.Android.SDL2.in'), ('Setup',)):
        path = build_dir.joinpath(*relative)
        if not path.is_file():
            info(f'{build_dir.name}: {"/".join(relative)} not found')
            continue
        original = path.read_text(encoding='utf-8')
        text, file_enabled = _patch_setup_text(original)
        enabled = enabled or file_enabled
        if text != original:
            path.write_text(text, encoding='utf-8')
            patched_files.append('/'.join(relative))
        info(f'{build_dir.name}: {"/".join(relative)} freetype lines -> '
             f'{[line.strip() for line in text.splitlines() if "freetype" in line.lower()]}')

    if patched_files:
        info(f'{build_dir.name}: _freetype enabled (patched {", ".join(patched_files)})')
    elif enabled:
        info(f'{build_dir.name}: _freetype was already enabled')
    else:
        info(f'{build_dir.name}: no _freetype line found, the module stays out')
    return enabled


def _patch_setup_text(text):
    """``(patched text, module enabled)`` for one Setup / template file."""
    result = []
    enabled = False
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith('_freetype'):
            enabled = True                        # already active
            result.append(line)
        elif stripped.startswith('#') and stripped.lstrip('#').lstrip().startswith('_freetype'):
            indent = line[:len(line) - len(stripped)]
            result.append(indent + stripped.lstrip('#').lstrip() + '\n')
            enabled = True
        elif stripped.startswith('FREETYPE'):
            indent = line[:len(line) - len(stripped)]
            result.append(f'{indent}FREETYPE = -lfreetype\n')
        else:
            result.append(line)
    return ''.join(result), enabled


def _freetype_include_dir(freetype_dir):
    """Folder that makes ``#include <ft2build.h>`` work, or None.

    p4a's freetype recipe only runs ``make install`` when harfbuzz is part of
    the build, so there are two possible layouts:

    ``<build>/include/freetype2/``  installed prefix (ft2build.h + freetype/)
    ``<build>/include/``            source tree (ft2build.h + freetype/)

    Both are checked instead of assuming one, because guessing wrong only shows
    up as "pygame was built without _freetype" an hour into a CI run.
    """
    for candidate in (freetype_dir / 'include' / 'freetype2',
                      freetype_dir / 'include'):
        if (candidate / 'ft2build.h').is_file():
            return candidate
    return None


def _use_setuptools_backend(build_dir):
    """Drop meson-python from the sdist metadata.

    Since 2.5 pygame-ce declares meson-python as its PEP 517 backend, and p4a
    installs with ``pip install .``. meson cannot cross-compile here: its sanity
    check compiles a native binary with the NDK compiler and then tries to run
    it. The legacy setup.py build works, so point the metadata at setuptools.
    The rest of pyproject.toml is left untouched.
    """
    pyproject = build_dir / 'pyproject.toml'
    if not pyproject.exists():
        return

    text = pyproject.read_text(encoding='utf-8')
    text = re.sub(r'\[build-system\].*?(?=\n\[|\Z)', '', text, flags=re.S)
    pyproject.write_text(_BUILD_SYSTEM + text.lstrip(), encoding='utf-8')


def _make_source_dir_importable(build_dir):
    """Let setup.py import the ``buildconfig`` folder it ships with.

    p4a starts setup.py as a script (sys.path[0] = the source directory) and the
    import works. pip drives the PEP 517 backend with exec() instead, where the
    source directory is *not* importable, so the build dies with
    ``ModuleNotFoundError: No module named 'buildconfig'``. Insert the directory
    from inside setup.py - after the module docstring and any ``__future__``
    imports, which have to stay first.
    """
    setup_py = build_dir / 'setup.py'
    if not setup_py.exists():
        return

    source = setup_py.read_text(encoding='utf-8')
    if _PATH_HACK_MARKER in source:
        return

    insert_at = 0
    for node in ast.parse(source).body:
        is_docstring = (isinstance(node, ast.Expr)
                        and isinstance(node.value, ast.Constant)
                        and isinstance(node.value.value, str))
        is_future = isinstance(node, ast.ImportFrom) and node.module == '__future__'
        if not (is_docstring or is_future):
            break
        insert_at = node.end_lineno

    lines = source.splitlines(keepends=True)
    lines.insert(insert_at, _PATH_HACK)
    setup_py.write_text(''.join(lines), encoding='utf-8')


recipe = PygameCERecipe()
