from pygamestudio.gui.inspector.component.spinbox import *


INSPECTOR_LAYOUT_LINE = {
    'start_point': {
        'i18n': {
            'zh': '开始坐标',
            'en': 'Start Point'
        },
        'component': {
            'enabled': [True, True],
            'attribute': ['start_x', 'start_y'],
            'widget': [PosSpinBox, PosSpinBox]
        }
    },
    'end_point': {
        'i18n': {
            'zh': '结束坐标',
            'en': 'End Point'
        },
        'component': {
            'enabled': [True, True],
            'attribute': ['end_x', 'end_y'],
            'widget': [PosSpinBox, PosSpinBox]
        }
    },
    'thickness': {
        'i18n': {
            'zh': '线宽',
            'en': 'Thickness'
        },
        'component': {
            'enabled': [True],
            'attribute': ['thickness'],
            'widget': [ThicknessSpinBox]
        }
    },
}