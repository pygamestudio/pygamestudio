import os
import sys
import re
import json
import inspect
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
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
from pygamestudio.game.object.progress_bar import *
from pygamestudio.game.object.slider import *
from pygamestudio.game.object.frame_sequence import *
from pygamestudio.game.object.tile_map import *
from pygamestudio.api.config.project import get_project_config
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils import assets
from pygamestudio.common.utils import project_modules


class SceneLoader:
    """Runtime mirror of the editor's scene tree.

    Reads the .scene JSON produced by the editor and rebuilds the same object
    tree with is_for_api=True objects, rendering them each frame and driving
    the attached behavior scripts (on_start / on_update / on_destroy).
    """

    # Event families that decide which object a pointer gesture belongs to:
    # the topmost object under the pointer that implements one of them, else
    # its parents (so clicking a button's caption still clicks the button).
    _POINTER_EVENTS = ('on_pressed', 'on_released', 'on_clicked',
                       'on_double_clicked', 'on_right_clicked',
                       'on_drag_start', 'on_drag', 'on_drag_end')
    _HOVER_EVENTS = ('on_mouse_enter', 'on_mouse_leave')

    def __init__(self):
        self._current_scene_path = ''
        self._all_object_tree_struct = {}
        # Objects marked by destroy_object(): they leave the scene at the end
        # of the frame, so a script can destroy anything while the tree is
        # being walked without pulling the ground away from the running frame.
        self._pending_destroy = []
        # Seconds elapsed since the last frame, updated by Game.run() each
        # frame and passed to the scripts' on_update(delta_time) hooks.
        self._delta_time = 0
        # The text-input (TEXT_INPUT) object that currently owns keyboard
        # input at runtime (None when none is focused).
        self._focused_text_input = None
        # The slider (SLIDER) currently being dragged by the pointer (None
        # when none is dragged).
        self._active_slider = None
        # The object that currently owns the pointer hover events (None when
        # the pointer is outside every object), the object that received the
        # pending left press, the one currently dragged and the one that
        # received the pending right press (None when there is none).
        self._hovered_object = None
        self._pressed_object = None
        self._drag_object = None
        self._right_pressed_object = None
        # Collision pairs found during the previous frame: {(uuid, uuid): (obj, obj)}.
        self._collision_pairs = {}
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
        self._reset_runtime_input_state()
        self._all_object_tree_struct = {}
        # Nothing is left to destroy: the whole tree is gone already.
        self._pending_destroy = []
        self._current_scene_path = str(scene_path)
        # Scene files are encrypted in a protected build and plain otherwise.
        scene_data = json.loads(assets.read_text(scene_path))

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
        return obj

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
        elif object_type == OBJECT_PROGRESS_BAR:
            obj = ObjectProgressBar(self, object_data, is_for_api=True)
        elif object_type == OBJECT_SLIDER:
            obj = ObjectSlider(self, object_data, is_for_api=True)
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
            # so the latest script content is always picked up. A protected
            # build ships the script encrypted, so it is decrypted and compiled
            # in memory instead of being read by Python itself.
            module = project_modules.load_module(f'pygamestudio_runtime_script_{obj.uuid}',
                                                 script_absolute_path)
        except Exception as e:
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

        if self._all_object_tree_struct:
            _update(self._all_object_tree_struct, screen_surface)
        self._update_collision_events()
        if self._pending_destroy:
            self._flush_destroyed()

    def _set_delta_time(self, delta_time):
        """Set the per-frame delta time (seconds) passed to scripts' on_update."""
        self._delta_time = delta_time

    def _start_scripts(self):
        """Fire on_start() on every attached script (after the scene is loaded).

        Scripts only have to define the callbacks they use (exactly like the
        object events), so a script without on_start is skipped instead of
        being reported as broken.
        """
        for obj in self._iter_objects():
            self._start_script(obj)

    def _start_script(self, obj):
        """Fire on_start() on one object's script (when it defines the hook)."""
        hook = getattr(obj.script_instance, 'on_start', None)
        if not callable(hook):
            return
        try:
            hook()
        except Exception as e:
            print(T.tr('api.script_start_error', 'Script on_start error for {}: {}').format(obj.name, e), file=sys.stderr)

    def _update_script(self, obj):
        """Fire on_update(delta_time) on an object's attached script (per frame).

        The hook is optional: scripts that only react to events do not have to
        define it, and are not reported as broken when they don't.
        """
        hook = getattr(obj.script_instance, 'on_update', None)
        if not callable(hook):
            return
        try:
            hook(self._delta_time)
        except Exception as e:
            print(T.tr('api.script_update_error', 'Script on_update error for {}: {}').format(obj.name, e), file=sys.stderr)

    def _destroy_scripts(self):
        """Fire on_destroy() on every attached script (before the scene is replaced)."""
        for obj in self._iter_objects():
            self._destroy_script(obj)

    def _destroy_script(self, obj):
        """Fire on_destroy() on one object's script (when it defines the hook)."""
        hook = getattr(obj.script_instance, 'on_destroy', None)
        if not callable(hook):
            return
        try:
            hook()
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

    # ------------------------------------------------- dynamic object creation
    def create_object(self, object_type:str, parent:str='', name:str='', properties:dict=None) -> object:
        """Create an object while the game is running and return it.

        ``parent`` is the uuid, the hierarchy path ("Canvas/Hud", built with
        the editor's list of names) or the name of the object the new one is
        added under; empty means the root of the scene. ``properties`` use the
        same names as the inspector and the .scene file (x, y, width, height,
        color, text, image_path, script_path, ...); everything not given falls
        back to that type's default, exactly like an object created in the
        editor.

        The new object behaves like one that was in the scene from the start:
        its script (``script_path``) is attached, on_start fires right away
        and it is updated and drawn from the next frame on.
        """
        object_type = (object_type or '').strip().upper()

        parent_object = None
        if parent:
            if not self._all_object_tree_struct:
                raise RuntimeError(T.tr('api.no_scene_loaded',
                                        'No scene is loaded yet - load a scene before creating objects.'))
            parent_object = self._resolve_object(parent)
            if parent_object is None:
                raise RuntimeError(T.tr('api.no_parent_object',
                                        'Parent object not found: {}').format(parent))
        elif self._all_object_tree_struct:
            # No parent given: add to the scene root (the canvas).
            parent_object = list(self._all_object_tree_struct.values())[0]['object']

        object_data = dict(properties or {})
        if name:
            object_data['name'] = name

        created = self._add(parent_object.uuid if parent_object else '', object_type, object_data)
        if created is not None:
            self._start_script(created)
        return created

    # ------------------------------------------------- object tree management
    def _resolve_object(self, ref):
        """An object from an object, a uuid, a hierarchy path or a name.

        Only objects that are part of the running scene are returned - a stale
        reference to something that was already removed resolves to None.
        """
        if not self._all_object_tree_struct:
            return None
        if isinstance(ref, ObjectBase):
            return ref if self._get_object_tree_struct_by_uuid(ref.uuid) is not None else None
        if not isinstance(ref, str) or not ref.strip():
            return None
        ref = ref.strip()
        return (self.get_object_by_uuid(ref)
                or self.get_object_by_path(ref)
                or next((obj for obj in self._iter_objects() if obj.name == ref), None))

    def _iter_tree_struct_objects(self, object_tree_struct):
        """Yield one tree struct's object and every object below it (depth-first)."""
        value = list(object_tree_struct.values())[0]
        yield value['object']
        for child_object_tree_struct in value['children']:
            yield from self._iter_tree_struct_objects(child_object_tree_struct)

    def get_root_object(self):
        """The root object of the running scene (the canvas), or None."""
        if not self._all_object_tree_struct:
            return None
        return list(self._all_object_tree_struct.values())[0]['object']

    def get_scene_path(self) -> str:
        """The scene file that is loaded right now ('' when there is none)."""
        return str(self._current_scene_path or '')

    def get_children(self, obj) -> list:
        """The direct children of an object (object, uuid, path or name)."""
        target = self._resolve_object(obj)
        if target is None:
            return []
        object_tree_struct = self._get_object_tree_struct_by_uuid(target.uuid)
        if not object_tree_struct:
            return []
        return [list(child_object_tree_struct.values())[0]['object']
                for child_object_tree_struct in list(object_tree_struct.values())[0]['children']]

    def get_all_objects(self) -> list:
        """Every object of the running scene, in tree order (the root first)."""
        return list(self._iter_objects())

    def find_objects(self, name:str='', object_type:str='', script:str='', visible_only:bool=False) -> list:
        """Every object matching the filters.

        ``name`` and ``script`` are substrings (case-insensitive), ``type`` is
        an exact object type (RECT, TEXT, ...); everything empty means "any".
        """
        name = (name or '').lower()
        object_type = (object_type or '').upper()
        script = (script or '').lower()
        matches = []
        for obj in self._iter_objects():
            if name and name not in obj.name.lower():
                continue
            if object_type and obj.type != object_type:
                continue
            script_path = (getattr(obj, 'script_path', '') or '').lower()
            if script and script not in script_path:
                continue
            if visible_only and not getattr(obj, 'visible', True):
                continue
            matches.append(obj)
        return matches

    def destroy_object(self, obj) -> bool:
        """Remove an object (and its children) from the running scene.

        ``obj`` is the object itself, its uuid, its hierarchy path or its
        name. The object leaves the scene at the **end of the current frame**,
        so a script can destroy anything - even the object it is attached to -
        while the frame is still running; on_destroy() of its script fires when
        it actually leaves. Returns False when there is nothing to destroy.
        """
        target = self._resolve_object(obj)
        if target is None or target in self._pending_destroy:
            return False
        self._pending_destroy.append(target)
        return True

    def _flush_destroyed(self):
        """Apply the deferred destroy_object() calls (end of the frame)."""
        pending, self._pending_destroy = self._pending_destroy, []
        for target in pending:
            self._remove_object(target)

    def _remove_object(self, target) -> bool:
        object_tree_struct = self._get_object_tree_struct_by_uuid(target.uuid)
        if not object_tree_struct:
            return False

        parent = self.get_parent_object(target.uuid)
        if parent is None:
            # The root object itself: the scene becomes empty (loading a scene
            # again reloads it from its file).
            for obj in self._iter_tree_struct_objects(object_tree_struct):
                self._destroy_script(obj)
            self._all_object_tree_struct = {}
            self._current_scene_path = ''
            self._reset_runtime_input_state()
            return True

        parent_tree_struct = self._get_object_tree_struct_by_uuid(parent.uuid)
        if not parent_tree_struct:
            return False
        children = list(parent_tree_struct.values())[0]['children']
        for index, child_object_tree_struct in enumerate(children):
            if list(child_object_tree_struct.keys())[0] != target.uuid:
                continue
            for obj in self._iter_tree_struct_objects(child_object_tree_struct):
                self._destroy_script(obj)
                self._forget_runtime_state(obj)
            del children[index]
            return True
        return False

    def _forget_runtime_state(self, obj):
        """Drop every runtime reference to an object that left the scene."""
        if self._focused_text_input is obj:
            self._clear_text_input_focus(notify=False)
        if self._active_slider is obj:
            self._active_slider = None
        if self._hovered_object is obj:
            self._hovered_object = None
        if self._pressed_object is obj:
            self._pressed_object = None
        if self._drag_object is obj:
            self._drag_object = None
        if self._right_pressed_object is obj:
            self._right_pressed_object = None
        if self._collision_pairs:
            self._collision_pairs = {pair: value for pair, value in self._collision_pairs.items()
                                     if obj.uuid not in pair}

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

    # ---------------------------------------- runtime object events
    def _visible_objects(self, topmost_first=False):
        """Every visible object of the scene, in draw order. Hidden objects
        and the children of hidden objects are skipped (they are not drawn, so
        they are not interactive either). With ``topmost_first`` the
        last-drawn (topmost) object comes first."""
        found = []

        def _gen(object_tree_struct):
            value = list(object_tree_struct.values())[0]
            obj = value['object']
            if not obj.visible:
                return
            found.append(obj)
            for child_object_tree_struct in value['children']:
                _gen(child_object_tree_struct)

        if self._all_object_tree_struct:
            _gen(self._all_object_tree_struct)
        if topmost_first:
            found.reverse()
        return found

    def _hit_object(self, pos):
        """The topmost visible object under ``pos`` (world coords) or None."""
        for obj in self._visible_objects(topmost_first=True):
            if obj._get_world_rect().collidepoint(pos):
                return obj
        return None

    @staticmethod
    def _overrides_hook(obj, event_name):
        """True when ``obj`` overrides the ObjectBase no-op hook.

        The base class declares every shared event as an empty hook (so the
        API is discoverable and Python subclasses can override it). Those
        empty defaults must not count as "implemented" or the event could
        never bubble up to a parent object.
        """
        hook = getattr(obj, event_name, None)
        if not callable(hook):
            return False
        default_hook = getattr(ObjectBase, event_name, None)
        if default_hook is None:
            return True
        return getattr(hook, '__func__', None) is not default_hook

    def _implements_event(self, obj, event_names):
        """True when ``obj`` or its attached script really implements one of
        the events (the empty ObjectBase hooks do not count)."""
        script_instance = getattr(obj, 'script_instance', None)
        for event_name in event_names:
            if self._overrides_hook(obj, event_name):
                return True
            if callable(getattr(script_instance, event_name, None)):
                return True
        return False

    def _event_target(self, pos, event_names):
        """The object a pointer gesture at ``pos`` belongs to.

        The topmost visible object under the pointer wins; when neither it nor
        its attached script implements one of the given events, the gesture
        bubbles up to its parents (so clicking a button's caption still clicks
        the button), and only then to the objects below it. Falls back to the
        topmost object when nobody implements the events.
        """
        topmost = None
        for obj in self._visible_objects(topmost_first=True):
            if not obj._get_world_rect().collidepoint(pos):
                continue
            if topmost is None:
                topmost = obj
            candidate = obj
            while candidate is not None:
                if self._implements_event(candidate, event_names):
                    return candidate
                candidate = self.get_parent_object(candidate.uuid)
        return topmost

    def _emit_object_event(self, obj, event_name, *args):
        """Deliver an object event to the object and to its attached script.

        Scripts are user authored and the older ones predate the object
        events, so a callback that is not defined is skipped (they keep
        working); a callback that raises is reported on stderr without
        stopping the game.
        """
        if obj is None:
            return
        for target in (obj, getattr(obj, 'script_instance', None)):
            hook = getattr(target, event_name, None)
            if not callable(hook):
                continue
            try:
                hook(*args)
            except Exception as e:
                print(T.tr('api.script_event_error', 'Script {} error for {}: {}')
                      .format(event_name, obj.name, e), file=sys.stderr)

    def _update_hover_target(self, pos):
        """Fire on_mouse_leave / on_mouse_enter when the pointed object changes."""
        hovered = self._event_target(pos, self._HOVER_EVENTS)
        if hovered is self._hovered_object:
            return
        previous = self._hovered_object
        self._hovered_object = hovered
        self._emit_object_event(previous, 'on_mouse_leave')
        self._emit_object_event(hovered, 'on_mouse_enter')
        
    def _update_collision_events(self):
        """Fire on_collision_enter / on_collision_exit once per frame.

        Only objects with collision enabled take part (hidden ones included,
        so invisible triggers and walls keep working). The overlapping pairs
        are remembered between frames so entering can be told apart from
        staying; exits are reported before the new enters.
        """
        colliders = [obj for obj in self._iter_objects()
                     if getattr(obj, 'collision_enabled', False)]
        current_pairs = {}
        if len(colliders) > 1:
            for index, obj_a in enumerate(colliders):
                rect_a = obj_a._get_world_rect()
                for obj_b in colliders[index + 1:]:
                    # Cheap world-rect reject before the precise shape test.
                    if not rect_a.colliderect(obj_b._get_world_rect()):
                        continue
                    if not obj_a.is_colliding_with_object(obj_b):
                        continue
                    key = tuple(sorted((obj_a.uuid, obj_b.uuid)))
                    current_pairs[key] = (obj_a, obj_b)

        for key, (obj_a, obj_b) in self._collision_pairs.items():
            if key in current_pairs:
                continue
            self._emit_object_event(obj_a, 'on_collision_exit', obj_b)
            self._emit_object_event(obj_b, 'on_collision_exit', obj_a)
        for key, (obj_a, obj_b) in current_pairs.items():
            if key in self._collision_pairs:
                continue
            self._emit_object_event(obj_a, 'on_collision_enter', obj_b)
            self._emit_object_event(obj_b, 'on_collision_enter', obj_a)
        self._collision_pairs = current_pairs
    # ---------------------------------------- runtime slider drag
    def _sliders(self, topmost_first=False):
        """Yield every visible SLIDER object. With ``topmost_first`` the
        last-drawn (topmost) object comes first (what a click should hit)."""
        found = []
        def _gen(object_tree_struct):
            value = list(object_tree_struct.values())[0]
            obj = value['object']
            if obj.type == OBJECT_SLIDER and obj.visible:
                found.append(obj)
            for child_object_tree_struct in value['children']:
                _gen(child_object_tree_struct)
        if self._all_object_tree_struct:
            _gen(self._all_object_tree_struct)
        if topmost_first:
            found.reverse()
        return found

    def _hit_slider(self, pos):
        """The topmost visible slider under ``pos`` (world coords) or None."""
        for obj in self._sliders(topmost_first=True):
            if obj._get_world_rect().collidepoint(pos):
                return obj
        return None

    def _slider_update_value(self, obj, pos):
        """Map the pointer x inside the slider's world rect back to a value.

        on_value_changed only fires when the value really changes, so a plain
        click that lands on the current handle position stays silent."""
        if obj is None or (int(getattr(obj, 'angle', 0) or 0) % 360) != 0:
            return
        rect = obj._get_world_rect()
        if rect.width <= 0:
            return
        fraction = max(0.0, min(1.0, (pos[0] - rect.left) / float(rect.width)))
        low = float(obj.min_value or 0)
        high = float(obj.max_value or 0)
        if high <= low:
            return
        value = low + fraction * (high - low)
        if value == obj.value:
            return
        obj.set_value(value)
        self._emit_object_event(obj, 'on_value_changed', obj.get_value())

    def handle_pointer_move(self, pos, buttons):
        """Pointer move: hover events (on_mouse_enter / on_mouse_leave), the
        generic drag events (on_drag_start / on_drag / on_drag_end) and the
        value update while dragging a slider. Returns True when the event was
        consumed by a slider drag."""
        self._update_hover_target(pos)
        left_pressed = bool((buttons or (0,))[0])
        if self._active_slider is not None and left_pressed:
            # A slider emits its own drag events (on_drag_start / on_drag_end).
            self._slider_update_value(self._active_slider, pos)
            return True
        if left_pressed and self._pressed_object is not None:
            if self._drag_object is None:
                self._drag_object = self._pressed_object
                self._emit_object_event(self._drag_object, 'on_drag_start')
            self._emit_object_event(self._drag_object, 'on_drag', pos)
        return False

    def handle_pointer_up(self, pos, button=1, clicks=1):
        """Pointer up ends a slider drag (the value is already up to date;
        clicking without dragging also jumps the handle), ends a generic object
        drag and completes the click gestures: on_released on the pressed
        object, plus on_clicked / on_double_clicked when the release lands on
        that same object again (right clicks fire on_right_clicked). Returns
        True when the event was consumed by a slider drag."""
        consumed = False
        if self._active_slider is not None:
            if button == 1:
                self._slider_update_value(self._active_slider, pos)
            self._emit_object_event(self._active_slider, 'on_drag_end')
            self._active_slider = None
            consumed = True

        if button == 1:
            if self._drag_object is not None:
                # Close the drag before the click events of the same release.
                self._emit_object_event(self._drag_object, 'on_drag_end')
                self._drag_object = None
            if self._pressed_object is not None:
                pressed = self._pressed_object
                self._emit_object_event(pressed, 'on_released')
                if self._event_target(pos, self._POINTER_EVENTS) is pressed:
                    self._emit_object_event(pressed, 'on_clicked')
                    if int(clicks or 1) >= 2:
                        self._emit_object_event(pressed, 'on_double_clicked')
            self._pressed_object = None
        elif button == 3 and self._right_pressed_object is not None:
            right_pressed = self._right_pressed_object
            self._right_pressed_object = None
            if self._event_target(pos, self._POINTER_EVENTS) is right_pressed:
                self._emit_object_event(right_pressed, 'on_right_clicked')
        return consumed

    def _set_caret_from_click(self, obj, pos):
        """Place obj's caret at the character under the click. The geometry
        is resolved by the object itself so it matches exactly what is drawn
        (alignment, horizontal scroll, multiline rows, scale/rotation)."""
        try:
            obj.set_caret_from_world_point(pos)
        except Exception:
            obj._runtime_caret = len(obj.text)

    def _set_text_input_focus(self, obj, notify=True):
        """Focus ``obj`` (an input box) or None to blur the current one.

        Focus changes fire on_blur / on_focus; ``notify`` is False while the
        scene is being torn down, where the previous scripts are already
        destroyed.
        """
        if self._focused_text_input is obj:
            return
        previous = self._focused_text_input
        if previous is not None:
            previous._runtime_focused = False
            previous._runtime_caret = 0
        self._focused_text_input = obj
        if obj is not None:
            obj._runtime_focused = True
            obj._runtime_caret = len(obj.text)
        if notify:
            self._emit_object_event(previous, 'on_blur')
            self._emit_object_event(obj, 'on_focus')
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

    def _clear_text_input_focus(self, notify=True):
        self._set_text_input_focus(None, notify=notify)

    def _reset_runtime_input_state(self):
        """Drop every pointer / keyboard / collision tracking state.

        Called when the scene is (re)loaded; no script events are fired while
        tearing the old scene down (its scripts are already destroyed).
        """
        self._clear_text_input_focus(notify=False)
        self._active_slider = None
        self._hovered_object = None
        self._pressed_object = None
        self._drag_object = None
        self._right_pressed_object = None
        self._collision_pairs = {}

    def handle_pointer_down(self, pos, button=1):
        """Pointer down: start dragging the slider under the cursor, else
        fall back to the input-box focus behaviour, and fire the press event
        (on_pressed) of the pointed object. Returns True when a UI control
        (slider or input box) was hit."""
        if button == 1:
            slider = self._hit_slider(pos)
            if slider is not None:
                self._active_slider = slider
                self._emit_object_event(slider, 'on_drag_start')
                self._slider_update_value(slider, pos)

            target = self._hit_text_input(pos)
            if slider is None:
                if target is not None:
                    self._set_text_input_focus(target)
                    self._set_caret_from_click(target, pos)
                else:
                    self._clear_text_input_focus()

            self._pressed_object = self._event_target(pos, self._POINTER_EVENTS)
            self._emit_object_event(self._pressed_object, 'on_pressed')
            return slider is not None or target is not None
        if button == 3:
            self._right_pressed_object = self._event_target(pos, self._POINTER_EVENTS)
        return False

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
        if obj._runtime_insert(text):
            self._emit_object_event(obj, 'on_text_changed', obj.text)
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
                if obj._runtime_insert('\n'):
                    self._emit_object_event(obj, 'on_text_changed', obj.text)
                self._skip_next_newline_textinput = True
            else:
                # Default: Enter confirms and stops editing.
                self._emit_object_event(obj, 'on_submitted', obj.text)
                self._clear_text_input_focus()
        elif key in (pygame.K_ESCAPE, pygame.K_TAB):
            self._clear_text_input_focus()
        elif key == pygame.K_BACKSPACE:
            if obj._runtime_backspace():
                self._emit_object_event(obj, 'on_text_changed', obj.text)
        elif key == pygame.K_DELETE:
            if obj._runtime_delete():
                self._emit_object_event(obj, 'on_text_changed', obj.text)
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

def create_object(object_type:str, parent:str='', name:str='', properties:dict=None) -> object:
    """
    在游戏运行时动态创建一个对象并返回它。
    :param object_type: 对象类型，如 RECT、TEXT、IMAGE、BUTTON、FRAME_SEQUENCE 等
    :param parent: 父对象的 uuid、层级路径（如 Canvas/Hud）或名称，留空则添加到场景根节点
    :param name: 对象名称
    :param properties: 初始属性字典（与属性检查器/.scene 文件同名），如 {'x': 0, 'y': 0, 'width': 50, 'height': 50, 'color': (255, 0, 0, 255)}

    Create an object at runtime (while the game is running) and return it. The
    new object is attached under ``parent`` (the scene root when it is empty)
    with the given properties, its script is loaded, on_start fires right away
    and it is updated/drawn from the next frame on.
    """
    return scene_loader.create_object(object_type, parent, name, properties)

def destroy_object(obj) -> bool:
    """
    从场景中移除一个对象（连同它的子对象）。
    :param obj: 对象本身、uuid、层级路径或名称
    :return: 是否成功登记移除（重复移除返回 False）

    Remove an object (and its children) while the game is running. It leaves
    the scene at the end of the current frame, so this is always safe to call
    from a script (even with the object it is attached to); its script's
    on_destroy() fires when it leaves.
    """
    return scene_loader.destroy_object(obj)

def get_root_object() -> object:
    """场景的根对象（画布），没有加载场景时返回 None。The root object of the scene, or None."""
    return scene_loader.get_root_object()

def get_scene_path() -> str:
    """当前加载的场景文件路径（未加载时为空字符串）。The loaded scene file path ('' when none)."""
    return scene_loader.get_scene_path()

def get_children(obj) -> list:
    """某个对象的直接子对象列表（参数可为对象、uuid、路径或名称）。Direct children of an object."""
    return scene_loader.get_children(obj)

def get_all_objects() -> list:
    """场景中的全部对象（按树的顺序，根对象在最前）。Every object of the scene, in tree order."""
    return scene_loader.get_all_objects()

def find_objects(name:str='', object_type:str='', script:str='', visible_only:bool=False) -> list:
    """
    按条件查找对象。
    :param name: 名称包含的文本（不区分大小写，留空表示不限）
    :param object_type: 对象类型（如 RECT、TEXT，需完全匹配）
    :param script: 脚本路径包含的文本（如 'player.py'）
    :param visible_only: 只返回可见对象

    Every object matching the filters: ``name``/``script`` are case-insensitive
    substrings, ``object_type`` is an exact type; empty means "any".
    """
    return scene_loader.find_objects(name, object_type, script, visible_only)