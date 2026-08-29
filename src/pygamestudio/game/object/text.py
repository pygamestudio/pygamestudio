import uuid
import pygame
import pygame.freetype
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import get_project_path


class ObjectText(ObjectBase):
    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False
                
        if hasattr(self, 'icon'):
            self.icon = ':/images/text.png'

        common_properties = {
            'name': 'Text',
            'type': OBJECT_TEXT,
            'uuid': str(uuid.uuid4()),
            'x': 20,
            'y': 20,
            'pos': (20, 20),
            'width': 60, 
            'height': 40,
            'size': (60, 40),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': (255, 255, 255, 255),
            'visible': True,
            'text': 'Text',
            'font_size': 30,
            'font_path': './font/SIMHEI.ttf',
            'bold': False,
            'italic': False,
            'underline': False,
            'strikethrough': False
        }
        
        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self._is_initialized = True

        self._start()

    def get_text(self) -> str:
        return self.text

    def get_font_size(self) -> int:
        return self.font_size

    def get_font_path(self) -> str:
        return self.font_path
    
    def get_bold_state(self):
        return self.bold

    def get_italic_state(self):
        return self.italic
    
    def get_underline_state(self):
        return self.underline
    
    def get_strikethrough_state(self):
        return self.strikethrough

    def get_text_size(self) -> tuple:
        """Return the (width, height) the current text renders at, using the
        current font settings (unscaled by scale_x/scale_y)."""
        return self._init_font().size(self.text)

    def set_text(self, text:str):
        self.text = text

    def set_font_size(self, font_size:int):
        self.font_size = font_size

    def set_font_path(self, font_path:str):
        self.font_path = font_path

    def set_bold_state(self, bold:bool):
        self.bold = bold

    def set_italic_state(self, italic:bool):
        self.italic = italic
    
    def set_underline_state(self, underline:bool):
        self.underline = underline
    
    def set_strikethrough_state(self, strikethrough:bool):
        self.strikethrough = strikethrough

    def set_font(self, font_path: str, font_size: int):
        """Set the font file and size in one call."""
        self.font_path = font_path
        self.font_size = font_size

    def _init_font(self):
        font_absolute_path = Path(get_project_path()) / self.font_path
        if self.font_path == '' or not font_absolute_path.exists():
            font = pygame.font.Font(None, size=self.font_size)
        else:
            font = pygame.font.Font(font_absolute_path, size=self.font_size)

        font.set_bold(self.bold)
        font.set_italic(self.italic)
        font.set_underline(self.underline)
        font.set_strikethrough(self.strikethrough)
        return font
    
    def _update_surface(self):
        font = self._init_font()
        text = font.render(self.text, True, self.color)
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self.surface.blit(text, text.get_rect(center=(self.surface.width//2, self.surface.height//2)))

        scaled_size = (self.surface.width * self.scale_x, self.surface.height * self.scale_y)
        scaled_surface = pygame.transform.scale(self.surface, scaled_size)
        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self.surface = self._apply_alpha(rotated_surface)

        super()._update_surface()

    def __setattr__(self, name, value):
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return

        if name == 'font_path':
            if value == '':
                super().__setattr__('font_path', '')
            else:
                project_path = Path(get_project_path())
                new_font_path = Path(value).absolute()
                try:
                    super().__setattr__('font_path', new_font_path.relative_to(project_path).as_posix())
                except ValueError:
                    super().__setattr__('font_path', new_font_path.as_posix())
        else:
            super().__setattr__(name, value)