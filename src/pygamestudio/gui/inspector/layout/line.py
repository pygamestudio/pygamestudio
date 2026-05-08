from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.checkbox import *

INSPECTOR_LAYOUT_LINE = {
    'visibility': {
        'i18n': {
            'key': 'inspector.visibility',
            'default': 'Visibility'
        },
        'component': {
            'enabled': [True],
            'attribute': ['is_visible'],
            'widget': [VisibilityCheckBox]
        }
    },
    'name': {
        'i18n': {
            'key': 'inspector.name',
            'default': 'Name'
        },
        'component': {
            'enabled': [True],
            'attribute': ['name'],
            'widget': [NameLineEdit]
        }
    },
    'start_point': {
        'i18n': {
            'key': 'inspector.start_point',
            'default': 'Start Point'
        },
        'component': {
            'enabled': [True, True],
            'attribute': ['start_x', 'start_y'],
            'widget': [PosSpinBox, PosSpinBox]
        }
    },
    'end_point': {
        'i18n': {
            'key': 'inspector.end_point',
            'default': 'End Point'
        },
        'component': {
            'enabled': [True, True],
            'attribute': ['end_x', 'end_y'],
            'widget': [PosSpinBox, PosSpinBox]
        }
    },
    'scale': {
        'i18n': {
            'key': 'inspector.scale',
            'default': 'Scale'
        },
        'component': {
            'enabled': [True, True],
            'attribute': ['scale_x', 'scale_y'],
            'widget': [ScaleSpinBox, ScaleSpinBox]
        }
    },
    'angle': {
        'i18n': {
            'key': 'inspector.angle',
            'default': 'Angle'
        },
        'component': {
            'enabled': [True],
            'attribute': ['angle'],
            'widget': [AngleSpinBox]
        }
    },
    'color': {
        'i18n': {
            'key': 'inspector.color',
            'default': 'Color'
        },
        'component': {
            'enabled': [True],
            'attribute': ['color'],
            'widget': [ColorPicker]
        }
    },
    'thickness': {
        'i18n': {
            'key': 'inspector.thickness',
            'default': 'Thickness'
        },
        'component': {
            'enabled': [True],
            'attribute': ['thickness'],
            'widget': [ThicknessSpinBox]
        }
    },
}