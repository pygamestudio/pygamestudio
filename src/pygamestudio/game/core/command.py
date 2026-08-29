from PySide6.QtGui import QUndoCommand


class AddObjectCommand(QUndoCommand):
    """Undoable command that inserts an object (subtree) into the scene tree.

    redo(): attach the object_tree_struct to its parent.
    undo(): detach it again (the whole subtree is removed at once).
    """

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
    """Undoable command that removes an object (subtree) from the scene tree.

    The exact inverse of AddObjectCommand: redo() detaches the subtree,
    undo() re-attaches it at the original parent and position.
    """

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
    """Undoable command that changes a single attribute of an object.

    Both redo() and undo() write the attribute directly through setattr() and
    then emit the matching GameManager signal so every panel (inspector,
    hierarchy, scene view, ...) stays in sync with the new value.
    """

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
        # Dispatch the changed attribute to the panel that displays it, so the
        # UI reflects the (possibly undone/redone) value immediately.
        if attr == 'name':
            self._game_manager.object_renamed.emit(self._obj.uuid)
        elif attr == 'visible':
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
        elif attr == 'bold':
            self._game_manager.object_bold_state_changed.emit(self._obj.uuid)
        elif attr == 'italic':
            self._game_manager.object_italic_state_changed.emit(self._obj.uuid)
        elif attr == 'underline':
            self._game_manager.object_underline_state_changed.emit(self._obj.uuid)
        elif attr == 'strikethrough':
            self._game_manager.object_strikethrough_state_changed.emit(self._obj.uuid)
        elif attr == 'image_path':
            self._game_manager.object_image_path_changed.emit(self._obj.uuid)
        elif attr == 'font_path':
            self._game_manager.object_font_path_changed.emit(self._obj.uuid)
        elif attr == 'script_path':
            self._game_manager.object_script_path_changed.emit(self._obj.uuid)