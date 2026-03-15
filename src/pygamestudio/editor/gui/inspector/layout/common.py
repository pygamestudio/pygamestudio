from pygamestudio.editor.gui.inspector.component.lineedit import *
from pygamestudio.editor.gui.inspector.component.picker import *
from pygamestudio.editor.gui.inspector.component.spinbox import *
from pygamestudio.editor.gui.inspector.component.checkbox import *


INSPECTOR_LAYOUT_COMMON_PREFIX = {
    'visibility': {
        'i18n': {
            'zh': '可见性',
            'en': 'Visibility'
        },
        'component': {
            'attribute': ['is_visible'],
            'widget': [VisibilityCheckBox]
        }
    },
    'name': {
        'i18n': {
            'zh': '名称',
            'en': 'Name'
        },
        'component': {
            'attribute': ['name'],
            'widget': [NameLineEdit]
        }
    },
    'scale': {
        'i18n': {
            'zh': '缩放',
            'en': 'Scale'
        },
        'component': {
            'attribute': ['scale_x', 'scale_y'],
            'widget': [ScaleSpinBox, ScaleSpinBox]
        }
    },
    'angle': {
        'i18n': {
            'zh': '角度',
            'en': 'Angle'
        },
        'component': {
            'attribute': ['angle'],
            'widget': [AngleSpinBox]
        }
    },
    'color': {
        'i18n': {
            'zh': '颜色',
            'en': 'Color'
        },
        'component': {
            'attribute': ['color'],
            'widget': [ColorPicker]
        }
    },
}


INSPECTOR_LAYOUT_COMMON_SUFFIX = {

}