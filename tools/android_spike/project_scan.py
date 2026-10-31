"""Report imports an Android build cannot satisfy - before the APK is installed.

The shipped runtime contains the standard library, ``pygame-ce``, ``pymunk``,
``cffi`` and the engine. Nothing else. A project that imports ``numpy`` (or
``pygame.freetype``, which p4a's pygame build does not compile) still packages
happily and then dies on the phone with ``ModuleNotFoundError`` - and the user
sees a black screen with no hint of what happened.

This walks the ``.py`` files of a project with ``ast`` and lists every top-level
import that the runtime cannot resolve, so the builder can refuse the build with
a name instead of shipping a broken APK:

    py -3.10 tools/android_spike/project_scan.py tools/android_spike/app
    py -3.10 tools/android_spike/project_scan.py <project> --engine <pygamestudio>

Exit code 1 means "this project would crash on the device".
"""
import argparse
import ast
import sys
from pathlib import Path

from engine_runtime import ANDROID_MISSING_PYGAME_MODULES

#: Third-party top-level modules the Android runtime actually contains.
SUPPORTED_THIRD_PARTY = frozenset((
    'pygame',
    'pymunk',
    'cffi',
    '_cffi_backend',
    'pygamestudio',
))

#: Top-level folders that belong to the engine or are never project code.
SKIP_DIRS = frozenset(('pygamestudio', '__pycache__', '.git', 'build', 'dist'))


def _stdlib_names():
    """Names of the standard library modules of the interpreter running this."""
    names = getattr(sys, 'stdlib_module_names', None)
    if names is not None:
        return set(names)
    # Python < 3.10: a coarse fallback - anything importable that ships with
    # CPython has no dot in its name and lives under the stdlib directory.
    import sysconfig
    stdlib_dir = Path(sysconfig.get_paths()['stdlib'])
    found = set(sys.builtin_module_names)
    for path in stdlib_dir.iterdir():
        if path.suffix == '.py':
            found.add(path.stem)
        elif path.is_dir() and (path / '__init__.py').is_file():
            found.add(path.name)
    return found


def _local_names(project_dir):
    """Modules the project itself provides (``foo.py`` / ``foo/``)."""
    names = set()
    for entry in project_dir.iterdir():
        if entry.name in SKIP_DIRS or entry.name.startswith('.'):
            continue
        if entry.is_dir() and (entry / '__init__.py').is_file():
            names.add(entry.name)
        elif entry.suffix == '.py':
            names.add(entry.stem)
    return names


def _imports(path):
    """``(module, lineno)`` of every absolute import in one python file."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'), filename=str(path))
    except SyntaxError as error:
        yield f'{path}:{error.lineno}', 0
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level:                          # relative import: project internal
                continue
            for alias in node.names:
                yield f'{node.module}.{alias.name}' if node.module else alias.name, node.lineno


def scan(project_dir, engine_root=None):
    """Check one project directory.

    :return: dict with ``files``, ``imports`` (used top-level names),
             ``missing`` ((module, file, line)) and ``blocked`` (Android-missing
             pygame submodules).
    """
    project_dir = Path(project_dir)
    supported = _stdlib_names() | SUPPORTED_THIRD_PARTY | _local_names(project_dir)

    files = []
    for path in sorted(project_dir.rglob('*.py')):
        relative = path.relative_to(project_dir)
        if any(part in SKIP_DIRS for part in relative.parts[:-1]):
            continue
        files.append(path)

    used = set()
    missing = []
    blocked = []
    for path in files:
        relative = path.relative_to(project_dir).as_posix()
        for module, lineno in _imports(path):
            if module in ANDROID_MISSING_PYGAME_MODULES or \
                    any(module.startswith(name + '.')
                        for name in ANDROID_MISSING_PYGAME_MODULES):
                blocked.append((module, relative, lineno))
                continue
            top = module.split('.')[0]
            used.add(top)
            if top not in supported:
                missing.append((module, relative, lineno))

    return {'files': len(files), 'imports': sorted(used),
            'missing': missing, 'blocked': blocked}


def report(summary, project_dir):
    print(f'project: {Path(project_dir)}')
    print(f'scanned: {summary["files"]} python file(s)')
    print(f'imports: {", ".join(summary["imports"]) or "-"}')

    for module, relative, lineno in summary['blocked']:
        print(f'  BLOCKED {module} ({relative}:{lineno}) - p4a does not build it')
    for module, relative, lineno in summary['missing']:
        print(f'  MISSING {module} ({relative}:{lineno}) - not part of the Android runtime')

    if summary['missing'] or summary['blocked']:
        print('RESULT : imports UNSUPPORTED')
        return 1
    print('RESULT : project imports ok')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Check project imports against the Android runtime')
    parser.add_argument('project_dir', type=Path)
    parser.add_argument('--engine', type=Path, default=None,
                        help='installed pygamestudio package (kept for the real builder)')
    args = parser.parse_args(argv)
    return report(scan(args.project_dir, args.engine), args.project_dir)


if __name__ == '__main__':
    raise SystemExit(main())
