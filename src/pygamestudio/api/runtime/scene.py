import os
import json
import pygame
from pathlib import Path
from pygamestudio.api.runtime.config import get_project_config

from pygamestudio.game.object.type import *
from pygamestudio.game.object.rect import *
from pygamestudio.game.object.canvas import *
from pygamestudio.game.object.text import *
from pygamestudio.game.object.ellipse import *


class SceneLoader:
    def __init__(self):
        self._current_scene_path = ''
        self._all_object_tree_struct = {}

    def load_scene(self, screen_surface:pygame.Surface, scene_path:str=''):
        if not scene_path and self._current_scene_path or scene_path and scene_path==self._current_scene_path:
            self._update_scene(screen_surface)
            return
        
        project_config = get_project_config()
        if not project_config['asset']['current_scene']:
            return
        
        if not scene_path:
            scene_path = Path(os.environ.get('PROJECT_PATH')) / project_config['asset']['current_scene']

        if not Path(scene_path).exists():
            raise RuntimeError(f'没有在scene文件夹下找到名为{scene_path}的场景文件')

        self._all_object_tree_struct = {}
        self._current_scene_path = scene_path
        with open(scene_path, 'r', encoding='utf-8') as f:
            scene_data = json.load(f)

        def _l(parent_uuid, object_tree_struct):
            if not object_tree_struct:
                self._add('', OBJECT_CANVAS)
                return
            
            key = list(object_tree_struct.keys())[0]
            value = list(object_tree_struct.values())[0]

            object_data = value['object']
            self._add(parent_uuid, value['object']['type'], object_data)
            children = value['children']
            for child_object_tree_struct in children:
                _l(key, child_object_tree_struct)

        _l('', scene_data)
        self._update_scene(screen_surface)

    def _add(self, parent_uuid, object_type, object_data={}):
        obj = self._new_object(object_type, object_data)

        object_tree_struct = {
            obj.uuid: {
                'object': obj,
                'children': []
            }
        }

        self._add_object_tree_struct(parent_uuid, object_tree_struct)

    def _new_object(self, object_type, object_data={}):
        if object_type == OBJECT_CANVAS:
            obj = ObjectCanvas(self, object_data, is_for_api=True)
        elif object_type == OBJECT_RECT:
            obj = ObjectRect(self, object_data, is_for_api=True)
        elif object_type == OBJECT_TEXT:
            obj = ObjectText(self, object_data, is_for_api=True)
        elif object_type == OBJECT_ELLIPSE:
            obj = ObjectEllipse(self, object_data, is_for_api=True)

        return obj
    
    def _add_object_tree_struct(self, parent_uuid, object_tree_struct_to_add): 
        if not self._all_object_tree_struct:
            self._all_object_tree_struct.update(object_tree_struct_to_add)
            return
        
        def _add(parent_uuid, object_tree_struct_to_update, object_tree_struct_to_add):
            key = list(object_tree_struct_to_update.keys())[0]
            value = list(object_tree_struct_to_update.values())[0]

            if parent_uuid == key:
                value['children'].append(object_tree_struct_to_add)
                return True
            
            for child_object_tree_struct in value['children']:
                result = _add(parent_uuid, child_object_tree_struct, object_tree_struct_to_add)
                if result:
                    return result
                
            return False
        
        _add(parent_uuid, self._all_object_tree_struct, object_tree_struct_to_add)

    def _update_scene(self, screen_surface:pygame.Surface):
        screen_surface.fill((0, 0, 0))

        def _update(object_tree_struct, parent_surface):
            value = list(object_tree_struct.values())[0]
            obj = value['object']
            obj.update_surface()
            
            if obj.is_visible:
                for child_object_tree_struct in value['children']:
                    _update(child_object_tree_struct, obj.get_surface())

                obj.draw(parent_surface)

        _update(self._all_object_tree_struct, screen_surface)

    def _get_object_tree_struct(self, object_uuid, parent_object_tree_struct=None):
        def _get(object_uuid, object_tree_struct):
            key = list(object_tree_struct.keys())[0]
            value = list(object_tree_struct.values())[0]
            if object_uuid == key:
                return {key:value}
                
            for child_object_tree_struct in value['children']:
                result = _get(object_uuid, child_object_tree_struct)
                if result:
                    return result
                
            return None
        
        if not parent_object_tree_struct:
            parent_object_tree_struct = self._all_object_tree_struct
        return _get(object_uuid, parent_object_tree_struct)
    
    def get_object_by_path(self, object_path:str):
        ...

    def get_object_by_uuid(self, object_uuid:str):
        object_tree_struct = self._get_object_tree_struct(object_uuid)
        return object_tree_struct[object_uuid]['object'] if object_tree_struct else None

    def get_object_by_name(self, object_name:str):
        ...


scene_loader = SceneLoader()

def load_scene(screen_surface:pygame.Surface, scene_path:str=''):
    scene_loader.load_scene(screen_surface, scene_path)

def get_object_by_path(object_path:str) -> object:
    return scene_loader.get_object_by_path(object_path)

def get_object_by_uuid(object_uuid:str) -> object:
    return scene_loader.get_object_by_uuid(object_uuid)

def get_object_by_name(object_name:str) -> object:
    return scene_loader.get_object_by_name(object_name)