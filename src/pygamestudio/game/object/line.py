import uuid
import pygame
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase


class ObjectLine(ObjectBase):
    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/line.png'

        common_properties = {
            'name': 'Line',
            'type': OBJECT_LINE,
            'uuid': str(uuid.uuid4()),
            'x': 0,
            'y': 0,
            'pos': (0, 0),
            'width': 100, 
            'height': 100,
            'size': (100, 100),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': '#ffffff',
            'is_visible': True,
            'thickness': 2,
            'start_x': 0,
            'start_y': 0,
            'start_point': (0, 0),
            'end_x': 100,
            'end_y': 100,
            'end_point': (100, 100)
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))
        
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self._is_initialized = True

    def _update_bounding_box(self):
        x = min(self.start_x, self.end_x)
        y = min(self.start_y, self.end_y)
        w = abs(self.end_x - self.start_x) + self.thickness
        h = abs(self.end_y - self.start_y) + self.thickness

        super().__setattr__('x', x)
        super().__setattr__('y', y)
        super().__setattr__('pos', (x, y))
        super().__setattr__('width', w)
        super().__setattr__('height', h)
        super().__setattr__('size', (w, h))

    def update_surface(self):
        self._update_bounding_box()

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.line(self.surface, self.color, (0, 0), (self.surface.width-self.thickness, self.surface.height-self.thickness), width=self.thickness)
        
        scaled_size = (self.surface.width * self.scale_x, self.surface.height * self.scale_y)
        scaled_surface = pygame.transform.scale(self.surface, scaled_size)

        if not self._is_for_api and self.is_selected:
            pygame.draw.rect(scaled_surface, (255, 255, 50), scaled_surface.get_rect(), width=2)
        
        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self.surface = rotated_surface

    def __setattr__(self, name, value):
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return

        if name =='pos':
            # attrs like x, y, pos will be updated in _update_bounding_box()
            dx = value[0] - self.x
            dy = value[1] - self.y

            new_start_x = self.start_x + dx
            new_start_y = self.start_y + dy
            new_end_x = self.end_x + dx
            new_end_y = self.end_y + dy

            self.start_point = (new_start_x, new_start_y)
            self.end_point = (new_end_x, new_end_y)

        elif name == 'start_point':
            super().__setattr__('start_x', value[0])
            super().__setattr__('start_y', value[1])
            super().__setattr__('start_point', value)

        elif name == 'end_point':
            super().__setattr__('end_x', value[0])
            super().__setattr__('end_y', value[1])
            super().__setattr__('end_point', value)

        else:
            super().__setattr__(name, value)