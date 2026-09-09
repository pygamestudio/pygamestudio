from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.checkbox import *


INSPECTOR_LAYOUT_SLIDER = {
    'visibility': {
        'i18n': {
            'key': 'inspector.visibility',
            'default': 'Visibility'
        },
        'component': {
            'enabled': [True],
            'attribute': ['visible'],
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
    'value': {
        'i18n': {
            'key': 'inspector.slider_value',
            'default': 'Value'
        },
        'component': {
            'enabled': [True],
            'attribute': ['value'],
            'widget': [SliderParameterSpinBox]
        }
    },
    'min_value': {
        'i18n': {
            'key': 'inspector.slider_min_value',
            'default': 'Min Value'
        },
        'component': {
            'enabled': [True],
            'attribute': ['min_value'],
            'widget': [SliderParameterSpinBox]
        }
    },
    'max_value': {
        'i18n': {
            'key': 'inspector.slider_max_value',
            'default': 'Max Value'
        },
        'component': {
            'enabled': [True],
            'attribute': ['max_value'],
            'widget': [SliderParameterSpinBox]
        }
    },
    'handle_width': {
        'i18n': {
            'key': 'inspector.slider_handle_width',
            'default': 'Handle Width'
        },
        'component': {
            'enabled': [True],
            'attribute': ['handle_width'],
            'widget': [SliderParameterSpinBox]
        }
    },
    'handle_height': {
        'i18n': {
            'key': 'inspector.slider_handle_height',
            'default': 'Handle Height'
        },
        'component': {
            'enabled': [True],
            'attribute': ['handle_height'],
            'widget': [SliderParameterSpinBox]
        }
    },
    'track_thickness': {
        'i18n': {
            'key': 'inspector.slider_track_thickness',
            'default': 'Track Thickness'
        },
        'component': {
            'enabled': [True],
            'attribute': ['track_thickness'],
            'widget': [SliderParameterSpinBox]
        }
    },
    'track_color': {
        'i18n': {
            'key': 'inspector.slider_track_color',
            'default': 'Track Color'
        },
        'component': {
            'enabled': [True],
            'attribute': ['track_color'],
            'widget': [ColorPicker]
        }
    },
    'fill_color': {
        'i18n': {
            'key': 'inspector.slider_fill_color',
            'default': 'Fill Color'
        },
        'component': {
            'enabled': [True],
            'attribute': ['fill_color'],
            'widget': [ColorPicker]
        }
    },
    'handle_color': {
        'i18n': {
            'key': 'inspector.slider_handle_color',
            'default': 'Handle Color'
        },
        'component': {
            'enabled': [True],
            'attribute': ['handle_color'],
            'widget': [ColorPicker]
        }
    },
    'track_image_path': {
        'i18n': {
            'key': 'inspector.slider_track_image',
            'default': 'Track Image'
        },
        'component': {
            'enabled': [True],
            'attribute': ['track_image_path'],
            'widget': [ImagePathLineEdit]
        }
    },
    'fill_image_path': {
        'i18n': {
            'key': 'inspector.slider_fill_image',
            'default': 'Fill Image'
        },
        'component': {
            'enabled': [True],
            'attribute': ['fill_image_path'],
            'widget': [ImagePathLineEdit]
        }
    },
    'handle_image_path': {
        'i18n': {
            'key': 'inspector.slider_handle_image',
            'default': 'Handle Image'
        },
        'component': {
            'enabled': [True],
            'attribute': ['handle_image_path'],
            'widget': [ImagePathLineEdit]
        }
    },
    'script_path': {
        'i18n': {
            'key': 'inspector.script_path',
            'default': 'Script Path'
        },
        'component': {
            'enabled': [True],
            'attribute': ['script_path'],
            'widget': [ScriptPathLineEdit]
        }
    },
}
