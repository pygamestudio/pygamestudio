import pygame
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import RES_PATH


class ObjectRect(ObjectBase):
    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        if hasattr(self, 'icon'):
            self.icon = str(RES_PATH/'images/item.png')

        self.name = 'Rect'
        self.type = OBJECT_RECT
        self.border_top_left_radius = 0
        self.border_top_right_radius = 0
        self.border_bottom_left_radius = 0
        self.border_bottom_right_radius = 0

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.rect(self.surface, self.color, self.surface.get_rect(), width=0,
                         border_radius=-1, border_top_left_radius=self.border_top_left_radius, border_top_right_radius=self.border_top_right_radius,
                         border_bottom_left_radius=self.border_bottom_left_radius, border_bottom_right_radius=self.border_bottom_right_radius)
    
    def update_surface(self):
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.rect(self.surface, self.color, self.surface.get_rect(), width=0,
                         border_radius=-1, border_top_left_radius=self.border_top_left_radius, border_top_right_radius=self.border_top_right_radius,
                         border_bottom_left_radius=self.border_bottom_left_radius, border_bottom_right_radius=self.border_bottom_right_radius)
        
        scaled_size = (self.width * self.scale_x, self.height * self.scale_y)
        scaled_surface = pygame.transform.scale(self.surface, scaled_size)

        if not self._is_for_api and self.is_selected:
            pygame.draw.rect(scaled_surface, (255, 255, 50), scaled_surface.get_rect(), width=2,
                             border_radius=-1, border_top_left_radius=self.border_top_left_radius, border_top_right_radius=self.border_top_right_radius,
                             border_bottom_left_radius=self.border_bottom_left_radius, border_bottom_right_radius=self.border_bottom_right_radius)

        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self.surface = rotated_surface