from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.spinbox import *
from pygamestudio.gui.inspector.component.lineedit import *
from pygamestudio.gui.inspector.component.picker import *
from pygamestudio.gui.inspector.component.checkbox import *


INSPECTOR_LAYOUT_TILE_MAP = {
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
    # The pixel size is DERIVED from the grid (columns*tile_width x rows*
    # tile_height), so it is shown read-only.
    'size': {
        'i18n': {
            'key': 'inspector.size',
            'default': 'Size'
        },
        'component': {
            'enabled': [False, False],
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
    'tileset_path': {
        'i18n': {
            'key': 'inspector.tileset_path',
            'default': 'Tileset Path'
        },
        'component': {
            'enabled': [True],
            'attribute': ['tileset_path'],
            'widget': [TilesetPathLineEdit]
        }
    },
    'tile_width': {
        'i18n': {
            'key': 'inspector.tile_width',
            'default': 'Tile Width'
        },
        'component': {
            'enabled': [True],
            'attribute': ['tile_width'],
            'widget': [TileMapSpinBox]
        }
    },
    'tile_height': {
        'i18n': {
            'key': 'inspector.tile_height',
            'default': 'Tile Height'
        },
        'component': {
            'enabled': [True],
            'attribute': ['tile_height'],
            'widget': [TileMapSpinBox]
        }
    },
    'columns': {
        'i18n': {
            'key': 'inspector.columns',
            'default': 'Columns'
        },
        'component': {
            'enabled': [True],
            'attribute': ['columns'],
            'widget': [TileMapSpinBox]
        }
    },
    'rows': {
        'i18n': {
            'key': 'inspector.rows',
            'default': 'Rows'
        },
        'component': {
            'enabled': [True],
            'attribute': ['rows'],
            'widget': [TileMapSpinBox]
        }
    },
}
