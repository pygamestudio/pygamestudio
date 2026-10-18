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


def _is_inside(path, root) -> bool:
    """True when ``path`` lives inside ``root`` (both made absolute)."""
    try:
        return Path(path).resolve().is_relative_to(Path(root).resolve())
    except (OSError, ValueError):
        return False


class _ProjectModuleFinder(importlib.abc.MetaPathFinder):
    """Resolve protected project modules before the normal file finder.

    A protected build encrypts the project's modules, so the standard finder
    would read the container as source (``ValueError: source code string
    cannot contain null bytes``). This finder looks for the module in

    * the project root (``import script.taptap_login``),
    * every sys.path entry inside the project - a game may add e.g. its
      ``script`` folder to sys.path and then ``import taptap_login``, and
    * the package folder of a sub-import, like the standard ``PathFinder``.

    Files that are not protected are left to the normal finder, so plain
    projects behave exactly as before.
    """

    @staticmethod
    def _spec_for(base, fullname):
        """Spec for ``base.py`` / ``base/__init__.py`` when it is protected."""
        module_file = Path(str(base) + '.py')
        if module_file.is_file() and assets.is_encrypted(module_file):
            return importlib.util.spec_from_loader(fullname, _ProtectedModuleLoader(module_file))
        package_file = Path(base) / '__init__.py'
        if package_file.is_file() and assets.is_encrypted(package_file):
            spec = importlib.util.spec_from_loader(fullname, _ProtectedModuleLoader(package_file, True),
                                                   is_package=True)
            if spec is not None:
                spec.submodule_search_locations = [str(package_file.parent)]
            return spec
        return None

    def find_spec(self, fullname, path=None, target=None):
        root = (get_project_path() or '').strip()
        if not root:
            return None
        parts = fullname.split('.')
        if not parts or any(not part.isidentifier() for part in parts):
            return None

        # Names relative to the project root and to project sys.path entries.
        bases = [Path(root)]
        bases += [Path(entry) for entry in sys.path
                  if entry and _is_inside(entry, root)]
        for base in bases:
            spec = self._spec_for(base.joinpath(*parts), fullname)
            if spec is not None:
                return spec

        # Names relative to the package folder of a sub-import.
        for entry in path or ():
            if entry:
                spec = self._spec_for(Path(entry).joinpath(parts[-1]), fullname)
                if spec is not None:
                    return spec
        return None


def install():
    """Add the project module finder to the import system (idempotent)."""
    global _installed
    if not _installed:
        sys.meta_path.insert(0, _ProjectModuleFinder())
        _installed = True
