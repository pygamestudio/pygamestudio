import uuid
from pygamestudio.game.object.type import *
from pygamestudio.common.utils.path import RES_PATH


class ObjectScene:
    def __init__(self, obj_data=None):
        obj_data = obj_data or {}
        self.icon = obj_data.get('icon', str(RES_PATH/'images/item.png'))
        self.name = obj_data.get('name', 'Scene')
        self.type = obj_data.get('type', OBJECT_SCENE)
        self.uuid = obj_data.get('uuid', str(uuid.uuid4()))
        self.parent_uuid = obj_data.get('parent_uuid', '')
        self.is_visible = obj_data.get('is_visible', True)
        self.is_expanded = obj_data.get('is_expanded', True)
        self.is_selected = obj_data.get('is_selected', False)

    def get_data(self):
        return self.__dict__.copy()
    
    def set_data(self, data):
        self.__dict__.update(data)
         