import uuid
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.common.utils.path import get_project_path


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
            'x': 20,
            'y': 20,
            'pos': (20, 20),
            'width': 128,
            'height': 128,
            'size': (128, 128),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': (255, 255, 255, 255),
            'is_visible': True,
            'image_path': './image/logo.png',
            # 'keep_aspect_ratio': False,
            'border_top_left_radius': 0,
            'border_top_right_radius': 0,
            'border_bottom_left_radius': 0,
            'border_bottom_right_radius': 0,
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)        
        self._is_initialized = True

        self._start()

    def get_image_path(self) -> str:
        return self.image_path

    def set_image_path(self, image_path:str):
        self.image_path = image_path
        
    def _load_image(self):
        image_absolute_path = Path(get_project_path()) / self.image_path
        if self.image_path == '' or not image_absolute_path.exists():
            self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        else:
            self.surface = pygame.image.load(image_absolute_path).convert(self.surface)

        self.surface = pygame.transform.scale(self.surface, self.size)
        # if self.keep_aspect_ratio:
        #     self.surface = self._fit_aspect_ratio(self.surface, self.size)
        # else:
        #     self.surface = pygame.transform.scale(self.surface, self.size)

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
        self._load_image()

        scaled_size = (int(self.surface.get_width() * self.scale_x), int(self.surface.get_height() * self.scale_y))
        scaled_surface = pygame.transform.scale(self.surface, scaled_size)
        rounded_surface = self._apply_border_radius(scaled_surface)
        rotated_surface = pygame.transform.rotate(rounded_surface, self.angle)
        self.surface = self._apply_alpha(rotated_surface)

        self.surface.fill(self.color[0:3], special_flags=pygame.BLEND_RGBA_MULT)

        super()._update_surface()

    def __setattr__(self, name, value):
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return

        if name == 'image_path':
            if value == '':
                super().__setattr__('image_path', '')
            else:
                project_path = Path(get_project_path())
                new_image_path = Path(value).absolute()
                try:
                    super().__setattr__('image_path', new_image_path.relative_to(project_path).as_posix())
                except ValueError:
                    super().__setattr__('image_path', new_image_path.as_posix())

        else:
            super().__setattr__(name, value)