from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from pygamestudio.game.object.type import *
from pygamestudio.game.object.rect import *
from pygamestudio.game.object.scene import *
from pygamestudio.game.object.text import *
from pygamestudio.game.object.circle import *


class ObjectManager(QObject):
    object_added = Signal(str, str, int)
    object_deleted = Signal(str)
    object_selected = Signal(str)
    object_deselected = Signal(str)
    object_renamed = Signal(str, str)
    object_moved = Signal(str)
    object_scaled = Signal(str)
    object_rotated = Signal(str)
    object_resized = Signal(str)
    object_showed = Signal(str)
    object_hidden = Signal(str)
    object_cut = Signal()
    object_copied = Signal()
    object_color_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._all_object_tree_struct = {}
        self._undo_stack = QUndoStack(self)
        self._is_cut = False
        self._scene_object_uuid = ''
        self._clipboard_content = []

    @property
    def all_object_tree_struct(self):
        return self._all_object_tree_struct

    @property
    def scene_object_uuid(self):
        return self._scene_object_uuid
    
    def add(self, parent_uuid, object_type, obj_data=None):
        obj = self._new_object(object_type, obj_data)

        object_tree_struct = {
            obj.uuid: {
                'object': obj,
                'children': []
            }
        }

        if object_type == OBJECT_SCENE:
            self._add_object_tree_struct(parent_uuid, object_tree_struct)
        else:
            inserted_pos = -1
            self._undo_stack.push(AddObjectCommand(self, parent_uuid, object_tree_struct, inserted_pos))
    
    def _new_object(self, object_type, obj_data=None):
        if object_type == OBJECT_SCENE:
            obj = ObjectScene(self, obj_data)
            self._scene_object_uuid = obj.uuid
        elif object_type == OBJECT_RECT:
            obj = ObjectRect(self, obj_data)
        elif object_type == OBJECT_TEXT:
            obj = ObjectText(self, obj_data)
        elif object_type == OBJECT_CIRCLE:
            obj = ObjectCircle(self, obj_data)

        return obj

    @property
    def undo_stack(self):
        return self._undo_stack

    def rename(self, object_uuid, new_name):   
        obj = self._get_object(object_uuid)     
        old_name = obj.name
        obj.name = new_name

        self._undo_stack.push(UpdateKeyValueCommand(self, obj, 'name', old_name, new_name))

    def resize(self, object_uuid, new_size):
        obj = self._get_object(object_uuid)
        old_size = (obj.width, obj.height)    
        self._undo_stack.push(UpdateKeyValueCommand(self, obj, 'size', old_size, new_size))

    def get_selected_objects_uuids(self):
        # def _get(object_tree_struct, selected_uuid_list):
        #     key = list(object_tree_struct.keys())[0]
        #     value = list(object_tree_struct.values())[0]

        #     if value['object'].is_selected:
        #         selected_uuid_list.append(key)

        #     for child_object_tree_struct in value['children']:
        #         _get(child_object_tree_struct, selected_uuid_list)
        
        # selected_uuid_list = []
        # _get(self._all_object_tree_struct, selected_uuid_list)
        # return selected_uuid_list
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
        self._undo_stack.push(UpdateKeyValueCommand(self, obj, 'pos', old_pos, new_pos))

    def scale(self, object_uuid, new_scale):
        obj = self._get_object(object_uuid)
        old_scale = (obj.scale_x, obj.scale_y)
        self._undo_stack.push(UpdateKeyValueCommand(self, obj, 'scale', old_scale, new_scale))

    def rotate(self, object_uuid, new_angle):
        obj = self._get_object(object_uuid)
        old_angle = obj.angle
        self._undo_stack.push(UpdateKeyValueCommand(self, obj, 'angle', old_angle, new_angle))

    def show(self, object_uuid):
        obj = self._get_object(object_uuid)       
        self._undo_stack.push(UpdateKeyValueCommand(self, obj, 'is_visible', False, True))

    def hide(self, object_uuid):
        obj = self._get_object(object_uuid)       
        self._undo_stack.push(UpdateKeyValueCommand(self, obj, 'is_visible', True, False))

    def expand(self, object_uuid):
        obj = self._get_object(object_uuid)
        obj.is_expanded = True

    def collapse(self, object_uuid):
        obj = self._get_object(object_uuid)
        obj.is_expanded = False

    def set_color(self, object_uuid, new_color):
        obj = self._get_object(object_uuid)
        old_color = obj.color
        self._undo_stack.push(UpdateKeyValueCommand(self, obj, 'color', old_color, new_color))

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
        # def _get(object_uuid, object_tree_struct):
        #     key = list(object_tree_struct.keys())[0]
        #     value = list(object_tree_struct.values())[0]

        #     if object_uuid in [list(child_object_tree_struct.keys())[0] for child_object_tree_struct in value['children']]:
        #         return key
            
        #     for child_object_tree_struct in value['children']:
        #         result = _get(object_uuid, child_object_tree_struct)
        #         if result:
        #             return result
                
        #     return None
        
        # return _get(object_uuid, self._all_object_tree_struct)
    
    def _get_parent_object(self, object_uuid):
        def _get(object_uuid, object_tree_struct):
            # key = list(object_tree_struct.keys())[0]
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
            if object_uuid == self._scene_object_uuid:
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
            if object_uuid == self._scene_object_uuid:
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

    def _paste_for_cut(self, parent_uuid):
        # Can't paste to the object or its children.
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
            # self._delete_object_tree_struct(object_uuid)

            original_parent_uuid = self._get_parent_uuid(object_uuid)
            inserted_pos = self._get_inserted_pos(object_uuid)
            self._undo_stack.push(DeleteObjectCommand(self, original_parent_uuid, object_tree_struct, inserted_pos))
        
        for new_object_tree_struct in deep_copy_clipboard_content:
            # self._add_object_tree_struct(parent_uuid, object_tree_struct)
            self._undo_stack.push(AddObjectCommand(self, parent_uuid, new_object_tree_struct, -1))
        self._undo_stack.endMacro()

        # self.object_pasted_for_cut.emit(parent_uuid, [OrderedDict(d) for d in deep_copy_clipboard_content])
        self._clipboard_content.clear()
        self._is_cut = False

    def _paste_for_copy(self, parent_uuid):
        for i, object_tree_struct in enumerate(self._clipboard_content):
            new_object_tree_struct = self._deep_copy_object_tree_struct(object_tree_struct, True)
            self._clipboard_content[i] = new_object_tree_struct

        self._undo_stack.beginMacro('Copy')
        for new_object_tree_struct in self._clipboard_content:
            # self._add_object_tree_struct(parent_uuid, new_object_tree_struct)
            self._undo_stack.push(AddObjectCommand(self, parent_uuid, new_object_tree_struct, -1))

        self._undo_stack.endMacro()

        # self.object_pasted_for_copy.emit(parent_uuid, [OrderedDict(d) for d in self._clipboard_content])

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
            if object_uuid == self._scene_object_uuid:
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
            # self._add_object_tree_struct(parent_uuid, new_object_tree_struct)
            self._undo_stack.push(AddObjectCommand(self, parent_uuid, new_object_tree_struct, -1))
        self._undo_stack.endMacro()

    def delete(self, object_uuid_list):
        object_tree_struct_list_to_delete = []

        def is_to_discard(object_uuid):
            for object_tree_struct in object_tree_struct_list_to_delete:
                return self._get_object_tree_struct(object_uuid, object_tree_struct)
            return False
        
        object_uuid_list_to_delete = []
        for object_uuid in object_uuid_list:
            if object_uuid == self._scene_object_uuid:
                continue
            
            if is_to_discard(object_uuid):
                continue

            object_tree_struct = self._get_object_tree_struct(object_uuid)
            object_tree_struct_list_to_delete.append(object_tree_struct)
            object_uuid_list_to_delete.append(object_uuid)
            # self._delete_object_tree_struct(object_uuid)
            # 确定inserted_pos

            parent_uuid = self._get_parent_uuid(object_uuid)
            inserted_pos = self._get_inserted_pos(object_uuid)
            self._undo_stack.push(DeleteObjectCommand(self, parent_uuid, object_tree_struct, inserted_pos))

    def delete_object_tree_struct(self, object_uuid):
        return self._delete_object_tree_struct(object_uuid)

    def _delete_object_tree_struct(self, object_uuid):
        def _delete(object_uuid, object_tree_struct):
            # key = list(object_tree_struct.keys())[0]
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


class AddObjectCommand(QUndoCommand):
    def __init__(self, object_manager, parent_uuid, object_tree_struct, inserted_pos, description='Added an object'):
        super().__init__(description)
        self._object_manager = object_manager
        self._parent_uuid = parent_uuid
        self._object_tree_struct = object_tree_struct
        self._inserted_pos = inserted_pos

    def redo(self):
        self._object_manager.add_object_tree_struct(self._parent_uuid, self._object_tree_struct, self._inserted_pos)

    def undo(self):
        self._object_manager.delete_object_tree_struct(list(self._object_tree_struct.keys())[0])


class DeleteObjectCommand(QUndoCommand):
    def __init__(self, object_manager, parent_uuid, object_tree_struct, inserted_pos, description='Deleted an item'):
        super().__init__(description)
        self._object_manager = object_manager
        self._parent_uuid = parent_uuid
        self._object_tree_struct = object_tree_struct
        self._inserted_pos = inserted_pos

    def redo(self):
        self._object_manager.delete_object_tree_struct(list(self._object_tree_struct.keys())[0])

    def undo(self):
        self._object_manager.add_object_tree_struct(self._parent_uuid, self._object_tree_struct, self._inserted_pos)


class UpdateKeyValueCommand(QUndoCommand):
    def __init__(self, object_manager, obj, key, old_value, new_value, descripton='Updated value'):
        super().__init__(descripton)
        self._object_manager = object_manager
        self._obj = obj
        self._key = key
        self._old_value = old_value
        self._new_value = new_value

    def redo(self):
        setattr(self._obj, self._key, self._new_value)
        self._emit_signal(self._key, self._new_value)

    def undo(self):
        setattr(self._obj, self._key, self._old_value)
        self._emit_signal(self._key, self._old_value)

    def _emit_signal(self, key, value):
        if key == 'name':
            self._object_manager.object_renamed.emit(self._obj.uuid, value)
        elif key == 'is_visible':
            if self._new_value == True:
                self._object_manager.object_showed.emit(self._obj.uuid)  
            else:
                self._object_manager.object_hidden.emit(self._obj.uuid)
        elif key == 'pos':
            self._object_manager.object_moved.emit(self._obj.uuid)
        elif key == 'size':
            self._object_manager.object_resized.emit(self._obj.uuid)
        elif key == 'scale':
            self._object_manager.object_scaled.emit(self._obj.uuid)
        elif key == 'angle':
            self._object_manager.object_rotated.emit(self._obj.uuid)
        elif key == 'color':
            self._object_manager.object_color_changed.emit(self._obj.uuid)


        
