import uuid
import pygame
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase


class ObjectEllipse(ObjectBase):
    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/ellipse.png'

        common_properties = {
            'name': 'Ellipse',
            'type': OBJECT_ELLIPSE,
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
            'color': '#ffffff',
            'is_visible': True,
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))
        
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self._is_initialized = True

    def update_surface(self):
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.ellipse(self.surface, self.color, self.surface.get_rect())
        
        scaled_size = (self.surface.width * self.scale_x, self.surface.height * self.scale_y)
        scaled_surface = pygame.transform.scale(self.surface, scaled_size)

        if not self._is_for_api and self.is_selected:
            pygame.draw.ellipse(scaled_surface, (255, 255, 50), scaled_surface.get_rect(), 2)

        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self.surface = rotated_surface