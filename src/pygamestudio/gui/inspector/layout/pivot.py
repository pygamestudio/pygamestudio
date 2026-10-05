from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.combo import PivotComboBox
from pygamestudio.gui.inspector.component.spinbox import PivotSpinBox


_PIVOT = {
    'i18n': {
        'key': 'inspector.pivot',
        'default': 'Pivot'
    },
    'component': {
        'enabled': [True],
        'attribute': ['pivot'],
        'widget': [PivotComboBox]
    }
}

_PIVOT_POINT = {
    'i18n': {
        'key': 'inspector.pivot_point',
        'default': 'Pivot Point'
    },
    'component': {
        'enabled': [True, True],
        'attribute': ['pivot_x', 'pivot_y'],
        'widget': [PivotSpinBox, PivotSpinBox]
    }
}


def build_pivot_layout(pivot_mode='center'):
    """Rows of the shared pivot section.

    Every object except the canvas root carries it: the anchor combo (which
    point of the object's own pixel grid rotation and scaling - a negative
    scale included - happen around), plus the free coordinates while
    'custom' is selected. The rows are rebuilt when the mode changes, like
    the collision / physics sections.
    """
    layout = {
        'pivot': _PIVOT,
    }
    if pivot_mode == 'custom':
        layout['pivot_point'] = _PIVOT_POINT
    return layout
