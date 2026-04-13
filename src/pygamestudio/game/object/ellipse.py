import pygame
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import RES_PATH


class ObjectEllipse(ObjectBase):
    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        if hasattr(self, 'icon'):
            self.icon = str(RES_PATH/'images/item.png')

        self.name = 'Ellipse'
        self.type = OBJECT_ELLIPSE

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.ellipse(self.surface, self.color, self.surface.get_rect())
    
    def update_surface(self):
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.ellipse(self.surface, self.color, self.surface.get_rect())
        
        scaled_size = (self.width * self.scale_x, self.height * self.scale_y)
        scaled_surface = pygame.transform.scale(self.surface, scaled_size)

        if not self._is_for_api and self.is_selected:
            pygame.draw.ellipse(scaled_surface, (255, 255, 50), scaled_surface.get_rect(), 2)

        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self.surface = rotated_surface