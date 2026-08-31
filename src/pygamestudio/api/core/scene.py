import os
import sys
import re
import json
import inspect
import importlib.util
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.rect import *
from pygamestudio.game.object.canvas import *
from pygamestudio.game.object.text import *
from pygamestudio.game.object.ellipse import *
from pygamestudio.game.object.line import *
from pygamestudio.game.object.polygon import *
from pygamestudio.game.object.image import *
from pygamestudio.game.object.button import *
from pygamestudio.api.config.project import get_project_config
from pygamestudio.common.i18n.translator import Translator as T


class SceneLoader:
    """Runtime mirror of the editor's scene tree.

    Reads the .scene JSON produced by the editor and rebuilds the same object
    tree with is_for_api=True objects, rendering them each frame and driving
    the attached behavior scripts (on_start / on_update / on_destroy).
    """

    def __init__(self):
        self._current_scene_path = ''
        self._all_object_tree_struct = {}
        # Seconds elapsed since the last frame, updated by Game.run() each
        # frame and passed to the scripts' on_update(delta_time) hooks.
        self._delta_time = 0

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
            raise RuntimeError(T.tr('api.no_scene_path', 'The scene path {} does not exist.').format(scene_path))

        if self._all_object_tree_struct:
            # The current scene is about to be replaced; let its scripts clean up.
            self._destroy_scripts()
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
        # The whole object tree now exists; fire the scripts' on_start hooks.
        self._start_scripts()
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
        elif object_type == OBJECT_POLYGON:
            obj = ObjectPolygon(self, object_data, is_for_api=True)
        elif object_type == OBJECT_LINE:
            obj = ObjectLine(self, object_data, is_for_api=True)
        elif object_type == OBJECT_IMAGE:
            obj = ObjectImage(self, object_data, is_for_api=True)
        elif object_type == OBJECT_BUTTON:
            obj = ObjectButton(self, object_data, is_for_api=True)
        else:
            raise RuntimeError(T.tr('api.unknown_object_type', 'Unknown object type: {}').format(object_type))

        # Attach the behavior script (if any) so the script's lifecycle hooks
        # can be driven later (see ObjectBase._start/_update_surface/_destroy).
        obj.script_instance = self._load_script(obj)
        return obj

    def _load_script(self, obj):
        """
        Dynamically load and instantiate the object's behavior script.

        The script module (obj.script_path, relative to the project) is loaded
        with importlib, the first user-defined class is instantiated with
        owner=obj, and the instance is stored on obj.script_instance. Returns
        None when no script is attached or it fails to load (the failure is
        reported to stderr but does not stop the game).
        """
        if not obj.script_path:
            return None

        script_absolute_path = Path(os.environ.get('PROJECT_PATH', '')) / obj.script_path
        if not script_absolute_path.exists():
            print(T.tr('api.no_script_path', 'The script path {} does not exist.').format(script_absolute_path), file=sys.stderr)
            return None

        try:
            # A unique module name per object keeps every scene (re)load fresh,
            # so the latest script content is always picked up.
            module_name = f'pygamestudio_runtime_script_{obj.uuid}'
            spec = importlib.util.spec_from_file_location(module_name, script_absolute_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            print(T.tr('api.fail_to_load_script', 'Failed to load script {}: {}').format(script_absolute_path, e), file=sys.stderr)
            return None

        script_class = self._get_script_class(module)
        if script_class is None:
            print(T.tr('api.no_script_class', 'No script class found in {}.').format(script_absolute_path), file=sys.stderr)
            return None

        try:
            return script_class(obj)
        except Exception as e:
            print(T.tr('api.fail_to_init_script', 'Failed to initialize script {}: {}').format(script_absolute_path, e), file=sys.stderr)
            return None

    @staticmethod
    def _get_script_class(module):
        """Return the first class defined in the given script module (ignores imports)."""
        for name, value in module.__dict__.items():
            if inspect.isclass(value) and value.__module__ == module.__name__:
                return value
        return None
    
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
            obj._update_surface()
            self._update_script(obj)
            
            if obj.visible:
                for child_object_tree_struct in value['children']:
                    _update(child_object_tree_struct, obj._get_surface())

                obj._draw(parent_surface)

        _update(self._all_object_tree_struct, screen_surface)

    def _set_delta_time(self, delta_time):
        """Set the per-frame delta time (seconds) passed to scripts' on_update."""
        self._delta_time = delta_time

    def _start_scripts(self):
        """Fire on_start() on every attached script (after the scene is loaded)."""
        for obj in self._iter_objects():
            if not obj.script_instance:
                continue
            try:
                obj.script_instance.on_start()
            except Exception as e:
                print(T.tr('api.script_start_error', 'Script on_start error for {}: {}').format(obj.name, e), file=sys.stderr)

    def _update_script(self, obj):
        """Fire on_update(delta_time) on an object's attached script (per frame)."""
        if not obj.script_instance:
            return
        try:
            obj.script_instance.on_update(self._delta_time)
        except Exception as e:
            print(T.tr('api.script_update_error', 'Script on_update error for {}: {}').format(obj.name, e), file=sys.stderr)

    def _destroy_scripts(self):
        """Fire on_destroy() on every attached script (before the scene is replaced)."""
        for obj in self._iter_objects():
            if not obj.script_instance:
                continue
            try:
                obj.script_instance.on_destroy()
            except Exception as e:
                print(T.tr('api.script_destroy_error', 'Script on_destroy error for {}: {}').format(obj.name, e), file=sys.stderr)

    def _iter_objects(self):
        """Yield every object in the current scene tree (depth-first)."""
        def _gen(object_tree_struct):
            value = list(object_tree_struct.values())[0]
            yield value['object']
            for child_object_tree_struct in value['children']:
                yield from _gen(child_object_tree_struct)

        if self._all_object_tree_struct:
            yield from _gen(self._all_object_tree_struct)

    def _get_object_tree_struct_by_path(self, object_path):
        def _get(name, target_item_index, current_item_index, recursion_time, part_number, object_tree_struct):
            key = list(object_tree_struct.keys())[0]
            value = list(object_tree_struct.values())[0]
        
            if part_number < recursion_time:
                return None
            elif part_number == recursion_time:
                if target_item_index == current_item_index and name == value['object'].name:
                    return {key: value}
                elif target_item_index is None and name == value['object'].name: 
                    return {key: value}
                else:
                    return None
            else:
                recursion_time += 1
                for i, child_object_tree_struct in enumerate(value['children']):
                    result = _get(name, target_item_index, i, recursion_time, part_number, child_object_tree_struct)
                    if result:
                        return result
                
            return None

        path_parts = object_path.strip('/').split('/')
        if not path_parts:
            return None
        
        for i, part in enumerate(path_parts):
            match = re.fullmatch(r'([^\[\]]+)(?:\[(\d+)\])?', part.strip())
            if not match:
                return None
            
            recursion_time = 0
            name = match.group(1)
            target_item_index = int(match.group(2)) if match.group(2) is not None else None
            object_tree_struct = _get(name, target_item_index, 0, recursion_time, i, self._all_object_tree_struct)

            if i < len(path_parts)-1:
                if object_tree_struct == None:
                    return None
            else:
                return object_tree_struct
        
    def _get_object_tree_struct_by_uuid(self, object_uuid, parent_object_tree_struct=None):
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
        object_tree_struct = self._get_object_tree_struct_by_path(object_path)
        return list(object_tree_struct.values())[0]['object'] if object_tree_struct else None
    
    def get_object_by_uuid(self, object_uuid:str):
        object_tree_struct = self._get_object_tree_struct_by_uuid(object_uuid)
        return object_tree_struct[object_uuid]['object'] if object_tree_struct else None
    
    def get_parent_object(self, object_uuid:str):
        def _get(object_uuid, object_tree_struct):
            value = list(object_tree_struct.values())[0]

            if object_uuid in [list(child_object_tree_struct.keys())[0] for child_object_tree_struct in value['children']]:
                return value['object']
            
            for child_object_tree_struct in value['children']:
                result = _get(object_uuid, child_object_tree_struct)
                if result:
                    return result
                
            return None
        
        return _get(object_uuid, self._all_object_tree_struct)
    

scene_loader = SceneLoader()

def load_scene(screen_surface:pygame.Surface, scene_path:str=''):
    scene_loader.load_scene(screen_surface, scene_path)

def get_object_by_path(object_path:str) -> object:
    return scene_loader.get_object_by_path(object_path)

def get_object_by_uuid(object_uuid:str) -> object:
    return scene_loader.get_object_by_uuid(object_uuid)

def get_parent_object(object_uuid:str) -> object:
    return scene_loader.get_parent_object(object_uuid)