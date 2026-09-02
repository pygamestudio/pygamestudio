import sys
import json
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.game.core.command import *
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
from pygamestudio.game.object.frame_sequence import *
from pygamestudio.common.utils.config import *
from pygamestudio.gui.console.logger import Logger
from pygamestudio.common.i18n.translator import Translator as T


class GameManager(QObject):
    """Central editor hub that owns the scene object tree and the undo stack.

    The whole scene is stored in ``_all_object_tree_struct``, a dict shaped
    like ``{uuid: {'object': <ObjectBase>, 'children': [<same shape>, ...]}}``.
    Every mutation that must be undoable goes through a QUndoCommand pushed
    onto ``_undo_stack`` (Ctrl+Z / Ctrl+Y). After a command runs, the matching
    Qt signal below is emitted so all panels (hierarchy, scene, inspector)
    refresh the affected object.
    """

    # Life cycle / whole-scene events.
    scene_saved_signal = Signal()
    scene_loaded_signal = Signal()
    scene_renamed_signal = Signal()

    # Generic object events (uuid of the affected object is always the payload).
    object_added = Signal(str, str, int)
    object_deleted = Signal(str)
    object_selected = Signal(str)
    object_deselected = Signal(str)
    object_renamed = Signal(str)
    object_moved = Signal(str)
    object_scaled = Signal(str)
    object_rotated = Signal(str)
    object_resized = Signal(str)
    object_showed = Signal(str)
    object_hidden = Signal(str)
    object_cut = Signal()
    object_copied = Signal()
    object_color_changed = Signal(str)

    # Attribute-specific events (only fired when that attribute changes).
    object_rect_border_radius_changed = Signal(str, str)
    object_line_start_point_changed = Signal(str)
    object_line_end_point_changed = Signal(str)
    object_line_thickness_changed = Signal(str)
    object_text_changed = Signal(str)
    object_font_size_changed = Signal(str)
    object_font_family_changed = Signal(str)
    object_bold_state_changed = Signal(str)
    object_italic_state_changed = Signal(str)
    object_underline_state_changed = Signal(str)
    object_strikethrough_state_changed = Signal(str)
    object_image_path_changed = Signal(str)
    object_font_path_changed = Signal(str)
    object_script_path_changed = Signal(str)
    object_points_changed = Signal(str)
    object_particle_parameter_changed = Signal(str)
    object_frame_sequence_parameter_changed = Signal(str)

    # Emitted whenever the "current scene has unsaved changes" flag flips
    # (True = saved, False = unsaved), so the UI can show unsaved indicators.
    scene_dirty_state_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self._is_cut = False
        self._project_path = ''
        self._is_loading_scene = False
        self._current_scene_file_path = ''
        self._is_current_scene_saved = True
        self._current_canvas_object_uuid = ''
        self._clipboard_content = []
        self._all_object_tree_struct = {}
        self._saved_object_tree_struct = {}
        self._is_project_ready = False
        self._undo_stack = QUndoStack(self)

        # Running game processes. Kept referenced so a running game is not
        # killed by garbage collection; removed again when it exits.
        self._game_processes = []

        self._set_up()

    def _set_up(self):
        self._set_signal()

    def _set_signal(self):
        # Recompute the saved-state flag after every undo command (push/undo/redo).
        self._undo_stack.indexChanged.connect(self._mark_scene_changed)

    @property
    def all_object_tree_struct(self):
        return self._all_object_tree_struct

    @property
    def is_project_ready(self):
        return self._is_project_ready

    @property
    def canvas_object_uuid(self):
        return self._current_canvas_object_uuid
    
    @property
    def undo_stack(self):
        return self._undo_stack
    
    @property
    def current_scene_file_path(self):
        return self._current_scene_file_path
    
    def set_current_scene_file_path(self, path):
        self._current_scene_file_path = path
    
    @property
    def is_current_scene_saved(self):
        """Read-only public view of the scene's saved state. The private
        _is_current_scene_saved property is the writable storage that emits
        scene_dirty_state_changed whenever the value flips."""
        return self._is_current_scene_saved

    @property
    def _is_current_scene_saved(self):
        """Whether the current scene has unsaved changes. Writing to this
        attribute emits scene_dirty_state_changed whenever the value flips,
        so every mutation site reports the new state without extra plumbing."""
        return self.__dict__.get('_is_current_scene_saved', True)

    @_is_current_scene_saved.setter
    def _is_current_scene_saved(self, value):
        old_value = self.__dict__.get('_is_current_scene_saved', True)
        self.__dict__['_is_current_scene_saved'] = value
        if old_value != value:
            self.scene_dirty_state_changed.emit(value)

    def _serialize_tree(self, object_tree_struct):
        """Recursively convert the scene tree into a comparable snapshot of its
        persistent state, used to tell whether the scene actually differs from
        disk. UI-only state ('selected', 'expanded') is already dropped by
        ObjectBase._to_dict, so it never counts as scene content."""
        serialized = {}
        for key, value in object_tree_struct.items():
            object_data = value['object']._to_dict()
            serialized[key] = {
                'object': object_data,
                'children': [self._serialize_tree(child) for child in value['children']],
            }
        return serialized

    def _mark_scene_changed(self, *args):
        """Recompute whether the current scene differs from the last saved
        snapshot. Called after every undo-stack change and after direct tree
        mutations, so net-zero edits (e.g. hide then show) or undos that
        restore the saved state don't leave the scene flagged as unsaved.
        Skipped while a scene is being (re)built."""
        if self._is_loading_scene:
            return
        self._is_current_scene_saved = self._serialize_tree(self._all_object_tree_struct) == self._saved_object_tree_struct
    
    def is_current_canvas_visible(self):
        canvas_obj = self._get_object(self._current_canvas_object_uuid)
        return canvas_obj.visible if canvas_obj else False
    
    def set_project_ready(self):
        self._is_project_ready = True
        Logger.info(T.tr('gm.project_init', 'Project initialized Successfully'))
    
    def get_ready_for_project(self, project_path):
        """Open a project: remember its path, then load the last scene in it."""
        self._project_path = project_path
        set_env('__PYGAMESTUDIO_PROJECT_PATH', project_path)

        # Re-open the scene the user was editing last time (stored in the
        # project config), or start from an empty canvas if there is none.
        current_scene_file_relative_path = get_current_scene_from_project_config()
        if current_scene_file_relative_path:
            current_scene_file_path = (Path(self._project_path) / current_scene_file_relative_path).as_posix()
        else:
            current_scene_file_path = ''

        self._load_scene(current_scene_file_path)
        self.deselect_all()

    def clean_up(self):
        """Reset every editor state back to "no project loaded"."""
        self._is_cut = False
        self._project_path = ''
        self._current_scene_file_path = ''
        self._is_current_scene_saved = True
        self._current_canvas_object_uuid = ''
        self._clipboard_content = []
        self._all_object_tree_struct = {}
        self._saved_object_tree_struct = {}
        self._is_project_ready = False

    def get_project_path(self):
        return self._project_path
    
    def add(self, parent_uuid, object_type, object_data={}):
        return self._add(parent_uuid, object_type, object_data)
    
    def _add(self, parent_uuid, object_type, object_data={}):
        """Create an object of the given type and insert it (undoably) into the tree."""
        obj, object_tree_struct = self._new_object(object_type, object_data)

        if object_type == OBJECT_CANVAS:
            # A canvas is the root of the whole scene; it is not tracked by
            # the undo stack because there is always exactly one.
            self._add_object_tree_struct(parent_uuid, object_tree_struct)
     
        elif object_type == OBJECT_BUTTON:
            inserted_pos = -1
            self._undo_stack.push(AddObjectCommand(self, parent_uuid, object_tree_struct, inserted_pos))

            if not self._is_loading_scene:
                # A button spawns with a default child text label so the user
                # can immediately see (and edit) its caption.
                child_text_object, child_text_object_tree_struct = self._new_object(OBJECT_TEXT, {})
                child_text_object.pos = (20, 0)
                child_text_object.color = (0, 0, 0, 255)
                self._add_object_tree_struct(obj.uuid, child_text_object_tree_struct)
                self.deselect_all()
                self.select(obj.uuid)

        else:
            inserted_pos = -1
            self._undo_stack.push(AddObjectCommand(self, parent_uuid, object_tree_struct, inserted_pos))

    def _new_object(self, object_type, object_data={}):
        """Instantiate the right ObjectBase subclass for an object type.

        The canvas is special: creating one also makes it the current canvas
        (the coordinate space every other object lives in).
        """
        if object_type == OBJECT_CANVAS:
            obj = ObjectCanvas(self, object_data)
            self._current_canvas_object_uuid = obj.uuid
        elif object_type == OBJECT_RECT:
            obj = ObjectRect(self, object_data)
        elif object_type == OBJECT_TEXT:
            obj = ObjectText(self, object_data)
        elif object_type == OBJECT_ELLIPSE:
            obj = ObjectEllipse(self, object_data)
        elif object_type == OBJECT_POLYGON:
            obj = ObjectPolygon(self, object_data)
        elif object_type == OBJECT_LINE:
            obj = ObjectLine(self, object_data)
        elif object_type == OBJECT_IMAGE:
            obj = ObjectImage(self, object_data)
        elif object_type == OBJECT_BUTTON:
            obj = ObjectButton(self, object_data)
        elif object_type == OBJECT_PARTICLE:
            obj = ObjectParticle(self, object_data)
        elif object_type == OBJECT_FRAME_SEQUENCE:
            obj = ObjectFrameSequence(self, object_data)

        object_tree_struct = {
            obj.uuid: {
                'object': obj,
                'children': []
            }
        }
    
        return obj, object_tree_struct

    def rename(self, object_uuid, new_name):   
        """Rename an object. The change is undoable (UpdateAttrValueCommand)."""
        obj = self._get_object(object_uuid)     
        old_name = obj.name
        obj.name = new_name

        if old_name == new_name:
            return
        
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'name', old_name, new_name))

    def resize(self, object_uuid, new_size):
        """Resize an object (undoable). The old size is restored by undo()."""
        obj = self._get_object(object_uuid)
        old_size = (obj.width, obj.height)

        if old_size == new_size:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'size', old_size, new_size))
        
    def get_selected_objects_uuids(self):
        selected_uuids = []
        selected_objects = self.get_selected_objects()
        for obj in selected_objects:
            selected_uuids.append(obj.uuid)
            
        return selected_uuids

    def get_selected_objects(self):
        def _get(object_tree_struct, selected_objects):
            value = list(object_tree_struct.values())[0]

            if value['object'].selected:
                selected_objects.append(value['object'])

            for child_object_tree_struct in value['children']:
                _get(child_object_tree_struct, selected_objects)
        
        selected_objects = []
        _get(self._all_object_tree_struct, selected_objects)
        return selected_objects
    
    def get_objects_to_move(self):
        """Return the selected objects that should move together.

        When a parent is selected, its whole subtree moves implicitly, so
        children are pruned out (is_parent_selected short-circuits the walk).
        The canvas itself is never moved.
        """
        def _get(object_tree_struct, objects_to_move, is_parent_selected):
            if is_parent_selected:
                return
            
            value = list(object_tree_struct.values())[0]
        
            if value['object'].selected:
                if value['object'].uuid != self._current_canvas_object_uuid:
                    objects_to_move.append(value['object'])
                    is_parent_selected = True

            for child_object_tree_struct in value['children']:
                _get(child_object_tree_struct, objects_to_move, is_parent_selected)
            
        objects_to_move = []
        _get(self._all_object_tree_struct, objects_to_move, False)
        return objects_to_move
    
    def select(self, object_uuid):
        """Select an object and notify the panels via object_selected."""
        obj = self._get_object(object_uuid)
        if not obj:
            return
        
        obj.selected = True
        self.object_selected.emit(object_uuid)

    def deselect(self, object_uuid):
        return self._deselect(object_uuid)
    
    def _deselect(self, object_uuid):
        obj = self._get_object(object_uuid)
        if not obj:
            return
    
        obj.selected = False
        self.object_deselected.emit(object_uuid)

    def deselect_all(self):
        def _de(object_tree_struct):
            value = list(object_tree_struct.values())[0]
            obj = value['object']
            if obj.selected:
                obj.selected = False
                self.object_deselected.emit(obj.uuid)
            
            for child_object_tree_struct in value['children']:
                _de(child_object_tree_struct)
        
        _de(self._all_object_tree_struct)

    def move(self, object_uuid, new_pos):
        """Move an object (undoable). Each call pushes one undo entry."""
        obj = self._get_object(object_uuid)
        old_pos = (obj.x, obj.y)

        if old_pos == new_pos:
            return
        
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'pos', old_pos, new_pos))

    def scale(self, object_uuid, new_scale):
        """Scale an object (undoable)."""
        obj = self._get_object(object_uuid)
        old_scale = (obj.scale_x, obj.scale_y)

        if old_scale == new_scale:
            return
        
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'scale', old_scale, new_scale))

    def rotate(self, object_uuid, new_angle):
        """Rotate an object (undoable)."""
        obj = self._get_object(object_uuid)
        old_angle = obj.angle

        if old_angle == new_angle:
            return
        
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'angle', old_angle, new_angle))

    def show(self, object_uuid):
        """Show the object (undoable). No-op when it is already visible."""
        obj = self._get_object(object_uuid)

        if obj.visible:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'visible', False, True))

    def hide(self, object_uuid):
        """Hide the object (undoable). No-op when it is already hidden."""
        obj = self._get_object(object_uuid)

        if not obj.visible:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'visible', True, False))

    def expand(self, object_uuid):
        obj = self._get_object(object_uuid)
        obj.expanded = True

    def collapse(self, object_uuid):
        obj = self._get_object(object_uuid)
        obj.expanded = False

    def set_color(self, object_uuid, new_color):
        obj = self._get_object(object_uuid)
        old_color = obj.color

        if old_color == new_color:
            return
        
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'color', old_color, new_color))

    def set_border_radius(self, object_uuid, attr, new_border_radius):
        """
        attr can be border_top_left_radius, border_top_right_radius, border_bottom_left_radius or border_bottom_right_radius
        """
        obj = self._get_object(object_uuid)
        old_border_radius = getattr(obj, attr)

        if old_border_radius == new_border_radius:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, attr, old_border_radius, new_border_radius))

    def set_thickness(self, object_uuid, new_thickness):
        obj = self._get_object(object_uuid)
        old_thickness = obj.thickness

        if old_thickness == new_thickness:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'thickness', old_thickness, new_thickness))

    def set_start_point(self, object_uuid, new_start_point):
        obj = self._get_object(object_uuid)
        old_start_point = obj.start_point

        if old_start_point == new_start_point:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'start_point', old_start_point, new_start_point))

    def set_end_point(self, object_uuid, new_end_point):
        obj = self._get_object(object_uuid)
        old_end_point = obj.end_point

        if old_end_point == new_end_point:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'end_point', old_end_point, new_end_point))

    def set_text(self, object_uuid, new_text):
        obj = self._get_object(object_uuid)
        old_text = obj.text

        if old_text == new_text:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'text', old_text, new_text))

    def set_font_size(self, object_uuid, new_font_size):
        obj = self._get_object(object_uuid)
        old_font_size = obj.font_size

        if old_font_size == new_font_size:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'font_size', old_font_size, new_font_size))

    def set_font_family(self, object_uuid, new_font_family):
        obj = self._get_object(object_uuid)
        old_font_family = obj.font_family

        if old_font_family == new_font_family:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'font_family', old_font_family, new_font_family))

    def set_bold_state(self, object_uuid, new_bold_state):
        obj = self._get_object(object_uuid)
        old_bold_state = obj.bold

        if old_bold_state == new_bold_state:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'bold', old_bold_state, new_bold_state))

    def set_italic_state(self, object_uuid, new_italic_state):
        obj = self._get_object(object_uuid)
        old_italic_state = obj.italic

        if old_italic_state == new_italic_state:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'italic', old_italic_state, new_italic_state))
    
    def set_underline_state(self, object_uuid, new_underline_state):
        obj = self._get_object(object_uuid)
        old_underline_state = obj.underline

        if old_underline_state == new_underline_state:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'underline', old_underline_state, new_underline_state))
    
    def set_strikethrough_state(self, object_uuid, new_strikethrough_state):
        obj = self._get_object(object_uuid)
        old_strikethrough_state = obj.strikethrough

        if old_strikethrough_state == new_strikethrough_state:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'strikethrough', old_strikethrough_state, new_strikethrough_state))

    def set_image_path(self, object_uuid, new_image_path):
        obj = self._get_object(object_uuid)
        old_image_path = obj.image_path

        if old_image_path == new_image_path:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'image_path', old_image_path, new_image_path))

    def set_font_path(self, object_uuid, new_font_path):
        obj = self._get_object(object_uuid)
        old_font_path = obj.font_path

        if old_font_path == new_font_path:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'font_path', old_font_path, new_font_path))

    def set_script_path(self, object_uuid, new_script_path):
        obj = self._get_object(object_uuid)
        old_script_path = obj.script_path

        if old_script_path == new_script_path:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'script_path', old_script_path, new_script_path))

    def set_points(self, object_uuid, new_points):
        obj = self._get_object(object_uuid)
        old_points = obj.points

        if old_points == new_points:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'points', old_points, new_points))

    def set_particle_parameter(self, object_uuid, attr, new_value):
        """Change one particle-emitter parameter (undoable)."""
        obj = self._get_object(object_uuid)
        old_value = getattr(obj, attr)

        if old_value == new_value:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, attr, old_value, new_value))

    def set_frame_sequence_parameter(self, object_uuid, attr, new_value):
        """Change one frame-sequence parameter (undoable)."""
        obj = self._get_object(object_uuid)
        old_value = getattr(obj, attr)

        if old_value == new_value:
            return

        self._undo_stack.push(UpdateAttrValueCommand(self, obj, attr, old_value, new_value))

    def _get_object_tree_struct(self, object_uuid, parent_object_tree_struct=None):
        """Depth-first search for a subtree by uuid. Returns the one-node
        dict {uuid: {'object':..., 'children': [...]}} or None if not found."""
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

        # _all_object_tree_struct is {} when a new scene is loaded.
        if not parent_object_tree_struct:
            return None
        
        return _get(object_uuid, parent_object_tree_struct)
    
    def _get_inserted_pos(self, object_uuid, parent_object_tree_struct=None):
        """Index of object_uuid among its siblings; -1 if not found. Used to
        restore the exact position when an undo re-inserts a deleted object."""
        def _get(object_uuid, object_tree_struct):
            value = list(object_tree_struct.values())[0]

            for i, child_object_tree_struct in enumerate(value['children']):
                if object_uuid == list(child_object_tree_struct.keys())[0]:
                    return i
                    
                result = _get(object_uuid, child_object_tree_struct)
                if result != -1:
                    return result
                
            return -1
        
        if not parent_object_tree_struct:
            parent_object_tree_struct = self._all_object_tree_struct
        return _get(object_uuid, parent_object_tree_struct)

    def _get_parent_uuid(self, object_uuid):
        parent_obj = self._get_parent_object(object_uuid)
        if parent_obj:
            return parent_obj.uuid
        return None

    def _get_parent_object(self, object_uuid):
        """Return the direct parent ObjectBase of object_uuid, or None for the root."""
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
    
    def _get_descendant_objects_uuids(self, object_uuid, is_to_get_child_only=False):
        descendant_objects = self._get_descendant_objects(object_uuid, is_to_get_child_only)
        descendant_objects_uuids = [obj.uuid for obj in descendant_objects]
        return descendant_objects_uuids

    def _get_descendant_objects(self, object_uuid, is_to_get_child_only=False):
        """Collect the descendants of object_uuid (children only, or the whole
        subtree when is_to_get_child_only is False)."""
        def _get(object_uuid, descendant_objects, object_tree_struct):
            value = list(object_tree_struct.values())[0]
            
            for child_object_tree_struct in value['children']:
                child_value = list(child_object_tree_struct.values())[0]
                descendant_objects.append(child_value['object'])
                
                if not is_to_get_child_only:
                    _get(object_uuid, descendant_objects, child_object_tree_struct)
                        
        descendant_objects = []
        _get(object_uuid, descendant_objects, self._get_object_tree_struct(object_uuid))
        return descendant_objects
    
    def get_parent_uuid(self, object_uuid):
        return self._get_parent_uuid(object_uuid)
    
    def get_parent_object(self, object_uuid):
        return self._get_parent_object(object_uuid)
    
    def get_descendant_objects(self, object_uuid, is_to_get_child_only=False):
        return self._get_descendant_objects(object_uuid, is_to_get_child_only)
    
    def add_object_tree_struct(self, parent_uuid, object_tree_struct_to_add, inserted_pos=-1):
        return self._add_object_tree_struct(parent_uuid, object_tree_struct_to_add, inserted_pos)

    def _add_object_tree_struct(self, parent_uuid, object_tree_struct_to_add, inserted_pos=-1): 
        """Attach a subtree to a parent and emit object_added for every node
        that became visible, so the hierarchy tree can animate the insertion."""
        if not self._all_object_tree_struct:
            # Empty scene: the first node becomes the root.
            self._all_object_tree_struct.update(object_tree_struct_to_add)
            self.object_added.emit(parent_uuid, list(object_tree_struct_to_add.keys())[0], 0)
            self._mark_scene_changed()
            return
        
        def _send_signal_for_deeper_object_tree_struct(object_tree_struct):
            parent_key = list(object_tree_struct.keys())[0]
            parent_value = list(object_tree_struct.values())[0]

            if not parent_value['children']:
                return
                
            for i, child_object_tree_struct in enumerate(parent_value['children']):
                self.object_added.emit(parent_key, list(child_object_tree_struct.keys())[0], i)
                _send_signal_for_deeper_object_tree_struct(child_object_tree_struct)
        
        def _add(parent_uuid, object_tree_struct_to_update, object_tree_struct_to_add):
            key = list(object_tree_struct_to_update.keys())[0]
            value = list(object_tree_struct_to_update.values())[0]

            if parent_uuid == key:
                if inserted_pos == -1:
                    value['children'].append(object_tree_struct_to_add)
                else:
                    value['children'].insert(inserted_pos, object_tree_struct_to_add)
                self.object_added.emit(parent_uuid, list(object_tree_struct_to_add.keys())[0], inserted_pos)
                _send_signal_for_deeper_object_tree_struct(object_tree_struct_to_add)
                return True
            
            for child_object_tree_struct in value['children']:
                result = _add(parent_uuid, child_object_tree_struct, object_tree_struct_to_add)
                if result:
                    return result
                
            return False
        
        _add(parent_uuid, self._all_object_tree_struct, object_tree_struct_to_add)
        self._mark_scene_changed()

    def get_object(self, object_uuid):
        return self._get_object(object_uuid)

    def _get_object(self, object_uuid):
        object_tree_struct = self._get_object_tree_struct(object_uuid)
        return object_tree_struct[object_uuid]['object'] if object_tree_struct else None

    def _extract_uuid_from_object_tree_struct(self, object_tree_struct):
        object_uuid_list = []
        key = list(object_tree_struct.keys())[0]
        value = list(object_tree_struct.values())[0]
        object_uuid_list.append(key)

        for child_object_tree_struct in value['children']:
            object_uuid_list.extend(self._extract_uuid_from_object_tree_struct(child_object_tree_struct))
        
        return object_uuid_list
    
    def is_cut(self):
        return self._is_cut
    
    def get_clipboard_content(self):
        return self._clipboard_content
    
    def get_all_uuid_from_clipboard_content(self):
        all_object_uuid_list = []
        for object_tree_struct in self._clipboard_content:
            all_object_uuid_list.extend(self._extract_uuid_from_object_tree_struct(object_tree_struct))
        return all_object_uuid_list
    
    def cut(self, object_uuid_list):
        """Mark the selected objects as cut and remember their subtrees.

        Pasting later removes the originals and re-adds copies under the new
        parent (all in one undo macro, so cut+paste undoes as a single step).
        """
        def is_to_discard(object_uuid):
            for object_tree_struct in self._clipboard_content:
                return self._get_object_tree_struct(object_uuid, object_tree_struct)
            return False
        
        self._is_cut = True
        self._clipboard_content = []
        
        for object_uuid in object_uuid_list:
            if object_uuid == self._current_canvas_object_uuid:
                continue
            
            if is_to_discard(object_uuid):
                continue

            object_tree_struct = self._get_object_tree_struct(object_uuid)
            self._clipboard_content.append(object_tree_struct)

        self.object_cut.emit()

    def copy(self, object_uuid_list):
        """Remember the selected subtrees for a later paste (no originals removed)."""
        def is_to_discard(object_uuid):
            for object_tree_struct in self._clipboard_content:
                return self._get_object_tree_struct(object_uuid, object_tree_struct)
            return False
        
        self._is_cut = False
        self._clipboard_content = []

        for object_uuid in object_uuid_list:
            if object_uuid == self._current_canvas_object_uuid:
                continue
            
            if is_to_discard(object_uuid):
                continue

            object_tree_struct = self._get_object_tree_struct(object_uuid)
            self._clipboard_content.append(object_tree_struct)
        
        self.object_copied.emit()

    def paste(self, parent_uuid):
        if self._is_cut:
            self._paste_for_cut(parent_uuid)
        else:
            self._paste_for_copy(parent_uuid)
        self._mark_scene_changed()

    def _paste_for_cut(self, parent_uuid):
        # Don't paste to the cut object or its children.
        for object_tree_struct in self._clipboard_content:
            if self._get_object_tree_struct(parent_uuid, object_tree_struct):
                self._clipboard_content.clear()
                self._is_cut = False
                return

        deep_copy_clipboard_content = []
        for object_tree_struct in self._clipboard_content:
            new_object_tree_struct = self._deep_copy_object_tree_struct(object_tree_struct, False)
            deep_copy_clipboard_content.append(new_object_tree_struct)
        
        self._undo_stack.beginMacro('Cut')
        for object_tree_struct in self._clipboard_content:
            object_uuid = list(object_tree_struct.keys())[0]

            original_parent_uuid = self._get_parent_uuid(object_uuid)
            inserted_pos = self._get_inserted_pos(object_uuid)
            self._undo_stack.push(DeleteObjectCommand(self, original_parent_uuid, object_tree_struct, inserted_pos))
        
        for new_object_tree_struct in deep_copy_clipboard_content:
            self._undo_stack.push(AddObjectCommand(self, parent_uuid, new_object_tree_struct, -1))
        self._undo_stack.endMacro()

        self._clipboard_content.clear()
        self._is_cut = False

    def _paste_for_copy(self, parent_uuid):
        for i, object_tree_struct in enumerate(self._clipboard_content):
            new_object_tree_struct = self._deep_copy_object_tree_struct(object_tree_struct, True)
            self._clipboard_content[i] = new_object_tree_struct

        self._undo_stack.beginMacro('Copy')
        for new_object_tree_struct in self._clipboard_content:
            self._undo_stack.push(AddObjectCommand(self, parent_uuid, new_object_tree_struct, -1))

        self._undo_stack.endMacro()

    def _deep_copy_object_tree_struct(self, object_tree_struct, is_new_uuid):
        """Deep-copy a subtree by re-creating every object from its data.

        When is_new_uuid is True (paste/duplicate) every node gets a fresh
        uuid; when False (cut-paste) the original uuids are preserved so the
        delete/add pair keeps object identity.
        """
        new_object_tree_struct = {}
        key = list(object_tree_struct.keys())[0]
        value = list(object_tree_struct.values())[0]        
        
        if is_new_uuid:
            obj = value['object']
            object_data = obj._get_data()
            new_uuid = str(uuid.uuid4())
            object_data['uuid'] = new_uuid
            new_object_tree_struct[new_uuid] = {
                'object': self._new_object(obj.type, object_data)[0],
                'children': [self._deep_copy_object_tree_struct(child_object_tree_struct, is_new_uuid) for child_object_tree_struct in value['children']]
            }
        else:
            obj = value['object']
            object_data = obj._get_data()
            new_object_tree_struct[key] = {
                'object': self._new_object(obj.type, object_data)[0],
                'children': [self._deep_copy_object_tree_struct(child_object_tree_struct, is_new_uuid) for child_object_tree_struct in value['children']]
            }

        return new_object_tree_struct
    
    def duplicate(self, object_uuid_list):
        def is_to_discard(object_uuid):
            for object_tree_struct in object_tree_struct_list_to_duplicate:
                return self._get_object_tree_struct(object_uuid, object_tree_struct)
            return False
        
        object_tree_struct_list_to_duplicate = []
        for object_uuid in object_uuid_list:
            if object_uuid == self._current_canvas_object_uuid:
                continue
            
            if is_to_discard(object_uuid):
                continue

            object_tree_struct = self._get_object_tree_struct(object_uuid)
            object_tree_struct_list_to_duplicate.append(object_tree_struct)

        content_to_duplicate = []
        for object_tree_struct in object_tree_struct_list_to_duplicate:
            new_object_tree_struct = self._deep_copy_object_tree_struct(object_tree_struct, True)
            parent_uuid = self._get_parent_uuid(list(object_tree_struct.keys())[0])
            content_to_duplicate.append((parent_uuid, new_object_tree_struct))

        self._undo_stack.beginMacro('Duplicate')
        for parent_uuid, new_object_tree_struct in content_to_duplicate:
            self._undo_stack.push(AddObjectCommand(self, parent_uuid, new_object_tree_struct, -1))
        self._undo_stack.endMacro()

    def delete(self, object_uuid_list):
        self._delete(object_uuid_list)

    def _delete(self, object_uuid_list):
        object_tree_struct_list_to_delete = []

        def is_to_discard(object_uuid):
            for object_tree_struct in object_tree_struct_list_to_delete:
                return self._get_object_tree_struct(object_uuid, object_tree_struct)
            return False
        
        object_uuid_list_to_delete = []
        for object_uuid in object_uuid_list:
            if object_uuid == self._current_canvas_object_uuid:
                continue
            
            if is_to_discard(object_uuid):
                continue

            object_tree_struct = self._get_object_tree_struct(object_uuid)
            object_tree_struct_list_to_delete.append(object_tree_struct)
            object_uuid_list_to_delete.append(object_uuid)

            parent_uuid = self._get_parent_uuid(object_uuid)
            inserted_pos = self._get_inserted_pos(object_uuid)
            self._undo_stack.push(DeleteObjectCommand(self, parent_uuid, object_tree_struct, inserted_pos))

    def delete_object_tree_struct(self, object_uuid):
        return self._delete_object_tree_struct(object_uuid)

    def _delete_object_tree_struct(self, object_uuid):
        if object_uuid == self._current_canvas_object_uuid:
            self._all_object_tree_struct = {}
            self.object_deleted.emit(object_uuid)
            self._mark_scene_changed()
            return

        def _delete(object_uuid, object_tree_struct):
            value = list(object_tree_struct.values())[0]
            for child_object_tree_struct in value['children']:
                if object_uuid == list(child_object_tree_struct.keys())[0]:
                    value['children'].remove(child_object_tree_struct)
                    self.object_deleted.emit(object_uuid)
                    return True
                
                result = _delete(object_uuid, child_object_tree_struct)
                if result:
                    return result
            
            return False
            
        _delete(object_uuid, self._all_object_tree_struct)
        self._mark_scene_changed()

    def _save(self):
        """Write the whole scene tree to the current .scene file as JSON.

        Objects are serialized through their _to_dict() method (see
        ObjectBase); _default handles nested objects transparently.
        """
        set_current_scene_to_project_config(self._current_scene_file_path)

        def _default(obj):
            if hasattr(obj, '_to_dict'):
                return obj._to_dict()
            raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')
    
        with open(self._current_scene_file_path, 'w', encoding='utf-8') as f:
            json.dump(self._all_object_tree_struct, f, default=_default, indent=4, ensure_ascii=False)

        # The scene now matches the file; remember it as the clean snapshot so
        # later net-zero edits don't falsely mark the scene as unsaved.
        self._saved_object_tree_struct = self._serialize_tree(self._all_object_tree_struct)
        self._is_current_scene_saved = True
        self.scene_saved_signal.emit()
        Logger.info(T.tr('scene.scene_saved', 'Scene saved'))

    def save_scene(self):
        return self._save_scene()
    
    def _save_scene(self):
        if not self._current_scene_file_path:
            self._save_as()
            return
        
        self._save()
    
    def save_as(self):
        return self._save_as()
    
    def _save_as(self):
        path, _ = QFileDialog.getSaveFileName(QApplication.activeWindow(), T.tr('dialog.save_title', 'Save File'), self._project_path, f"{T.tr('dialog.format', 'Format')} (*.scene)")
        if not path:
            return
        
        self._current_scene_file_path = path
        self._save()

    def load_scene(self, current_scene_file_path):
        return self._load_scene(current_scene_file_path)
    
    def _load_scene(self, current_scene_file_path):
        """Load a .scene file and rebuild the whole object tree.

        Unsaved changes trigger a save prompt first. The canvas is replaced
        first, then every node is re-created recursively via _add() so the
        same signal flow as interactive editing runs. The undo stack is cleared
        because the new tree has no history.
        """
        if not self._is_current_scene_saved:
            choice = QMessageBox.warning(QApplication.activeWindow(), T.tr('message_box.warning_title', 'Warning'), T.tr('message_box.warning_scene_save_content', 'The current scene data has been modified. Do you want to save it?'), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            if choice == QMessageBox.StandardButton.Cancel:
                return
            
            elif choice == QMessageBox.StandardButton.Yes:
                self._save_scene()
        
        self._is_loading_scene = True
        if self._current_canvas_object_uuid:
            self._delete_object_tree_struct(self._current_canvas_object_uuid)

        self._current_scene_file_path = current_scene_file_path
        set_current_scene_to_project_config(current_scene_file_path)

        if not current_scene_file_path or not Path(current_scene_file_path).exists():
            data = {}
        else:
            with open(self._current_scene_file_path, 'r', encoding='utf-8') as f:
                data = json.loads(f.read())
                if not data:
                    data = {}
                
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

        _l('', data)
        self._undo_stack.clear()
        # Remember the freshly loaded tree as the clean snapshot.
        self._saved_object_tree_struct = self._serialize_tree(self._all_object_tree_struct)
        self._is_current_scene_saved = True
        self.scene_loaded_signal.emit()

        self._is_loading_scene = False

    def is_empty(self):
        return self._all_object_tree_struct == {}
    
    def clear(self):
        self._all_object_tree_struct = {}

    def run_project(self):
        """Launch the project's main.py in a separate process and forward its
        stdout/stderr to the editor console (info for stdout, error for stderr)."""
        try:
            # QProcess integrates with the Qt event loop, so the game's output
            # is read asynchronously without ever blocking the editor UI.
            process = QProcess(self)
            process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
            process.setWorkingDirectory(self._project_path)
            process.readyReadStandardOutput.connect(lambda: self._on_game_stdout_ready(process))
            process.readyReadStandardError.connect(lambda: self._on_game_stderr_ready(process))
            process.finished.connect(lambda code, status: self._on_game_finished(process, code, status))
            process.errorOccurred.connect(lambda error: self._on_game_error(process, error))

            # Force UTF-8 and unbuffered I/O in the child process so its piped
            # output decodes reliably AND arrives in real time (Python
            # block-buffers stdout when it is a pipe, which would otherwise
            # batch the logs into chunks).
            process_env = QProcess.systemEnvironment()
            process_env.append('PYTHONIOENCODING=utf-8')
            process_env.append('PYTHONUTF8=1')
            process_env.append('PYTHONUNBUFFERED=1')
            process.setEnvironment(process_env)

            process.start(sys.executable, [str(Path(self._project_path) / 'main.py')])
            self._game_processes.append(process)
            Logger.info(T.tr('scene.run_project', 'Run Project {}').format(Path(self._project_path).name))
        except Exception as e:
            Logger.error(T.tr('scene.failed_to_run_project', 'Failed to Run Project {}: {}').format(Path(self._project_path).name, e))

    def _on_game_stdout_ready(self, process):
        """Forward the game's stdout lines to the console as info logs."""
        self._forward_game_output(process, process.readAllStandardOutput(), is_error=False)

    def _on_game_stderr_ready(self, process):
        """Forward the game's stderr lines to the console as error logs."""
        self._forward_game_output(process, process.readAllStandardError(), is_error=True)

    def _forward_game_output(self, process, data, is_error=False):
        """Decode a chunk of the game's output and log it line by line.

        A partial line that may span two reads is buffered on the process
        until the rest of the line arrives.
        """
        if not data:
            return

        text = bytes(data).decode('utf-8', errors='replace')
        buffer = getattr(process, '_game_output_buffer', '') + text
        lines = buffer.split('\n')
        # The last element may be an incomplete line; keep it for the next read.
        process._game_output_buffer = lines.pop()
        for line in lines:
            line = line.strip()
            if line:
                if is_error:
                    Logger.error(line)
                else:
                    Logger.info(line)

    def _on_game_finished(self, process, exit_code, exit_status):
        """Flush any leftover output and log the game's exit code."""
        remaining = getattr(process, '_game_output_buffer', '').strip()
        if remaining:
            Logger.info(remaining)
        Logger.info(T.tr('scene.run_project_finished', 'Project {} exited with code {}').format(Path(self._project_path).name, exit_code))
        if process in self._game_processes:
            self._game_processes.remove(process)
        process.deleteLater()

    def _on_game_error(self, process, error):
        """Log when the game process fails to start or crashes."""
        Logger.error(T.tr('scene.failed_to_run_project', 'Failed to Run Project {}: {}').format(Path(self._project_path).name, error))
        if process in self._game_processes:
            self._game_processes.remove(process)
        process.deleteLater()