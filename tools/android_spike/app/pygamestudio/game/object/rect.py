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
            'border_top_left_radius': 0,
            'border_top_right_radius': 0,
            'border_bottom_left_radius': 0,
            'border_bottom_right_radius': 0
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        # Caches: composing the surface (fill, rounded corners, scale,
        # rotate, alpha) costs far more than blitting it, while a rectangle
        # usually looks the same for many frames - a background made of a few
        # hundred RECT objects used to rebuild every one of them per frame.
        self._render_cache = None
        self._render_state = None

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

    def _surface_state(self):
        """Everything the composed surface is built from. While it is
        unchanged the previous surface is reused instead of being composed
        again, which is what happens on most frames."""
        return (tuple(self.size), tuple(self.color),
                self.scale_x, self.scale_y, self.angle,
                self.border_top_left_radius, self.border_top_right_radius,
                self.border_bottom_left_radius, self.border_bottom_right_radius)

    def _render_surface(self):
        """Compose the rectangle's surface (cache-miss path)."""
        surface = pygame.Surface(self.size, pygame.SRCALPHA)
        pygame.draw.rect(surface, self.color[0:3], surface.get_rect(), width=0,
                         border_radius=-1, border_top_left_radius=self.border_top_left_radius, border_top_right_radius=self.border_top_right_radius,
                         border_bottom_left_radius=self.border_bottom_left_radius, border_bottom_right_radius=self.border_bottom_right_radius)

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