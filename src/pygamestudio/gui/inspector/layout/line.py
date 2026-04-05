from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.checkbox import *

INSPECTOR_LAYOUT_LINE = {
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