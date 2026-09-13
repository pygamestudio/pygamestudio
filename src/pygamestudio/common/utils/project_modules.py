"""Load the python modules of a game project, decrypting protected builds.

In a protected build the project's own modules ship encrypted (see
``pygamestudio.common.utils.assets``), so Python cannot read them straight from
disk. This module compiles them from memory instead, and installs a small
import hook, so that both the scene scripts the engine loads and any module a
script imports behave exactly like in a normal project.

Plain projects (the editor, games run from source) are untouched: the hook only
steps in when a project file really is a protected container.
"""
import importlib.abc
import importlib.util
import linecache
import sys
import types
from pathlib import Path

from pygamestudio.common.utils import assets
from pygamestudio.common.utils.path import get_project_path

_installed = False


def read_source(path) -> str:
    """Source text of a project module (decrypted when the file is protected)."""
    return assets.read_text(path)


def _compile(filename, source):
    """Compile the module and let tracebacks show the decrypted source."""
    linecache.cache[filename] = (len(source), None, source.splitlines(keepends=True), filename)
    return compile(source, filename, 'exec')


def load_module(name, path):
    """Compile and execute a project module, decrypting it when protected.

    The runtime uses this for the behavior scripts attached to scene objects:
    they are loaded from an explicit path, not through the import system. The
    module is not registered in ``sys.modules``, so every scene (re)load takes
    the current file content.
    """
    path = Path(path)
    filename = str(path)
    code = _compile(filename, read_source(path))
    module = types.ModuleType(name)
    module.__file__ = filename
    module.__package__ = ''
    exec(code, module.__dict__)
    return module


class _ProtectedModuleLoader(importlib.abc.Loader):
    """Loader that reads a protected project module through the asset facade."""

    def __init__(self, path, is_package=False):
        self._path = Path(path)
        self._is_package = is_package

    def get_source(self, fullname):
        return read_source(self._path)

    def get_filename(self, fullname):
        return str(self._path)

    def create_module(self, spec):
        module = types.ModuleType(spec.name)
        module.__file__ = str(self._path)
        if self._is_package:
            module.__path__ = [str(self._path.parent)]
        return module

    def exec_module(self, module):
        filename = str(self._path)
        exec(_compile(filename, read_source(self._path)), module.__dict__)


class _ProjectModuleFinder(importlib.abc.MetaPathFinder):
    """Resolve protected project modules before the normal file finder."""

    def find_spec(self, fullname, path=None, target=None):
        root = (get_project_path() or '').strip()
        if not root:
            return None
        parts = fullname.split('.')
        if not parts or any(not part.isidentifier() for part in parts):
            return None

        module_file = Path(root).joinpath(*parts).with_suffix('.py')
        if module_file.is_file() and assets.is_encrypted(module_file):
            return importlib.util.spec_from_loader(fullname, _ProtectedModuleLoader(module_file))

        package_file = Path(root).joinpath(*parts) / '__init__.py'
        if package_file.is_file() and assets.is_encrypted(package_file):
            spec = importlib.util.spec_from_loader(fullname, _ProtectedModuleLoader(package_file, True),
                                                   is_package=True)
            if spec is not None:
                spec.submodule_search_locations = [str(package_file.parent)]
            return spec
        return None


def install():
    """Add the project module finder to the import system (idempotent)."""
    global _installed
    if not _installed:
        sys.meta_path.insert(0, _ProjectModuleFinder())
        _installed = True
