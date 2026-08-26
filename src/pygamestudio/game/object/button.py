import uuid
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import get_project_path


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
            'is_visible': True,
            'color': (255, 255, 255, 255),
            'image_path': '',
            'border_top_left_radius': 10,
            'border_top_right_radius': 10,
            'border_bottom_left_radius': 10,
            'border_bottom_right_radius': 10,
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

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
    
    def set_image_path(self, image_path:str):
        self.image_path = image_path

    def set_border_top_left_radius(self,  radius:int):
        self.border_top_left_radius = radius

    def set_border_top_right_radius(self,  radius:int):
        self.border_top_right_radius = radius
    
    def set_border_bottom_left_radius(self,  radius:int):
        self.border_bottom_left_radius = radius

    def set_border_bottom_right_radius(self,  radius:int):
        self.border_top_right_radius = radius
    
    def _load_image(self):
        image_absolute_path = Path(get_project_path()) / self.image_path
        if self.image_path == '' or not image_absolute_path.exists():
            self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        else:
            self.surface = pygame.image.load(image_absolute_path).convert(self.surface)

        self.surface = pygame.transform.scale(self.surface, self.size)

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

    def _update_surface(self):
        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        
        if self.image_path:
            self._load_image()
            self.surface.fill(self.color[0:3], special_flags=pygame.BLEND_RGBA_MULT)
        else:
            pygame.draw.rect(self.surface, self.color[0:3], self.surface.get_rect(), width=0,
                         border_radius=-1, border_top_left_radius=self.border_top_left_radius, border_top_right_radius=self.border_top_right_radius,
                         border_bottom_left_radius=self.border_bottom_left_radius, border_bottom_right_radius=self.border_bottom_right_radius)
        
        scaled_size = (int(self.surface.get_width() * self.scale_x), int(self.surface.get_height() * self.scale_y))
        scaled_surface = pygame.transform.scale(self.surface, scaled_size)
        rounded_surface = self._apply_border_radius(scaled_surface)
        rotated_surface = pygame.transform.rotate(rounded_surface, self.angle)
        self.surface = self._apply_alpha(rotated_surface)

        if not self._is_for_api and self.is_selected:
            pygame.draw.rect(self.surface, (0, 122, 204), self.surface.get_rect(), width=2)
        
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