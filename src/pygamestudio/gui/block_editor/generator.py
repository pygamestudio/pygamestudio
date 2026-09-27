"""
Workspace -> Python code generation (one-way: blocks are the source of truth).

Generated code lives between ``# === pygs-generated ===`` markers inside the
script file; everything outside those markers is preserved untouched, so users
can keep hand-written helpers in the same class.
"""

import math
import re

from pygamestudio.gui.block_editor.registry import (event_callback, get_definition, label_text,
                                                    options_for)

INDENT = '    '
_FIELD_PATTERN = re.compile(r'\{(\w+)\}')

# the statement-list placeholders of a block template -> statement list key
_SLOT_PLACEHOLDERS = {'{body}': 'body', '{elif_block}': 'elif', '{else_block}': 'else'}

# Left in the generated region when a callback is implemented by hand in the
# same file (see storage.save_workspace).
SKIP_NOTE = ('# [blocks] 已跳过 {callback}：文件里有同名手写方法，积木不会覆盖它 / '
             'skipped: a hand-written {callback} wins '
             '(delete it and save to let the blocks generate it again)')

# Left in the generated region when an “else if” / “else” piece has no “If”
# right before it in the same statement list (it cannot become Python code).
ORPHAN_BRANCH_NOTE = ('# [blocks] 已跳过分支积木“{}”：它前面没有“如果” / '
                      'skipped: this branch block needs an “If” right before it')


def generate_workspace(workspace, skip=()):
    """Generate the code (class-level, 4-space indented) of every event stack.

    Event blocks are independent callbacks: they land at class level even when
    the user snapped one inside another stack (hoisted). Stacks without any
    event block are ignored - nothing would ever call them. ``skip`` names the
    callbacks that the file implements by hand: they are replaced by a short
    note instead of generated code, so the hand-written method stays in
    charge.
    """
    lines = []
    variables = list(workspace.get('variables') or [])
    if '__init__' not in skip:
        # The variables of the workspace are instance attributes; a generated
        # __init__ appears only when the file does not define one by hand
        # (storage injects the lines into the hand-written __init__ instead).
        lines.extend(_emit_variables(variables))
    for stack in hat_stacks(workspace):
        definition = get_definition(stack.get('type'))
        callback, _ = event_callback(stack)
        if callback and callback in skip:
            if lines:
                lines.append('')
            lines.append(INDENT + SKIP_NOTE.format(callback=callback))
            continue
        if lines:
            lines.append('')
        lines.extend(_emit_hat(stack, definition, variables))
    return '\n'.join(lines)


def value_code(value, value_type=None):
    """The Python code of a variable's initial value (per its type).

    ``value_type`` is the type picked in the variables tab; entries that have
    none keep the number-or-text guessing of the first version.
    """
    text = str(value if value is not None else '').strip()
    if value_type == 'text':
        return repr(text)
    if value_type == 'bool':
        return 'False' if text in ('', '0', 'False') else 'True'
    text = text or '0'
    try:
        number = float(text)
    except (TypeError, ValueError):
        number = None
    if number is not None and math.isfinite(number):
        return _format_number(number)
    if text in ('True', 'False', 'None'):
        return text
    return repr(text)


def _emit_variables(variables):
    """The ``__init__`` of a script that has custom variables (when needed)."""
    from pygamestudio.gui.block_editor.model import variable_name_error, variable_type
    usable = []
    for variable in variables:
        name = str(variable.get('name') or '').strip() if isinstance(variable, dict) else ''
        if name and not variable_name_error(name):
            usable.append((name, value_code(variable.get('value'), variable_type(variable))))
    if not usable:
        return []
    lines = [INDENT + 'def __init__(self, obj):',
             INDENT + INDENT + 'self.obj = obj']
    for name, code in usable:
        lines.append('{}{}self.{} = {}'.format(INDENT, INDENT, name, code))
    return lines


def hat_stacks(workspace):
    """Every event stack of a workspace, nested ones included (parents first)."""
    from pygamestudio.gui.block_editor.model import block_children
    result = []

    def walk(blocks):
        for block in blocks:
            definition = get_definition(block.get('type'))
            if definition is not None and definition['shape'] == 'hat':
                result.append(block)
            for _, children in block_children(block):
                walk(children)

    walk(workspace.get('stacks', []))
    return result


def generate_block(block):
    """Generate the code lines of a single block (used by tests / previews)."""
    return _emit_block(block, '', ())


def generated_callbacks(workspace):
    """The callback names a workspace generates (event stacks only)."""
    names = []
    for stack in hat_stacks(workspace):
        callback, _ = event_callback(stack)
        if callback:
            names.append(callback)
    return names


def _emit_hat(block, definition, variables=()):
    callback, params = event_callback(block)
    if not callback:
        return [INDENT + '# event block without a selected event']
    header = 'def {}(self{}):'.format(callback, ', ' + params if params else '')
    lines = [INDENT + header]
    body = block.get('body') or []
    body_lines = _emit_stack(body, INDENT + INDENT, variables) if body else []
    lines.extend(body_lines if body_lines else [INDENT + INDENT + 'pass'])
    return lines


def _emit_stack(blocks, indent, variables=()):
    """Emit one statement list; an “If” absorbs the branch pieces after it.

    “else if” / “else” are stand-alone blocks on the canvas; when they
    follow an “If” directly (same statement list) they are emitted together
    with it as one real if / elif / else chain.
    """
    lines = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        definition = get_definition(block.get('type'))
        branch = definition.get('branch') if definition else None
        if branch == 'if':
            index += 1
            followers = []
            while index < len(blocks):
                follower_definition = get_definition(blocks[index].get('type'))
                follower_branch = (follower_definition.get('branch')
                                   if follower_definition else None)
                if follower_branch not in ('elif', 'else'):
                    break
                followers.append(blocks[index])
                index += 1
                if follower_branch == 'else':
                    break
            lines.extend(_emit_branch_chain(block, definition, followers, indent, variables))
            continue
        if branch in ('elif', 'else'):
            # no “If” right before it: the piece cannot become Python code
            lines.append(indent + ORPHAN_BRANCH_NOTE.format(label_text(definition)))
            lines.append(indent + 'pass')
            index += 1
            continue
        lines.extend(_emit_block(block, indent, variables))
        index += 1
    return lines


def _emit_branch_chain(head, head_definition, followers, indent, variables):
    """The Python of an “If” plus the “else if” / “else” pieces after it."""
    lines = []
    for piece in [head] + followers:
        definition = get_definition(piece.get('type'))
        branch = definition.get('branch') if definition else 'if'
        fields = piece.get('fields') or {}
        if branch == 'else':
            lines.append(indent + 'else:')
        else:
            keyword = 'if' if branch == 'if' else 'elif'
            condition = '{} {} {}'.format(
                _field_code(definition, 'property', fields.get('property'), variables),
                _field_code(definition, 'operator', fields.get('operator'), variables),
                _field_code(definition, 'value', fields.get('value'), variables))
            lines.append('{}{} {}:'.format(indent, keyword, condition))
        children = piece.get('body') or []
        body_lines = _emit_stack(children, indent + INDENT, variables) if children else []
        lines.extend(body_lines if body_lines else [indent + INDENT + 'pass'])
    return lines


def _emit_block(block, indent, variables=()):
    definition = get_definition(block.get('type'))
    if definition is None:
        return [indent + '# unknown block: {}'.format(block.get('type'))]
    if definition['shape'] == 'hat':
        # event blocks are hoisted to class level (see hat_stacks)
        return []
    if not definition['code']:
        return [indent + '# empty block: {}'.format(block.get('type'))]
    lines = []
    for raw_line in definition['code'].split('\n'):
        stripped = raw_line.strip()
        key = _SLOT_PLACEHOLDERS.get(stripped)
        if key is not None:
            children = block.get(key) or []
            children_lines = _emit_stack(children, indent + INDENT, variables) if children else []
            lines.extend(children_lines if children_lines else [indent + INDENT + 'pass'])
            continue
        text = _fill_template(raw_line, block, definition, variables)
        lines.append(indent + text if text else '')
    return lines


def _fill_template(template, block, definition, variables=()):
    def replace(match):
        return _field_code(definition, match.group(1),
                           (block.get('fields') or {}).get(match.group(1)), variables)
    return _FIELD_PATTERN.sub(replace, template)


def _field_code(definition, name, value, variables=()):
    spec = next((field for field in definition.get('fields', []) if field['name'] == name), None)
    kind = spec['kind'] if spec else 'text'
    if value is None or value == '':
        value = spec['default'] if spec else ''
    if kind == 'number':
        return _format_number(value)
    if kind == 'amount':
        # a number, or one of the script's number variables
        codes = [option[0] for option in options_for('amount', variables)]
        text = str(value).strip()
        return text if text in codes else _format_number(value)
    if kind in ('property', 'expr', 'operator', 'key', 'toggle', 'event'):
        # dropdown kinds store the code expression itself; an unknown value
        # (e.g. from an older file) falls back to the first option
        options = options_for(kind, variables)
        codes = [option[0] for option in options]
        return value if value in codes else (codes[0] if codes else repr(str(value)))
    if kind == 'value':
        # "number-or-text": bare number when possible, else a string literal.
        text = str(value).strip()
        try:
            return _format_number(float(text))
        except (TypeError, ValueError):
            return repr(text)
    return repr(str(value))


def _format_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return '0'
    if number.is_integer():
        return str(int(number))
    return '{:g}'.format(number)
