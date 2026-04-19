from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.checkbox import *


INSPECTOR_LAYOUT_CANVAS = {
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
            'enabled': [False],
            'attribute': ['name'],
            'widget': [NameLineEdit]
        }
    },
    'size': {
        "text": T.tr('inspector.size', 'Size'),
        'component': {
            'enabled': [False, False],
            'attribute': ['width', 'height'],
            'widget': [SizeSpinBox, SizeSpinBox]
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
}