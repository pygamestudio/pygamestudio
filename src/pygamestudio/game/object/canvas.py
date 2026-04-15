import pygame
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import RES_PATH


class ObjectCanvas(ObjectBase):
    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        if hasattr(self, 'icon'):
            self.icon = str(RES_PATH/'images/item.png')

        self.name = 'Canvas'
        self.type = OBJECT_CANVAS
        self.color = '#000000'

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.rect(self.surface, self.color, self.surface.get_rect())
    
    def update_surface(self):
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.rect(self.surface, self.color, self.surface.get_rect())
        if not self._is_for_api and self.is_selected:
            pygame.draw.rect(self.surface, (255, 255, 50), (0, 0, self.surface.width, self.surface.height), 2)
