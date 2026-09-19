from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.checkbox import PhysicsCheckBox
from pygamestudio.gui.inspector.component.combo import PhysicsShapeComboBox, PhysicsTypeComboBox
from pygamestudio.gui.inspector.component.spinbox import PhysicsShapeSpinBox, PhysicsSpinBox
from pygamestudio.gui.inspector.component.widget import PhysicsShapePointsWidget


_PHYSICS_ENABLED = {
    'i18n': {
        'key': 'inspector.physics_enabled',
        'default': 'Enable Physics'
    },
    'component': {
        'enabled': [True],
        'attribute': ['physics_enabled'],
        'widget': [PhysicsCheckBox]
    }
}

_PHYSICS_TYPE = {
    'i18n': {
        'key': 'inspector.physics_type',
        'default': 'Body Type'
    },
    'component': {
        'enabled': [True],
        'attribute': ['physics_type'],
        'widget': [PhysicsTypeComboBox]
    }
}

_PHYSICS_MASS = {
    'i18n': {
        'key': 'inspector.physics_mass',
        'default': 'Mass'
    },
    'component': {
        'enabled': [True],
        'attribute': ['physics_mass'],
        'widget': [PhysicsSpinBox]
    }
}

_PHYSICS_FIXED_ROTATION = {
    'i18n': {
        'key': 'inspector.physics_fixed_rotation',
        'default': 'Fixed Rotation'
    },
    'component': {
        'enabled': [True],
        'attribute': ['physics_fixed_rotation'],
        'widget': [PhysicsCheckBox]
    }
}

_PHYSICS_FRICTION = {
    'i18n': {
        'key': 'inspector.physics_friction',
        'default': 'Friction'
    },
    'component': {
        'enabled': [True],
        'attribute': ['physics_friction'],
        'widget': [PhysicsSpinBox]
    }
}

_PHYSICS_ELASTICITY = {
    'i18n': {
        'key': 'inspector.physics_elasticity',
        'default': 'Elasticity'
    },
    'component': {
        'enabled': [True],
        'attribute': ['physics_elasticity'],
        'widget': [PhysicsSpinBox]
    }
}

_PHYSICS_GRAVITY_SCALE = {
    'i18n': {
        'key': 'inspector.physics_gravity_scale',
        'default': 'Gravity Scale'
    },
    'component': {
        'enabled': [True],
        'attribute': ['physics_gravity_scale'],
        'widget': [PhysicsSpinBox]
    }
}

_PHYSICS_LINEAR_DAMPING = {
    'i18n': {
        'key': 'inspector.physics_linear_damping',
        'default': 'Linear Damping'
    },
    'component': {
        'enabled': [True],
        'attribute': ['physics_linear_damping'],
        'widget': [PhysicsSpinBox]
    }
}

_PHYSICS_ANGULAR_DAMPING = {
    'i18n': {
        'key': 'inspector.physics_angular_damping',
        'default': 'Angular Damping'
    },
    'component': {
        'enabled': [True],
        'attribute': ['physics_angular_damping'],
        'widget': [PhysicsSpinBox]
    }
}

_PHYSICS_SHAPE = {
    'i18n': {
        'key': 'inspector.physics_shape',
        'default': 'Rigid Body Shape'
    },
    'component': {
        'enabled': [True],
        'attribute': ['physics_shape_type'],
        'widget': [PhysicsShapeComboBox]
    }
}

_PHYSICS_SHAPE_OFFSET = {
    'i18n': {
        'key': 'inspector.physics_shape_offset',
        'default': 'Shape Offset'
    },
    'component': {
        'enabled': [True, True],
        'attribute': ['physics_shape_offset_x', 'physics_shape_offset_y'],
        'widget': [PhysicsShapeSpinBox, PhysicsShapeSpinBox]
    }
}

_PHYSICS_SHAPE_SIZE = {
    'i18n': {
        'key': 'inspector.physics_shape_size',
        'default': 'Shape Size'
    },
    'component': {
        'enabled': [True, True],
        'attribute': ['physics_shape_width', 'physics_shape_height'],
        'widget': [PhysicsShapeSpinBox, PhysicsShapeSpinBox]
    }
}

_PHYSICS_SHAPE_POINTS = {
    'i18n': {
        'key': 'inspector.physics_shape_points',
        'default': 'Shape Points'
    },
    'component': {
        'enabled': [True],
        'attribute': ['physics_shape_points'],
        'widget': [PhysicsShapePointsWidget]
    }
}


def build_physics_layout(physics_enabled, physics_shape_type='rect',
                         physics_type='dynamic'):
    """Return the rows of the shared physics section.

    While physics is disabled only the enable checkbox is shown; once enabled
    the body-type combo appears, then the rigid-body shape (its own type,
    offset and size/vertices - independent from the collision section), then
    the material fields. Mass and fixed rotation are dynamic-only."""
    layout = {
        'physics_enabled': _PHYSICS_ENABLED,
    }
    if not physics_enabled:
        return layout

    layout['physics_type'] = _PHYSICS_TYPE

    layout['physics_shape'] = _PHYSICS_SHAPE
    if physics_shape_type == 'polygon':
        layout['physics_shape_offset'] = _PHYSICS_SHAPE_OFFSET
        layout['physics_shape_points'] = _PHYSICS_SHAPE_POINTS
    elif physics_shape_type != 'bbox':  # rect and ellipse use the box size
        layout['physics_shape_offset'] = _PHYSICS_SHAPE_OFFSET
        layout['physics_shape_size'] = _PHYSICS_SHAPE_SIZE

    if physics_type == 'dynamic':
        layout['physics_mass'] = _PHYSICS_MASS
        layout['physics_fixed_rotation'] = _PHYSICS_FIXED_ROTATION
    layout['physics_friction'] = _PHYSICS_FRICTION
    layout['physics_elasticity'] = _PHYSICS_ELASTICITY
    layout['physics_gravity_scale'] = _PHYSICS_GRAVITY_SCALE
    layout['physics_linear_damping'] = _PHYSICS_LINEAR_DAMPING
    layout['physics_angular_damping'] = _PHYSICS_ANGULAR_DAMPING
    return layout
