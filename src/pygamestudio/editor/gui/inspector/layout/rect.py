from pygamestudio.editor.gui.inspector.component.spinbox import *

INSPECTOR_LAYOUT_RECT = {
    'pos': {
        'i18n': {
            'zh': '坐标',
            'en': 'Pos'
        },
        'component': {
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
            'attribute': ['width', 'height'],
            'widget': [SizeSpinBox, SizeSpinBox]
        }
    },
    'border_radius': {
        'i18n': {
            'zh': '边框圆角',
            'en': 'Border Radius'
        },
        'component': {
            'attribute': ['border_top_left_radius', 'border_top_right_radius', 'border_bottom_left_radius', 'border_bottom_right_radius'],
            'widget': [BorderRadiusSpinBox, BorderRadiusSpinBox, BorderRadiusSpinBox, BorderRadiusSpinBox]
        }
    },
}