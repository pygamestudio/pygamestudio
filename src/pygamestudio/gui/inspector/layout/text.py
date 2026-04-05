from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.checkbox import *
from pygamestudio.gui.inspector.component.combobox import *
from pygamestudio.gui.inspector.component.textedit import *


INSPECTOR_LAYOUT_TEXT = {
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
    'string': {
        'i18n': {
            'zh': '文本内容',
            'en': 'Text'
        },
        'component': {
            'enabled': [True],
            'attribute': ['text'],
            'widget': [TextEdit]
        }
    },
    'font_size': {
        'i18n': {
            'zh': '字体大小',
            'en': 'Font Size'
        },
        'component': {
            'enabled': [True],
            'attribute': ['font_size'],
            'widget': [FontSizeSpinBox]
        }
    },
    'font_family': {
        'i18n': {
            'zh': '字体',
            'en': 'Font Family'
        },
        'component': {
            'enabled': [True],
            'attribute': ['font_family'],
            'widget': [FontFamilyComboBox]
        }
    },
    'is_bold': {
        'i18n': {
            'zh': '加粗',
            'en': 'Bold'
        },
        'component': {
            'enabled': [True],
            'attribute': ['is_bold'],
            'widget': [BoldCheckBox]
        }
    },
    'is_italic': {
        'i18n': {
            'zh': '斜体',
            'en': 'Italic'
        },
        'component': {
            'enabled': [True],
            'attribute': ['is_italic'],
            'widget': [ItalicCheckBox]
        }
    },
    'is_underline': {
        'i18n': {
            'zh': '下划线',
            'en': 'Underline'
        },
        'component': {
            'enabled': [True],
            'attribute': ['is_underline'],
            'widget': [UnderlineCheckBox]
        }
    },
    'is_strikethrough': {
        'i18n': {
            'zh': '删除线',
            'en': 'Strikethrough'
        },
        'component': {
            'enabled': [True],
            'attribute': ['is_strikethrough'],
            'widget': [StrikethroughCheckBox]
        }
    },
}