import uuid
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.common.utils.path import get_project_path
from pygamestudio.common.utils import assets


class ObjectImage(ObjectBase):
    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/image.png'

        common_properties = {
            'name': 'Image',
            'type': OBJECT_IMAGE,
            'uuid': str(uuid.uuid4()),
            'x': 0,
            'y': 0,
            'pos': (0, 0),
            'width': 128,
            'height': 128,
            'size': (128, 128),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': (255, 255, 255, 255),
            'visible': True,
            'image_path': './image/logo.png',
            # 'keep_aspect_ratio': False,
            'border_top_left_radius': 0,
            'border_top_right_radius': 0,
            'border_bottom_left_radius': 0,
            'border_bottom_right_radius': 0,
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        # Caches. Decoding the PNG and composing the whole pipeline (scale,
        # rounded corners, rotate, alpha, tint) is orders of magnitude more
        # expensive than blitting the result, while an image usually looks the
        # same for many frames - a tiled background of a few hundred IMAGE
        # objects used to re-decode every file on every frame. The decoded
        # file and the composed surface are kept until one of the properties
        # they depend on changes.
        self._image_cache = None
        self._image_cache_key = None
        self._render_cache = None
        self._render_state = None

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)        
        self._is_initialized = True

        self._start()

    def get_image_path(self) -> str:
        return self.image_path

    def set_image_path(self, image_path:str):
        self.image_path = image_path

    def _image_state(self):
        """What the cached image depends on: the path, the file's
        mtime/size (so replacing the image on disk is picked up in the
        running game without a restart) and the object size it is scaled to."""
        if not self.image_path:
            return None

        return (self.image_path,
                self._asset_file_state(self.image_path),
                tuple(self.size))

    def _load_image(self):
        """The image file scaled to the object's size, or a blank surface when
        no image is set or the file is missing. Loaded once and cached."""
        state = self._image_state()
        if self._image_cache is not None and state == self._image_cache_key:
            return self._image_cache

        image_absolute_path = Path(get_project_path()) / self.image_path
        if self.image_path == '' or not image_absolute_path.exists():
            surface = pygame.Surface(self.size, pygame.SRCALPHA)
        else:
            surface = pygame.image.load(assets.open_stream(image_absolute_path)).convert(self.surface)

        self._image_cache = pygame.transform.scale(surface, self.size)
        self._image_cache_key = state
        return self._image_cache

    def _fit_aspect_ratio(self, surface, target_size):
        orig_w, orig_h = surface.get_size()
        target_w, target_h = target_size

        scale = min(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        return pygame.transform.scale(surface, (new_w, new_h))

    def _apply_border_radius(self, surface):
        radius = [
            self.border_top_left_radius,
            self.border_top_right_radius,
            self.border_bottom_left_radius,
            self.border_bottom_right_radius
        ]
        mask = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(),
                         border_top_left_radius=radius[0],
                         border_top_right_radius=radius[1],
                         border_bottom_left_radius=radius[2],
                         border_bottom_right_radius=radius[3])
        surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        return surface

    def _update_surface(self):
        # The editor's selection outline is drawn by ObjectBase._draw around
        # the object (and, for a selected top-level object, into the surface
        # _get_surface returns), so it is deliberately not baked in here.
        state = self._surface_state()
        if state != self._render_state:
            self._render_state = state
            self._render_surface()

        # The render cache is shared between frames; self.surface only splits
        # off into a private copy when a caller needs one it may write into
        # (see _get_surface).
        self.surface = self._render_cache
        super()._update_surface()

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
        """Compose the object's surface (cache-miss path): the image, scaled,
        with rounded corners, rotated, alpha-applied and tinted by the color."""
        surface = self._load_image()

        scaled_surface = self._apply_scale(surface)
        rounded_surface = self._apply_border_radius(scaled_surface)
        rotated_surface = pygame.transform.rotate(rounded_surface, self.angle)
        self._render_cache = self._apply_alpha(rotated_surface)

        self._render_cache.fill(self.color[0:3], special_flags=pygame.BLEND_RGBA_MULT)

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
                project_path = Path(get_project_path())
                new_image_path = Path(value)
                if not new_image_path.is_absolute():
                    # A relative path is project-relative (the documented
                    # convention), never relative to the process directory.
                    new_image_path = project_path / new_image_path
                try:
                    super().__setattr__('image_path',
                                        new_image_path.resolve().relative_to(project_path.resolve()).as_posix())
                except ValueError:
                    super().__setattr__('image_path', new_image_path.resolve().as_posix())

        else:
            super().__setattr__(name, value)