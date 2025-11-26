from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.editor.asset.type import *


DEFAULT_FOLDER_ITEM_DATA = {
    'uuid': '',
    'name': 'new folder',
    'type': ITEM_FOLDER,
    'path': '',
    'icon': str(RES_PATH/'images/folder.png'),
    'isExpanded': True,
    'isRootItem': False,
}

DEFAULT_FILE_SCENE_ITEM_DATA = {
    'uuid': '',
    'name': 'new scene',
    'type': ITEM_SCENE,
    'path': '',
    'icon': str(RES_PATH/'images/scene.png'),
    'isExpanded': False,
}

DEFAULT_FILE_SCRIPT_ITEM_DATA = {
    'uuid': '',
    'name': 'new py',
    'type': ITEM_SCRIPT,
    'path': '',
    'icon': str(RES_PATH/'images/py.png'),
    'isExpanded': False,
}

DEFAULT_FILE_TXT_ITEM_DATA = {
    'uuid': '',
    'name': 'new txt',
    'type': ITEM_TXT,
    'path': '',
    'icon': str(RES_PATH/'images/txt.png'),
    'isExpanded': False,
}

DEFAULT_FILE_JSON_ITEM_DATA = {
    'uuid': '',
    'name': 'new json',
    'type': ITEM_SCRIPT,
    'path': '',
    'icon': str(RES_PATH/'images/json.png'),
    'isExpanded': False,
}

DEFAULT_OTHER_FILE_ITEM_DATA = {
    'uuid': '',
    'name': 'file',
    'type': ITEM_OTHER,
    'path': '',
    'icon': str(RES_PATH/'images/other.png'),
    'isExpanded': False,
}