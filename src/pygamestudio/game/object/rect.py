import uuid
import pygame
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase


class ObjectRect(ObjectBase):
    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/rect.png'

        common_properties = {
            'name': 'Rect',
            'type': OBJECT_RECT,
            'uuid': str(uuid.uuid4()),
            'x': 20,
            'y': 20,
            'pos': (20, 20),
            'width': 50, 
            'height': 50,
            'size': (50, 50),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': (255, 255, 255, 255),
            'visible': True,
            'border_top_left_radius': 0,
            'border_top_right_radius': 0,
            'border_bottom_left_radius': 0,
            'border_bottom_right_radius': 0
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self._is_initialized = True

        self._start()

    def get_border_top_left_radius(self) -> int:
        return self.border_top_left_radius

    def get_border_top_right_radius(self) -> int:
        return self.border_top_right_radius
    
    def get_border_bottom_left_radius(self) -> int:
        return self.border_bottom_left_radius 

    def get_border_bottom_right_radius(self) -> int:
        return self.border_bottom_right_radius

    def get_border_radius(self) -> tuple:
        """All four corner radii as (top_left, top_right, bottom_left, bottom_right)."""
        return (self.border_top_left_radius, self.border_top_right_radius,
                self.border_bottom_left_radius, self.border_bottom_right_radius)

    def set_border_top_left_radius(self,  radius:int):
        self.border_top_left_radius = radius

    def set_border_top_right_radius(self,  radius:int):
        self.border_top_right_radius = radius
    
    def set_border_bottom_left_radius(self,  radius:int):
        self.border_bottom_left_radius = radius

    def set_border_bottom_right_radius(self,  radius:int):
        self.border_bottom_right_radius = radius

    def set_border_radius(self, radius):
        """Set all four corners at once: pass a single int, or a 4-item
        tuple/list (top_left, top_right, bottom_left, bottom_right)."""
        if isinstance(radius, (tuple, list)):
            (self.border_top_left_radius, self.border_top_right_radius,
             self.border_bottom_left_radius, self.border_bottom_right_radius) = radius
        else:
            self.border_top_left_radius = radius
            self.border_top_right_radius = radius
            self.border_bottom_left_radius = radius
            self.border_bottom_right_radius = radius

    def _update_surface(self):
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.rect(self.surface, self.color[0:3], self.surface.get_rect(), width=0,
                         border_radius=-1, border_top_left_radius=self.border_top_left_radius, border_top_right_radius=self.border_top_right_radius,
                         border_bottom_left_radius=self.border_bottom_left_radius, border_bottom_right_radius=self.border_bottom_right_radius)
        
        scaled_size = (self.surface.width * self.scale_x, self.surface.height * self.scale_y)
        scaled_surface = pygame.transform.scale(self.surface, scaled_size)
        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self.surface = self._apply_alpha(rotated_surface)

        super()._update_surface()