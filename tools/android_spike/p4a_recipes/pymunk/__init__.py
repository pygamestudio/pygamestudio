"""p4a recipe: pymunk (physics backend of the engine).

p4a already ships a pymunk recipe, but pinned to 6.0.0 while the engine needs
7.3.1. The build itself is unchanged (a cffi module compiled at build time), so
the only differences are the version/URL and the two extra linker flags the
recipe already needed: Chipmunk logs through ``__android_log_print`` (``-llog``)
and the older Android APIs need ``-lm``.
"""

from pythonforandroid.recipe import CompiledComponentsPythonRecipe


class PymunkRecipe(CompiledComponentsPythonRecipe):
    name = 'pymunk'
    version = '7.3.1'
    url = ('https://files.pythonhosted.org/packages/source/p/pymunk/'
           'pymunk-{version}.tar.gz')
    depends = ['cffi', 'setuptools']
    call_hostpython_via_targetpython = False

    def get_recipe_env(self, arch):
        env = super().get_recipe_env(arch)
        env['LDFLAGS'] += ' -llog'      # Chipmunk's cpMessage()
        env['LDFLAGS'] += ' -lm'
        return env


recipe = PymunkRecipe()
