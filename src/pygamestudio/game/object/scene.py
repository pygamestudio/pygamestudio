import uuid
import pygame
import random
from pygamestudio.game.object.type import *
from pygamestudio.common.utils.path import RES_PATH


class ObjectCanvas:
    def __init__(self, game_manager, object_data={}):
        self._is_initialized = False
        self._game_manager = game_manager

        defaults = {
            'name': 'Canvas',
            'type': OBJECT_CANVAS,
            'uuid': str(uuid.uuid4()),
            'is_visible': True,
            'is_expanded': True,
            'is_selected': False,
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
            'icon': str(RES_PATH/'images/item.png'),
            'color': '#000000'
        }

        for key, default_value in defaults.items():
            setattr(self, key, object_data.get(key, default_value))

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.rect(self.surface, self.color, self.surface.get_rect())

        self._is_initialized = True

    def draw(self, parent_surface):
        # self.surface is the canvas surface. No need to draw it on another parent surface.
        ...

    def get_surface(self):
        return self.surface
    
    def set_surface(self, surface):
        self.surface = surface
    
    def get_pos(self):
        return self.pos
    
    def get_world_pos(self):
        return self.get_world_rect().topleft
    
    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.surface.width, self.surface.height)

    def get_world_rect(self):
        world_rect = self.get_rect()

        parent_object = self._game_manager.get_parent_object(self.uuid)
        while parent_object:
            parent_rect = parent_object.get_rect()
            world_rect.move_ip(parent_rect.x, parent_rect.y)
            parent_object = self._game_manager.get_parent_object(parent_object.uuid)

        return world_rect
    
    def check_click_collision(self, click_pos):
        ...
        # if not self.get_world_rect().collidepoint(click_pos):
        #     return False

        # scaled_size = (int(self.width * self.scale_x), int(self.height * self.scale_y))
        # scaled_surface = pygame.transform.scale(self.surface, scaled_size)
        # rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        # rotated_mask = pygame.mask.from_surface(rotated_surface)

        # local_x = click_pos[0] - self.get_world_pos()[0]
        # local_y = click_pos[1] - self.get_world_pos()[1]
        # return rotated_mask.get_at((local_x, local_y))
    
    def update_surface(self):
        # self.surface = pygame.Surface(self.size, pygame.SRCALPHA)

        pygame.draw.rect(self.surface, self.color, self.surface.get_rect())
        if self.is_selected:
            pygame.draw.rect(self.surface, (255, 255, 50), (0, 0, self.surface.width, self.surface.height), 2)

    def get_data(self):
        return self.__dict__.copy()
    
    def set_data(self, data):
        self.__dict__.update(data)

    def to_dict(self):
        exclude_fields = ['_is_initialized', '_game_manager', 'surface', 'icon']
        return {
            key: value for key, value in self.__dict__.items() 
            if key not in exclude_fields
        }
         
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

        # elif name == 'border_radius':
        #     self.border_radius = value
        #     self.border_top_left_radius = value[0]
        #     self.border_top_right_radius = value[1]
        #     self.bor

        super().__setattr__(name, value)
         