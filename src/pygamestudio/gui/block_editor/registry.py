"""
Block definitions (the block "registry") for the block script editor.

Every definition declares its category, shape, label, editable fields and the
Python code template that generates it:

  * ``{field}``      -> replaced by the field's code (literal, dropdown value, ...)
  * ``{body}``       -> a line of its own: the nested statement list of the block
  * ``{else_block}`` -> a line of its own: the else-list of an if/else block

The block set mirrors the engine API: hats are the runtime object events
(on_start / on_clicked / on_collision_enter / ...), one block per event, and
every event / action declares which object types it belongs to, so the palette
can group them by object (rect, slider, text input, ...). Control blocks are
plain Python control flow and are shared by every object.
"""

from pygamestudio.common.i18n.translator import Translator as T

# ---------------------------------------------------------------- categories

CATEGORIES = (
    {'key': 'event', 'label': 'block.cat.event', 'default_label': 'Events', 'color': '#d9a03c'},
    {'key': 'action', 'label': 'block.cat.action', 'default_label': 'Actions', 'color': '#4c97ff'},
    {'key': 'physics', 'label': 'block.cat.physics', 'default_label': 'Physics', 'color': '#9b59b6'},
    {'key': 'control', 'label': 'block.cat.control', 'default_label': 'Control', 'color': '#2ea8a0'},
)

# The object types the scene editor can create. The palette groups the event
# and action blocks under these names (collapsed by default); control blocks
# are shared by every object and are listed flat.
OBJECTS = (
    {'key': 'rect', 'label': 'item.rect', 'default_label': 'Rect'},
    {'key': 'ellipse', 'label': 'item.ellipse', 'default_label': 'Ellipse'},
    {'key': 'line', 'label': 'item.line', 'default_label': 'Line'},
    {'key': 'polygon', 'label': 'item.polygon', 'default_label': 'Polygon'},
    {'key': 'text', 'label': 'item.text', 'default_label': 'Text'},
    {'key': 'image', 'label': 'item.image', 'default_label': 'Image'},
    {'key': 'button', 'label': 'item.button', 'default_label': 'Button'},
    {'key': 'text_input', 'label': 'item.text_input', 'default_label': 'Text Input'},
    {'key': 'progress_bar', 'label': 'item.progress_bar', 'default_label': 'Progress Bar'},
    {'key': 'slider', 'label': 'item.slider', 'default_label': 'Slider'},
    {'key': 'frame_sequence', 'label': 'item.frame_sequence', 'default_label': 'Frame Sequence'},
    {'key': 'particle', 'label': 'item.particle', 'default_label': 'Particle Emitter'},
    {'key': 'tile_map', 'label': 'item.tile_map', 'default_label': 'Tile Map'},
)
ALL_OBJECTS = tuple(obj['key'] for obj in OBJECTS)

# Field geometry used by the canvas (pixels).
FIELD_WIDTHS = {
    'text': 100,
    'value': 70,
    'number': 60,
    'property': 132,
    'expr': 132,
    'operator': 62,
    'choice': 84,
    'key': 110,
    'toggle': 64,
}

# Field kinds rendered as a dropdown whose stored value IS a code expression
# (the canvas asks options_for() for the entries).
OPTION_FIELD_KINDS = ('property', 'expr', 'operator', 'key', 'toggle', 'event')

_DEFAULT_BY_KIND = {'text': '', 'value': '0', 'number': 0, 'property': None, 'operator': None,
                    'choice': None}

# Values a "property" field can produce (code expression, i18n key, default text).
PROPERTY_OPTIONS = (
    ('self.obj.x', 'block.prop.x', 'x'),
    ('self.obj.y', 'block.prop.y', 'y'),
    ('self.obj.width', 'block.prop.width', 'width'),
    ('self.obj.height', 'block.prop.height', 'height'),
    ('self.obj.scale_x', 'block.prop.scale_x', 'scale x'),
    ('self.obj.scale_y', 'block.prop.scale_y', 'scale y'),
    ('self.obj.angle', 'block.prop.angle', 'angle'),
    ('self.obj.visible', 'block.prop.visible', 'visible'),
    ('self.obj.text', 'block.prop.text', 'text'),
    ('self.obj.value', 'block.prop.value', 'value'),
    ('self.obj.progress', 'block.prop.progress', 'progress'),
    ('dt', 'block.prop.dt', 'dt'),
    ('value', 'block.prop.param_value', 'value param'),
    ('text', 'block.prop.param_text', 'text param'),
    ('other', 'block.prop.other', 'other object'),
)

# Comparison operators for condition blocks.
OPERATOR_OPTIONS = (
    ('==', 'block.op.eq', '='),
    ('!=', 'block.op.ne', '!= '),
    ('>', 'block.op.gt', '>'),
    ('<', 'block.op.lt', '<'),
    ('>=', 'block.op.ge', '>='),
    ('<=', 'block.op.le', '<='),
)

# Values a condition can READ on top of the assignable property list: engine
# expressions that make sense in an if / while comparison but cannot be
# assigned to (the "Set property" block must never produce
# ``self.obj.is_grounded() = 1``, so it keeps using PROPERTY_OPTIONS alone).
CONDITION_OPTIONS = (
    ('self.obj.is_grounded()', 'block.val.grounded', 'on ground'),
    ('self.obj.is_collision_enabled()', 'block.val.collision_on', 'collision on'),
    ('(self.obj.get_velocity() or (0.0, 0.0))[0]', 'block.val.velocity_x', 'speed x'),
    ('(self.obj.get_velocity() or (0.0, 0.0))[1]', 'block.val.velocity_y', 'speed y'),
    ('self.obj.get_angular_velocity() or 0.0', 'block.val.spin', 'spin (deg/s)'),
    ('self.obj.physics_enabled', 'block.val.physics_enabled', 'physics on'),
    ('self.obj.physics_mass', 'block.val.physics_mass', 'mass'),
    ('self.obj.physics_friction', 'block.val.physics_friction', 'friction'),
    ('self.obj.physics_elasticity', 'block.val.physics_elasticity', 'elasticity'),
    ('self.obj.physics_gravity_scale', 'block.val.physics_gravity_scale', 'gravity scale'),
    ('studio.get_mouse_position()[0]', 'block.val.mouse_x', 'mouse x'),
    ('studio.get_mouse_position()[1]', 'block.val.mouse_y', 'mouse y'),
)

# Keys the "if key pressed" blocks can test (the constants come from the
# engine's pygame re-exports). The few keys games ask for most often come
# first, the rest of the keyboard follows - the picker scrolls.
def _literal_key(code, label):
    """A key whose label is the same in every language (A, 1, F5, ...)."""
    return (code, '', label)


KEY_OPTIONS = (
    # arrows and the keys a game tests all the time
    ('studio.K_LEFT', 'block.key.left', 'Left arrow'),
    ('studio.K_RIGHT', 'block.key.right', 'Right arrow'),
    ('studio.K_UP', 'block.key.up', 'Up arrow'),
    ('studio.K_DOWN', 'block.key.down', 'Down arrow'),
    ('studio.K_SPACE', 'block.key.space', 'Space'),
    ('studio.K_RETURN', 'block.key.enter', 'Enter'),
    ('studio.K_TAB', 'block.key.tab', 'Tab'),
    ('studio.K_ESCAPE', 'block.key.escape', 'Escape'),
    ('studio.K_BACKSPACE', 'block.key.backspace', 'Backspace'),
    ('studio.K_DELETE', 'block.key.delete', 'Delete'),
    # modifiers and navigation
    ('studio.K_LSHIFT', 'block.key.lshift', 'Left Shift'),
    ('studio.K_RSHIFT', 'block.key.rshift', 'Right Shift'),
    ('studio.K_LCTRL', 'block.key.lctrl', 'Left Ctrl'),
    ('studio.K_RCTRL', 'block.key.rctrl', 'Right Ctrl'),
    ('studio.K_LALT', 'block.key.lalt', 'Left Alt'),
    ('studio.K_RALT', 'block.key.ralt', 'Right Alt'),
    ('studio.K_HOME', 'block.key.home', 'Home'),
    ('studio.K_END', 'block.key.end', 'End'),
    ('studio.K_PAGEUP', 'block.key.pageup', 'Page Up'),
    ('studio.K_PAGEDOWN', 'block.key.pagedown', 'Page Down'),
    ('studio.K_INSERT', 'block.key.insert', 'Insert'),
) + tuple(
    _literal_key('studio.K_' + letter, letter.upper())
    for letter in 'abcdefghijklmnopqrstuvwxyz'
) + tuple(
    _literal_key('studio.K_' + digit, digit)
    for digit in '0123456789'
) + tuple(
    _literal_key('studio.K_F{}'.format(number), 'F{}'.format(number))
    for number in range(1, 13)
) + (
    # punctuation
    ('studio.K_MINUS', 'block.key.minus', 'Minus -'),
    ('studio.K_EQUALS', 'block.key.equals', 'Equals ='),
    ('studio.K_COMMA', 'block.key.comma', 'Comma ,'),
    ('studio.K_PERIOD', 'block.key.period', 'Period .'),
    ('studio.K_SLASH', 'block.key.slash', 'Slash /'),
    ('studio.K_SEMICOLON', 'block.key.semicolon', 'Semicolon ;'),
    ('studio.K_QUOTE', 'block.key.quote', "Quote '"),
    ('studio.K_LEFTBRACKET', 'block.key.lbracket', 'Left bracket ['),
    ('studio.K_RIGHTBRACKET', 'block.key.rbracket', 'Right bracket ]'),
    ('studio.K_BACKSLASH', 'block.key.backslash', 'Backslash \\'),
    ('studio.K_BACKQUOTE', 'block.key.backquote', 'Backquote `'),
)

# on / off values for toggle-style blocks.
TOGGLE_OPTIONS = (
    ('True', 'block.toggle.on', 'On'),
    ('False', 'block.toggle.off', 'Off'),
)

BLOCKS = {}
ORDER = []


def _add(block_type, category, label, default_label, fields=(), code='', callback=None, params='',
         shape=None, objects=None, header=None):
    definition = {
        'type': block_type,
        'category': category,
        'label': label,
        'default_label': default_label,
        # Some blocks read shorter on the canvas than in the palette (an
        # if/else block is labelled “If” on its header and “else” on its bar).
        'header': header,
        'fields': [
            {'name': name,
             'kind': kind,
             'default': (default[0] if default and default[0] is not None
                         else _kind_default(kind))}
            for field in fields
            for name, kind, *default in (field,)
        ],
        'code': code,
        'callback': callback,
        'params': params,
        'has_body': '{body}' in code,
        'has_else': '{else_block}' in code,
        'objects': tuple(objects) if objects else ALL_OBJECTS,
    }
    if shape is None:
        if callback:
            shape = 'hat'
        elif definition['has_else']:
            shape = 'c_else'
        elif definition['has_body']:
            shape = 'c'
        else:
            shape = 'stack'
    if shape == 'hat':
        # a hat owns the statements stacked below it (its function body)
        definition['has_body'] = True
    definition['shape'] = shape
    BLOCKS[block_type] = definition
    ORDER.append(block_type)
    return definition


def _kind_default(kind):
    if kind in ('property', 'expr'):
        return PROPERTY_OPTIONS[0][0]
    if kind == 'key':
        return KEY_OPTIONS[0][0]
    if kind == 'toggle':
        return TOGGLE_OPTIONS[0][0]
    if kind == 'operator':
        return OPERATOR_OPTIONS[0][0]
    if kind == 'choice':
        return ''
    return _DEFAULT_BY_KIND.get(kind, '')


# ------------------------------------------------------------ event blocks

# ONE BLOCK PER EVENT: the old type names (event_start, event_clicked, ...)
# are used again, so scripts saved before the dropdown existed load as-is.
# (callback, i18n key, default label, callback parameters, object types)
EVENT_BLOCKS = (
    ('on_start', 'start', 'When the game starts', '', ALL_OBJECTS),
    ('on_update', 'update', 'Every frame (dt)', 'dt', ALL_OBJECTS),
    ('on_destroy', 'destroy', 'When this object is destroyed', '', ALL_OBJECTS),
    ('on_visible_changed', 'visible_changed', 'When shown or hidden (visible)', 'visible', ALL_OBJECTS),
    ('on_pressed', 'pressed', 'When pressed on this object', '', ALL_OBJECTS),
    ('on_released', 'released', 'When released', '', ALL_OBJECTS),
    ('on_clicked', 'clicked', 'When clicked', '', ALL_OBJECTS),
    ('on_double_clicked', 'double_clicked', 'When double clicked', '', ALL_OBJECTS),
    ('on_right_clicked', 'right_clicked', 'When right clicked', '', ALL_OBJECTS),
    ('on_mouse_enter', 'mouse_enter', 'When the mouse enters', '', ALL_OBJECTS),
    ('on_mouse_leave', 'mouse_leave', 'When the mouse leaves', '', ALL_OBJECTS),
    ('on_drag_start', 'drag_start', 'When a drag starts', '', ALL_OBJECTS),
    ('on_drag', 'drag', 'While dragging (pos)', 'pos', ALL_OBJECTS),
    ('on_drag_end', 'drag_end', 'When a drag ends', '', ALL_OBJECTS),
    ('on_focus', 'focus', 'When an input gains focus', '', ('text_input',)),
    ('on_blur', 'blur', 'When an input loses focus', '', ('text_input',)),
    ('on_text_changed', 'text_changed', 'When the text changes (text)', 'text', ('text_input',)),
    ('on_submitted', 'submitted', 'When the text is submitted (text)', 'text', ('text_input',)),
    ('on_value_changed', 'value_changed', 'When the slider value changes (value)', 'value', ('slider',)),
    ('on_collision_enter', 'collision_enter', 'When a collision starts (other)', 'other', ALL_OBJECTS),
    ('on_collision_exit', 'collision_exit', 'When a collision ends (other)', 'other', ALL_OBJECTS),
    ('on_animation_start', 'animation_start', 'When the animation starts', '', ('frame_sequence',)),
    ('on_frame_changed', 'frame_changed', 'When the frame changes (frame_index)', 'frame_index',
     ('frame_sequence',)),
    ('on_animation_finished', 'animation_finished', 'When the animation finishes', '', ('frame_sequence',)),
    ('on_particles_finished', 'particles_finished', 'When the particles are done', '', ('particle',)),
    ('on_progress_changed', 'progress_changed', 'When the progress changes (progress)', 'progress',
     ('progress_bar',)),
    ('on_progress_full', 'progress_full', 'When the progress is full', '', ('progress_bar',)),
)

for _callback, _key, _default_label, _params, _objects in EVENT_BLOCKS:
    _add('event_' + _callback[3:], 'event', 'block.ev.' + _key, _default_label,
         callback=_callback, params=_params, objects=_objects)

# Renamed blocks: type -> (new type, {old field: new field}).
LEGACY_BLOCK_TYPES = {
    'action_move_by': ('action_move_to', {'dx': 'x', 'dy': 'y'}),
}


# ---------------------------------------------------------------- actions

_add('action_set_property', 'action', 'block.act.set_property', 'Set property to value',
     fields=(('property', 'property'), ('value', 'value')),
     code='{property} = {value}')
_add('action_change_property', 'action', 'block.act.change_property', 'Change property by',
     fields=(('property', 'property'), ('delta', 'number')),
     code='{property} += {delta}')
_add('action_move_to', 'action', 'block.act.move_to', 'Move to x y',
     fields=(('x', 'number'), ('y', 'number')),
     code='self.obj.x = {x}\nself.obj.y = {y}')
_add('action_turn', 'action', 'block.act.turn', 'Turn by (degrees)',
     fields=(('degrees', 'number', 15),),
     code='self.obj.angle += {degrees}')
_add('action_show', 'action', 'block.act.show', 'Show',
     code='self.obj.show()')
_add('action_hide', 'action', 'block.act.hide', 'Hide',
     code='self.obj.hide()')
_add('action_toggle_visible', 'action', 'block.act.toggle_visible', 'Toggle show / hide',
     code='self.obj.visible = not self.obj.visible')
_add('action_set_color', 'action', 'block.act.set_color', 'Set color',
     fields=(('color', 'text', '(255, 255, 255, 255)'),),
     code='self.obj.set_color({color})')
_add('action_set_image', 'action', 'block.act.set_image', 'Set image',
     fields=(('path', 'text'),),
     code='self.obj.set_image_path({path})', objects=('image', 'button'))
_add('action_set_text', 'action', 'block.act.set_text', 'Set text',
     fields=(('text', 'text'),),
     code='self.obj.set_text({text})', objects=('text', 'text_input'))
_add('action_play_sound', 'action', 'block.act.play_sound', 'Play sound',
     fields=(('path', 'text'),),
     code='studio.play_sound({path})')
_add('action_play_music', 'action', 'block.act.play_music', 'Play music (loop)',
     fields=(('path', 'text'),),
     code='studio.play_music({path}, loops=-1)')
_add('action_stop_music', 'action', 'block.act.stop_music', 'Stop music',
     code='studio.stop_music()')
_add('action_stop_sounds', 'action', 'block.act.stop_sounds', 'Stop all sounds',
     code='studio.stop_all_sounds()')
_add('action_set_window_title', 'action', 'block.act.set_window_title', 'Set window title',
     fields=(('title', 'text'),),
     code='studio.set_window_title({title})')
_add('action_print', 'action', 'block.act.print', 'Print',
     fields=(('text', 'text'),),
     code='print({text})')
_add('action_play_animation', 'action', 'block.act.play_animation', 'Play animation',
     code='self.obj.play()', objects=('frame_sequence',))
_add('action_pause_animation', 'action', 'block.act.pause_animation', 'Pause animation',
     code='self.obj.pause()', objects=('frame_sequence',))
_add('action_set_frame', 'action', 'block.act.set_frame', 'Go to frame (index)',
     fields=(('index', 'number'),),
     code='self.obj.set_frame_index({index})', objects=('frame_sequence',))
_add('action_restart_animation', 'action', 'block.act.restart_animation', 'Restart animation',
     code='self.obj.restart()', objects=('frame_sequence',))
_add('action_emit_particles', 'action', 'block.act.emit_particles', 'Emit particles',
     fields=(('count', 'number', 10),),
     code='self.obj.emit_particles({count})', objects=('particle',))
_add('action_set_slider_value', 'action', 'block.act.set_slider_value', 'Set slider value',
     fields=(('value', 'number', 50),),
     code='self.obj.set_value({value})', objects=('slider',))
_add('action_set_progress', 'action', 'block.act.set_progress', 'Set progress',
     fields=(('value', 'number', 50),),
     code='self.obj.set_progress({value})', objects=('progress_bar',))

# ---------------------------------------------------------------- physics

_add('physics_apply_force', 'physics', 'block.phy.apply_force', 'Apply force x y',
     fields=(('fx', 'number', 0), ('fy', 'number', 0)),
     code='self.obj.apply_force(({fx}, {fy}))')
_add('physics_apply_impulse', 'physics', 'block.phy.apply_impulse', 'Apply impulse (a jump)',
     fields=(('ix', 'number', 0), ('iy', 'number', -520)),
     code='self.obj.apply_impulse(({ix}, {iy}))')
_add('physics_set_velocity', 'physics', 'block.phy.set_velocity', 'Set speed x y',
     fields=(('vx', 'number', 0), ('vy', 'number', 0)),
     code='self.obj.set_velocity(({vx}, {vy}))')
_add('physics_set_spin', 'physics', 'block.phy.set_spin', 'Set spin (degrees/s)',
     fields=(('degrees', 'number', 90),),
     code='self.obj.set_angular_velocity({degrees})')
_add('physics_set_state', 'physics', 'block.phy.set_state', 'Set physics',
     fields=(('state', 'toggle'),),
     code='self.obj.set_physics_enabled({state})')
_add('physics_set_gravity', 'physics', 'block.phy.set_gravity', 'World gravity x y',
     fields=(('gx', 'number', 0), ('gy', 'number', 980)),
     code='studio.set_gravity(({gx}, {gy}))')

# ---------------------------------------------------------------- control

_add('control_if', 'control', 'block.ctl.if', 'If',
     fields=(('property', 'expr'), ('operator', 'operator'), ('value', 'value')),
     code='if {property} {operator} {value}:\n{body}')
_add('control_if_else', 'control', 'block.ctl.if_else', 'If / else',
     fields=(('property', 'expr'), ('operator', 'operator'), ('value', 'value')),
     code='if {property} {operator} {value}:\n{body}\nelse:\n{else_block}',
     header=('block.ctl.if', 'If'))
_add('control_repeat', 'control', 'block.ctl.repeat', 'Repeat',
     fields=(('times', 'number', 10),),
     code='for _ in range({times}):\n{body}')
_add('control_while', 'control', 'block.ctl.while', 'While (repeat while true)',
     fields=(('property', 'expr'), ('operator', 'operator'), ('value', 'value')),
     code='while {property} {operator} {value}:\n{body}')
_add('control_repeat_until', 'control', 'block.ctl.repeat_until', 'Repeat until',
     fields=(('property', 'expr'), ('operator', 'operator'), ('value', 'value')),
     code='while not ({property} {operator} {value}):\n{body}')
_add('control_if_key', 'control', 'block.ctl.if_key', 'If key is pressed',
     fields=(('key', 'key'),),
     code='if studio.is_key_pressed({key}):\n{body}')
_add('control_while_key', 'control', 'block.ctl.while_key', 'While key is held',
     fields=(('key', 'key'),),
     code='while studio.is_key_pressed({key}):\n{body}')
_add('control_continue', 'control', 'block.ctl.continue', 'Skip to the next loop step',
     code='continue')
_add('control_break', 'control', 'block.ctl.break', 'Break out of the loop',
     code='break')
_add('control_return', 'control', 'block.ctl.return', 'Stop this event',
     code='return')


# ---------------------------------------------------------------- helpers

def get_definition(block_type):
    """The definition of a block type, or None when it is unknown."""
    return BLOCKS.get(block_type)


def definitions():
    """Every definition, in toolbox order."""
    return [BLOCKS[block_type] for block_type in ORDER]


def definitions_by_category(category):
    """The definitions of one category, in toolbox order."""
    return [BLOCKS[block_type] for block_type in ORDER
            if BLOCKS[block_type]['category'] == category]


def get_category(category):
    """The category dict of a key, or None."""
    return next((item for item in CATEGORIES if item['key'] == category), None)


def field_spec(definition, name):
    """The field spec called ``name`` of a definition, or None."""
    return next((field for field in definition.get('fields', []) if field['name'] == name), None)


def field_default(definition, name):
    """The default value of a field."""
    spec = field_spec(definition, name)
    return spec['default'] if spec else ''


def field_value(block, definition, name):
    """The current value of a field of a placed block (falls back to the default)."""
    value = (block.get('fields') or {}).get(name)
    if value is None or value == '':
        return field_default(definition, name)
    return value


def label_text(definition, block=None):
    """The translated label of a block."""
    if definition is None:
        return ''
    return T.tr(definition['label'], definition.get('default_label', definition['type']))


def header_text(definition):
    """The label drawn on the block HEADER (falls back to the normal label).

    An if/else block shows just “If” on its header plus an “else” bar, so the
    developer is not told “If / else” by the block itself (the palette still
    lists it as “If / else” so the two control blocks can be told apart).
    """
    if definition is None:
        return ''
    header = definition.get('header')
    if not header:
        return label_text(definition)
    return T.tr(header[0], header[1])


def event_callback(block):
    """(callback, params) of a placed event block, or (None, '') for others."""
    definition = get_definition(block.get('type'))
    if definition is None or definition['shape'] != 'hat':
        return None, ''
    return definition.get('callback'), definition.get('params', '') or ''


def object_text(obj):
    """The translated name of an object group of the palette."""
    return T.tr(obj['label'], obj.get('default_label', obj['key']))


def object_groups(category):
    """[(object, [definition, ...]), ...] for the event / action sections.

    Every object lists exactly the blocks its script can use: the ones that
    belong to that object type first, then the ones shared by every object.
    """
    groups = []
    for obj in OBJECTS:
        members = [BLOCKS[block_type] for block_type in ORDER
                   if BLOCKS[block_type]['category'] == category
                   and obj['key'] in BLOCKS[block_type]['objects']]
        if not members:
            continue
        members.sort(key=lambda definition: (0 if len(definition['objects']) < len(ALL_OBJECTS)
                                             else 1, ORDER.index(definition['type'])))
        groups.append((obj, members))
    return groups


def category_text(category):
    """The translated name of a category."""
    return T.tr(category['label'], category.get('default_label', category['key']))


def option_text(option):
    """The translated label of a (code, i18n key, default) option."""
    if not option[1]:
        # literal labels (A, 1, F5, ...) read the same in every language
        return option[2]
    return T.tr(option[1], option[2])


def options_for(kind):
    """The dropdown options of a field kind."""
    if kind == 'property':
        return PROPERTY_OPTIONS
    if kind == 'expr':
        # condition operands: the assignable fields plus the read-only values
        return PROPERTY_OPTIONS + CONDITION_OPTIONS
    if kind == 'operator':
        return OPERATOR_OPTIONS
    if kind == 'key':
        return KEY_OPTIONS
    if kind == 'toggle':
        return TOGGLE_OPTIONS
    return ()
