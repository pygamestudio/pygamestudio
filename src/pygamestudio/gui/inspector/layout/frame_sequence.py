from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.checkbox import *


INSPECTOR_LAYOUT_FRAME_SEQUENCE = {
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
    'auto_play': {
        'i18n': {
            'key': 'inspector.auto_play',
            'default': 'Auto Play'
        },
        'component': {
            'enabled': [True],
            'attribute': ['auto_play'],
            'widget': [FrameSequenceCheckBox]
        }
    },
    'loop': {
        'i18n': {
            'key': 'inspector.loop',
            'default': 'Loop'
        },
        'component': {
            'enabled': [True],
            'attribute': ['loop'],
            'widget': [FrameSequenceCheckBox]
        }
    },
    'frame_rate': {
        'i18n': {
            'key': 'inspector.frame_rate',
            'default': 'Frame Rate'
        },
        'component': {
            'enabled': [True],
            'attribute': ['frame_rate'],
            'widget': [FrameSequenceSpinBox]
        }
    },
    'frame_folder': {
        'i18n': {
            'key': 'inspector.frame_folder',
            'default': 'Frame Folder'
        },
        'component': {
            'enabled': [True],
            'attribute': ['frame_folder'],
            'widget': [FrameFolderLineEdit]
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
