
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.common.utils.system import get_system_lang
from pygamestudio.common.utils.path import get_project_path
from pygamestudio.common.i18n.translator import Translator as T


class ObjectBase:
    """Base class for every scene object (rect, text, image, ...).

    Used in two modes:
    - Editor mode (is_for_api=False): driven by GameManager, properties are
      serialized to the .scene file, and pygame surfaces are rendered into the
      editor's scene view.
    - Runtime mode (is_for_api=True): driven by SceneLoader, the object is
      rendered into the game window and a behavior script (script_path) can be
      attached.
    """

    def __init__(self, game_manager, object_data={}, is_for_api=False):
        self._is_for_api = is_for_api
        self._game_manager = game_manager

        # Editor-only bookkeeping (never serialized to disk).
        internal_properties = {
            'is_expanded': True,
            'is_selected': False,
            'icon': '',
        }
    
        if not self._is_for_api:
            for key, value in internal_properties.items():
                setattr(self, key, object_data.get(key, value))

        self.surface = None
        # The behavior script instance attached to this object at runtime
        # (created from script_path). None when no script is attached.
        self.script_instance = None

        # Path of the object script (a .py file inside the project, e.g.
        # './script/new.py', relative to the project path). Empty string means
        # no script is attached. It is serialized into the .scene file and used
        # by the runtime to attach a behavior script to the object.
        self.script_path = object_data.get('script_path', '')

    def is_pressed(self, x:int, y:int) -> bool:
        return True if self._check_click_collision((x, y)) else False
    
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

    def on_start(self):
        """User hook: called once when the object enters the scene at runtime."""
        ...

    def on_destroy(self):
        """User hook: called when the object leaves the scene at runtime."""
        ...
    
    def on_update(self):
        """User hook: called every frame (before drawing) at runtime."""
        ...

    def _start(self):
        """Internal wrapper for on_start (driven by the script system)."""
        self.on_start()

    def _destroy(self):
        """Internal wrapper for on_destroy (driven by the script system)."""
        self.on_destroy()

    def _draw(self, parent_surface):
        """Blit this object onto its parent surface at its local position.

        In editor mode a blue selection outline is drawn around the object.
        """
        parent_surface.blit(self.surface, self._get_rect())
        if not self._is_for_api and self.is_selected:
            pygame.draw.rect(parent_surface, (0, 122, 204), self._get_rect(), width=2)

    def _get_surface(self):
        return self.surface

    def _update_surface(self):
        self.on_update()

    def _get_world_pos(self):
        return self._get_world_rect().topleft

    def _get_rect(self):
        # Get the rect of the object. Note that the rect returned by Surface.get_rect() always starts at (0, 0).
        return pygame.Rect(self.x, self.y, self.surface.width, self.surface.height)

    def _get_world_rect(self):
        """Rect in scene coordinates: local rect shifted up the parent chain
        until the canvas root, so nested objects report absolute positions."""
        world_rect = self._get_rect()
        parent_object = self._game_manager.get_parent_object(self.uuid)

        while parent_object:
            parent_rect = parent_object._get_rect()
            world_rect.move_ip(parent_rect.x, parent_rect.y)
            parent_object = self._game_manager.get_parent_object(parent_object.uuid)

        return world_rect
    
    def _set_world_rect(self, world_x, world_y):
        """Inverse of _get_world_rect: convert a scene (world) position back
        into the object's local position by subtracting parent offsets."""
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
        """Return the object's full attribute dict (used to clone objects)."""
        return self.__dict__.copy()

    def _check_click_collision(self, click_pos):
        """Pixel-perfect hit test: first a cheap world-rect test, then a
        per-pixel alpha mask so transparent pixels don't count as a hit."""
        if not self._get_world_rect().collidepoint(click_pos):
            return False

        rotated_mask = pygame.mask.from_surface(self.surface)
        local_x = click_pos[0] - self._get_world_pos()[0]
        local_y = click_pos[1] - self._get_world_pos()[1]
        return rotated_mask.get_at((local_x, local_y))
    
    def _check_rect_collision(self, rect):
        return self._get_world_rect().colliderect(rect)
    
    def _to_dict(self):
        """Serialize the object for the .scene JSON file.

        Runtime-only / non-persistent fields (surface, script instance, the
        manager reference, editor selection state, ...) are excluded so the
        file stays small and reloadable.
        """
        exclude_fields = ['_is_initialized', '_is_for_api', '_game_manager', 'surface', 'icon', 'script_instance']
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
        """Intercept attribute writes to keep derived fields in sync.

        - pos/size/scale also update their x/y/width/height components.
        - script_path is stored relative to the project path.
        - At runtime, name/uuid/type are read-only (identity fields).
        """
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

        elif name == 'script_path':
            # Store the script path relative to the project (e.g. './script/x.py').
            if value == '':
                super().__setattr__('script_path', '')
            else:
                project_path = Path(get_project_path())
                new_script_path = Path(value).absolute()
                try:
                    super().__setattr__('script_path', new_script_path.relative_to(project_path).as_posix())
                except ValueError:
                    super().__setattr__('script_path', new_script_path.as_posix())

        else:
            super().__setattr__(name, value)

