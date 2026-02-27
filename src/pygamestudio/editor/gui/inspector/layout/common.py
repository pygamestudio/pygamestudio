from pygamestudio.editor.gui.inspector.component.lineedit import *
from pygamestudio.editor.gui.inspector.component.picker import *
from pygamestudio.editor.gui.inspector.component.spinbox import *
from pygamestudio.editor.gui.inspector.component.checkbox import *


INSPECTOR_LAYOUT_COMMON_PREFIX = {
    'name': {
        'i18n': {
            'zh': '名称',
            'en': 'Name'
        },
        'component': {
            'layout': 'horizontal',
            'attribute': ['name'],
            'widget': [NameLineEdit]
        }
    },
    'pos': {
        'i18n': {
            'zh': '坐标',
            'en': 'Pos'
        },
        'component': {
            'layout': 'horizontal',
            'attribute': ['x', 'y'],
            'widget': [PosSpinBox, PosSpinBox]
        }
    },
    'size': {
        'i18n': {
            'zh': '尺寸',
            'en': 'Size'
        },
        'component': {
            'layout': 'horizontal',
            'attribute': ['width', 'height'],
            'widget': [SizeSpinBox, SizeSpinBox]
        }
    },
    'scale': {
        'i18n': {
            'zh': '缩放',
            'en': 'Scale'
        },
        'component': {
            'layout': 'horizontal',
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
            'layout': 'horizontal',
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
            'layout': 'horizontal',
            'attribute': ['color'],
            'widget': [ColorPicker]
        }
    },
    'visibility': {
        'i18n': {
            'zh': '可见性',
            'en': 'Visibility'
        },
        'component': {
            'layout': 'horizontal',
            'attribute': ['is_visible'],
            'widget': [VisibilityCheckBox]
        }
    },
}


INSPECTOR_LAYOUT_COMMON_SUFFIX = {

}