from pygamestudio.editor.gui.inspector.component.spinbox import *

INSPECTOR_LAYOUT_ELLIPSE = {
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
}