"""Code protection for game builds (stripping + pyobfus + PyInstaller).

A protected build never packages the project folder itself: it copies it into a
staging folder and rewrites that copy.

1. every comment, docstring and any other formatting is removed (``strip_code``)
   and the modules are minified, so nothing readable is left;
2. when pyobfus is installed the code is obfuscated (names, numbers);
3. the assets (images, audio, fonts, scenes, project.pygs) are encrypted by
   ``gui/build/assets.py`` and the per-build key ships with the game.

PyInstaller then packages the staging copy, so the shipped game carries no
readable source and no plain resource. Callbacks the engine calls by name
(``on_*``: on_start, on_update, on_drag, ...) are preserved - renaming them
would break every game. When pyobfus is not installed the build still ships
stripped code and encrypted assets, but no name mangling.
"""
import ast
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tokenize
from pathlib import Path

from pygamestudio.gui.build import assets as asset_protection

#: Never part of a build (caches, virtual envs, build outputs).
IGNORED_DIR_NAMES = {'__pycache__', 'node_modules', 'venv', 'env', 'dist', 'build'}

#: Names the engine calls on game/script classes by name - obfuscating them
#: would break every callback.
RESERVED_NAMES = ('on_*',)

_OBFUSCATOR_NAME = 'pyobfus'

_CONFIG_TEMPLATE = """obfuscation:
  level: community
  exclude_names:
{exclude_names}
  remove_comments: true
  remove_docstrings: true
"""

_CALLBACK_PATTERN = re.compile(r'^\s*def (on_[A-Za-z0-9_]+)\s*\(', re.MULTILINE)


class ProtectionError(Exception):
    """Raised when the project cannot be prepared for a protected build."""


class StagingError(ProtectionError):
    """Raised when the project cannot be copied into the staging folder."""


class ObfuscationError(ProtectionError):
    """Raised when the project code cannot be obfuscated."""


def find_obfuscator():
    """Command prefix for pyobfus, or None when it is not installed."""
    if importlib.util.find_spec(_OBFUSCATOR_NAME) is None:
        return None
    executable_dir = Path(sys.executable).parent
    for candidate in (executable_dir / f'{_OBFUSCATOR_NAME}.exe', executable_dir / _OBFUSCATOR_NAME,
                      executable_dir / 'Scripts' / f'{_OBFUSCATOR_NAME}.exe'):
        if candidate.exists():
            return [str(candidate)]
    found = shutil.which(_OBFUSCATOR_NAME)
    if found:
        return [found]
    return [sys.executable, '-m', _OBFUSCATOR_NAME]


def _collect_callback_names(root):
    """``on_*`` method names defined below the given folder."""
    names = set()
    for script in sorted(Path(root).rglob('*.py')):
        try:
            names.update(_CALLBACK_PATTERN.findall(script.read_text(encoding='utf-8', errors='replace')))
        except OSError:
            continue
    return names


def _strip_bare_strings(node):
    """Drop every string that is only a statement (docstrings included)."""
    body = getattr(node, 'body', None)
    if isinstance(body, list):
        kept = [statement for statement in body
                if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
                        and isinstance(statement.value.value, str))]
        node.body = kept or [ast.Pass()]
    for field in ('orelse', 'finalbody'):
        statements = getattr(node, field, None)
        if isinstance(statements, list) and statements:
            kept = [statement for statement in statements
                    if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
                            and isinstance(statement.value.value, str))]
            setattr(node, field, kept or [ast.Pass()])
    for child in ast.iter_child_nodes(node):
        _strip_bare_strings(child)


def _has_multiline_string(source_code) -> bool:
    """True when the module holds a string literal spanning several lines."""
    try:
        for token in tokenize.generate_tokens(io.StringIO(source_code).readline):
            if token.type == tokenize.STRING and token.start[0] != token.end[0]:
                return True
    except (tokenize.TokenError, IndentationError):
        return True
    return False


def _compact(source_code) -> str:
    """Drop the empty lines of a module (never inside a multiline string)."""
    if _has_multiline_string(source_code):
        return source_code
    return '\n'.join(line for line in source_code.splitlines() if line.strip())


def strip_source(source_code, filename='<project>') -> str:
    """Remove every comment and docstring of a module and minify it.

    Comments never reach the AST, so re-emitting it drops them; bare string
    statements (module/class/function docstrings) are deleted explicitly. The
    blank lines ast.unparse keeps around definitions are removed as well, but
    only when the module has no string literal spanning several lines - the
    empty lines of such a literal are part of its value.
    """
    tree = ast.parse(source_code, filename=filename)
    _strip_bare_strings(tree)
    return _compact(ast.unparse(tree))


def strip_code(project_dir) -> dict:
    """Rewrite every python file of the staged project without documentation.

    The stripped source is compiled before it is written, so a file that cannot
    be handled aborts the build instead of shipping broken code.
    """
    files = 0
    for script in sorted(Path(project_dir).rglob('*.py')):
        source_code = script.read_text(encoding='utf-8', errors='replace')
        try:
            stripped = strip_source(source_code, str(script))
            compile(stripped, str(script), 'exec')
        except (SyntaxError, ValueError) as error:
            raise ObfuscationError(f'{script.name} cannot be stripped: {error}') from error
        script.write_text(stripped, encoding='utf-8')
        files += 1
    return {'files': files}


def _has_comments(source_code) -> bool:
    """True when the module still holds a comment (tokenizer, not text search)."""
    try:
        for token in tokenize.generate_tokens(io.StringIO(source_code).readline):
            if token.type == tokenize.COMMENT:
                return True
    except (tokenize.TokenError, IndentationError):
        return False
    return False


def _has_docstrings(source_code) -> bool:
    """True when a module, class or function still starts with a docstring."""
    for node in ast.walk(ast.parse(source_code)):
        body = getattr(node, 'body', None)
        if isinstance(body, list) and body:
            first = body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                return True
    return False


def stage_project(project_path, target_dir, output_dir) -> dict:
    """Copy the project (resources and code) into the staging folder."""
    project_path = Path(project_path)
    target_dir = Path(target_dir)
    output_resolved = Path(output_dir).resolve()
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    for entry in sorted(project_path.iterdir()):
        if entry.name in IGNORED_DIR_NAMES or entry.name.startswith('.'):
            continue
        try:
            resolved = entry.resolve()
        except OSError:
            continue
        if resolved == output_resolved or output_resolved.is_relative_to(resolved):
            # never copy the build output itself
            continue
        destination = target_dir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination,
                            ignore=shutil.ignore_patterns(*IGNORED_DIR_NAMES, '.*'))
        else:
            shutil.copy2(entry, destination)

    if not (target_dir / 'main.py').exists():
        raise StagingError('main.py is not found in the project root')
    python_files = sorted(target_dir.rglob('*.py'))
    return {'files': len(python_files), 'py_files': len(python_files)}


def obfuscate(project_dir, work_dir) -> dict:
    """Obfuscate every python file of the staged project in place."""
    command = find_obfuscator()
    if command is None:
        raise ObfuscationError('pyobfus is not installed')

    project_dir = Path(project_dir)
    work_dir = Path(work_dir)
    python_files = sorted(project_dir.rglob('*.py'))
    if not python_files:
        raise ObfuscationError('the project has no python files')
    callbacks = _collect_callback_names(project_dir)

    code_dir = work_dir / 'code'
    obfuscated_dir = work_dir / 'obfuscated'
    for folder in (code_dir, obfuscated_dir):
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
    for script in python_files:
        relative = script.relative_to(project_dir)
        target = code_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(script, target)

    config_path = work_dir / 'pyobfus.yaml'
    exclude_lines = '\n'.join(f'    - "{name}"' for name in RESERVED_NAMES)
    config_path.write_text(_CONFIG_TEMPLATE.format(exclude_names=exclude_lines), encoding='utf-8')

    completed = subprocess.run(
        command + [str(code_dir), '-o', str(obfuscated_dir),
                   '--config', str(config_path), '--no-community-marker',
                   '--numeric-obfuscation', '--verify-syntax'],
        cwd=str(work_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if completed.returncode != 0:
        tail = '\n'.join((completed.stdout or '').strip().splitlines()[-8:])
        raise ObfuscationError(f'pyobfus failed: {tail}')

    # the obfuscated files must mirror the project and stay valid python
    obfuscated_files = sorted(obfuscated_dir.rglob('*.py'))
    if len(obfuscated_files) != len(python_files):
        raise ObfuscationError('pyobfus did not process every python file')
    for script in obfuscated_files:
        relative = script.relative_to(obfuscated_dir)
        source_code = script.read_text(encoding='utf-8', errors='replace')
        try:
            compile(source_code, str(relative), 'exec')
        except SyntaxError as error:
            raise ObfuscationError(f'{relative} is not valid python after obfuscation: {error}')
        # the shipped code must not carry any documentation either
        if _has_comments(source_code):
            raise ObfuscationError(f'{relative} still contains comments after obfuscation')
        if _has_docstrings(source_code):
            raise ObfuscationError(f'{relative} still contains docstrings after obfuscation')
        # the obfuscator re-adds blank lines; drop them again so the shipped
        # module stays as compact as possible
        compacted = _compact(source_code)
        if compacted != source_code:
            compile(compacted, str(relative), 'exec')
        (project_dir / relative).write_text(compacted, encoding='utf-8')

    # callbacks the engine calls by name still have to exist
    staged_callbacks = _collect_callback_names(project_dir)
    missing = sorted(callbacks - staged_callbacks)
    if missing:
        raise ObfuscationError(f'callbacks were renamed by the obfuscator: {", ".join(missing)}')

    return {'files': len(python_files), 'callbacks': len(callbacks)}


def prepare(project_path, output_dir) -> dict:
    """Prepare the project for a protected build.

    The project is copied into the staging folder of the build, that copy loses
    every comment and docstring, is obfuscated when pyobfus is installed and
    finally has its assets encrypted. The project itself is never modified.

    :return: a dictionary with the staged project (entry script and data) and
             one summary per step (obfuscation is None without pyobfus).
    """
    output_dir = Path(output_dir)
    work_dir = output_dir / '_protected'
    project_dir = work_dir / 'project'
    stage_summary = stage_project(project_path, project_dir, output_dir)
    strip_summary = strip_code(project_dir)
    obfuscation_summary = None
    if find_obfuscator() is not None:
        obfuscation_summary = obfuscate(project_dir, work_dir)
    asset_summary = asset_protection.prepare(project_dir)
    return {
        'project_dir': project_dir,
        'entry_script': project_dir / 'main.py',
        'stage_summary': stage_summary,
        'strip_summary': strip_summary,
        'obfuscation_summary': obfuscation_summary,
        'asset_summary': asset_summary,
    }
