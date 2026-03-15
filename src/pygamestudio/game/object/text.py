import uuid
import random
import pygame
from pygamestudio.game.object.type import *
from pygamestudio.common.utils.path import RES_PATH


class ObjectText:
    def __init__(self, object_manager, object_data=None):
        self._is_initialized = False

        self._object_manager = object_manager
        object_data = object_data or {}

        self.name = object_data.get('name', 'Text')
        self.type = object_data.get('type', OBJECT_TEXT)
        self.uuid = object_data.get('uuid', str(uuid.uuid4()))
        self.is_visible = object_data.get('is_visible', True)
        self.is_expanded = object_data.get('is_expanded', True)
        self.is_selected = object_data.get('is_selected', False)

        self.text = object_data.get('string', 'Text')
        self.background_color = object_data.get('color', random.choice(['#ff0000', '#00ff00', '#0000ff']))
        self.font = object_data.get

        self.x = object_data.get('x', 0)
        self.y = object_data.get('y', 0)
        self.pos = object_data.get('pos', (0, 0))
        self.width = object_data.get('width', 50)
        self.height = object_data.get('height', 50)
        self.size = object_data.get('size', (50, 50))
        self.scale_x = object_data.get('scale_x', 1)
        self.scale_y = object_data.get('scale_y', 1)
        self.scale = object_data.get('scale', (1, 1))
        self.angle = object_data.get('angle', 50)
        self.icon = object_data.get('icon', str(RES_PATH/'images/item.png'))
        self.color = object_data.get('color', random.choice(['#ff0000', '#00ff00', '#0000ff']))

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.rect(self.surface, self.color, self.surface.get_rect(), width=0,
                         border_radius=-1, border_top_left_radius=self.border_top_left_radius, border_top_right_radius=self.border_top_right_radius,
                         border_bottom_left_radius=self.border_bottom_left_radius, border_bottom_right_radius=self.border_bottom_right_radius)

        self._is_initialized = True

    def draw(self, parent_surface):
        parent_surface.blit(self.surface, self.get_rect())
    
    def get_surface(self):
        return self.surface
    
    def update_surface(self):
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.rect(self.surface, self.color, self.surface.get_rect(), width=0,
                         border_radius=-1, border_top_left_radius=self.border_top_left_radius, border_top_right_radius=self.border_top_right_radius,
                         border_bottom_left_radius=self.border_bottom_left_radius, border_bottom_right_radius=self.border_bottom_right_radius)

        
        scaled_size = (self.width * self.scale_x, self.height * self.scale_y)
        scaled_surface = pygame.transform.scale(self.surface, scaled_size)

        if self.is_selected:
            pygame.draw.rect(scaled_surface, (255, 255, 50), scaled_surface.get_rect(), width=2,
                             border_radius=-1, border_top_left_radius=self.border_top_left_radius, border_top_right_radius=self.border_top_right_radius,
                             border_bottom_left_radius=self.border_bottom_left_radius, border_bottom_right_radius=self.border_bottom_right_radius)

        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self.surface = rotated_surface

    def get_pos(self):
        return self.pos
    
    def get_world_pos(self):
        return self.get_world_rect().topleft

    def get_rect(self):
        # Get the rect of the object. Note that the rect returned by Surface.get_rect() always starts at (0, 0).
        return pygame.FRect(self.x, self.y, self.surface.width, self.surface.height)

    def get_world_rect(self):
        world_rect = self.get_rect()
        parent_object = self._object_manager.get_parent_object(self.uuid)

        while parent_object:
            parent_rect = parent_object.get_rect()
            world_rect.move_ip(parent_rect.x, parent_rect.y)
            parent_object = self._object_manager.get_parent_object(parent_object.uuid)

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

    def __str__(self):
        return self.__dict__.copy()
    
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
         