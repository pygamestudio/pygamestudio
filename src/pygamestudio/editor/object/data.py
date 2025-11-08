from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.editor.object.type import *

DEFAULT_RECT_ITEM_DATA = {
    'uuid': '',
    'name': 'Rect',
    'type': ITEM_RECT,
    'icon': str(RES_PATH/'images/item.png'),
    'rect': (50, 50, 100, 80),
    'color': (255, 255, 255),
    'isVisible': True,
    'isSelected': False,
    'isExpanded': False,
}

DEFAULT_TEXT_ITEM_DATA = {
    'uuid': '',
    'name': 'Text',
    'type': ITEM_TEXT,
    'icon': str(RES_PATH/'images/item.png'),
    'text': 'text',
    'pos': (0, 0),
    'color': (255, 255, 255),
    'isVisible': True,
    'isSelected': False,
    'isExpanded': False,
}

DEFAULT_CIRCLE_ITEM_DATA = {
    'uuid': '',
    'name': 'Circle',
    'type': ITEM_CIRCLE,
    'icon': str(RES_PATH/'images/item.png'),
    'center': (0, 0),
    'radius': 50,
    'color': (255, 255, 255),
    'isVisible': True,
    'isSelected': False,
    'isExpanded': False,
}