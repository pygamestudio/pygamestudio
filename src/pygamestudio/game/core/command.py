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
        elif attr == 'points':
            self._game_manager.object_points_changed.emit(self._obj.uuid)
        elif attr in ('emission_rate', 'max_particles', 'particle_lifetime',
                      'particle_speed', 'particle_size', 'particle_image',
                      'gravity', 'spread_angle'):
            self._game_manager.object_particle_parameter_changed.emit(self._obj.uuid)
        elif attr in ('frame_folder', 'frame_rate', 'auto_play', 'loop',
                      'frame_index'):
            self._game_manager.object_frame_sequence_parameter_changed.emit(self._obj.uuid)
        elif attr in ('placeholder', 'max_length', 'password',
                      'enter_newline', 'text_align', 'text_valign',
                      'background_color', 'border_color'):
            self._game_manager.object_text_input_parameter_changed.emit(self._obj.uuid)
        elif attr in ('collision_enabled', 'collision_type',
                      'collision_offset_x', 'collision_offset_y',
                      'collision_width', 'collision_height',
                      'collision_points'):
            self._game_manager.object_collision_parameter_changed.emit(self._obj.uuid)
        elif attr in ('tileset_path', 'tile_width', 'tile_height',
                      'columns', 'rows'):
            self._game_manager.object_tile_map_parameter_changed.emit(self._obj.uuid)


class TileMapGridCommand(QUndoCommand):
    """Undoable change of a tile map's grid dimensions + EVERY layer's tile
    data as ONE unit.

    Resizing the grid (columns/rows) also reshapes every layer's ``tiles``
    list (cells are trimmed or padded), so undoing must restore the old
    dimensions AND all layer data together - a plain attribute command on
    'columns' alone would lose cells. Each grid is stored as
    (columns, rows, [layers-tiles-lists...]).
    """

    def __init__(self, game_manager, obj, old_grid, new_grid, description=''):
        super().__init__(description or 'Tile Map Grid')
        self._game_manager = game_manager
        self._obj = obj
        self._old_grid = old_grid
        self._new_grid = new_grid

    def _apply(self, columns, rows, layers_tiles):
        setattr(self._obj, 'columns', columns)
        setattr(self._obj, 'rows', rows)
        for i, tiles in enumerate(layers_tiles):
            if 0 <= i < len(self._obj.layers):
                self._obj.layers[i]['tiles'] = list(tiles)
        self._game_manager.object_tile_map_parameter_changed.emit(self._obj.uuid)

    def redo(self):
        columns, rows, layers_tiles = self._new_grid
        self._apply(columns, rows, layers_tiles)

    def undo(self):
        columns, rows, layers_tiles = self._old_grid
        self._apply(columns, rows, layers_tiles)


class TileMapLayerPaintCommand(QUndoCommand):
    """Undoable paint stroke on ONE layer (restores the layer's tiles list)."""

    def __init__(self, game_manager, obj, layer_index, old_tiles, new_tiles,
                 description=''):
        super().__init__(description or 'Tile Map Paint')
        self._game_manager = game_manager
        self._obj = obj
        self._layer_index = int(layer_index)
        self._old_tiles = list(old_tiles)
        self._new_tiles = list(new_tiles)

    def redo(self):
        if 0 <= self._layer_index < len(self._obj.layers):
            self._obj.layers[self._layer_index]['tiles'] = list(self._new_tiles)
        self._game_manager.object_tile_map_parameter_changed.emit(self._obj.uuid)

    def undo(self):
        if 0 <= self._layer_index < len(self._obj.layers):
            self._obj.layers[self._layer_index]['tiles'] = list(self._old_tiles)
        self._game_manager.object_tile_map_parameter_changed.emit(self._obj.uuid)


class TileMapLayerConfigCommand(QUndoCommand):
    """Undoable change of one layer's property (name/visible/collision)."""

    def __init__(self, game_manager, obj, layer_index, attr, old_value,
                 new_value, description=''):
        super().__init__(description or 'Tile Map Layer')
        self._game_manager = game_manager
        self._obj = obj
        self._layer_index = int(layer_index)
        self._attr = attr
        self._old_value = old_value
        self._new_value = new_value

    def _apply(self, value):
        if 0 <= self._layer_index < len(self._obj.layers):
            self._obj.layers[self._layer_index][self._attr] = value
        self._game_manager.object_tile_map_parameter_changed.emit(self._obj.uuid)

    def redo(self):
        self._apply(self._new_value)

    def undo(self):
        self._apply(self._old_value)


class TileMapLayerAddCommand(QUndoCommand):
    """Undoable addition of a new layer (appended at the end)."""

    def __init__(self, game_manager, obj, layer_dict, description=''):
        super().__init__(description or 'Add Tile Map Layer')
        self._game_manager = game_manager
        self._obj = obj
        self._layer_dict = layer_dict
        self._active_before = None

    def redo(self):
        self._active_before = self._obj.get_active_layer_index()
        self._obj.layers.append(dict(self._layer_dict))
        self._obj.set_active_layer_index(len(self._obj.layers) - 1)
        self._obj._bump_content_version()
        self._game_manager.object_tile_map_parameter_changed.emit(self._obj.uuid)

    def undo(self):
        if self._obj.layers:
            self._obj.layers.pop()
        if self._active_before is not None:
            self._obj.set_active_layer_index(
                max(0, min(self._active_before, len(self._obj.layers) - 1)))
        self._obj._bump_content_version()
        self._game_manager.object_tile_map_parameter_changed.emit(self._obj.uuid)


class TileMapLayerRemoveCommand(QUndoCommand):
    """Undoable removal of one layer (the last remaining one cannot be
    removed - guarded by the manager)."""

    def __init__(self, game_manager, obj, layer_index, description=''):
        super().__init__(description or 'Remove Tile Map Layer')
        self._game_manager = game_manager
        self._obj = obj
        self._layer_index = int(layer_index)
        self._layer_dict = None
        self._active_before = None

    def redo(self):
        if not (0 <= self._layer_index < len(self._obj.layers)):
            return
        self._layer_dict = self._obj.layers[self._layer_index]
        self._active_before = self._obj.get_active_layer_index()
        del self._obj.layers[self._layer_index]
        self._obj.set_active_layer_index(
            max(0, min(self._active_before, len(self._obj.layers) - 1)))
        self._obj._bump_content_version()
        self._game_manager.object_tile_map_parameter_changed.emit(self._obj.uuid)

    def undo(self):
        if self._layer_dict is not None:
            self._obj.layers.insert(self._layer_index, self._layer_dict)
        if self._active_before is not None:
            self._obj.set_active_layer_index(self._active_before)
        self._obj._bump_content_version()
        self._game_manager.object_tile_map_parameter_changed.emit(self._obj.uuid)