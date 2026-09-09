import uuid
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import get_project_path

_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp',
                     '.tga', '.pcx', '.qoi', '.xpm', '.lbm'}


class ObjectSlider(ObjectBase):
    """A horizontal UI slider made of a thin RAIL and a HANDLE knob:

    - the RAIL is a thin horizontal strip, vertically centred in the object
      box (``track_color`` or an optional ``track_image_path``; its height is
      ``track_thickness`` px),
    - a FILL strip grows along the rail from the minimum side up to the
      handle centre (``fill_color`` or an optional ``fill_image_path``), and
    - a HANDLE knob sits on the rail at the value position; its default size
      is 16 x 16 px (``handle_width`` x ``handle_height``). A ``handle_height``
      of 0 draws NO handle. The handle size is independent of the rail
      thickness and is only clamped to the object's box.

    The value maps linearly between ``min_value`` and ``max_value``. All
    images default to empty - the slider is drawn with colors so it works
    without any asset. ``set_value()`` can be called at runtime (e.g. from a
    script); the running game also lets the player drag the handle or click
    the rail to change the value (see SceneLoader's runtime slider input).
    """

    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/slider.png'

        common_properties = {
            'name': 'Slider',
            'type': OBJECT_SLIDER,
            'uuid': str(uuid.uuid4()),
            'x': 20,
            'y': 20,
            'pos': (20, 20),
            'width': 200,
            'height': 20,
            'size': (200, 20),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': (255, 255, 255, 255),
            'visible': True,
            # Slider content.
            'value': 50.0,
            'min_value': 0.0,
            'max_value': 100.0,
            # Rail is a THIN strip (not a fat bar), so the slider does not
            # look like a progress bar.
            'track_thickness': 6,
            'handle_width': 16,
            'handle_height': 16,          # 0 = no handle (hidden)
            'track_color': (70, 70, 70, 255),
            'fill_color': (86, 200, 120, 255),
            'handle_color': (235, 235, 235, 255),
            # Optional strip images (project-relative). Empty = drawn.
            'track_image_path': '',
            'fill_image_path': '',
            'handle_image_path': '',
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self._image_cache = {}   # path -> loaded Surface (transient)
        self._is_initialized = True

        self._start()

    # ---------------------------------------------------------------- value
    def get_value(self) -> float:
        return float(self.value or self.min_value or 0)

    def set_value(self, value: float):
        self.value = value

    def get_min_value(self) -> float:
        return float(self.min_value)

    def set_min_value(self, min_value: float):
        self.min_value = min_value

    def get_max_value(self) -> float:
        return float(self.max_value)

    def set_max_value(self, max_value: float):
        self.max_value = max_value

    def get_range(self) -> tuple:
        return (float(self.min_value), float(self.max_value))

    # ------------------------------------------------------------ normalized
    def _fraction(self) -> float:
        """Value mapped to 0..1 along [min_value, max_value]."""
        low = float(self.min_value or 0)
        high = float(self.max_value or 0)
        if high <= low:
            return 0.0
        return max(0.0, min(1.0, (float(self.value) - low) / (high - low)))

    # -------------------------------------------------------------- images
    def get_track_image_path(self) -> str:
        return self.track_image_path

    def set_track_image_path(self, path: str):
        self.track_image_path = path

    def get_fill_image_path(self) -> str:
        return self.fill_image_path

    def set_fill_image_path(self, path: str):
        self.fill_image_path = path

    def get_handle_image_path(self) -> str:
        return self.handle_image_path

    def set_handle_image_path(self, path: str):
        self.handle_image_path = path

    # ---------------------------------------------------------------- render
    def _load_image(self, image_path: str):
        """Load one strip image (project-relative) from cache. None when the
        path is empty or the file cannot be loaded."""
        if not image_path:
            return None
        if image_path in self._image_cache:
            return self._image_cache[image_path]
        img = None
        project_root = Path(get_project_path()) if (get_project_path() or '').strip() else Path.cwd()
        path = Path(image_path)
        if not path.is_absolute():
            path = project_root / path
        if path.is_file() and path.suffix.lower() in _IMAGE_EXTENSIONS:
            try:
                img = pygame.image.load(str(path))
                try:
                    img = img.convert_alpha()
                except pygame.error:
                    pass
            except Exception:
                img = None
        self._image_cache[image_path] = img
        return img

    @staticmethod
    def _paint_solid(surface, rect, color):
        """Fill ``rect`` with a color, applying its alpha via RGBA_MULT."""
        color = tuple(int(c) for c in color)
        pygame.draw.rect(surface, color[:3], rect, 0)
        if len(color) > 3:
            surface.fill((255, 255, 255, color[3]), rect,
                         special_flags=pygame.BLEND_RGBA_MULT)

    def _build_content_surface(self):
        """Draw the thin rail + fill + handle onto a width x height surface."""
        width = max(1, int(self.width or 1))
        height = max(1, int(self.height or 1))
        surface = pygame.Surface((width, height), pygame.SRCALPHA)

        # --- thin rail, vertically centred --------------------------------
        thickness = max(1, min(height, int(self.track_thickness or 1)))
        rail_top = int(round((height - thickness) / 2.0))
        rail_rect = pygame.Rect(0, rail_top, width, thickness)

        track_image = self._load_image(self.track_image_path)
        if track_image is not None:
            surface.blit(pygame.transform.scale(track_image, (width, thickness)),
                         rail_rect.topleft)
        else:
            self._paint_solid(surface, rail_rect,
                              self.track_color or (0, 0, 0, 255))

        # --- value geometry ----------------------------------------------
        frac = self._fraction()
        handle_cx = frac * width

        # --- fill along the rail up to the handle centre ------------------
        fill_width = int(round(handle_cx))
        if fill_width > 0:
            fill_image = self._load_image(self.fill_image_path)
            if fill_image is not None:
                full = pygame.transform.scale(fill_image, (width, thickness))
                surface.blit(full, (0, rail_top),
                             area=pygame.Rect(0, 0, fill_width, thickness))
            else:
                self._paint_solid(surface,
                                  pygame.Rect(0, rail_top, fill_width, thickness),
                                  self.fill_color or (0, 0, 0, 255))

        # --- handle knob (independent of the rail thickness; 0 height = no
        # handle is drawn at all) ------------------------------------------
        raw_handle_height = int(self.handle_height or 0)
        if raw_handle_height > 0:
            handle_width = max(1, min(width, int(self.handle_width or 1)))
            handle_height = min(height, raw_handle_height)
            handle_left = max(0, min(width - handle_width,
                                     int(round(handle_cx - handle_width / 2.0))))
            handle_top = int(round((height - handle_height) / 2.0))
            handle_rect = pygame.Rect(handle_left, handle_top,
                                      handle_width, handle_height)
            handle_image = self._load_image(self.handle_image_path)
            if handle_image is not None:
                surface.blit(pygame.transform.scale(handle_image,
                                                    handle_rect.size),
                             handle_rect.topleft)
            else:
                self._paint_solid(surface, handle_rect,
                                  self.handle_color or (200, 200, 200, 255))
        return surface

    def _update_surface(self):
        content = self._build_content_surface()

        scaled_size = (max(1, int(content.get_width() * self.scale_x)),
                       max(1, int(content.get_height() * self.scale_y)))
        scaled_surface = pygame.transform.scale(content, scaled_size)
        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self.surface = self._apply_alpha(rotated_surface)

        super()._update_surface()

    def __setattr__(self, name, value):
        """Normalize the strip image paths (project-relative, like image_path)
        and clamp the slider's numeric fields."""
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return

        if name in ('track_image_path', 'fill_image_path', 'handle_image_path'):
            old_path = getattr(self, name, '') or ''
            raw = str(value).strip() if value is not None else ''
            project_root = (Path(get_project_path()).absolute()
                            if (get_project_path() or '').strip()
                            else Path.cwd())
            if not raw:
                super().__setattr__(name, '')
            else:
                path = Path(raw)
                if not path.is_absolute():
                    path = project_root / path
                path = path.absolute()
                try:
                    super().__setattr__(name,
                                        path.relative_to(project_root).as_posix())
                except ValueError:
                    super().__setattr__(name, path.as_posix())
            if old_path in self._image_cache:
                del self._image_cache[old_path]
            return

        if name == 'value':
            super().__setattr__('value', float(value))
            return
        if name == 'min_value':
            super().__setattr__('min_value', float(value))
            return
        if name == 'max_value':
            super().__setattr__('max_value', float(value))
            return
        if name == 'handle_width':
            super().__setattr__('handle_width', max(1, int(value)))
            return
        if name == 'handle_height':
            super().__setattr__('handle_height', max(0, int(value)))
            return
        if name == 'track_thickness':
            super().__setattr__('track_thickness', max(1, int(value)))
            return

        super().__setattr__(name, value)

    def _to_dict(self):
        """Serialize the slider, excluding the transient image cache."""
        data = super()._to_dict()
        data.pop('_image_cache', None)
        return data
