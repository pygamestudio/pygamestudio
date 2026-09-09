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
from pygamestudio.game.object.particle import *
from pygamestudio.game.object.text_input import *
from pygamestudio.game.object.frame_sequence import *
from pygamestudio.game.object.tile_map import *
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
        # The text-input (TEXT_INPUT) object that currently owns keyboard
        # input at runtime (None when none is focused).
        self._focused_text_input = None
        # Set right after Enter inserted a '\n' (enter_newline mode) so the
        # duplicate newline TEXTINPUT that some platforms also emit for the
        # Return key is swallowed (otherwise it would double the line break).
        self._skip_next_newline_textinput = False

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
        self._clear_text_input_focus()
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
        elif object_type == OBJECT_PARTICLE:
            obj = ObjectParticle(self, object_data, is_for_api=True)
        elif object_type == OBJECT_TEXT_INPUT:
            obj = ObjectTextInput(self, object_data, is_for_api=True)
        elif object_type == OBJECT_FRAME_SEQUENCE:
            obj = ObjectFrameSequence(self, object_data, is_for_api=True)
        elif object_type == OBJECT_TILE_MAP:
            obj = ObjectTileMap(self, object_data, is_for_api=True)
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

    # ---------------------------------------- runtime text-input focus
    def get_focused_text_input(self):
        """The TEXT_INPUT object currently receiving keyboard input (or None)."""
        return self._focused_text_input

    def _text_inputs(self, topmost_first=False):
        """Yield every visible TEXT_INPUT object. With ``topmost_first`` the
        last-drawn (topmost) object comes first, which is what a mouse click
        should hit."""
        found = []
        def _gen(object_tree_struct):
            value = list(object_tree_struct.values())[0]
            obj = value['object']
            if obj.type == OBJECT_TEXT_INPUT and obj.visible:
                found.append(obj)
            for child_object_tree_struct in value['children']:
                _gen(child_object_tree_struct)
        if self._all_object_tree_struct:
            _gen(self._all_object_tree_struct)
        if topmost_first:
            found.reverse()
        return found

    def _hit_text_input(self, pos):
        """The topmost visible input box under ``pos`` (world coords) or None."""
        for obj in self._text_inputs(topmost_first=True):
            if obj._get_world_rect().collidepoint(pos):
                return obj
        return None

    def _set_caret_from_click(self, obj, pos):
        """Place obj's caret at the character under the click. The geometry
        is resolved by the object itself so it matches exactly what is drawn
        (alignment, horizontal scroll, multiline rows, scale/rotation)."""
        try:
            obj.set_caret_from_world_point(pos)
        except Exception:
            obj._runtime_caret = len(obj.text)

    def _set_text_input_focus(self, obj):
        """Focus ``obj`` (an input box) or None to blur the current one."""
        if self._focused_text_input is obj:
            return
        if self._focused_text_input is not None:
            self._focused_text_input._runtime_focused = False
            self._focused_text_input._runtime_caret = 0
        self._focused_text_input = obj
        if obj is not None:
            obj._runtime_focused = True
            obj._runtime_caret = len(obj.text)
        # Enable OS text input only while a box is focused (drives TEXTINPUT),
        # and key repeat so holding Backspace/Delete/arrows keeps acting.
        try:
            if obj is not None:
                pygame.key.start_text_input()
                pygame.key.set_repeat(400, 30)
            else:
                pygame.key.stop_text_input()
                pygame.key.set_repeat()
        except Exception:
            pass

    def _clear_text_input_focus(self):
        self._set_text_input_focus(None)

    def handle_pointer_down(self, pos, button=1):
        """Click handling for input boxes: focus the box under the pointer,
        blur when clicking anywhere else. Returns True when a box was hit."""
        if button != 1:
            return False
        target = self._hit_text_input(pos)
        if target is not None:
            self._set_text_input_focus(target)
            self._set_caret_from_click(target, pos)
        else:
            self._clear_text_input_focus()
        return target is not None

    def handle_text_input(self, text):
        """Insert typed text into the focused input box. Returns True when a
        box is focused (the event is consumed)."""
        obj = self._focused_text_input
        if obj is None or not text:
            return False
        # Normalize line endings: pasted/IME text often uses CRLF or a lone CR
        # which must never land in the stored text as stray characters.
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        if not text:
            return False
        # Some platforms report the Return key as a TEXTINPUT newline in
        # addition to the KEYDOWN that handle_key_down already consumed (and
        # turned into '\n' when enter_newline is on). Swallow that one.
        if self._skip_next_newline_textinput:
            self._skip_next_newline_textinput = False
            if text == '\n':
                return True
        obj._runtime_insert(text)
        return True

    def handle_key_down(self, key, mod, unicode_char=''):
        """Route non-text keys (Backspace, arrows, Enter, Escape, ...) of a
        focused input box. Returns True when a box is focused (key consumed)."""
        obj = self._focused_text_input
        if obj is None:
            return False

        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if getattr(obj, 'enter_newline', False):
                # enter_newline on: Enter inserts a new line (multi-line).
                obj._runtime_insert('\n')
                self._skip_next_newline_textinput = True
            else:
                # Default: Enter confirms and stops editing.
                self._clear_text_input_focus()
        elif key in (pygame.K_ESCAPE, pygame.K_TAB):
            self._clear_text_input_focus()
        elif key == pygame.K_BACKSPACE:
            obj._runtime_backspace()
        elif key == pygame.K_DELETE:
            obj._runtime_delete()
        elif key == pygame.K_LEFT:
            obj._runtime_caret_move(-1)
        elif key == pygame.K_RIGHT:
            obj._runtime_caret_move(1)
        elif key == pygame.K_HOME:
            obj._runtime_caret_home()
        elif key == pygame.K_END:
            obj._runtime_caret_end()
        return True


scene_loader = SceneLoader()

def load_scene(screen_surface:pygame.Surface, scene_path:str=''):
    scene_loader.load_scene(screen_surface, scene_path)

def get_object_by_path(object_path:str) -> object:
    return scene_loader.get_object_by_path(object_path)

def get_object_by_uuid(object_uuid:str) -> object:
    return scene_loader.get_object_by_uuid(object_uuid)

def get_parent_object(object_uuid:str) -> object:
    return scene_loader.get_parent_object(object_uuid)