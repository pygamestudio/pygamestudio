"""p4a recipe: pygame-ce.

pygame-ce keeps pygame's legacy build system and ships the same
``buildconfig/Setup.Android.SDL2.in`` template, so p4a's own pygame recipe
(which writes that Setup file and sets the SDL2 cross-compile env) is reused -
only the source, the recipe name and two workarounds change.

The package still installs as ``pygame`` (``site_packages_name``), which is what
``import pygame`` in the engine resolves to.

Accepted by buildozer as ``pygame_ce`` inside ``requirements``.
"""

import re
from pathlib import Path

from pythonforandroid.recipes.pygame import Pygame2Recipe

#: Replacement for the sdist's PEP 517 metadata, see prebuild_arch().
_BUILD_SYSTEM = '''[build-system]
requires = ["setuptools>=61", "wheel", "Cython<3.1"]
build-backend = "setuptools.build_meta"

'''


class PygameCERecipe(Pygame2Recipe):
    name = 'pygame_ce'
    version = '2.5.8'
    site_packages_name = 'pygame'
    # PyPI's stable "source" alias - no hash needed, and it survives version bumps.
    url = ('https://files.pythonhosted.org/packages/source/p/pygame-ce/'
           'pygame_ce-{version}.tar.gz')
    # Unlike pygame 2.1, the pygame-ce sdist ships .pyx sources: its
    # setup.py build_ext aborts with "You need cython" unless Cython is
    # importable from the *host* interpreter that p4a uses to drive the
    # cross build. Pinned below 3.1 for the same reason pyjnius pins <3.2.
    hostpython_prerequisites = ['Cython<3.1']

    def prebuild_arch(self, arch):
        # Writes the legacy ``Setup`` file pygame's setup.py consumes.
        super().prebuild_arch(arch)

        # Since 2.5 the sdist also declares meson-python as its PEP 517 backend.
        # p4a installs with ``pip install .``, so pip would call meson, which
        # cannot run here: its sanity check compiles a native binary with the
        # NDK cross compiler and then fails to execute it. The legacy setup.py
        # build that ran just before this works (it is what p4a's pygame recipe
        # has always used), so point the metadata at setuptools instead and let
        # pip take the setup.py path. The rest of the file is left untouched.
        pyproject = Path(self.get_build_dir(arch.arch)) / 'pyproject.toml'
        if not pyproject.exists():
            return

        text = pyproject.read_text(encoding='utf-8')
        text = re.sub(r'\[build-system\].*?(?=\n\[|\Z)', '', text, flags=re.S)
        pyproject.write_text(_BUILD_SYSTEM + text.lstrip(), encoding='utf-8')


recipe = PygameCERecipe()
