from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.checkbox import *


INSPECTOR_LAYOUT_CANVAS = {
    'visibility': {
        'i18n': {
            'zh': '可见性',
            'en': 'Visibility'
        },
        'component': {
            'enabled': [True],
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
            'enabled': [False],
            'attribute': ['name'],
            'widget': [NameLineEdit]
        }
    },
    'size': {
        'i18n': {
            'zh': '尺寸',
            'en': 'Size'
        },
        'component': {
            'enabled': [False, False],
            'attribute': ['width', 'height'],
            'widget': [SizeSpinBox, SizeSpinBox]
        }
    },
    'color': {
        'i18n': {
            'zh': '颜色',
            'en': 'Color'
        },
        'component': {
            'enabled': [True],
            'attribute': ['color'],
            'widget': [ColorPicker]
        }
    },
}