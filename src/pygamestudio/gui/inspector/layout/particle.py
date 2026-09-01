from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.checkbox import *


INSPECTOR_LAYOUT_PARTICLE = {
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
    'emission_rate': {
        'i18n': {
            'key': 'inspector.emission_rate',
            'default': 'Emission Rate'
        },
        'component': {
            'enabled': [True],
            'attribute': ['emission_rate'],
            'widget': [ParticleParameterSpinBox]
        }
    },
    'max_particles': {
        'i18n': {
            'key': 'inspector.max_particles',
            'default': 'Max Particles'
        },
        'component': {
            'enabled': [True],
            'attribute': ['max_particles'],
            'widget': [ParticleParameterSpinBox]
        }
    },
    'particle_lifetime': {
        'i18n': {
            'key': 'inspector.particle_lifetime',
            'default': 'Lifetime'
        },
        'component': {
            'enabled': [True],
            'attribute': ['particle_lifetime'],
            'widget': [ParticleParameterSpinBox]
        }
    },
    'particle_speed': {
        'i18n': {
            'key': 'inspector.particle_speed',
            'default': 'Speed'
        },
        'component': {
            'enabled': [True],
            'attribute': ['particle_speed'],
            'widget': [ParticleParameterSpinBox]
        }
    },
    'particle_size': {
        'i18n': {
            'key': 'inspector.particle_size',
            'default': 'Particle Size'
        },
        'component': {
            'enabled': [True],
            'attribute': ['particle_size'],
            'widget': [ParticleParameterSpinBox]
        }
    },
    'gravity': {
        'i18n': {
            'key': 'inspector.gravity',
            'default': 'Gravity'
        },
        'component': {
            'enabled': [True],
            'attribute': ['gravity'],
            'widget': [ParticleParameterSpinBox]
        }
    },
    'spread_angle': {
        'i18n': {
            'key': 'inspector.spread_angle',
            'default': 'Spread Angle'
        },
        'component': {
            'enabled': [True],
            'attribute': ['spread_angle'],
            'widget': [ParticleParameterSpinBox]
        }
    },
    'particle_image': {
        'i18n': {
            'key': 'inspector.particle_image',
            'default': 'Particle Image'
        },
        'component': {
            'enabled': [True],
            'attribute': ['particle_image'],
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
