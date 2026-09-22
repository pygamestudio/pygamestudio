"""Object tools: read, create, update, delete, duplicate, move, select."""

import uuid as uuid_module

from pygamestudio.mcp.registry import ToolError, tool
from pygamestudio.mcp.tools.context import (
    begin_macro, canvas_object, end_macro, fit_object_size, iter_objects,
    json_value, manager, object_details, object_path, object_summary,
    object_type_names, parent_of, property_changes, push_property,
    resolve_object,
)


@tool(
    'get_object',
    'Every property of one object (what the inspector shows), by uuid, '
    'hierarchy path ("Canvas/Player") or unique name. Without an argument the '
    'object selected in the editor is used.',
    {
        'type': 'object',
        'properties': {
            'ref': {'type': 'string', 'description': 'Uuid, path or name of the object.'},
            'include_children': {'type': 'boolean', 'default': False,
                                 'description': 'Also describe the children of the object.'},
        },
        'additionalProperties': False,
    },
    annotations={'readOnlyHint': True, 'title': 'Get object'},
)
def get_object(args):
    obj = resolve_object(args.get('ref'))
    data = object_details(obj)
    parent = parent_of(obj)
    data['parent'] = {'uuid': parent.uuid, 'name': parent.name, 'type': parent.type} if parent else None
    if args.get('include_children'):
        manager_ = manager()
        data['children'] = [object_summary(child, with_children=False)
                            for child in manager_.get_descendant_objects(obj.uuid, True)]
    return data


@tool(
    'create_object',
    'Create a scene object of the given type under a parent (the canvas by '
    'default). Undoable. Use object_types to see the properties of each type.',
    {
        'type': 'object',
        'properties': {
            'type': {'type': 'string', 'enum': object_type_names(),
                     'description': 'Object type, e.g. RECT, TEXT, IMAGE, BUTTON, FRAME_SEQUENCE.'},
            'parent': {'type': 'string', 'description':
                       'Uuid, path or name of the parent object (default: the canvas).'},
            'name': {'type': 'string', 'description': 'Object name (must be unique to be addressable by name).'},
            'properties': {'type': 'object', 'additionalProperties': True,
                           'description': 'Initial properties: x, y, width, height, color, text, '
                                          'script_path, image_path, font_size, ... A TEXT object also '
                                          'takes "auto_size": true, which fits width/height to the '
                                          'text so the label is not clipped.'},
            'select': {'type': 'boolean', 'default': True,
                       'description': 'Select the new object in the editor (the user sees it).'},
        },
        'required': ['type'],
        'additionalProperties': False,
    },
    annotations={'title': 'Create object'},
)
def create_object(args):
    from pygamestudio.game.object.type import OBJECT_TEXT

    manager_ = manager()
    object_type = args['type'].upper()
    if object_type not in object_type_names():
        raise ToolError('Unknown object type "{}". Known: {}'.format(
            args['type'], ', '.join(object_type_names())))

    parent = resolve_object(args['parent']) if args.get('parent') else canvas_object()
    if parent is None:
        raise ToolError('The parent object was not found.')

    new_uuid = str(uuid_module.uuid4())
    object_data = dict(args.get('properties') or {})
    auto_size = bool(object_data.pop('auto_size', False))
    if auto_size and object_type != OBJECT_TEXT:
        raise ToolError('"auto_size" only applies to TEXT objects (a {} lays its '
                        'content out itself).'.format(object_type))
    object_data['uuid'] = new_uuid
    if args.get('name'):
        object_data['name'] = args['name']

    conflicts = [obj for obj in iter_objects() if obj.name == object_data.get('name')]
    if conflicts and args.get('name'):
        raise ToolError('An object called "{}" already exists. Use another name.'.format(args['name']))

    # Creating + fitting a text box is ONE undo step, so Ctrl+Z removes the
    # whole label again.
    if auto_size:
        begin_macro(manager_, 'Create Object')
    try:
        manager_.add(parent.uuid, object_type, object_data)
        created = manager_.get_object(new_uuid)
        if created is None:
            raise ToolError('The object could not be created.')
        if auto_size:
            fit_object_size(manager_, created)
    finally:
        if auto_size:
            end_macro(manager_)

    if args.get('select', True):
        manager_.deselect_all()
        manager_.select(new_uuid)

    data = object_details(created)
    data['parent'] = parent.name
    return data


@tool(
    'update_object',
    'Change one or more properties of an object (all changes of this call are '
    'ONE undo step). Values are converted to the type the property already '
    'has. A TEXT object also takes "auto_size": true, which refits its box '
    'to the text after the other values so the label is not clipped.',
    {
        'type': 'object',
        'properties': {
            'ref': {'type': 'string', 'description':
                    'Uuid, path or name of the object (default: the selection).'},
            'properties': {'type': 'object', 'additionalProperties': True,
                           'description': 'e.g. {"x": 120, "color": [255, 0, 0], "text": "Score"}'},
        },
        'required': ['properties'],
        'additionalProperties': False,
    },
    annotations={'title': 'Update object'},
)
def update_object(args):
    return update_object_properties(args.get('ref'), args['properties'])


@tool(
    'fit_object_size',
    'Resize a TEXT object so its text fits: the text is drawn inside the '
    'width/height box and everything longer is clipped, which a model cannot '
    'see coming because it cannot measure a font. The box becomes the '
    'rendered text size; "padding" adds a margin on every side. One undo '
    'step. Call it after changing text / font_size, or pass "auto_size": '
    'true to create_object / update_object.',
    {
        'type': 'object',
        'properties': {
            'ref': {'type': 'string', 'description':
                    'Uuid, path or name of the TEXT object (default: the selection).'},
            'padding': {'type': 'integer', 'minimum': 0, 'maximum': 200, 'default': 0,
                        'description': 'Extra pixels added around the text.'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Fit a text object to its text'},
)
def fit_object_size_tool(args):
    obj = resolve_object(args.get('ref'))
    return fit_object_size(manager(), obj, args.get('padding', 0))


def update_object_properties(ref, properties, macro_name='Update Object'):
    """Shared implementation of update_object (also used by other tools)."""
    from pygamestudio.game.object.type import OBJECT_TEXT

    manager_ = manager()
    obj = resolve_object(ref)
    properties = dict(properties or {})
    auto_size = bool(properties.pop('auto_size', False))
    if not properties and not auto_size:
        raise ToolError('No properties given.')
    if auto_size and getattr(obj, 'type', '') != OBJECT_TEXT:
        raise ToolError('"auto_size" only applies to TEXT objects ("{}" is a {}).'.format(
            obj.name, obj.type))

    unknown = [attr for attr in properties if not hasattr(obj, attr)]
    if unknown:
        raise ToolError('Object "{}" ({}) has no propert{} {}. Known: {}'.format(
            obj.name, obj.type, 'y' if len(unknown) == 1 else 'ies',
            ', '.join(sorted(unknown)), ', '.join(sorted(_editable_names(obj)))))

    # An EMPTY QUndoStack macro stays on the stack (Qt 6 does not drop it), so
    # a call that changes nothing must not open one - Ctrl+Z would step past
    # it doing nothing at all.
    will_change = any(property_changes(obj, attr, value)
                      for attr, value in properties.items())

    changed = {}
    if will_change:
        begin_macro(manager_, macro_name)
    try:
        if will_change:
            for attr, value in properties.items():
                if push_property(manager_, obj, attr, value):
                    changed[attr] = json_value(getattr(obj, attr))
        if auto_size:
            # Refit AFTER the other values, so a new text / font size is what
            # the box is measured against (explicit width/height lose). When
            # it is the only change it owns its own undo step.
            fitted = fit_object_size(manager_, obj)
            if fitted['changed']:
                changed['width'] = fitted['size'][0]
                changed['height'] = fitted['size'][1]
    finally:
        if will_change:
            end_macro(manager_)

    return {
        'uuid': obj.uuid,
        'path': object_path(obj),
        'changed': changed,
        'unchanged': sorted(set(properties) - set(changed)),
    }


def _editable_names(obj):
    return [name for name in vars(obj) if not name.startswith('_')]


def _patch_would_change(operations):
    """Conservative peek: False only when every operation is a no-op update.

    Keeps apply_scene_patch from leaving an empty undo macro behind (Qt 6
    keeps empty macros on the stack). Anything that cannot be judged here is
    treated as a change, so the real run reports errors the same way as
    before.
    """
    for operation in operations:
        if operation.get('op') != 'update':
            return True
        properties = dict(operation.get('properties') or {})
        if properties.pop('auto_size', False):
            return True
        if not properties:
            continue
        try:
            obj = resolve_object(operation.get('ref'))
            if any(property_changes(obj, attr, value)
                   for attr, value in properties.items()):
                return True
        except Exception:  # noqa: BLE001 - let the real run report it
            return True
    return False


@tool(
    'apply_scene_patch',
    'Apply several scene changes at once (create/update/delete/move objects) as '
    'ONE undo step. Use it to build a whole level or a UI screen in one call. '
    'Operations run in order; later operations can refer to objects created '
    'earlier by name.',
    {
        'type': 'object',
        'properties': {
            'operations': {
                'type': 'array',
                'description': 'List of operations, e.g. [{"op": "create", "type": "RECT", '
                               '"name": "Wall", "properties": {"width": 40, "height": 200}}]',
                'items': {
                    'type': 'object',
                    'properties': {
                        'op': {'type': 'string', 'enum': ['create', 'update', 'delete', 'move']},
                        'type': {'type': 'string', 'description': 'create: object type.'},
                        'name': {'type': 'string', 'description': 'create: name of the new object.'},
                        'ref': {'type': 'string', 'description': 'update/delete/move: which object.'},
                        'parent': {'type': 'string', 'description': 'Parent for create/move.'},
                        'properties': {'type': 'object', 'additionalProperties': True},
                        'select': {'type': 'boolean', 'default': False},
                    },
                    'required': ['op'],
                    'additionalProperties': False,
                },
            },
        },
        'required': ['operations'],
        'additionalProperties': False,
    },
    annotations={'title': 'Apply a batch of scene changes'},
)
def apply_scene_patch(args):
    operations = args['operations']
    if not operations:
        raise ToolError('No operations given.')
    if len(operations) > 200:
        raise ToolError('Too many operations in one call (max 200).')
    if not _patch_would_change(operations):
        return {'applied': 0, 'results': [],
                'note': 'Nothing changed: the values are already the current ones.'}

    manager_ = manager()
    results = []
    begin_macro(manager_, 'AI scene patch')
    try:
        for index, operation in enumerate(operations):
            op = operation['op']
            if op == 'create':
                results.append(create_object({
                    'type': operation.get('type', 'RECT'),
                    'parent': operation.get('parent'),
                    'name': operation.get('name'),
                    'properties': operation.get('properties') or {},
                    'select': bool(operation.get('select', False)),
                }))
            elif op == 'update':
                results.append(update_object_properties(
                    operation.get('ref'), operation.get('properties') or {},
                    macro_name='AI update'))
            elif op == 'delete':
                results.append({'deleted': delete_object_ref(operation.get('ref'))})
            elif op == 'move':
                results.append(move_object_ref(operation.get('ref'), operation.get('parent')))
            else:
                raise ToolError('Operation #{} has an unknown op "{}".'.format(index + 1, op))
    finally:
        end_macro(manager_)
    return {'applied': len(results), 'results': results, 'undo': 'all changes undo in one step'}


@tool(
    'delete_object',
    'Delete an object and its children (undoable).',
    {
        'type': 'object',
        'properties': {
            'ref': {'type': 'string', 'description': 'Uuid, path or name (default: the selection).'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Delete object', 'destructiveHint': True},
)
def delete_object(args):
    return {'deleted': delete_object_ref(args.get('ref'))}


def delete_object_ref(ref):
    manager_ = manager()
    obj = resolve_object(ref)
    if obj.uuid == manager_.canvas_object_uuid:
        raise ToolError('The canvas cannot be deleted.')
    path = object_path(obj)
    manager_.delete([obj.uuid])
    return path


@tool(
    'duplicate_object',
    'Duplicate an object (with its children) inside the same parent. Undoable.',
    {
        'type': 'object',
        'properties': {
            'ref': {'type': 'string', 'description': 'Uuid, path or name (default: the selection).'},
            'offset_x': {'type': 'number', 'default': 0, 'description': 'Move the copy this far right.'},
            'offset_y': {'type': 'number', 'default': 0, 'description': 'Move the copy this far down.'},
        },
        'additionalProperties': False,
    },
    annotations={'title': 'Duplicate object'},
)
def duplicate_object(args):
    manager_ = manager()
    obj = resolve_object(args.get('ref'))
    before = {item.uuid for item in iter_objects()}
    manager_.duplicate([obj.uuid])
    created = [item for item in iter_objects() if item.uuid not in before]
    if not created:
        raise ToolError('The object could not be duplicated.')

    offset_x = float(args.get('offset_x', 0) or 0)
    offset_y = float(args.get('offset_y', 0) or 0)
    root = created[0]
    if offset_x or offset_y:
        begin_macro(manager_, 'Move duplicated object')
        try:
            push_property(manager_, root, 'x', root.x + offset_x)
            push_property(manager_, root, 'y', root.y + offset_y)
        finally:
            end_macro(manager_)

    manager_.deselect_all()
    manager_.select(root.uuid)
    return {
        'uuid': root.uuid,
        'name': root.name,
        'path': object_path(root),
        'children_created': len(created) - 1,
    }


@tool(
    'move_object',
    'Move an object to another parent (re-parent it, with its children). '
    'Undoable as one step.',
    {
        'type': 'object',
        'properties': {
            'ref': {'type': 'string', 'description': 'Uuid, path or name (default: the selection).'},
            'parent': {'type': 'string', 'description': 'New parent (uuid, path or name).'},
        },
        'required': ['parent'],
        'additionalProperties': False,
    },
    annotations={'title': 'Re-parent object'},
)
def move_object(args):
    return move_object_ref(args.get('ref'), args['parent'])


def move_object_ref(ref, parent_ref):
    manager_ = manager()
    obj = resolve_object(ref)
    parent = resolve_object(parent_ref)
    if obj.uuid == manager_.canvas_object_uuid:
        raise ToolError('The canvas cannot be moved.')
    if obj.uuid == parent.uuid:
        raise ToolError('An object cannot be its own parent.')
    # Walking down from the object must never reach the new parent (cycle).
    descendant_uuids = {child.uuid for child in manager_.get_descendant_objects(obj.uuid)}
    if parent.uuid in descendant_uuids:
        raise ToolError('"{}" is a child of "{}": it cannot become its parent.'.format(
            parent.name, obj.name))

    old_parent = parent_of(obj)
    if old_parent is not None and old_parent.uuid == parent.uuid:
        return {'moved': False, 'reason': 'already a child of {}'.format(parent.name)}

    begin_macro(manager_, 'Move object')
    try:
        manager_.cut([obj.uuid])
        manager_.paste(parent.uuid)
    finally:
        end_macro(manager_)
    manager_.deselect_all()
    manager_.select(obj.uuid)
    return {
        'moved': True,
        'uuid': obj.uuid,
        'name': obj.name,
        'path': object_path(obj),
        'parent': parent.name,
    }


@tool(
    'select_objects',
    'Select objects in the editor (or clear the selection with an empty list). '
    'Useful to show the user what an agent is working on.',
    {
        'type': 'object',
        'properties': {
            'refs': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Uuids, paths or names. Empty list = clear the selection.',
            },
        },
        'required': ['refs'],
        'additionalProperties': False,
    },
    annotations={'title': 'Select objects'},
)
def select_objects(args):
    manager_ = manager()
    manager_.deselect_all()
    selected = []
    for ref in args['refs']:
        obj = resolve_object(ref)
        manager_.select(obj.uuid)
        selected.append({'uuid': obj.uuid, 'path': object_path(obj)})
    return {'selected': selected}
