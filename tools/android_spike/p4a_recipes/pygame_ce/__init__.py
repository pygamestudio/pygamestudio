"""p4a recipe: pygame-ce.

pygame-ce is a drop-in fork that keeps pygame's legacy build system and ships
the same ``buildconfig/Setup.Android.SDL2.in`` template, so p4a's own pygame
recipe (which writes that Setup file and sets the SDL2 cross-compile env) can
be reused as-is - only the source and the recipe name change.

The package still installs as ``pygame`` (``site_packages_name``), which is what
``import pygame`` in the engine resolves to.

Accepted by buildozer as ``pygame_ce`` inside ``requirements``.
"""

from pythonforandroid.recipes.pygame import Pygame2Recipe


class PygameCERecipe(Pygame2Recipe):
    name = 'pygame_ce'
    version = '2.5.8'
    site_packages_name = 'pygame'
    # PyPI's stable "source" alias - no hash needed, and it survives version bumps.
    url = ('https://files.pythonhosted.org/packages/source/p/pygame-ce/'
           'pygame_ce-{version}.tar.gz')


recipe = PygameCERecipe()
