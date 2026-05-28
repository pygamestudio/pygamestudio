import uuid
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import RES_PATH


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
            'color': '#ffffff',
            'is_visible': True,
            'image_path': '',
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

    def _load_image(self):
        if self.image_path and Path(self.image_path).exists():
            self.surface = pygame.image.load(self.image_path).convert(self.surface)
        else:
            image_placeholder_path = RES_PATH/'images/image_placeholder.png'
            if image_placeholder_path.exists():  
                self.surface = pygame.image.load(image_placeholder_path).convert(self.surface)

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
            self.border_bottom_right_radius,
            self.border_bottom_left_radius
        ]
        mask = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(),
                         border_top_left_radius=radius[0],
                         border_top_right_radius=radius[1],
                         border_bottom_right_radius=radius[2],
                         border_bottom_left_radius=radius[3])
        surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        return surface

    def update_surface(self):
        self._load_image()

        scaled_size = (int(self.surface.get_width() * self.scale_x), int(self.surface.get_height() * self.scale_y))
        scaled_surface = pygame.transform.scale(self.surface, scaled_size)
        rounded_surface = self._apply_border_radius(scaled_surface)
        rotated_surface = pygame.transform.rotate(rounded_surface, self.angle)
        self.surface = rotated_surface

        self.surface.fill(self.color, special_flags=pygame.BLEND_RGBA_MULT)

        if not self._is_for_api and self.is_selected:
            pygame.draw.rect(self.surface, (0, 122, 204), self.surface.get_rect(), width=2,
                             border_top_left_radius=self.border_top_left_radius,
                             border_top_right_radius=self.border_top_right_radius,
                             border_bottom_left_radius=self.border_bottom_left_radius,
                             border_bottom_right_radius=self.border_bottom_right_radius)