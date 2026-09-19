import uuid
import pygame
import pygame.freetype
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import get_project_path
from pygamestudio.common.utils import assets


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
            'strikethrough': False,
            'text_align': 'center',
            'text_valign': 'middle'
        }
        
        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        # Caches. Reading a .ttf and rasterizing text are expensive compared
        # with blitting the result, while the text itself usually stays the
        # same for many frames: both the font and the composed surface are
        # kept until one of the properties they depend on changes.
        self._font_cache = None
        self._font_cache_key = None
        self._render_cache = None
        self._render_state = None

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

    def get_text_align(self) -> str:
        """Horizontal alignment of the text inside the object box: 'left',
        'center' (default) or 'right'."""
        return self.text_align

    def get_text_valign(self) -> str:
        """Vertical alignment of the text inside the object box: 'top',
        'middle' (default) or 'bottom'."""
        return self.text_valign

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

    def set_text_align(self, align:str):
        """Align the text horizontally: 'left', 'center' or 'right'."""
        if align in ('left', 'center', 'right'):
            self.text_align = align

    def set_text_valign(self, align:str):
        """Align the text vertically: 'top', 'middle' or 'bottom'."""
        if align in ('top', 'middle', 'bottom'):
            self.text_valign = align

    def set_font(self, font_path: str, font_size: int):
        """Set the font file and size in one call."""
        self.font_path = font_path
        self.font_size = font_size

    def _font_state(self):
        """Everything the cached font depends on. The font file's mtime/size
        is part of it, so replacing a font file on disk is picked up in the
        running game without a restart."""
        if self.font_path:
            file_state = self._asset_file_state(self.font_path)
        else:
            file_state = None

        return (self.font_path, self.font_size, bool(self.bold),
                bool(self.italic), bool(self.underline),
                bool(self.strikethrough), file_state)

    def _init_font(self):
        state = self._font_state()
        if state == self._font_cache_key:
            return self._font_cache

        font_absolute_path = Path(get_project_path()) / self.font_path
        if self.font_path == '' or not font_absolute_path.exists():
            font = pygame.font.Font(None, size=self.font_size)
        else:
            font = pygame.font.Font(assets.open_stream(font_absolute_path), size=self.font_size)

        font.set_bold(self.bold)
        font.set_italic(self.italic)
        font.set_underline(self.underline)
        font.set_strikethrough(self.strikethrough)

        self._font_cache_key = state
        self._font_cache = font
        return font

    def _surface_state(self):
        """Everything the composed surface is built from. While it is
        unchanged the previous surface is reused instead of being rendered
        again, which is what happens on most frames."""
        return (self.text, self.text_align, self.text_valign, tuple(self.size),
                tuple(self.color), self.scale_x, self.scale_y, self.angle,
                self._font_state())

    def _text_pos(self, text_surface, box_surface):
        """Top-left corner that places the rendered text inside the box,
        following text_align / text_valign (both centered by default)."""
        box = box_surface.get_rect()
        text = text_surface.get_rect()

        if self.text_align == 'left':
            x = box.left
        elif self.text_align == 'right':
            x = box.right - text.width
        else:
            x = box.centerx - text.width // 2

        if self.text_valign == 'top':
            y = box.top
        elif self.text_valign == 'bottom':
            y = box.bottom - text.height
        else:
            y = box.centery - text.height // 2

        return (x, y)

    def _render_surface(self):
        """Rasterize the text into the object's surface (cache-miss path)."""
        font = self._init_font()
        text_surface = font.render(self.text, True, self.color)
        surface = pygame.Surface(self.size, pygame.SRCALPHA)
        surface.blit(text_surface, self._text_pos(text_surface, surface))

        scaled_size = (surface.width * self.scale_x, surface.height * self.scale_y)
        scaled_surface = pygame.transform.scale(surface, scaled_size)
        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self._render_cache = self._apply_alpha(rotated_surface)

    def _update_surface(self):
        state = self._surface_state()
        if state != self._render_state:
            self._render_state = state
            self._render_surface()

        # The render cache is shared between frames; self.surface only splits
        # off into a private copy when a caller needs one it may write into
        # (see _get_surface).
        self.surface = self._render_cache
        super()._update_surface()

    def _get_surface(self):
        """The surface the caller may read from or composite children into.

        The cached render is shared, so the first such caller of a frame gets
        a private copy instead of a surface that is about to be drawn into.
        """
        if self.surface is self._render_cache:
            self.surface = self._render_cache.copy()
        return self.surface

    def __setattr__(self, name, value):
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return

        if name == 'font_path':
            if value == '':
                super().__setattr__('font_path', '')
            else:
                new_font_path = Path(value)
                if not new_font_path.is_absolute():
                    # A relative path is relative to the PROJECT (that is how
                    # it is stored in the .scene file and what the inspector
                    # shows), so setting './font/x.ttf' from a script behaves
                    # like the same value saved in the scene - it does not
                    # depend on the working directory.
                    super().__setattr__('font_path', new_font_path.as_posix())
                    return

                project_path = Path(get_project_path())
                try:
                    super().__setattr__('font_path', new_font_path.relative_to(project_path).as_posix())
                except ValueError:
                    super().__setattr__('font_path', new_font_path.as_posix())
        else:
            super().__setattr__(name, value)