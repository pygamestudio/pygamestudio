from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.checkbox import *
from pygamestudio.gui.inspector.component.textedit import *
from pygamestudio.gui.inspector.component.alignment import *


INSPECTOR_LAYOUT_TEXT_INPUT = {
    'visibility': {
        'i18n': {'key': 'inspector.visibility', 'default': 'Visibility'},
        'component': {
            'enabled': [True],
            'attribute': ['visible'],
            'widget': [VisibilityCheckBox]
        }
    },
    'name': {
        'i18n': {'key': 'inspector.name', 'default': 'Name'},
        'component': {
            'enabled': [True],
            'attribute': ['name'],
            'widget': [NameLineEdit]
        }
    },
    'pos': {
        'i18n': {'key': 'inspector.pos', 'default': 'Pos'},
        'component': {
            'enabled': [True, True],
            'attribute': ['x', 'y'],
            'widget': [PosSpinBox, PosSpinBox]
        }
    },
    'size': {
        'i18n': {'key': 'inspector.size', 'default': 'Size'},
        'component': {
            'enabled': [True, True],
            'attribute': ['width', 'height'],
            'widget': [SizeSpinBox, SizeSpinBox]
        }
    },
    'scale': {
        'i18n': {'key': 'inspector.scale', 'default': 'Scale'},
        'component': {
            'enabled': [True, True],
            'attribute': ['scale_x', 'scale_y'],
            'widget': [ScaleSpinBox, ScaleSpinBox]
        }
    },
    'angle': {
        'i18n': {'key': 'inspector.angle', 'default': 'Angle'},
        'component': {
            'enabled': [True],
            'attribute': ['angle'],
            'widget': [AngleSpinBox]
        }
    },
    'color': {
        'i18n': {'key': 'inspector.text_input_text_color', 'default': 'Text Color'},
        'component': {
            'enabled': [True],
            'attribute': ['color'],
            'widget': [ColorPicker]
        }
    },
    'background_color': {
        'i18n': {'key': 'inspector.text_input_background_color', 'default': 'Background Color'},
        'component': {
            'enabled': [True],
            'attribute': ['background_color'],
            'widget': [ColorPicker]
        }
    },
    'border_color': {
        'i18n': {'key': 'inspector.text_input_border_color', 'default': 'Border Color'},
        'component': {
            'enabled': [True],
            'attribute': ['border_color'],
            'widget': [ColorPicker]
        }
    },
    'text': {
        'i18n': {'key': 'inspector.text', 'default': 'Text'},
        'component': {
            'enabled': [True],
            'attribute': ['text'],
            'widget': [TextInputTextEdit]
        }
    },
    'text_align': {
        'i18n': {'key': 'inspector.text_align', 'default': 'H Align'},
        'component': {
            'enabled': [True],
            'attribute': ['text_align'],
            'widget': [AlignmentButtonGroup]
        }
    },
    'text_valign': {
        'i18n': {'key': 'inspector.text_valign', 'default': 'V Align'},
        'component': {
            'enabled': [True],
            'attribute': ['text_valign'],
            'widget': [AlignmentButtonGroup]
        }
    },
    'enter_newline': {
        'i18n': {'key': 'inspector.enter_newline', 'default': 'Enter adds Newline'},
        'component': {
            'enabled': [True],
            'attribute': ['enter_newline'],
            'widget': [TextInputParameterCheckBox]
        }
    },
    'placeholder': {
        'i18n': {'key': 'inspector.placeholder', 'default': 'Placeholder'},
        'component': {
            'enabled': [True],
            'attribute': ['placeholder'],
            'widget': [SingleLineTextEdit]
        }
    },
    'password': {
        'i18n': {'key': 'inspector.password', 'default': 'Password'},
        'component': {
            'enabled': [True],
            'attribute': ['password'],
            'widget': [TextInputParameterCheckBox]
        }
    },
    'max_length': {
        'i18n': {'key': 'inspector.max_length', 'default': 'Max Length'},
        'component': {
            'enabled': [True],
            'attribute': ['max_length'],
            'widget': [TextInputParameterSpinBox]
        }
    },
    'font_size': {
        'i18n': {'key': 'inspector.font_size', 'default': 'Font Size'},
        'component': {
            'enabled': [True],
            'attribute': ['font_size'],
            'widget': [FontSizeSpinBox]
        }
    },
    'font_path': {
        'i18n': {'key': 'inspector.font_path', 'default': 'Font Path'},
        'component': {
            'enabled': [True],
            'attribute': ['font_path'],
            'widget': [FontPathLineEdit]
        }
    },
    'bold': {
        'i18n': {'key': 'inspector.bold', 'default': 'Bold'},
        'component': {
            'enabled': [True],
            'attribute': ['bold'],
            'widget': [BoldCheckBox]
        }
    },
    'italic': {
        'i18n': {'key': 'inspector.italic', 'default': 'Italic'},
        'component': {
            'enabled': [True],
            'attribute': ['italic'],
            'widget': [ItalicCheckBox]
        }
    },
    'underline': {
        'i18n': {'key': 'inspector.underline', 'default': 'Underline'},
        'component': {
            'enabled': [True],
            'attribute': ['underline'],
            'widget': [UnderlineCheckBox]
        }
    },
    'strikethrough': {
        'i18n': {'key': 'inspector.strikethrough', 'default': 'Strikethrough'},
        'component': {
            'enabled': [True],
            'attribute': ['strikethrough'],
            'widget': [StrikethroughCheckBox]
        }
    },
    'border_radius': {
        'i18n': {'key': 'inspector.border_radius', 'default': 'Border Radius'},
        'component': {
            'enabled': [True, True, True, True],
            'attribute': ['border_top_left_radius', 'border_top_right_radius',
                          'border_bottom_left_radius', 'border_bottom_right_radius'],
            'widget': [BorderRadiusSpinBox, BorderRadiusSpinBox,
                       BorderRadiusSpinBox, BorderRadiusSpinBox]
        }
    },
    'script_path': {
        'i18n': {'key': 'inspector.script_path', 'default': 'Script Path'},
        'component': {
            'enabled': [True],
            'attribute': ['script_path'],
            'widget': [ScriptPathLineEdit]
        }
    },
}
