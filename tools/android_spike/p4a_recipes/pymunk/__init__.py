"""p4a recipe: pymunk (physics backend of the engine).

p4a already ships a pymunk recipe, but pinned to 6.0.0 while the engine needs
7.3.1. The build itself is unchanged - pymunk compiles its bundled Chipmunk
through cffi at build time - so this recipe adds what 7.x needs on top of it:

* ``cffi`` in the hostpython env: ``setup.py`` declares ``cffi_modules``, a
  keyword only the cffi setuptools extension understands. Without it setuptools
  warns "Unknown distribution option: 'cffi_modules'", compiles nothing, and p4a
  then fails with ``glob('build/lib.*')[0] -> IndexError``.
* the two linker flags Chipmunk's ``cpMessage`` needs (``-llog``) and older
  Android APIs need (``-lm``).
* a wheel-based install, so pip never re-executes setup.py (see the method).
"""

import shutil
import zipfile
from pathlib import Path

from pythonforandroid.recipe import CompiledComponentsPythonRecipe


class PymunkRecipe(CompiledComponentsPythonRecipe):
    name = 'pymunk'
    version = '7.3.1'
    url = ('https://files.pythonhosted.org/packages/source/p/pymunk/'
           'pymunk-{version}.tar.gz')
    depends = ['cffi', 'setuptools']
    call_hostpython_via_targetpython = False
    # cffi must be importable from the interpreter that drives the build, not
    # only from the target site-packages (which is what `depends` provides).
    hostpython_prerequisites = ['cffi>=1.15']

    def get_recipe_env(self, arch):
        env = super().get_recipe_env(arch)
        env['LDFLAGS'] += ' -llog'      # Chipmunk's cpMessage()
        env['LDFLAGS'] += ' -lm'
        return env

    def install_python_package(self, arch, name=None, env=None, is_dir=True):
        """Install the built package without letting pip run setup.py again.

        Same approach as the pygame_ce recipe: build the wheel from the command
        line - setup.py started as a script keeps cffi's build hooks attached -
        and unpack it into the target site-packages. Falls back to a plain
        ``setup.py build`` when the hostpython has no bdist_wheel command.
        """
        import sh

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
        except Exception:                          # noqa: BLE001 - fall back below
            wheels = []

        if wheels:
            with zipfile.ZipFile(wheels[-1]) as wheel:
                wheel.extractall(target_dir)
            return

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


recipe = PymunkRecipe()
