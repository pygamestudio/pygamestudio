import uuid
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import get_project_path

_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp',
                     '.tga', '.pcx', '.qoi', '.xpm', '.lbm'}


class ObjectProgressBar(ObjectBase):
    """A UI progress bar made of two strips:

    - the BACKGROUND strip fills the whole box (an optional background image,
      otherwise a flat ``background_color`` rectangle), and
    - the FOREGROUND strip sits on top and its width follows ``progress``
      (0..100 %; an optional foreground image, otherwise a flat
      ``foreground_color`` rectangle clipped to the filled width).

    Both strip images default to empty - the bar is then drawn with colors so
    it works without any asset. ``set_progress()`` can be called at runtime;
    the next frame re-renders the bar with the new fill width.
    """

    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/progress_bar.png'

        common_properties = {
            'name': 'Progress Bar',
            'type': OBJECT_PROGRESS_BAR,
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
            # Progress bar content.
            'progress': 50.0,                 # current value, 0..100
            'background_color': (70, 70, 70, 255),
            'foreground_color': (86, 200, 120, 255),
            # Optional strip images (project-relative). Empty = drawn.
            'background_image_path': '',
            'foreground_image_path': '',
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self._image_cache = {}   # path -> loaded Surface (transient)
        self._is_initialized = True

        self._start()

    # -------------------------------------------------------------- progress
    def get_progress(self) -> float:
        """Current progress in 0..100 (%)."""
        return float(self.progress or 0)

    def set_progress(self, progress: float):
        """Set the current progress (clamped to 0..100)."""
        self.progress = progress

    # -------------------------------------------------------------- colors
    def get_background_color(self) -> tuple:
        return tuple(self.background_color)

    def set_background_color(self, color):
        self.background_color = color

    def get_foreground_color(self) -> tuple:
        return tuple(self.foreground_color)

    def set_foreground_color(self, color):
        self.foreground_color = color

    # -------------------------------------------------------------- images
    def get_background_image_path(self) -> str:
        return self.background_image_path

    def set_background_image_path(self, path: str):
        self.background_image_path = path

    def get_foreground_image_path(self) -> str:
        return self.foreground_image_path

    def set_foreground_image_path(self, path: str):
        self.foreground_image_path = path

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

    def _build_content_surface(self):
        """Draw the progress bar (background strip + foreground strip at the
        current progress) onto a fresh width x height surface."""
        width = max(1, int(self.width or 1))
        height = max(1, int(self.height or 1))
        surface = pygame.Surface((width, height), pygame.SRCALPHA)

        # Background strip: image stretched over the whole box, or flat color.
        bg_image = self._load_image(self.background_image_path)
        if bg_image is not None:
            scaled = pygame.transform.scale(bg_image, (width, height))
            surface.blit(scaled, (0, 0))
        else:
            bg_color = tuple(int(c) for c in (self.background_color or (0, 0, 0, 255)))
            pygame.draw.rect(surface, bg_color[:3], surface.get_rect(), 0)
            if len(bg_color) > 3:
                surface.fill((255, 255, 255, bg_color[3]),
                             special_flags=pygame.BLEND_RGBA_MULT)

        # Foreground strip width follows the progress (0..100).
        progress = max(0.0, min(100.0, float(self.progress or 0)))
        fg_width = int(round(width * progress / 100.0))
        if fg_width <= 0:
            return surface

        fg_image = self._load_image(self.foreground_image_path)
        if fg_image is not None:
            # Stretch the image to the full box and keep only the filled part.
            full = pygame.transform.scale(fg_image, (width, height))
            surface.blit(full, (0, 0), area=pygame.Rect(0, 0, fg_width, height))
        else:
            fg_color = tuple(int(c) for c in (self.foreground_color or (0, 0, 0, 255)))
            pygame.draw.rect(surface, fg_color[:3],
                             pygame.Rect(0, 0, fg_width, height), 0)
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
        """Normalize the strip image paths (always project-relative, like the
        image object's image_path)."""
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return

        if name in ('background_image_path', 'foreground_image_path'):
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
            # The cached image for the OLD path is stale.
            if old_path in self._image_cache:
                del self._image_cache[old_path]
            return

        if name == 'progress':
            super().__setattr__('progress', max(0.0, min(100.0, float(value))))
            return

        super().__setattr__(name, value)

    def _to_dict(self):
        """Serialize the progress bar, excluding the transient image cache."""
        data = super()._to_dict()
        data.pop('_image_cache', None)
        return data
