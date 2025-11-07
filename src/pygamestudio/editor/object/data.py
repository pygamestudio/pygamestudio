from pygamestudio.common.utils.path import RES_PATH


DEFAULT_RECT_ITEM_DATA = {
    'uuid': '',
    'type': 'RECT',
    'name': 'Rect',
    'icon': str(RES_PATH/'images/item.png'),
    'rect': (50, 50, 100, 80),
    'color': (255, 255, 255),
    'isVisible': True,
    'isSelected': False,
    'isExpanded': False,
}

DEFAULT_TEXT_ITEM_DATA = {
    'uuid': '',
    'type': 'TEXT',
    'name': 'Text',
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
    'type': 'CIRCLE',
    'name': 'Circle',
    'icon': str(RES_PATH/'images/item.png'),
    'center': (0, 0),
    'radius': 50,
    'color': (255, 255, 255),
    'isVisible': True,
    'isSelected': False,
    'isExpanded': False,
}