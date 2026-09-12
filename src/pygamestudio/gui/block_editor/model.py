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

import uuid

WORKSPACE_VERSION = 1

_SKIP_IDS = ('body', 'else')


def new_workspace():
    """An empty workspace."""
    return {'version': WORKSPACE_VERSION, 'stacks': []}


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
        if definition['has_body']:
            block.setdefault('body', [])
        if definition['has_else']:
            block.setdefault('else', [])
    return block


def normalize_workspace(workspace):
    """Normalize every block of a workspace (used on load and on rebuild)."""
    for stack in workspace.get('stacks', []):
        for block in walk([stack]):
            normalize_block(block)
    return workspace


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
