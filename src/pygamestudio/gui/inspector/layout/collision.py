from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.checkbox import CollisionCheckBox
from pygamestudio.gui.inspector.component.combo import CollisionTypeComboBox
from pygamestudio.gui.inspector.component.spinbox import CollisionSpinBox
from pygamestudio.gui.inspector.component.widget import CollisionPointsWidget


_COLLISION_ENABLED = {
    'i18n': {
        'key': 'inspector.collision_enabled',
        'default': 'Enable Collision'
    },
    'component': {
        'enabled': [True],
        'attribute': ['collision_enabled'],
        'widget': [CollisionCheckBox]
    }
}

_COLLISION_TYPE = {
    'i18n': {
        'key': 'inspector.collision_type',
        'default': 'Collision Type'
    },
    'component': {
        'enabled': [True],
        'attribute': ['collision_type'],
        'widget': [CollisionTypeComboBox]
    }
}

_COLLISION_OFFSET = {
    'i18n': {
        'key': 'inspector.collision_offset',
        'default': 'Collision Offset'
    },
    'component': {
        'enabled': [True, True],
        'attribute': ['collision_offset_x', 'collision_offset_y'],
        'widget': [CollisionSpinBox, CollisionSpinBox]
    }
}

_COLLISION_SIZE = {
    'i18n': {
        'key': 'inspector.collision_size',
        'default': 'Collision Size'
    },
    'component': {
        'enabled': [True, True],
        'attribute': ['collision_width', 'collision_height'],
        'widget': [CollisionSpinBox, CollisionSpinBox]
    }
}

_COLLISION_POINTS = {
    'i18n': {
        'key': 'inspector.collision_points',
        'default': 'Collision Points'
    },
    'component': {
        'enabled': [True],
        'attribute': ['collision_points'],
        'widget': [CollisionPointsWidget]
    }
}


def build_collision_layout(collision_enabled, collision_type='rect'):
    """Return the rows of the shared collision section.

    While collision is disabled only the enable checkbox is shown; once enabled
    the shape-type combo appears, followed by the fields that make sense for
    that shape: offset+size (rect/ellipse), offset+vertices (polygon) or
    nothing (bbox). Every non-bbox shape carries a collision offset."""
    layout = {
        'collision_enabled': _COLLISION_ENABLED,
    }
    if not collision_enabled:
        return layout

    layout['collision_type'] = _COLLISION_TYPE
    if collision_type == 'bbox':
        return layout
    layout['collision_offset'] = _COLLISION_OFFSET
    if collision_type == 'polygon':
        layout['collision_points'] = _COLLISION_POINTS
    else:  # rect and ellipse both use the box size (full W/H)
        layout['collision_size'] = _COLLISION_SIZE
    return layout
