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
2. ``setup_extra_args = ['--no-build-isolation']`` - the isolated build env is a
   different Python (3.14 on the buildozer image), which has no wheel for the
   pinned Cython range; the hostpython env already has everything.
3. the two patches in ``prebuild_arch`` - see their docstrings.
"""

import ast
import re
from pathlib import Path

from pythonforandroid.recipes.pygame import Pygame2Recipe

#: Replacement for the sdist's PEP 517 metadata, see _use_setuptools_backend().
_BUILD_SYSTEM = '''[build-system]
requires = ["setuptools>=61", "wheel"]
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
    # See the module docstring: build with the hostpython env, not an isolated one.
    setup_extra_args = ['--no-build-isolation']

    def prebuild_arch(self, arch):
        # Writes the legacy ``Setup`` file pygame's setup.py consumes.
        super().prebuild_arch(arch)

        build_dir = Path(self.get_build_dir(arch.arch))
        _use_setuptools_backend(build_dir)
        _make_source_dir_importable(build_dir)


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
