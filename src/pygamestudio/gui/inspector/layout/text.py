from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.checkbox import *
from pygamestudio.gui.inspector.component.combobox import *
from pygamestudio.gui.inspector.component.textedit import *


INSPECTOR_LAYOUT_TEXT = {
    'visibility': {
        'i18n': {
            'key': 'inspector.visibility',
            'default': 'Visibility'
        },
        'component': {
            'enabled': [True],
            'attribute': ['is_visible'],
            'widget': [VisibilityCheckBox]
        }
    },
    'name': {
        'i18n': {
            'key': 'inspector.name',
            'default': 'Name'
        },
        'component': {
            'enabled': [True],
            'attribute': ['name'],
            'widget': [NameLineEdit]
        }
    },
    'pos': {
        'i18n': {
            'key': 'inspector.pos',
            'default': 'Pos'
        },
        'component': {
            'enabled': [True, True],
            'attribute': ['x', 'y'],
            'widget': [PosSpinBox, PosSpinBox]
        }
    },
    'size': {
        'i18n': {
            'key': 'inspector.size',
            'default': 'Size'
        },
        'component': {
            'enabled': [True, True],
            'attribute': ['width', 'height'],
            'widget': [SizeSpinBox, SizeSpinBox]
        }
    },
    'scale': {
        'i18n': {
            'key': 'inspector.scale',
            'default': 'Scale'
        },
        'component': {
            'enabled': [True, True],
            'attribute': ['scale_x', 'scale_y'],
            'widget': [ScaleSpinBox, ScaleSpinBox]
        }
    },
    'angle': {
        'i18n': {
            'key': 'inspector.angle',
            'default': 'Angle'
        },
        'component': {
            'enabled': [True],
            'attribute': ['angle'],
            'widget': [AngleSpinBox]
        }
    },
    'color': {
        'i18n': {
            'key': 'inspector.color',
            'default': 'Color'
        },
        'component': {
            'enabled': [True],
            'attribute': ['color'],
            'widget': [ColorPicker]
        }
    },
    'text': {
        'i18n': {
            'key': 'inspector.text',
            'default': 'Text'
        },        
        'component': {
            'enabled': [True],
            'attribute': ['text'],
            'widget': [TextEdit]
        }
    },
    'font_size': {
        'i18n': {
            'key': 'inspector.font_size',
            'default': 'Font Size'
        },
        'component': {
            'enabled': [True],
            'attribute': ['font_size'],
            'widget': [FontSizeSpinBox]
        }
    },
    'font_family': {
        'i18n': {
            'key': 'inspector.font_family',
            'default': 'Font Family'
        },
        'component': {
            'enabled': [True],
            'attribute': ['font_family'],
            'widget': [FontFamilyComboBox]
        }
    },
    'is_bold': {
        'i18n': {
            'key': 'inspector.bold',
            'default': 'Bold'
        },
        'component': {
            'enabled': [True],
            'attribute': ['is_bold'],
            'widget': [BoldCheckBox]
        }
    },
    'is_italic': {
        'i18n': {
            'key': 'inspector.italic',
            'default': 'Italic'
        },
        'component': {
            'enabled': [True],
            'attribute': ['is_italic'],
            'widget': [ItalicCheckBox]
        }
    },
    'is_underline': {
        'i18n': {
            'key': 'inspector.underline',
            'default': 'Underline'
        },
        'component': {
            'enabled': [True],
            'attribute': ['is_underline'],
            'widget': [UnderlineCheckBox]
        }
    },
    'is_strikethrough': {
        'i18n': {
            'key': 'inspector.strikethrough',
            'default': 'Strikethrough'
        },
        'component': {
            'enabled': [True],
            'attribute': ['is_strikethrough'],
            'widget': [StrikethroughCheckBox]
        }
    },
}