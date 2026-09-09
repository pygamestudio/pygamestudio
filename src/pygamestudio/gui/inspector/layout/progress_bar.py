from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.checkbox import *


INSPECTOR_LAYOUT_PROGRESS_BAR = {
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
    'progress': {
        'i18n': {
            'key': 'inspector.progress_bar_progress',
            'default': 'Progress'
        },
        'component': {
            'enabled': [True],
            'attribute': ['progress'],
            'widget': [ProgressBarValueSpinBox]
        }
    },
    'background_color': {
        'i18n': {
            'key': 'inspector.progress_bar_background_color',
            'default': 'Background Color'
        },
        'component': {
            'enabled': [True],
            'attribute': ['background_color'],
            'widget': [ColorPicker]
        }
    },
    'foreground_color': {
        'i18n': {
            'key': 'inspector.progress_bar_foreground_color',
            'default': 'Foreground Color'
        },
        'component': {
            'enabled': [True],
            'attribute': ['foreground_color'],
            'widget': [ColorPicker]
        }
    },
    'background_image_path': {
        'i18n': {
            'key': 'inspector.progress_bar_background_image',
            'default': 'Background Image'
        },
        'component': {
            'enabled': [True],
            'attribute': ['background_image_path'],
            'widget': [ImagePathLineEdit]
        }
    },
    'foreground_image_path': {
        'i18n': {
            'key': 'inspector.progress_bar_foreground_image',
            'default': 'Foreground Image'
        },
        'component': {
            'enabled': [True],
            'attribute': ['foreground_image_path'],
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
