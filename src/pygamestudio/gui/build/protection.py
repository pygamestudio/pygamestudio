"""Code protection for game builds (stripping + asset encryption).

A protected build never packages the project folder itself: it copies it into a
staging folder and rewrites that copy.

1. every comment, docstring and any other formatting is removed (``strip_code``)
   and the modules are minified, so no documentation is left;
2. the assets (images, audio, fonts, scenes, project.pygs) and the project's own
   python modules are encrypted by ``gui/build/assets.py``; the per-build key
   ships with the game.

PyInstaller then packages the staging copy, so the shipped game carries no
readable documentation and no plain resource.

Name obfuscation (pyobfus) used to run between the two steps. It is gone on
purpose: renaming the game's own symbols adds no real protection on top of the
encryption (the modules are unreadable anyway) and it broke third party SDKs
that look symbols up at runtime, so builds failed or crashed.
"""
import ast
import io
import shutil
import tokenize
from pathlib import Path

from pygamestudio.gui.build import assets as asset_protection

#: Never part of a build (caches, virtual envs, build outputs).
IGNORED_DIR_NAMES = {'__pycache__', 'node_modules', 'venv', 'env', 'dist', 'build'}


class ProtectionError(Exception):
    """Raised when the project cannot be prepared for a protected build."""


class StagingError(ProtectionError):
    """Raised when the project cannot be copied into the staging folder."""


class StripError(ProtectionError):
    """Raised when the project code cannot be stripped of its documentation."""


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
            raise StripError(f'{script.name} cannot be stripped: {error}') from error
        script.write_text(stripped, encoding='utf-8')
        files += 1
    return {'files': files}


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


def prepare(project_path, output_dir) -> dict:
    """Prepare the project for a protected build.

    The project is copied into the staging folder of the build, that copy loses
    every comment and docstring and finally has its assets and modules
    encrypted. The project itself is never modified.

    :return: a dictionary with the staged project (entry script and data) and a
             summary per step.
    """
    output_dir = Path(output_dir)
    work_dir = output_dir / '_protected'
    project_dir = work_dir / 'project'
    stage_summary = stage_project(project_path, project_dir, output_dir)
    strip_summary = strip_code(project_dir)
    asset_summary = asset_protection.prepare(project_dir)
    return {
        'project_dir': project_dir,
        'entry_script': project_dir / 'main.py',
        'stage_summary': stage_summary,
        'strip_summary': strip_summary,
        'asset_summary': asset_summary,
    }
