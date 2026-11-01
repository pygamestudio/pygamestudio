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
            'color': (255, 255, 255, 255),
            'visible': True,
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        # Caches: composing the surface (ellipse fill, scale, rotate, alpha)
        # costs far more than blitting it, while an ellipse usually looks the
        # same for many frames - a background made of many ELLIPSE objects
        # used to rebuild every one of them per frame.
        self._render_cache = None
        self._render_state = None

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self._is_initialized = True

        self._start()

    def _surface_state(self):
        """Everything the composed surface is built from. While it is
        unchanged the previous surface is reused instead of being composed
        again, which is what happens on most frames."""
        return (tuple(self.size), tuple(self.color),
                self.scale_x, self.scale_y, self.angle)

    def _render_surface(self):
        """Compose the ellipse's surface (cache-miss path)."""
        surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.ellipse(surface, self.color[0:3], surface.get_rect())

        scaled_surface = self._apply_scale(surface)
        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self._render_cache = self._apply_alpha(rotated_surface)

    def _update_surface(self):
        # The editor's selection outline is drawn by ObjectBase._draw around
        # the object (and, for a selected top-level object, into the surface
        # _get_surface returns), so it is deliberately not baked in here.
        state = self._surface_state()
        if state != self._render_state:
            self._render_state = state
            self._render_surface()

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
