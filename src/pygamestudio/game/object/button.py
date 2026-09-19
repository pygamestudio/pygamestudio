import uuid
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import get_project_path
from pygamestudio.common.utils import assets


class ObjectButton(ObjectBase):
    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/button.png'

        common_properties = {
            'name': 'Button',
            'type': OBJECT_BUTTON,
            'uuid': str(uuid.uuid4()),
            'x': 20,
            'y': 20,
            'pos': (20, 20),
            'width': 100,
            'height': 40,
            'size': (100, 40),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'visible': True,
            'color': (255, 255, 255, 255),
            'image_path': '',
            'border_top_left_radius': 10,
            'border_top_right_radius': 10,
            'border_bottom_left_radius': 10,
            'border_bottom_right_radius': 10,
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        # Caches. Loading and scaling a PNG is expensive compared with
        # blitting it, while a button usually looks the same for many frames:
        # the image file and the composed surface are kept until one of the
        # properties they depend on changes.
        self._image_cache = None
        self._image_cache_key = None
        self._render_cache = None
        self._render_state = None

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self._is_initialized = True

        self._start()

    def get_image_path(self) -> str:
        return self.image_path

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
    
    def set_image_path(self, image_path:str):
        self.image_path = image_path

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

    def _image_state(self):
        """What the cached image depends on: the path, the object size it is
        scaled to, and the file's mtime/size so replacing the image on disk is
        picked up in the running game without a restart."""
        if not self.image_path:
            return None

        return (self.image_path,
                self._asset_file_state(self.image_path),
                tuple(self.size))

    def _load_image(self):
        """The image file scaled to the object's size, or a blank surface when
        no image is set or the file is missing. Loaded once and cached."""
        state = self._image_state()
        if state == self._image_cache_key:
            return self._image_cache

        image_absolute_path = Path(get_project_path()) / self.image_path
        if self.image_path == '' or not image_absolute_path.exists():
            surface = pygame.Surface(self.size, pygame.SRCALPHA)
        else:
            surface = pygame.image.load(assets.open_stream(image_absolute_path)).convert_alpha()

        self._image_cache = pygame.transform.scale(surface, self.size)
        self._image_cache_key = state
        return self._image_cache

    def _apply_border_radius(self, surface):
        radius = [self.border_top_left_radius, self.border_top_right_radius,
                  self.border_bottom_left_radius, self.border_bottom_right_radius]
        
        mask = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(),
                         border_top_left_radius=radius[0],
                         border_top_right_radius=radius[1],
                         border_bottom_left_radius=radius[2],
                         border_bottom_right_radius=radius[3])
        surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        return surface

    def _surface_state(self):
        """Everything the composed surface is built from. While it is
        unchanged the previous surface is reused instead of being composed
        again, which is what happens on most frames."""
        return (self.image_path, tuple(self.size), tuple(self.color),
                self.scale_x, self.scale_y, self.angle,
                self.border_top_left_radius, self.border_top_right_radius,
                self.border_bottom_left_radius, self.border_bottom_right_radius,
                self._image_state())

    def _render_surface(self):
        """Compose the button's surface (cache-miss path): the image tinted by
        the color, or a rounded rectangle filled with the color."""
        if self.image_path:
            # A copy, because the color is multiplied into the surface: the
            # cached image itself must stay untouched.
            surface = self._load_image().copy()
            surface.fill(self.color[0:3], special_flags=pygame.BLEND_RGBA_MULT)
        else:
            surface = pygame.Surface(self.size, pygame.SRCALPHA)
            pygame.draw.rect(surface, self.color[0:3], surface.get_rect(), width=0,
                         border_radius=-1, border_top_left_radius=self.border_top_left_radius, border_top_right_radius=self.border_top_right_radius,
                         border_bottom_left_radius=self.border_bottom_left_radius, border_bottom_right_radius=self.border_bottom_right_radius)
        
        scaled_size = (int(surface.get_width() * self.scale_x), int(surface.get_height() * self.scale_y))
        scaled_surface = pygame.transform.scale(surface, scaled_size)
        rounded_surface = self._apply_border_radius(scaled_surface)
        rotated_surface = pygame.transform.rotate(rounded_surface, self.angle)
        self._render_cache = self._apply_alpha(rotated_surface)

    def _update_surface(self):
        # The editor's selection outline is drawn by ObjectBase._draw() around
        # the object, so it is deliberately not baked into this surface.
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

        if name == 'image_path':
            if value == '':
                super().__setattr__('image_path', '')
            else:
                new_image_path = Path(value)
                if not new_image_path.is_absolute():
                    # A relative path is relative to the PROJECT (that is how
                    # it is stored in the .scene file and what the inspector
                    # shows), so setting './image/x.png' from a script behaves
                    # like the same value saved in the scene - it does not
                    # depend on the working directory.
                    super().__setattr__('image_path', new_image_path.as_posix())
                    return

                project_path = Path(get_project_path())
                try:
                    super().__setattr__('image_path', new_image_path.relative_to(project_path).as_posix())
                except ValueError:
                    super().__setattr__('image_path', new_image_path.as_posix())

        else:
            super().__setattr__(name, value)