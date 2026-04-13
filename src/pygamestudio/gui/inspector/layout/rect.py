from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.checkbox import *

INSPECTOR_LAYOUT_RECT = {
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
            'enabled': [True],
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
            'enabled': [True, True],
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
            'enabled': [True, True],
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
            'enabled': [True, True],
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
            'enabled': [True],
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
            'enabled': [True],
            'attribute': ['color'],
            'widget': [ColorPicker]
        }
    },
    'border_radius': {
        'i18n': {
            'zh': '边框圆角',
            'en': 'Border Radius'
        },
        'component': {
            'enabled': [True, True, True, True],
            'attribute': ['border_top_left_radius', 'border_top_right_radius', 'border_bottom_left_radius', 'border_bottom_right_radius'],
            'widget': [BorderRadiusSpinBox, BorderRadiusSpinBox, BorderRadiusSpinBox, BorderRadiusSpinBox]
        }
    },
}