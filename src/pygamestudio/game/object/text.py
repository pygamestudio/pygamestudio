import uuid
import pygame
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import RES_PATH


class ObjectText(ObjectBase):
    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False
                
        if hasattr(self, 'icon'):
            self.icon = str(RES_PATH/'images/item.png')

        common_properties = {
            'name': 'Text',
            'type': OBJECT_TEXT,
            'uuid': str(uuid.uuid4()),
            'x': 0,
            'y': 0,
            'pos': (0, 0),
            'width': 50, 
            'height': 30,
            'size': (50, 30),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': "#ffffff",
            'is_visible': True,
            'text': 'Text',
            'font_size': 30,
            'font_family': 'Arial',
            'is_bold': False,
            'is_italic': False,
            'is_underline': False,
            'is_strikethrough': False
        }
        
        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        font = self._init_font()
        text = font.render(self.text, True, self.color)
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self.surface.blit(text, text.get_rect(center=(self.surface.width//2, self.surface.height//2)))
        self._is_initialized = True

    def _init_font(self):
        font = pygame.font.SysFont(self.font_family, self.font_size)
        font.set_bold(self.is_bold)
        font.set_italic(self.is_italic)
        font.set_underline(self.is_underline)
        font.set_strikethrough(self.is_strikethrough)
        return font
    
    def update_surface(self):
        font = self._init_font()
        text = font.render(self.text, True, self.color)
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self.surface.blit(text, text.get_rect(center=(self.surface.width//2, self.surface.height//2)))
        
        scaled_size = (self.width * self.scale_x, self.height * self.scale_y)
        scaled_surface = pygame.transform.scale(self.surface, scaled_size)

        if not self._is_for_api and self.is_selected:
            pygame.draw.rect(scaled_surface, (255, 255, 50), scaled_surface.get_rect(), width=2)

        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self.surface = rotated_surface
         