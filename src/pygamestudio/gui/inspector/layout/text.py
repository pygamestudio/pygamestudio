from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.checkbox import *
from pygamestudio.gui.inspector.component.combobox import *
from pygamestudio.gui.inspector.component.textedit import *


INSPECTOR_LAYOUT_TEXT = {
    'visibility': {
        'text': T.tr('inspector.visibility', 'Visibility'),
        'component': {
            'enabled': [True],
            'attribute': ['is_visible'],
            'widget': [VisibilityCheckBox]
        }
    },
    'name': {
        'text': T.tr('inspector.name', 'Name'),
        'component': {
            'enabled': [True],
            'attribute': ['name'],
            'widget': [NameLineEdit]
        }
    },
    'pos': {
        "text": T.tr('inspector.pos', 'Pos'),
        'component': {
            'enabled': [True, True],
            'attribute': ['x', 'y'],
            'widget': [PosSpinBox, PosSpinBox]
        }
    },
    'size': {
        "text": T.tr('inspector.size', 'Size'),
        'component': {
            'enabled': [True, True],
            'attribute': ['width', 'height'],
            'widget': [SizeSpinBox, SizeSpinBox]
        }
    },
    'scale': {
        "text": T.tr('inspector.scale', 'Scale'),
        'component': {
            'enabled': [True, True],
            'attribute': ['scale_x', 'scale_y'],
            'widget': [ScaleSpinBox, ScaleSpinBox]
        }
    },
    'angle': {
        "text": T.tr('inspector.angle', 'Angle'),
        'component': {
            'enabled': [True],
            'attribute': ['angle'],
            'widget': [AngleSpinBox]
        }
    },
    'color': {
        "text": T.tr('inspector.color', 'Color'),
        'component': {
            'enabled': [True],
            'attribute': ['color'],
            'widget': [ColorPicker]
        }
    },
    'string': {
        "text": T.tr('inspector.text', 'Text'),
        'component': {
            'enabled': [True],
            'attribute': ['text'],
            'widget': [TextEdit]
        }
    },
    'font_size': {
        "text": T.tr('inspector.font_size', 'Font Size'),
        'component': {
            'enabled': [True],
            'attribute': ['font_size'],
            'widget': [FontSizeSpinBox]
        }
    },
    'font_family': {
        "text": T.tr('inspector.font_family', 'Font Family'),
        'component': {
            'enabled': [True],
            'attribute': ['font_family'],
            'widget': [FontFamilyComboBox]
        }
    },
    'is_bold': {
        "text": T.tr('inspector.bold', 'Bold'),
        'component': {
            'enabled': [True],
            'attribute': ['is_bold'],
            'widget': [BoldCheckBox]
        }
    },
    'is_italic': {
        "text": T.tr('inspector.italic', 'Italic'),
        'component': {
            'enabled': [True],
            'attribute': ['is_italic'],
            'widget': [ItalicCheckBox]
        }
    },
    'is_underline': {
        "text": T.tr('inspector.underline', 'Underline'),
        'component': {
            'enabled': [True],
            'attribute': ['is_underline'],
            'widget': [UnderlineCheckBox]
        }
    },
    'is_strikethrough': {
        "text": T.tr('inspector.strikethrough', 'Strikethrough'),
        'component': {
            'enabled': [True],
            'attribute': ['is_strikethrough'],
            'widget': [StrikethroughCheckBox]
        }
    },
}