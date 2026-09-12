"""
Reading / writing block scripts.

A block script is a single ``.py`` file:

    import pygamestudio as studio


    class ObjectScript:
        def __init__(self, obj):
            self.obj = obj

        # === pygs-blocks: {"version":1,"stacks":[...]} ===
        # === pygs-generated ===
        def on_clicked(self):
            ...
        # === /pygs-generated ===

        # hand-written area (kept as-is by the block editor)

Everything above the blocks marker and below the generated-end marker
survives round-trips untouched.
"""

import ast
import json
import re
from pathlib import Path

from pygamestudio.gui.block_editor.generator import generate_workspace, generated_callbacks
from pygamestudio.gui.block_editor.model import (WORKSPACE_VERSION, new_workspace,
                                                 normalize_workspace)

BLOCKS_MARKER = '# === pygs-blocks:'
GENERATED_START = '# === pygs-generated ==='
GENERATED_END = '# === /pygs-generated ==='

DEFAULT_HEAD = '''import pygamestudio as studio


class ObjectScript:
    def __init__(self, obj):
        self.obj = obj

'''

DEFAULT_TAIL = '''
    # === 以下为手写区域，积木编辑器不会改动 ===
    # === hand-written area below, the block editor never touches it ===
'''

_BLOCKS_PATTERN = re.compile(re.escape(BLOCKS_MARKER) + r'\s*(\{.*\})\s*===')
_CLASS_PATTERN = re.compile(r'^([ \t]*)class[ \t]+ObjectScript\b.*:[ \t]*$', re.MULTILINE)
_INDENT_PATTERN = re.compile(r'^([ \t]+)\S')
_NOTE_LINE = ('# [blocks] 与积木生成的回调重名，已自动停用 / disabled: collides with a generated callback '
              '(remove the "# " prefix to restore)\n')


def is_block_script(path):
    """True when the file exists and embeds a blocks marker."""
    try:
        text = Path(path).read_text(encoding='utf-8', errors='ignore')
    except OSError:
        return False
    return BLOCKS_MARKER in text


def load_workspace(path):
    """Read the embedded workspace of a block script.

    Raises ValueError when the file has no (or corrupted) block data.
    """
    text = Path(path).read_text(encoding='utf-8')
    match = _BLOCKS_PATTERN.search(text)
    if match is None:
        raise ValueError('not a block script: {}'.format(path))
    try:
        workspace = json.loads(match.group(1))
    except ValueError as error:
        raise ValueError('corrupted block data: {}'.format(error))
    if not isinstance(workspace, dict) or not isinstance(workspace.get('stacks'), list):
        raise ValueError('corrupted block data: {}'.format(path))
    workspace.setdefault('version', WORKSPACE_VERSION)
    return normalize_workspace(workspace)


def create_script(path, workspace=None):
    """Create a fresh block script (hand-written head/tail included)."""
    workspace = workspace if workspace is not None else new_workspace()
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(compose(workspace, DEFAULT_HEAD, DEFAULT_TAIL), encoding='utf-8')
    return file_path


def can_hold_blocks(path):
    """(ok, error_key) - may the block editor attach blocks to this file?

    Nothing is written here: the blocks section is only injected when the user
    really saves blocks (see ``save_workspace``), so merely LOOKING at a
    script in the block editor never touches the developer's file.
    """
    file_path = Path(path)
    if not file_path.exists():
        return True, ''
    try:
        text = file_path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return False, 'block.convert_read_failed'
    if BLOCKS_MARKER in text or not text.strip():
        return True, ''
    if _CLASS_PATTERN.search(text) is None:
        return False, 'block.convert_no_class'
    return True, ''


def ensure_block_script(path, workspace=None):
    """Make sure the file can hold blocks. Returns (ok, error_key).

    There is no separate "block script" file type: any ordinary object script
    can be opened in the block editor. The markers are inserted right below the
    ``class ObjectScript:`` line (methods may appear in any order, so the file
    stays valid Python); every other line is preserved as-is - including the
    object template's own on_start/on_update/on_destroy stubs, which are NEVER
    dropped (hand-written code wins, see ``save_workspace``). Only a missing or
    empty file is created from the template (there is nothing to lose there).
    """
    file_path = Path(path)
    ok, error = can_hold_blocks(file_path)
    if not ok:
        return False, error
    if not file_path.exists():
        create_script(file_path, workspace)
        return True, ''
    text = file_path.read_text(encoding='utf-8')
    if BLOCKS_MARKER in text:
        return True, ''
    if not text.strip():
        create_script(file_path, workspace)
        return True, ''
    match = _CLASS_PATTERN.search(text)
    if match is None:
        return False, 'block.convert_no_class'
    class_indent = match.group(1)
    line_end = text.find('\n', match.end())
    if line_end < 0:
        line_end = len(text)
    # Reuse the indentation of the first real line of the class body so files
    # with tabs or a different indent width survive the round-trip.
    body_indent = None
    for line in text[line_end:].splitlines():
        if line.strip():
            stripped = _INDENT_PATTERN.match(line)
            body_indent = stripped.group(1) if stripped else class_indent + '    '
            break
    indent = body_indent if body_indent else class_indent + '    '
    payload = json.dumps(workspace if workspace is not None else new_workspace(),
                         ensure_ascii=False, separators=(',', ':'))
    injected = ''.join([
        '\n',
        indent, BLOCKS_MARKER, ' ', payload, ' ===\n',
        indent, GENERATED_START, '\n',
        indent, GENERATED_END, '\n',
        '\n',
    ])
    file_path.write_text(text[:line_end + 1] + injected + text[line_end + 1:], encoding='utf-8')
    return True, ''


def save_workspace(path, workspace):
    """Write the workspace back, keeping the existing head/tail of the file.

    A hand-written method is NEVER destroyed or disabled:
      * a method with REAL code wins - its callback is skipped in the
        generated region with a short note, so the developer's implementation
        keeps running;
      * an EMPTY stub (the object template ships docstring + pass) is taken
        over and commented out with a note (otherwise it would silently shadow
        the generated callback), and removing the "# " prefix restores it.

    A plain script that has no blocks in the workspace is left completely
    untouched - the blocks section is only injected once there is something to
    store, so opening a script in the block editor never modifies it by itself.
    """
    file_path = Path(path)
    if not file_path.exists():
        create_script(file_path, workspace)
        return file_path
    if not is_block_script(file_path):
        if not workspace.get('stacks'):
            # nothing to record: never inject markers into an untouched script
            return file_path
        if not ensure_block_script(file_path, workspace)[0]:
            # the file cannot hold blocks (no ObjectScript class): it must not
            # be overwritten with the template either
            return file_path
    head, tail = read_surroundings(path)
    callbacks = generated_callbacks(workspace)
    hand_written = _hand_written_definitions(head)
    hand_written.update(_hand_written_definitions(tail))
    empty = [name for name in callbacks if hand_written.get(name)]
    by_hand = [name for name in callbacks if name in hand_written and not hand_written[name]]
    head = _disable_duplicate_definitions(head, empty)
    tail = _disable_duplicate_definitions(tail, empty)
    file_path = Path(path)
    file_path.write_text(compose(workspace, head, tail, skip=by_hand), encoding='utf-8')
    return file_path


def _hand_written_definitions(text):
    """{method name: is_empty_body} of every method a text region defines.

    A method with only ``pass`` / ``...`` / a docstring is an unused stub:
    the block editor may take it over. Anything else is real developer code.
    Returns {} when the region cannot be parsed.
    """
    if not text:
        return {}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        try:
            tree = ast.parse('class _BlockFragment:\n' + text)
        except SyntaxError:
            return {}
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[node.name] = _is_empty_body(node.body)
    return result


def _is_empty_body(body):
    """True when a function body only contains pass / ... / docstring / return."""
    for statement in body:
        if isinstance(statement, ast.Pass):
            continue
        if isinstance(statement, ast.Return) and statement.value is None:
            continue
        if (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant)
                and (statement.value.value is Ellipsis or isinstance(statement.value.value, str))):
            continue
        return False
    return True


def _disable_duplicate_definitions(text, callbacks):
    """Comment out EMPTY hand-written methods that collide with callbacks.

    A method that only holds ``pass``/``...``/a docstring has nothing to lose
    (the object script template ships such stubs) and would otherwise shadow
    the generated callback, because Python keeps the LAST definition and the
    generated region sits above the hand-written area. The stub is commented
    out - never deleted - so nothing is lost and it can be restored by hand.
    Methods with real code are NOT touched here (they win, see save_workspace).

    Returns the text unchanged when the region cannot be parsed.
    """
    if not text or not callbacks:
        return text
    wrapped = False
    try:
        tree = ast.parse(text)
    except SyntaxError:
        try:
            tree = ast.parse('class _BlockFragment:\n' + text)
            wrapped = True
        except SyntaxError:
            return text
    offset = 1 if wrapped else 0
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in callbacks:
            ranges.append((node.lineno - offset, node.end_lineno - offset))
    if not ranges:
        return text
    lines = text.splitlines(keepends=True)
    for start, end in sorted(ranges, reverse=True):
        if start < 1 or end > len(lines) or start > end:
            continue
        block = lines[start - 1:end]
        indent = block[0][:len(block[0]) - len(block[0].lstrip())]
        commented = []
        for line in block:
            if not line.strip():
                commented.append(line)
            elif line.startswith(indent):
                commented.append(indent + '# ' + line[len(indent):])
            else:
                commented.append('# ' + line)
        lines[start - 1:end] = [indent + _NOTE_LINE] + commented
    return ''.join(lines)


def read_surroundings(path):
    """Return (head, tail) of an existing script, defaulting to the templates."""
    head, tail = DEFAULT_HEAD, DEFAULT_TAIL
    file_path = Path(path)
    if not file_path.exists():
        return head, tail
    lines = file_path.read_text(encoding='utf-8').splitlines(keepends=True)
    marker_index = next((index for index, line in enumerate(lines) if BLOCKS_MARKER in line), None)
    end_index = next((index for index, line in enumerate(lines) if GENERATED_END in line), None)
    if marker_index is not None:
        head = ''.join(lines[:marker_index])
    if end_index is not None and (marker_index is None or end_index > marker_index):
        tail = ''.join(lines[end_index + 1:])
    return head, tail


def compose(workspace, head, tail, skip=()):
    """Assemble the full file text for a workspace.

    ``skip`` lists callbacks that the file implements by hand; they are not
    generated (see ``save_workspace``).
    """
    if head and not head.endswith('\n'):
        head += '\n'
    payload = json.dumps(workspace, ensure_ascii=False, separators=(',', ':'))
    parts = [
        head,
        '{} {} ===\n'.format('    ' + BLOCKS_MARKER, payload),
        '    {}\n'.format(GENERATED_START),
    ]
    generated = generate_workspace(workspace, skip=skip)
    if generated:
        parts.append(generated + '\n')
    parts.append('    {}\n'.format(GENERATED_END))
    if tail and not tail.startswith('\n'):
        parts.append('\n')
    parts.append(tail)
    return ''.join(parts)
