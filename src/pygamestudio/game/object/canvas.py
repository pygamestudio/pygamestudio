import uuid
import pygame
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase


class ObjectCanvas(ObjectBase):
    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False
                
        if hasattr(self, 'icon'):
            self.icon = ':/images/canvas.png'

        common_properties = {
            'name': 'Canvas',
            'type': OBJECT_CANVAS,
            'uuid': str(uuid.uuid4()),
            'x': 0,
            'y': 0,
            'pos': (0, 0),
            'width': 800, 
            'height': 600,
            'size': (800, 600),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': (0, 0, 0, 255),
            'visible': True,
        }
        
        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        self._render_state = None
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.rect(self.surface, self.color, self.surface.get_rect())
        self._is_initialized = True

        self._start()

    def _surface_state(self):
        """Everything the background bitmap depends on."""
        return (tuple(self.size), tuple(self.color),
                bool(not self._is_for_api and self.selected))

    def _update_surface(self):
        """Rebuild the background only when it actually changed.

        This used to allocate a canvas-sized SRCALPHA surface and repaint it on
        EVERY frame - on an 800x600 canvas that is ~1.9 MB allocated, cleared and
        then alpha-blended over the screen every frame, which on its own kept the
        device at 26 fps while the same screen presented 809 fps of empty frames.
        The colour and size almost never change, so the bitmap is cached like
        every other object's, and an opaque background uses a plain surface (a
        copy instead of a half-million-pixel alpha blend).
        """
        state = self._surface_state()
        if state != self._render_state:
            self._render_state = state
            alpha = self.color[3] if len(self.color) > 3 else 255
            if alpha >= 255:
                self.surface = pygame.Surface(self.size)
                self.surface.fill(self.color)
            else:
                self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
                pygame.draw.rect(self.surface, self.color, self.surface.get_rect())
            if not self._is_for_api and self.selected:
                pygame.draw.rect(self.surface, (0, 122, 204), (0, 0, self.surface.width, self.surface.height), 2)

        super()._update_surface()
