
import pygame
from pygamestudio.game.object.type import *
from pygamestudio.common.utils.system import get_system_lang
from pygamestudio.common.i18n.translator import Translator as T


class ObjectBase:
    def __init__(self, game_manager, object_data={}, is_for_api=False):
        self._is_for_api = is_for_api
        self._game_manager = game_manager

        internal_properties = {
            'is_expanded': True,
            'is_selected': False,
            'icon': '',
        }
    
        if not self._is_for_api:
            for key, value in internal_properties.items():
                setattr(self, key, object_data.get(key, value))

        self.surface = None

    def is_pressed(self, x:int, y:int) -> bool:
        return True if self._check_click_collision((x, y)) else False
    
    def is_visible(self) -> bool:
        return self.is_visible
    
    def get_name(self) -> str:
        return self.name
        
    def get_uuid(self) -> str:
        return self.uuid

    def get_type(self) -> str:
        return self.type

    def get_pos(self) -> tuple:
        return self.pos
    
    def get_world_pos(self) -> tuple:
        return self._get_world_pos()
    
    def get_x(self) -> int:
        return self.x
    
    def get_y(self) -> int:
        return self.y
    
    def get_width(self) -> int:
        return self.width
    
    def get_height(self) -> int:
        return self.height
    
    def get_size(self) -> tuple:
        return self.size
    
    def get_scale_x(self) -> float:
        return self.scale_x
    
    def get_scale_y(self) -> float:
        return self.scale_y
    
    def get_scale(self) -> tuple:
        return self.scale
    
    def get_visibility(self) -> bool:
        return self.is_visible
    
    def get_color(self) -> tuple:
        return self.color
    
    def set_pos(self, x:int, y:int):
        self.x = x
        self.y = y

    def set_world_pos(self, x:int, y:int):
        self._set_world_rect(x, y)

    def set_x(self, x:int) -> int:
        self.x = x

    def set_y(self, y:int) -> int:
        self.y = y

    def set_width(self, width:int):
        self.width = width
    
    def set_height(self, height:int):
        self.height = height

    def set_size(self, width:int , height:int):
        self.size = (width, height)
    
    def set_scale_x(self, scale_x:float):
        self.scale_x = scale_x
    
    def set_scale_y(self, scale_y:float):
        self.scale_y = scale_y

    def set_scale(self, scale_x:float, scale_y:float):
        self.scale = (scale_x, scale_y)

    def get_angle(self) -> float:
        return self.angle
    
    def set_angle(self, angle:float):
        self.angle = angle

    def set_visibility(self, visibility:bool):
        self.is_visible = visibility
    
    def set_color(self, color:tuple):
        self.color = color

    def _draw(self, parent_surface):
        parent_surface.blit(self.surface, self._get_rect())
        if not self._is_for_api and self.is_selected:
            pygame.draw.rect(parent_surface, (0, 122, 204), self._get_rect(), width=2)

    def _get_surface(self):
        return self.surface

    def _update_surface(self):
        pass

    def _get_world_pos(self):
        return self._get_world_rect().topleft

    def _get_rect(self):
        # Get the rect of the object. Note that the rect returned by Surface.get_rect() always starts at (0, 0).
        return pygame.Rect(self.x, self.y, self.surface.width, self.surface.height)

    def _get_world_rect(self):
        world_rect = self._get_rect()
        parent_object = self._game_manager.get_parent_object(self.uuid)

        while parent_object:
            parent_rect = parent_object._get_rect()
            world_rect.move_ip(parent_rect.x, parent_rect.y)
            parent_object = self._game_manager.get_parent_object(parent_object.uuid)

        return world_rect
    
    def _set_world_rect(self, world_x, world_y):
        px, py = 0, 0
        parent_object = self._game_manager.get_parent_object(self.uuid)

        while parent_object:
            parent_rect = parent_object._get_rect()
            px += parent_rect.x
            py += parent_rect.y
            parent_object = self._game_manager.get_parent_object(parent_object.uuid)

        self.x = world_x - px
        self.y = world_y - py

    def _get_data(self):
        return self.__dict__.copy()

    def _check_click_collision(self, click_pos):
        if not self._get_world_rect().collidepoint(click_pos):
            return False

        rotated_mask = pygame.mask.from_surface(self.surface)
        local_x = click_pos[0] - self._get_world_pos()[0]
        local_y = click_pos[1] - self._get_world_pos()[1]
        return rotated_mask.get_at((local_x, local_y))
    
    def _check_rect_collision(self, rect):
        return self._get_world_rect().colliderect(rect)
    
    def _to_dict(self):
        exclude_fields = ['_is_initialized', '_game_manager', 'surface', 'icon']
        return {
            key: value for key, value in self.__dict__.items() 
            if key not in exclude_fields
        }
    
    def _apply_alpha(self, surface):
        if len(self.color) < 4:
            alpha = 255
        else:
            alpha = self.color[-1]
        
        if alpha > 255:
            alpha = 255
        elif alpha < 0:
            alpha = 0
            
        surface.set_alpha(alpha)
        return surface
    
    def __setattr__(self, name, value):
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return
        
        if self._is_for_api:
            if name == 'name' or name == 'uuid' or name == 'type':
                print(f'{name} is a read-only property and cannot be modified.')
                return
        
        if name == 'pos':
            super().__setattr__('x', value[0])
            super().__setattr__('y', value[1])
            super().__setattr__('pos', value)

        elif name == 'size':
            super().__setattr__('width', value[0])
            super().__setattr__('height', value[1])
            super().__setattr__('size', value)

        elif name == 'scale':
            super().__setattr__('scale_x', value[0])
            super().__setattr__('scale_y', value[1])
            super().__setattr__('scale', value)

        else:
            super().__setattr__(name, value)

