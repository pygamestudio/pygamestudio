import sys
import json
import subprocess
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.game.object.type import *
from pygamestudio.game.object.rect import *
from pygamestudio.game.object.canvas import *
from pygamestudio.game.object.text import *
from pygamestudio.game.object.ellipse import *
from pygamestudio.game.object.line import *
from pygamestudio.common.utils.config import *
from pygamestudio.gui.console.logger import Logger
from pygamestudio.common.i18n.translator import Translator as T


class GameManager(QObject):
    scene_saved_signal = Signal()
    scene_loaded_signal = Signal()
    scene_renamed_signal = Signal()

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

    def __init__(self):
        super().__init__()
        self._is_cut = False
        self._project_path = ''
        self._current_scene_file_path = ''
        self._is_current_scene_saved = True
        self._current_canvas_object_uuid = ''
        self._clipboard_content = []
        self._all_object_tree_struct = {}
        self._is_project_ready = False
        self._undo_stack = QUndoStack(self)

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
    
    def is_current_scene_saved(self):
        return self._is_current_scene_saved
    
    def is_current_canvas_visible(self):
        canvas_obj = self._get_object(self._current_canvas_object_uuid)
        return canvas_obj.is_visible if canvas_obj else False
    
    def set_project_ready(self):
        self._is_project_ready = True
    
    def get_ready_for_project(self, project_path):
        self._project_path = project_path
        set_env('__PYGAMESTUDIO_PROJECT_PATH', project_path)

        current_scene_file_relative_path = get_current_scene_from_project_config()
        if current_scene_file_relative_path:
            current_scene_file_path = (Path(self._project_path) / current_scene_file_relative_path).as_posix()
        else:
            current_scene_file_path = ''
        self._load_scene(current_scene_file_path)

    def clean_up(self):
        self._is_cut = False
        self._project_path = ''
        self._current_scene_file_path = ''
        self._is_current_scene_saved = True
        self._current_canvas_object_uuid = ''
        self._clipboard_content = []
        self._all_object_tree_struct = {}
        self._is_project_ready = False

    def get_project_path(self):
        return self._project_path
    
    def add(self, parent_uuid, object_type, object_data={}):
        return self._add(parent_uuid, object_type, object_data)
    
    def _add(self, parent_uuid, object_type, object_data={}):
        obj = self._new_object(object_type, object_data)

        object_tree_struct = {
            obj.uuid: {
                'object': obj,
                'children': []
            }
        }

        if object_type == OBJECT_CANVAS:
            self._add_object_tree_struct(parent_uuid, object_tree_struct)
        else:
            inserted_pos = -1
            self._undo_stack.push(AddObjectCommand(self, parent_uuid, object_tree_struct, inserted_pos))

    def _new_object(self, object_type, object_data={}):
        if object_type == OBJECT_CANVAS:
            obj = ObjectCanvas(self, object_data)
            self._current_canvas_object_uuid = obj.uuid
        elif object_type == OBJECT_RECT:
            obj = ObjectRect(self, object_data)
        elif object_type == OBJECT_TEXT:
            obj = ObjectText(self, object_data)
        elif object_type == OBJECT_ELLIPSE:
            obj = ObjectEllipse(self, object_data)
        elif object_type == OBJECT_LINE:
            obj = ObjectLine(self, object_data)
        return obj

    def rename(self, object_uuid, new_name):   
        obj = self._get_object(object_uuid)     
        old_name = obj.name
        obj.name = new_name

        if old_name == new_name:
            return
        
        self._is_current_scene_saved = False
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'name', old_name, new_name))

    def resize(self, object_uuid, new_size):
        self._is_current_scene_saved = False
        obj = self._get_object(object_uuid)
        old_size = (obj.width, obj.height)    
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

            if value['object'].is_selected:
                selected_objects.append(value['object'])

            for child_object_tree_struct in value['children']:
                _get(child_object_tree_struct, selected_objects)
        
        selected_objects = []
        _get(self._all_object_tree_struct, selected_objects)
        return selected_objects
    
    def get_objects_to_move(self):
        def _get(object_tree_struct, objects_to_move, is_parent_selected):
            if is_parent_selected:
                return
            
            value = list(object_tree_struct.values())[0]
        
            if value['object'].is_selected:
                objects_to_move.append(value['object'])
                is_parent_selected = True

            for child_object_tree_struct in value['children']:
                _get(child_object_tree_struct, objects_to_move, is_parent_selected)
            
        objects_to_move = []
        _get(self._all_object_tree_struct, objects_to_move, False)
        return objects_to_move
    
    def select(self, object_uuid):
        obj = self._get_object(object_uuid)
        if not obj:
            return
        
        obj.is_selected = True
        self.object_selected.emit(object_uuid)

    def deselect(self, object_uuid):
        return self._deselect(object_uuid)
    
    def _deselect(self, object_uuid):
        obj = self._get_object(object_uuid)
        if not obj:
            return
    
        obj.is_selected = False
        self.object_deselected.emit(object_uuid)

    def deselect_all(self):
        def _de(object_tree_struct):
            value = list(object_tree_struct.values())[0]
            obj = value['object']
            if obj.is_selected:
                obj.is_selected = False
                self.object_deselected.emit(obj.uuid)
            
            for child_object_tree_struct in value['children']:
                _de(child_object_tree_struct)
        
        _de(self._all_object_tree_struct)

    def move(self, object_uuid, new_pos):
        obj = self._get_object(object_uuid)
        old_pos = (obj.x, obj.y)

        if old_pos == new_pos:
            return
        
        self._is_current_scene_saved = False
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'pos', old_pos, new_pos))

    def scale(self, object_uuid, new_scale):
        obj = self._get_object(object_uuid)
        old_scale = (obj.scale_x, obj.scale_y)

        if old_scale == new_scale:
            return
        
        self._is_current_scene_saved = False
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'scale', old_scale, new_scale))

    def rotate(self, object_uuid, new_angle):
        obj = self._get_object(object_uuid)
        old_angle = obj.angle

        if old_angle == new_angle:
            return
        
        self._is_current_scene_saved = False
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'angle', old_angle, new_angle))

    def show(self, object_uuid):
        self._is_current_scene_saved = False
        obj = self._get_object(object_uuid)       
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'is_visible', False, True))

    def hide(self, object_uuid):
        self._is_current_scene_saved = False
        obj = self._get_object(object_uuid)       
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'is_visible', True, False))

    def expand(self, object_uuid):
        obj = self._get_object(object_uuid)
        obj.is_expanded = True

    def collapse(self, object_uuid):
        obj = self._get_object(object_uuid)
        obj.is_expanded = False

    def set_color(self, object_uuid, new_color):
        obj = self._get_object(object_uuid)
        old_color = obj.color

        if old_color == new_color:
            return
        
        self._is_current_scene_saved = False
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'color', old_color, new_color))

    def set_border_radius(self, object_uuid, attr, new_border_radius):
        """
        attr can be border_top_left_radius, border_top_right_radius, border_bottom_left_radius or border_bottom_right_radius
        """
        obj = self._get_object(object_uuid)
        old_border_radius = getattr(obj, attr)
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, attr, old_border_radius, new_border_radius))

    def set_thickness(self, object_uuid, new_thickness):
        obj = self._get_object(object_uuid)
        old_thickness = obj.thickness
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'thickness', old_thickness, new_thickness))

    def set_start_point(self, object_uuid, new_start_point):
        obj = self._get_object(object_uuid)
        old_start_point = obj.start_point
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'start_point', old_start_point, new_start_point))

    def set_end_point(self, object_uuid, new_end_point):
        obj = self._get_object(object_uuid)
        old_end_point = obj.end_point
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'end_point', old_end_point, new_end_point))

    def set_text(self, object_uuid, new_text):
        obj = self._get_object(object_uuid)
        old_text = obj.text
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'text', old_text, new_text))

    def set_font_size(self, object_uuid, new_font_size):
        obj = self._get_object(object_uuid)
        old_font_size = obj.font_size
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'font_size', old_font_size, new_font_size))

    def set_font_family(self, object_uuid, new_font_family):
        obj = self._get_object(object_uuid)
        old_font_family = obj.font_family
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'font_family', old_font_family, new_font_family))

    def set_bold_state(self, object_uuid, new_bold_state):
        obj = self._get_object(object_uuid)
        old_bold_state = obj.is_bold
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'is_bold', old_bold_state, new_bold_state))

    def set_italic_state(self, object_uuid, new_italic_state):
        obj = self._get_object(object_uuid)
        old_italic_state = obj.is_italic
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'is_italic', old_italic_state, new_italic_state))
    
    def set_underline_state(self, object_uuid, new_underline_state):
        obj = self._get_object(object_uuid)
        old_underline_state = obj.is_underline
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'is_underline', old_underline_state, new_underline_state))
    
    def set_strikethrough_state(self, object_uuid, new_strikethrough_state):
        obj = self._get_object(object_uuid)
        old_strikethrough_state = obj.is_strikethrough
        self._undo_stack.push(UpdateAttrValueCommand(self, obj, 'is_strikethrough', old_strikethrough_state, new_strikethrough_state))

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
    
    def _get_inserted_pos(self, object_uuid, parent_object_tree_struct=None):
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
    
    def get_parent_object(self, object_uuid):
        return self._get_parent_object(object_uuid)
    
    def add_object_tree_struct(self, parent_uuid, object_tree_struct_to_add, inserted_pos=-1):
        return self._add_object_tree_struct(parent_uuid, object_tree_struct_to_add, inserted_pos)

    def _add_object_tree_struct(self, parent_uuid, object_tree_struct_to_add, inserted_pos=-1): 
        self._is_current_scene_saved = False

        if not self._all_object_tree_struct:
            self._all_object_tree_struct.update(object_tree_struct_to_add)
            self.object_added.emit(parent_uuid, list(object_tree_struct_to_add.keys())[0], 0)
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
        self._is_current_scene_saved = False

        if self._is_cut:
            self._paste_for_cut(parent_uuid)
        else:
            self._paste_for_copy(parent_uuid)

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
        new_object_tree_struct = {}
        key = list(object_tree_struct.keys())[0]
        value = list(object_tree_struct.values())[0]        
        
        if is_new_uuid:
            obj = value['object']
            object_data = obj.get_data()
            new_uuid = str(uuid.uuid4())
            object_data['uuid'] = new_uuid
            new_object_tree_struct[new_uuid] = {
                'object': self._new_object(obj.type, object_data),
                'children': [self._deep_copy_object_tree_struct(child_object_tree_struct, is_new_uuid) for child_object_tree_struct in value['children']]
            }
        else:
            obj = value['object']
            object_data = obj.get_data()
            new_object_tree_struct[key] = {
                'object': self._new_object(obj.type, object_data),
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
        self._is_current_scene_saved = False

        if object_uuid == self._current_canvas_object_uuid:
            self._all_object_tree_struct = {}
            self.object_deleted.emit(object_uuid)
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

    def _save(self):
        self._is_current_scene_saved = True
        set_current_scene_to_project_config(self._current_scene_file_path)
        self.scene_saved_signal.emit()

        def _default(obj):
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')
    
        with open(self._current_scene_file_path, 'w', encoding='utf-8') as f:
            json.dump(self._all_object_tree_struct, f, default=_default, indent=4, ensure_ascii=False)

        Logger.info('Scene saved')

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
        if not self._is_current_scene_saved:
            choice = QMessageBox.warning(QApplication.activeWindow(), T.tr('message_box.warning_title', 'Warning'), T.tr('message_box.warning_scene_save_content', 'The current scene data has been modified. Do you want to save it?'), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            if choice == QMessageBox.StandardButton.Cancel:
                return
            
            elif choice == QMessageBox.StandardButton.Yes:
                self._save_scene()

        if self._current_canvas_object_uuid:
            self._delete_object_tree_struct(self._current_canvas_object_uuid)

        self._current_scene_file_path = current_scene_file_path
        set_current_scene_to_project_config(current_scene_file_path)
        self.scene_loaded_signal.emit()

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
        self._is_current_scene_saved = True

    def is_empty(self):
        return self._all_object_tree_struct == {}
    
    def clear(self):
        self._all_object_tree_struct = {}

    def run_project(self):
        try:
            subprocess.Popen(
                [sys.executable, Path(self._project_path)/'main.py'],
                cwd=self._project_path,
                stdout=None,
                stderr=None,
                shell=False
            )
            Logger.info(f'Run Project{Path(self._project_path).name}')
        except Exception as e:
            Logger.error(f'Failed to run project{Path(self._project_path).name}: {e}')


class AddObjectCommand(QUndoCommand):
    def __init__(self, game_manager, parent_uuid, object_tree_struct, inserted_pos, description=''):
        super().__init__(description)
        self._game_manager = game_manager
        self._parent_uuid = parent_uuid
        self._object_tree_struct = object_tree_struct
        self._inserted_pos = inserted_pos

    def redo(self):
        self._game_manager.add_object_tree_struct(self._parent_uuid, self._object_tree_struct, self._inserted_pos)

    def undo(self):
        self._game_manager.delete_object_tree_struct(list(self._object_tree_struct.keys())[0])


class DeleteObjectCommand(QUndoCommand):
    def __init__(self, game_manager, parent_uuid, object_tree_struct, inserted_pos, description=''):
        super().__init__(description)
        self._game_manager = game_manager
        self._parent_uuid = parent_uuid
        self._object_tree_struct = object_tree_struct
        self._inserted_pos = inserted_pos

    def redo(self):
        self._game_manager.delete_object_tree_struct(list(self._object_tree_struct.keys())[0])

    def undo(self):
        self._game_manager.add_object_tree_struct(self._parent_uuid, self._object_tree_struct, self._inserted_pos)


class UpdateAttrValueCommand(QUndoCommand):
    def __init__(self, game_manager, obj, attr, old_value, new_value, descripton=''):
        super().__init__(descripton)
        self._game_manager = game_manager
        self._obj = obj
        self._attr = attr
        self._old_value = old_value
        self._new_value = new_value

    def redo(self):
        setattr(self._obj, self._attr, self._new_value)
        self._emit_signal(self._attr, self._new_value)

    def undo(self):
        setattr(self._obj, self._attr, self._old_value)
        self._emit_signal(self._attr, self._old_value)

    def _emit_signal(self, attr, value):
        if attr == 'name':
            self._game_manager.object_renamed.emit(self._obj.uuid)
        elif attr == 'is_visible':
            if self._new_value == True:
                self._game_manager.object_showed.emit(self._obj.uuid)  
            else:
                self._game_manager.object_hidden.emit(self._obj.uuid)
        elif attr == 'pos':
            self._game_manager.object_moved.emit(self._obj.uuid)
        elif attr == 'size':
            self._game_manager.object_resized.emit(self._obj.uuid)
        elif attr == 'scale':
            self._game_manager.object_scaled.emit(self._obj.uuid)
        elif attr == 'angle':
            self._game_manager.object_rotated.emit(self._obj.uuid)
        elif attr == 'color':
            self._game_manager.object_color_changed.emit(self._obj.uuid)
        elif attr=='border_top_left_radius' or attr=='border_top_right_radius' or attr=='border_bottom_left_radius' or attr=='border_bottom_right_radius':
            self._game_manager.object_rect_border_radius_changed.emit(self._obj.uuid, attr)
        elif attr == 'start_point':
            self._game_manager.object_line_start_point_changed.emit(self._obj.uuid)
        elif attr == 'end_point':
            self._game_manager.object_line_end_point_changed.emit(self._obj.uuid)
        elif attr == 'thickness':
            self._game_manager.object_line_thickness_changed.emit(self._obj.uuid)
        elif attr == 'text':
            self._game_manager.object_text_changed.emit(self._obj.uuid)
        elif attr == 'font_size':
            self._game_manager.object_font_size_changed.emit(self._obj.uuid)
        elif attr == 'font_family':
            self._game_manager.object_font_family_changed.emit(self._obj.uuid)
        elif attr == 'is_bold':
            self._game_manager.object_bold_state_changed.emit(self._obj.uuid)
        elif attr == 'is_italic':
            self._game_manager.object_italic_state_changed.emit(self._obj.uuid)
        elif attr == 'is_underline':
            self._game_manager.object_underline_state_changed.emit(self._obj.uuid)
        elif attr == 'is_strikethrough':
            self._game_manager.object_strikethrough_state_changed.emit(self._obj.uuid)