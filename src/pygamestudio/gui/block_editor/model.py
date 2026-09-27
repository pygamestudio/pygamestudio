"""
Block workspace model for the block (visual) script editor.

A workspace is plain JSON-able data:

    {"version": 1, "stacks": [block, ...]}

Every block is a dict:

    {"id": "a1b2c3d4", "type": "event_clicked", "fields": {...},
     "body": [block, ...], "else": [block, ...]}

``body``/``else`` are nested lists (no linked lists), which keeps inserting,
removing and re-serializing trivial. ``x``/``y`` are only stored on top-level
stacks so the editor remembers where the user parked them.
"""

import keyword
import math
import uuid

WORKSPACE_VERSION = 1

_SKIP_IDS = ('body', 'elif', 'else')


def new_workspace():
    """An empty workspace."""
    return {'version': WORKSPACE_VERSION, 'stacks': [], 'variables': []}


def new_block(block_type, fields=None):
    """A fresh statement/hat block (no position, meant to live in a body)."""
    block = {'id': uuid.uuid4().hex[:8], 'type': block_type, 'fields': dict(fields or {})}
    return normalize_block(block)


def normalize_block(block):
    """Make sure the statement lists declared by the definition exist.

    The canvas lays out a body slot only when the key exists, so every hat /
    C-block must own its ``body`` (and ``else``) list, even when empty. Scripts
    saved while the single “event” block with its dropdown existed are split
    back into one block per event (``event_start``, ``event_clicked``, ...).
    """
    from pygamestudio.gui.block_editor.registry import LEGACY_BLOCK_TYPES, get_definition
    if block.get('type') == 'event':
        callback = (block.get('fields') or {}).pop('event', None)
        if callback:
            block['type'] = 'event_' + callback[3:]
    migrate = LEGACY_BLOCK_TYPES.get(block.get('type'))
    if migrate is not None:
        new_type, field_map = migrate
        fields = block.setdefault('fields', {})
        for old_name, new_name in field_map.items():
            if old_name in fields and new_name not in fields:
                fields[new_name] = fields.pop(old_name)
        block['type'] = new_type
    definition = get_definition(block.get('type'))
    if definition is not None:
        for key in definition.get('slots', ()):
            block.setdefault(key, [])
    return block


def normalize_workspace(workspace):
    """Normalize every block of a workspace (used on load and on rebuild)."""
    migrate_chain_blocks(workspace)
    for stack in workspace.get('stacks', []):
        for block in walk([stack]):
            normalize_block(block)
    normalize_variables(workspace)
    return workspace


# ------------------------------------------------------------ legacy blocks

def migrate_chain_blocks(workspace):
    """Split the removed combined if blocks into stand-alone chain pieces.

    “If / else” and “If / elif / else” used to be single blocks; scripts saved
    with them get the “If” / “else if” / “else” pieces back in the same
    statement list, in the same order, so the generated code is unchanged.
    """
    def walk_list(blocks):
        index = 0
        while index < len(blocks):
            block = blocks[index]
            for _key, children in block_children(block):
                walk_list(children)
            pieces = _split_chain_block(block)
            if pieces is None:
                index += 1
                continue
            blocks[index:index + 1] = pieces
            index += len(pieces)

    walk_list(workspace.get('stacks', []))
    return workspace


def _split_chain_block(block):
    """One old combined if block -> [if, (elif,) else] pieces, or None."""
    block_type = block.get('type')
    if block_type not in ('control_if_else', 'control_if_elif'):
        return None
    fields = block.get('fields') or {}
    head = {'id': block.get('id') or uuid.uuid4().hex[:8], 'type': 'control_if',
            'fields': {key: fields[key] for key in ('property', 'operator', 'value')
                       if key in fields},
            'body': block.get('body') or []}
    if 'x' in block:
        head['x'] = block['x']
    if 'y' in block:
        head['y'] = block['y']
    pieces = [head]
    if block_type == 'control_if_elif':
        elif_fields = {}
        for old_name, new_name in (('property2', 'property'), ('operator2', 'operator'),
                                   ('value2', 'value')):
            if old_name in fields:
                elif_fields[new_name] = fields[old_name]
        pieces.append({'id': uuid.uuid4().hex[:8], 'type': 'control_elif',
                       'fields': elif_fields, 'body': block.get('elif') or []})
    pieces.append({'id': uuid.uuid4().hex[:8], 'type': 'control_else',
                   'fields': {}, 'body': block.get('else') or []})
    # a loose (top-level) combined block hands a stacked position to its pieces
    for offset, piece in enumerate(pieces[1:], start=1):
        if 'x' in block:
            piece['x'] = block['x']
        if 'y' in block:
            piece['y'] = int(block['y']) + 120 * offset
    return pieces


# ---------------------------------------------------------------- variables
# The variables of a workspace are instance attributes of the script: every
# entry generates one ``self.<name> = <value>`` line in ``__init__`` (see
# ``storage._sync_variables``). They are offered wherever a block reads or
# writes a property (see ``registry.options_for``).


def reserved_variable_names():
    """Names a variable must not take: they would shadow engine members.

    Every event callback is a method of ``ObjectScript`` (``self.on_update``
    would hide it), ``obj`` is the object the engine hands to the script and
    ``self`` plus the dunders are Python internals.
    """
    from pygamestudio.gui.block_editor.registry import EVENT_BLOCKS
    names = {'obj', 'self'}
    names.update(callback for callback, _key, _label, _params, _objects in EVENT_BLOCKS)
    return frozenset(names)


def variable_name_error(name):
    """The i18n key of why ``name`` cannot be a variable, or '' when it can."""
    text = str(name or '').strip()
    if not text or not text.isidentifier() or keyword.iskeyword(text) or text.startswith('__'):
        return 'block.var.err_identifier'
    if text in reserved_variable_names():
        return 'block.var.err_reserved'
    return ''


def new_variable(name, value='0', value_type='number'):
    """A fresh variable entry (``self.<name> = <value>`` in the script)."""
    value_type = value_type if value_type in VARIABLE_TYPES else 'number'
    return {'id': uuid.uuid4().hex[:8], 'name': str(name).strip(),
            'value': normalize_variable_value(value, value_type), 'type': value_type}


VARIABLE_TYPES = ('number', 'text', 'bool')


def infer_variable_type(value):
    """The type a raw value looks like (used for older entries without one)."""
    text = str(value if value is not None else '').strip()
    try:
        number = float(text)
    except (TypeError, ValueError):
        number = None
    if number is not None and math.isfinite(number):
        return 'number'
    return 'bool' if text in ('True', 'False') else 'text'


def variable_type(variable):
    """The stored type of a variable entry (inferred when it has none)."""
    value_type = str((variable or {}).get('type') or '')
    if value_type in VARIABLE_TYPES:
        return value_type
    return infer_variable_type((variable or {}).get('value'))


def normalize_variable_value(value, value_type):
    """The stored text of a value, normalized for its type."""
    text = str(value if value is not None else '').strip()
    if value_type == 'bool':
        return 'False' if text in ('', '0', 'False') else 'True'
    if value_type == 'number':
        try:
            number = float(text)
        except (TypeError, ValueError):
            return '0'
        return text if math.isfinite(number) else '0'
    return text


def normalize_variables(workspace):
    """Drop variable entries that would generate broken code (bad / duplicate names)."""
    cleaned = []
    taken = set()
    for item in workspace.get('variables') or ():
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '').strip()
        if variable_name_error(name) or name in taken:
            continue
        taken.add(name)
        value_type = variable_type(item)
        cleaned.append({'id': str(item.get('id') or uuid.uuid4().hex[:8]), 'name': name,
                        'value': normalize_variable_value(item.get('value'), value_type),
                        'type': value_type})
    workspace['variables'] = cleaned
    return cleaned


def find_variable(workspace, variable_id):
    """The variable entry with the given id, or None."""
    return next((item for item in workspace.get('variables') or ()
                 if str(item.get('id')) == str(variable_id)), None)


def rewrite_variable_references(workspace, variable_name, new_code):
    """Point every block field that reads ``self.<variable_name>`` at new_code.

    Used by renames (to ``self.<new name>``) and deletions (back to the
    default property, so the canvas and the generated code agree again).
    """
    old_code = 'self.{}'.format(variable_name)
    for stack in workspace.get('stacks', []):
        for block in walk([stack]):
            fields = block.get('fields')
            if not isinstance(fields, dict):
                continue
            for field_name, value in list(fields.items()):
                if value == old_code:
                    fields[field_name] = new_code


def new_stack(block_type, x=40, y=40, fields=None):
    """A top-level stack block carrying its canvas position."""
    block = new_block(block_type, fields)
    block['x'] = int(x)
    block['y'] = int(y)
    return block


def block_children(block):
    """The statement lists of a block as (key, list) pairs, in order."""
    children = []
    for key in _SKIP_IDS:
        value = block.get(key)
        if isinstance(value, list):
            children.append((key, value))
    return children


def walk(blocks):
    """Yield every block of a stack list, parents before children."""
    for block in blocks:
        yield block
        for _, children in block_children(block):
            yield from walk(children)


def find_block(stacks, block_id):
    """Return (parent_list, index, block) for an id, or (None, -1, None)."""
    for index, block in enumerate(stacks):
        if block.get('id') == block_id:
            return stacks, index, block
        for _, children in block_children(block):
            parent_list, child_index, found = find_block(children, block_id)
            if found is not None:
                return parent_list, child_index, found
    return None, -1, None


def clone_block(block):
    """Deep-copy a block, giving every block inside a fresh id."""
    cloned = {key: value for key, value in block.items() if key not in _SKIP_IDS}
    cloned['id'] = uuid.uuid4().hex[:8]
    cloned['fields'] = dict(block.get('fields') or {})
    for key, children in block_children(block):
        cloned[key] = [clone_block(child) for child in children]
    return cloned


def clone_stack(block, x=None, y=None):
    """Deep-copy a top-level stack, optionally moving it somewhere else."""
    cloned = clone_block(block)
    if x is not None:
        cloned['x'] = int(x)
    if y is not None:
        cloned['y'] = int(y)
    return cloned


def is_descendant(block, block_id):
    """True when block_id is the block itself or lives anywhere inside it."""
    if block.get('id') == block_id:
        return True
    for _, children in block_children(block):
        if any(is_descendant(child, block_id) for child in children):
            return True
    return False


def remove_segment(stacks, block_id):
    """Detach the segment starting at block_id. Returns (block, parent_list, index)."""
    parent_list, index, block = find_block(stacks, block_id)
    if block is None:
        return None, None, -1
    del parent_list[index]
    return block, parent_list, index


def insert_block(block, target_list, index):
    """Insert a block into a statement list at the given index."""
    index = max(0, min(int(index), len(target_list)))
    target_list.insert(index, block)
    return block


def loose_stacks(workspace):
    """Top-level stacks that no event ever runs (no event block on top)."""
    from pygamestudio.gui.block_editor.registry import get_definition
    result = []
    for stack in workspace.get('stacks', []):
        definition = get_definition(stack.get('type'))
        if definition is None or definition['shape'] != 'hat':
            result.append(stack)
    return result
