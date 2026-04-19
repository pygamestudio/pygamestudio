from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.checkbox import *

INSPECTOR_LAYOUT_LINE = {
    'visibility': {
        'text': T.tr('inspector.visibility', 'Visibility'),
        'component': {
            'enabled': [True],
            'attribute': ['is_visible'],
            'widget': [VisibilityCheckBox]
        }
    },
    'name': {
        'text': T.tr('inspector.name', 'Name'),
        'component': {
            'enabled': [True],
            'attribute': ['name'],
            'widget': [NameLineEdit]
        }
    },
    'scale': {
        "text": T.tr('inspector.scale', 'Scale'),
        'component': {
            'enabled': [True, True],
            'attribute': ['scale_x', 'scale_y'],
            'widget': [ScaleSpinBox, ScaleSpinBox]
        }
    },
    'angle': {
        "text": T.tr('inspector.angle', 'Angle'),
        'component': {
            'enabled': [True],
            'attribute': ['angle'],
            'widget': [AngleSpinBox]
        }
    },
    'color': {
        "text": T.tr('inspector.color', 'Color'),
        'component': {
            'enabled': [True],
            'attribute': ['color'],
            'widget': [ColorPicker]
        }
    },
    'start_point': {
        "text": T.tr('inspector.start_point', 'Start Point'),
        'component': {
            'enabled': [True, True],
            'attribute': ['start_x', 'start_y'],
            'widget': [PosSpinBox, PosSpinBox]
        }
    },
    'end_point': {
        "text": T.tr('inspector.end_point', 'End Point'),
        'component': {
            'enabled': [True, True],
            'attribute': ['end_x', 'end_y'],
            'widget': [PosSpinBox, PosSpinBox]
        }
    },
    'thickness': {
        "text": T.tr('inspector.thickness', 'Thickness'),
        'component': {
            'enabled': [True],
            'attribute': ['thickness'],
            'widget': [ThicknessSpinBox]
        }
    },
}