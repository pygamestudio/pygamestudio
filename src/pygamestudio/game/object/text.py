import uuid
import random
import pygame
from pygamestudio.game.object.type import *
from pygamestudio.common.utils.path import RES_PATH


class ObjectText:
    def __init__(self, obj_data=None):
        obj_data = obj_data or {}
        self.x = obj_data.get('x', 0)
        self.y = obj_data.get('y', 0)
        self.pos = obj_data.get('pos', (0, 0))
        self.width = obj_data.get('width', 50)
        self.height = obj_data.get('height', 50)
        self.icon = obj_data.get('icon', str(RES_PATH/'images/item.png'))
        self.color = obj_data.get('color', random.choice(['#ff0000', '#00ff00', '#0000ff']))
        
        self.name = obj_data.get('name', 'Text')
        self.type = obj_data.get('type', OBJECT_TEXT)
        self.uuid = obj_data.get('uuid', str(uuid.uuid4()))
        self.parent_uuid = obj_data.get('parent_uuid', '')
        self.is_visible = obj_data.get('is_visible', True)
        self.is_expanded = obj_data.get('is_expanded', True)
        self.is_selected = obj_data.get('is_selected', False)

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, (self.x, self.y, self.width, self.height))

    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def get_data(self):
        return self.__dict__.copy()
    
    def set_data(self, data):
        self.__dict__.update(data)
    
    def __setattr__(self, name, value):
        if name == 'pos':
            self.x = value[0]
            self.y = value[1]

        super().__setattr__(name, value)