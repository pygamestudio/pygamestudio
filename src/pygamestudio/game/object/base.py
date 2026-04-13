
import uuid
import random
import pygame
from pygamestudio.game.object.type import *
from pygamestudio.common.utils.path import RES_PATH


class ObjectBase:
    def __init__(self, game_manager, object_data={}, is_for_api=False):
        self._is_initialized = False
        self._is_for_api = is_for_api
        self._game_manager = game_manager

        internal_properties = {
            'is_expanded': True,
            'is_selected': False,
            'icon': str(RES_PATH/'images/item.png'),
        }
        
        common_properties = {
            'name': 'Base',
            'type': OBJECT_BASE,
            'uuid': str(uuid.uuid4()),
            'x': 0,
            'y': 0,
            'pos': (0, 0),
            'width': 50, 
            'height': 50,
            'size': (50, 50),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': random.choice(['#ff0000', '#00ff00', '#0000ff']),
            'is_visible': True,
        }
    
        if not self._is_for_api:
            for key, value in internal_properties.items():
                setattr(self, key, object_data.get(key, value))

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self._is_initialized = True

    def draw(self, parent_surface):
        parent_surface.blit(self.surface, self.get_rect())

    def get_surface(self):
        return self.surface
    
    def update_surface(self):
        ...

    def get_pos(self):
        return self.pos
    
    def get_world_pos(self):
        return self.get_world_rect().topleft

    def get_rect(self):
        # Get the rect of the object. Note that the rect returned by Surface.get_rect() always starts at (0, 0).
        return pygame.FRect(self.x, self.y, self.surface.width, self.surface.height)

    def get_world_rect(self):
        world_rect = self.get_rect()
        parent_object = self._game_manager.get_parent_object(self.uuid)

        while parent_object:
            parent_rect = parent_object.get_rect()
            world_rect.move_ip(parent_rect.x, parent_rect.y)
            parent_object = self._game_manager.get_parent_object(parent_object.uuid)

        return world_rect 

    def get_data(self):
        return self.__dict__.copy()
    
    def set_data(self, data):
        self.__dict__.update(data)

    def check_click_collision(self, click_pos):
        if not self.get_world_rect().collidepoint(click_pos):
            return False

        rotated_mask = pygame.mask.from_surface(self.surface)
        local_x = click_pos[0] - self.get_world_pos()[0]
        local_y = click_pos[1] - self.get_world_pos()[1]
        return rotated_mask.get_at((local_x, local_y))
    
    def to_dict(self):
        exclude_fields = ['_is_initialized', '_game_manager', 'surface', 'icon']
        return {
            key: value for key, value in self.__dict__.items() 
            if key not in exclude_fields
        }
    
    def __str__(self):
        return str(self._object_data)

    def __repr__(self):
        return str(self._object_data)
    
    def __setattr__(self, name, value):
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return
        
        if name == 'pos':
            self.x = value[0]
            self.y = value[1]

        elif name == 'size':
            self.width = value[0]
            self.height = value[1]

        elif name == 'scale':
            self.scale_x = value[0]
            self.scale_y = value[1]

        super().__setattr__(name, value)