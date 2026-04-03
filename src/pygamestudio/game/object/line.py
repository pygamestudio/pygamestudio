import uuid
import random
import pygame
from pygamestudio.game.object.type import *
from pygamestudio.common.utils.path import RES_PATH


class ObjectLine:
    def __init__(self, game_manager, object_data=None):
        self._is_initialized = False

        self._game_manager = game_manager
        self._object_data = object_data or {}

        self.name = self._object_data.get('name', 'Line')
        self.type = self._object_data.get('type', OBJECT_LINE)
        self.uuid = self._object_data.get('uuid', str(uuid.uuid4()))
        self.is_visible = self._object_data.get('is_visible', True)
        self.is_expanded = self._object_data.get('is_expanded', True)
        self.is_selected = self._object_data.get('is_selected', False)

        self.thickness = self._object_data.get('thickness', 2)
        self.start_x = self._object_data.get('start_x', 0)
        self.start_y = self._object_data.get('start_y', 0)
        self.start_point = self._object_data.get('start_point', (self.start_x, self.start_y))
        self.end_x = self._object_data.get('end_x', 100)
        self.end_y = self._object_data.get('end_y', 100)
        self.end_point = self._object_data.get('end_point', (self.end_x, self.end_y))

        self.x = self._object_data.get('x', self.start_x)
        self.y = self._object_data.get('y', self.start_y)
        self.pos = self._object_data.get('pos', (self.x, self.y))
        self.width = self._object_data.get('width', self.end_x-self.start_x+self.thickness)
        self.height = self._object_data.get('height', self.end_y-self.start_y+self.thickness)
        self.size = self._object_data.get('size', (self.width, self.height))
        self.scale_x = self._object_data.get('scale_x', 1)
        self.scale_y = self._object_data.get('scale_y', 1)
        self.scale = self._object_data.get('scale', (1, 1))
        self.angle = self._object_data.get('angle', 0)
        self.icon = self._object_data.get('icon', str(RES_PATH/'images/item.png'))
        self.color = self._object_data.get('color', random.choice(['#ff0000', '#00ff00', '#0000ff']))
        
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.line(self.surface, self.color, (0, 0), (self.surface.width-self.thickness, self.surface.height-self.thickness), width=self.thickness)

        self._is_initialized = True

    def draw(self, parent_surface):
        parent_surface.blit(self.surface, self.get_rect())
    
    def get_surface(self):
        return self.surface
    
    def update_surface(self):
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        
        x1, y1, x2, y2 = 0, 0, 0, 0
        if self.start_x <= self.end_x:
            x1 = 0
            x2 = self.surface.width-self.thickness
        else:
            x1 = self.surface.width-self.thickness
            x2 = 0

        if self.start_y <= self.end_y:
            y1 = 0
            y2 = self.surface.height-self.thickness
        else:
            y1 = self.surface.height-self.thickness
            y2 = 0

        if self.is_selected:
            pygame.draw.line(self.surface, (255, 255, 50), (x1, y1), (x2, y2), width=self.thickness+8)
        pygame.draw.line(self.surface, self.color, (x1, y1), (x2, y2), width=self.thickness)
        
        scaled_surface = pygame.transform.scale_by(self.surface, (self.scale_x, self.scale_y))

        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self.surface = rotated_surface

    def get_pos(self):
        return self.pos
    
    def get_world_pos(self):
        return self.get_world_rect().topleft

    def get_rect(self):
        # Get the rect of the object. Note that the rect returned by Surface.get_rect() always starts at (0, 0).
        return pygame.FRect(min(self.start_x, self.end_x), min(self.start_y, self.end_y), self.surface.width, self.surface.height)

    def get_world_rect(self):
        world_rect = self.get_rect()
        parent_object = self._game_manager.get_parent_object(self.uuid)

        while parent_object:
            parent_rect = parent_object.get_rect()
            world_rect.move_ip(parent_rect.x, parent_rect.y)
            parent_object = self._game_manager.get_parent_object(parent_object.uuid)

        return world_rect 

    def get_data(self):
        return self._object_data
    
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
 
            if self.start_x <= self.end_x:
                self.start_x = self.x
                self.end_x = self.start_x + self.width - self.thickness
            else:
                self.end_x = self.x
                self.start_x = self.end_x + self.width - self.thickness

            if self.start_y <= self.end_y:
                self.start_y = self.y
                self.end_y = self.start_y + self.height - self.thickness
            else:
                self.end_y = self.y
                self.start_y = self.end_y + self.height - self.thickness

            object.__setattr__(self, 'start_point', (self.start_x, self.start_y))
            object.__setattr__(self, 'end_point', (self.end_x, self.end_y))

        elif name == 'start_point':
            self.start_x = value[0]
            self.start_y = value[1]
            self.x = min(self.start_x, self.end_x)
            self.y = min(self.start_y, self.end_y)
            self.width = abs(self.end_x - self.start_x) + self.thickness
            self.height = abs(self.end_y - self.start_y) + self.thickness
            self.size = (self.width, self.height)

        elif name == 'end_point':
            self.end_x = value[0]
            self.end_y = value[1]
            self.x = min(self.start_x, self.end_x)
            self.y = min(self.start_y, self.end_y)
            self.width = abs(self.end_x - self.start_x) + self.thickness
            self.height = abs(self.end_y - self.start_y) + self.thickness
            self.size = (self.width, self.height)

        elif name == 'scale':
            self.scale_x = value[0]
            self.scale_y = value[1]

        elif name == 'thickness':
            self.width = abs(self.end_x - self.start_x) + value
            self.height = abs(self.end_y - self.start_y) + value

        super().__setattr__(name, value)
         