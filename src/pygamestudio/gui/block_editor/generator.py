"""
Workspace -> Python code generation (one-way: blocks are the source of truth).

Generated code lives between ``# === pygs-generated ===`` markers inside the
script file; everything outside those markers is preserved untouched, so users
can keep hand-written helpers in the same class.
"""

import re

from pygamestudio.gui.block_editor.registry import event_callback, get_definition, options_for

INDENT = '    '
_FIELD_PATTERN = re.compile(r'\{(\w+)\}')

# Left in the generated region when a callback is implemented by hand in the
# same file (see storage.save_workspace).
SKIP_NOTE = ('# [blocks] 已跳过 {callback}：文件里有同名手写方法，积木不会覆盖它 / '
             'skipped: a hand-written {callback} wins '
             '(delete it and save to let the blocks generate it again)')


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
        lines.extend(_emit_hat(stack, definition))
    return '\n'.join(lines)


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
    return _emit_block(block, '')


def generated_callbacks(workspace):
    """The callback names a workspace generates (event stacks only)."""
    names = []
    for stack in hat_stacks(workspace):
        callback, _ = event_callback(stack)
        if callback:
            names.append(callback)
    return names


def _emit_hat(block, definition):
    callback, params = event_callback(block)
    if not callback:
        return [INDENT + '# event block without a selected event']
    header = 'def {}(self{}):'.format(callback, ', ' + params if params else '')
    lines = [INDENT + header]
    body = block.get('body') or []
    body_lines = _emit_stack(body, INDENT + INDENT) if body else []
    lines.extend(body_lines if body_lines else [INDENT + INDENT + 'pass'])
    return lines


def _emit_stack(blocks, indent):
    lines = []
    for block in blocks:
        lines.extend(_emit_block(block, indent))
    return lines


def _emit_block(block, indent):
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
        if stripped in ('{body}', '{else_block}'):
            key = 'body' if stripped == '{body}' else 'else'
            children = block.get(key) or []
            children_lines = _emit_stack(children, indent + INDENT) if children else []
            lines.extend(children_lines if children_lines else [indent + INDENT + 'pass'])
            continue
        text = _fill_template(raw_line, block, definition)
        lines.append(indent + text if text else '')
    return lines


def _fill_template(template, block, definition):
    def replace(match):
        return _field_code(definition, match.group(1), (block.get('fields') or {}).get(match.group(1)))
    return _FIELD_PATTERN.sub(replace, template)


def _field_code(definition, name, value):
    spec = next((field for field in definition.get('fields', []) if field['name'] == name), None)
    kind = spec['kind'] if spec else 'text'
    if value is None or value == '':
        value = spec['default'] if spec else ''
    if kind == 'number':
        return _format_number(value)
    if kind in ('property', 'expr', 'operator', 'key', 'toggle', 'event'):
        # dropdown kinds store the code expression itself; an unknown value
        # (e.g. from an older file) falls back to the first option
        options = options_for(kind)
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
