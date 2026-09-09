from pathlib import Path
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.game.object.type import *
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils.path import get_project_path
from pygamestudio.gui.inspector.color import ColorPicker
from pygamestudio.gui.inspector.component.label import PropertyLabel
from pygamestudio.gui.inspector.layout.rect import INSPECTOR_LAYOUT_RECT
from pygamestudio.gui.inspector.layout.ellipse import INSPECTOR_LAYOUT_ELLIPSE
from pygamestudio.gui.inspector.layout.polygon import INSPECTOR_LAYOUT_POLYGON
from pygamestudio.gui.inspector.layout.line import INSPECTOR_LAYOUT_LINE
from pygamestudio.gui.inspector.layout.canvas import INSPECTOR_LAYOUT_CANVAS
from pygamestudio.gui.inspector.layout.text import INSPECTOR_LAYOUT_TEXT
from pygamestudio.gui.inspector.layout.image import INSPECTOR_LAYOUT_IMAGE
from pygamestudio.gui.inspector.layout.button import INSPECTOR_LAYOUT_BUTTON
from pygamestudio.gui.inspector.layout.particle import INSPECTOR_LAYOUT_PARTICLE
from pygamestudio.gui.inspector.layout.text_input import INSPECTOR_LAYOUT_TEXT_INPUT
from pygamestudio.gui.inspector.layout.frame_sequence import INSPECTOR_LAYOUT_FRAME_SEQUENCE
from pygamestudio.gui.inspector.layout.tile_map import INSPECTOR_LAYOUT_TILE_MAP
from pygamestudio.gui.inspector.layout.progress_bar import INSPECTOR_LAYOUT_PROGRESS_BAR
from pygamestudio.gui.inspector.layout.slider import INSPECTOR_LAYOUT_SLIDER
from pygamestudio.gui.inspector.layout.collision import build_collision_layout


class Container(QFrame):
    selection_history_changed = Signal(int, int)
    selection_index_changed = Signal(int, int)

    def __init__(self, parent, game_manager):
        super().__init__(parent)
        self._inspector_window = parent
        self._game_manager = game_manager
        self._color_picker = ColorPicker()
        # Attribute the shared color popup currently edits ('' / None = the
        # base 'color' property; anything else routes through the line-edit
        # generic parameter channel, e.g. background_color / border_color).
        self._color_attr_target = None
        
        self._is_selected_from_inspector = False
        self._current_selected_object_uuid_index = -1
        self._selected_objects_uuids_in_history = []
        self._container_layout = QGridLayout(self)
        self._object_uuid_in_inspection = None
        self._container_row = 0
        self._max_column = 1
        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self.setMinimumWidth(270)

    def _set_signal(self):
        T.add_observer(self)
        self._color_picker.color_changed.connect(self._on_color_picker_color_changed)
        self._game_manager.scene_loaded_signal.connect(self._on_scene_loaded)

        # self._game_manager.object_added.connect(self._on_object_added)
        self._game_manager.object_deleted.connect(self._on_object_deleted)
        self._game_manager.object_selected.connect(self._on_object_selected)
        # self._game_manager.object_deselected.connect(self._on_object_deselected)
        self._game_manager.object_renamed.connect(self._on_object_renamed)
        self._game_manager.object_moved.connect(self._on_object_moved)
        self._game_manager.object_resized.connect(self._on_object_resized)
        self._game_manager.object_scaled.connect(self._on_object_scaled)
        self._game_manager.object_rotated.connect(self._on_object_rotated)
        self._game_manager.object_showed.connect(self._on_object_showed)
        self._game_manager.object_hidden.connect(self._on_object_hidden)
        self._game_manager.object_color_changed.connect(self._on_object_color_changed)
        self._game_manager.object_text_changed.connect(self._on_object_text_changed)
        self._game_manager.object_rect_border_radius_changed.connect(self._on_object_rect_border_radius_changed)
        self._game_manager.object_line_start_point_changed.connect(self._on_object_line_start_point_changed)
        self._game_manager.object_line_end_point_changed.connect(self._on_object_line_end_point_changed)
        self._game_manager.object_line_thickness_changed.connect(self._on_object_line_thickness_changed)
        self._game_manager.object_image_path_changed.connect(self._on_object_image_path_changed)
        self._game_manager.object_font_path_changed.connect(self._on_object_font_path_changed)
        self._game_manager.object_script_path_changed.connect(self._on_object_script_path_changed)
        self._game_manager.object_points_changed.connect(self._on_object_points_changed)
        self._game_manager.object_particle_parameter_changed.connect(self._on_object_particle_parameter_changed)
        self._game_manager.object_text_input_parameter_changed.connect(self._on_object_text_input_parameter_changed)
        self._game_manager.object_frame_sequence_parameter_changed.connect(self._on_object_frame_sequence_parameter_changed)
        self._game_manager.object_tile_map_parameter_changed.connect(self._on_object_tile_map_parameter_changed)
        self._game_manager.object_progress_bar_parameter_changed.connect(self._on_object_progress_bar_parameter_changed)
        self._game_manager.object_slider_parameter_changed.connect(self._on_object_slider_parameter_changed)
        self._game_manager.object_collision_parameter_changed.connect(self._on_object_collision_parameter_changed)

    def _set_layout(self):
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._container_layout.setVerticalSpacing(10)
        self._container_layout.setContentsMargins(8, 4, 8, 4)

    def _set_object_name(self):
        self.setObjectName('inspectorContainer')

    def get_ready_for_project(self):
        self._clear_selection_history()

    def clean_up(self):
        self._object_uuid_in_inspection = None
        self._container_row = 0
        self._max_column = 1
        self._clear_layout(self._container_layout)
        self._color_picker.close()

    def rename_object(self):
        lineedit = self._find_widget(self._container_layout, 'name')
        self._game_manager.rename(self._object_uuid_in_inspection, lineedit.text().strip())

    def resize_object(self):
        spinbox_width = self._find_widget(self._container_layout, 'width')
        spinbox_height = self._find_widget(self._container_layout, 'height')
        new_size = (spinbox_width.value(), spinbox_height.value())
        self._game_manager.resize(self._object_uuid_in_inspection, new_size)

    def move_object(self):
        spinbox_x = self._find_widget(self._container_layout, 'x')
        spinbox_y = self._find_widget(self._container_layout, 'y')
        new_pos = (spinbox_x.value(), spinbox_y.value())
        self._game_manager.move(self._object_uuid_in_inspection, new_pos)

    def scale_object(self):
        spinbox_scale_x = self._find_widget(self._container_layout, 'scale_x')
        spinbox_scale_y = self._find_widget(self._container_layout, 'scale_y')
        new_scale = (spinbox_scale_x.value(), spinbox_scale_y.value())
        self._game_manager.scale(self._object_uuid_in_inspection, new_scale)

    def rotate_object(self):
        spinbox_angle = self._find_widget(self._container_layout, 'angle')
        new_angle = spinbox_angle.value()
        self._game_manager.rotate(self._object_uuid_in_inspection, new_angle)

    def show_object(self):
        self._game_manager.show(self._object_uuid_in_inspection)

    def hide_object(self):
        self._game_manager.hide(self._object_uuid_in_inspection)

    def set_object_color(self, new_color):
        self._game_manager.set_color(self._object_uuid_in_inspection, new_color)

    def set_object_border_radius(self, attr, new_border_radius):
        self._game_manager.set_border_radius(self._object_uuid_in_inspection, attr, new_border_radius)
    
    def set_object_thickness(self):
        spinbox_thickness = self._find_widget(self._container_layout, 'thickness')
        new_thickness = int(spinbox_thickness.value())
        self._game_manager.set_thickness(self._object_uuid_in_inspection, new_thickness)

    def set_object_start_point(self):
        spinbox_start_x = self._find_widget(self._container_layout, 'start_x')
        spinbox_start_y = self._find_widget(self._container_layout, 'start_y')
        new_start_point = (spinbox_start_x.value(), spinbox_start_y.value())
        self._game_manager.set_start_point(self._object_uuid_in_inspection, new_start_point)

    def set_object_end_point(self):
        spinbox_end_x = self._find_widget(self._container_layout, 'end_x')
        spinbox_end_y = self._find_widget(self._container_layout, 'end_y')
        new_end_point = (spinbox_end_x.value(), spinbox_end_y.value())
        self._game_manager.set_end_point(self._object_uuid_in_inspection, new_end_point)

    def set_object_text(self):
        text_edit = self._find_widget(self._container_layout, 'text')
        text = text_edit.toPlainText()
        self._game_manager.set_text(self._object_uuid_in_inspection, text)

    def set_object_font_family(self):
        combobox_font_family = self._find_widget(self._container_layout, 'font_family')
        font_family = combobox_font_family.currentText()
        self._game_manager.set_font_family(self._object_uuid_in_inspection, font_family)

    def set_object_font_size(self):
        spinbox_font_size = self._find_widget(self._container_layout, 'font_size')
        new_font_size = int(spinbox_font_size.value())
        self._game_manager.set_font_size(self._object_uuid_in_inspection, new_font_size)

    def set_object_bold_state(self):
        checkbox_bold = self._find_widget(self._container_layout, 'bold')
        new_bold_state = checkbox_bold.isChecked()
        self._game_manager.set_bold_state(self._object_uuid_in_inspection, new_bold_state)

    def set_object_italic_state(self):
        checkbox_italic = self._find_widget(self._container_layout, 'italic')
        new_italic_state = checkbox_italic.isChecked()
        self._game_manager.set_italic_state(self._object_uuid_in_inspection, new_italic_state)

    def set_object_underline_state(self):
        checkbox_underline = self._find_widget(self._container_layout, 'underline')
        new_underline_state = checkbox_underline.isChecked()
        self._game_manager.set_underline_state(self._object_uuid_in_inspection, new_underline_state)

    def set_object_strikethrough_state(self):
        checkbox_strikethrough = self._find_widget(self._container_layout, 'strikethrough')
        new_strikethrough_state = checkbox_strikethrough.isChecked()
        self._game_manager.set_strikethrough_state(self._object_uuid_in_inspection, new_strikethrough_state)

    def set_object_image_path(self):
        lineedit = self._find_widget(self._container_layout, 'image_path')
        self._game_manager.set_image_path(self._object_uuid_in_inspection, lineedit.toolTip())

    def set_object_path(self, attr='', tooltip=''):
        """Set an image-path style attribute (image_path, particle_image or
        frame_folder) from the line edit that triggered this slot."""
        if not attr:
            sender = self.sender()
            attr = sender.property('component_attribute') if sender else ''
        if attr == 'image_path':
            self._game_manager.set_image_path(self._object_uuid_in_inspection, tooltip)
        elif attr == 'particle_image':
            self._game_manager.set_particle_parameter(self._object_uuid_in_inspection, attr, tooltip)
        elif attr == 'frame_folder':
            self._game_manager.set_frame_sequence_parameter(self._object_uuid_in_inspection, attr, tooltip)
        elif attr == 'tileset_path':
            self._game_manager.set_tile_map_parameter(self._object_uuid_in_inspection, attr, tooltip)
        elif attr in ('background_image_path', 'foreground_image_path'):
            self._game_manager.set_progress_bar_parameter(self._object_uuid_in_inspection, attr, tooltip)
        elif attr in ('track_image_path', 'fill_image_path', 'handle_image_path'):
            self._game_manager.set_slider_parameter(self._object_uuid_in_inspection, attr, tooltip)
        elif attr:
            self._game_manager.set_particle_parameter(self._object_uuid_in_inspection, attr, tooltip)

    def set_object_font_path(self):
        lineedit = self._find_widget(self._container_layout, 'font_path')
        self._game_manager.set_font_path(self._object_uuid_in_inspection, lineedit.toolTip())

    def set_object_script_path(self):
        lineedit = self._find_widget(self._container_layout, 'script_path')
        self._game_manager.set_script_path(self._object_uuid_in_inspection, lineedit.toolTip())

    def set_object_points(self, new_points):
        self._game_manager.set_points(self._object_uuid_in_inspection, new_points)

    def set_object_particle_parameter(self, attr, new_value):
        self._game_manager.set_particle_parameter(self._object_uuid_in_inspection, attr, new_value)

    def set_object_text_input_parameter(self, attr, new_value):
        """Change one text-input box parameter through the manager."""
        self._game_manager.set_text_input_parameter(self._object_uuid_in_inspection, attr, new_value)
        # Lowering max_length below the current text length should trim the
        # content too, so editor and runtime stay consistent.
        if attr == 'max_length':
            self._clamp_text_input_text()

    def _sync_text_edit(self):
        """Refresh the 'text' editor widget with the object's current text.
        Skips when they already match, so live typing never resets the
        cursor (only undo/redo/external changes actually rewrite the field)."""
        obj = self._game_manager.get_object(self._object_uuid_in_inspection)
        widget = self._find_widget(self._container_layout, 'text')
        if obj is None or widget is None:
            return
        current = obj.text or ''
        if widget.toPlainText() == current:
            return
        widget.blockSignals(True)
        widget.setPlainText(current)
        widget.blockSignals(False)

    def _clamp_text_input_text(self):
        """Trim the inspected text-input's content to its max_length so typing
        in the inspector respects the same limit as the running game."""
        if self._object_uuid_in_inspection is None:
            return
        obj = self._game_manager.get_object(self._object_uuid_in_inspection)
        if obj is None or getattr(obj, 'type', '') != OBJECT_TEXT_INPUT:
            return
        limit = int(getattr(obj, 'max_length', 0) or 0)
        if limit <= 0:
            return
        text = obj.text or ''
        if len(text) > limit:
            self._game_manager.set_text(self._object_uuid_in_inspection, text[:limit])
        self._sync_text_edit()

    def _on_object_text_changed(self, object_uuid):
        """Keep the text editor widget in sync when text is changed by undo/
        redo or by clamping."""
        if object_uuid != self._object_uuid_in_inspection:
            return
        self._sync_text_edit()

    def _on_color_picker_color_changed(self, color_rgba):
        """The shared color popup changed: route to the base 'color' property,
        or to the attribute that opened the popup (box colors, strip colors)."""
        rgba = tuple(int(c) for c in color_rgba)
        attr = self._color_attr_target
        if attr and attr != 'color':
            obj = self._game_manager.get_object(self._object_uuid_in_inspection)
            obj_type = getattr(obj, 'type', '') if obj is not None else ''
            if (obj_type == OBJECT_PROGRESS_BAR
                    and attr in ('background_color', 'foreground_color')):
                self.set_object_progress_bar_parameter(attr, rgba)
            elif (obj_type == OBJECT_SLIDER
                    and attr in ('track_color', 'fill_color', 'handle_color')):
                self.set_object_slider_parameter(attr, rgba)
            else:
                self.set_object_text_input_parameter(attr, rgba)
        else:
            self.set_object_color(rgba)

    def set_object_frame_sequence_parameter(self, attr, new_value):
        self._game_manager.set_frame_sequence_parameter(self._object_uuid_in_inspection, attr, new_value)

    def set_object_tile_map_parameter(self, attr, new_value):
        """Change one tile-map parameter (tile size, grid columns/rows, ...)
        through the manager (undoable)."""
        self._game_manager.set_tile_map_parameter(self._object_uuid_in_inspection, attr, new_value)

    def set_object_progress_bar_parameter(self, attr, new_value):
        """Change one progress-bar parameter (progress value, strip colors or
        strip image paths) through the manager (undoable)."""
        self._game_manager.set_progress_bar_parameter(
            self._object_uuid_in_inspection, attr, new_value)

    def set_object_slider_parameter(self, attr, new_value):
        """Change one slider parameter (value/range, handle width, strip
        colors or strip image paths) through the manager (undoable)."""
        self._game_manager.set_slider_parameter(
            self._object_uuid_in_inspection, attr, new_value)

    def _on_object_slider_parameter_changed(self, object_uuid):
        """Keep the slider editors in sync with an undone/redone change."""
        if object_uuid != self._object_uuid_in_inspection:
            return
        obj = self._game_manager.get_object(object_uuid)
        if obj is None:
            return
        for attr in ('value', 'min_value', 'max_value', 'handle_width',
                     'handle_height', 'track_thickness'):
            widget = self._find_widget(self._container_layout, attr)
            if widget:
                widget.blockSignals(True)
                widget.setValue(float(getattr(obj, attr)))
                widget.blockSignals(False)
        for attr in ('track_color', 'fill_color', 'handle_color'):
            widget = self._find_widget(self._container_layout, attr)
            if widget:
                widget.set_color(tuple(int(c) for c in getattr(obj, attr, (0, 0, 0, 255))))
        for attr in ('track_image_path', 'fill_image_path', 'handle_image_path'):
            widget = self._find_widget(self._container_layout, attr)
            if widget:
                widget.blockSignals(True)
                path = getattr(obj, attr, '') or ''
                widget.setText(Path(path).name if path else '')
                widget.setToolTip(Path(path).as_posix() if path else '')
                widget.blockSignals(False)

    def _on_object_progress_bar_parameter_changed(self, object_uuid):
        """Keep the progress-bar editors in sync with an undone/redone change."""
        if object_uuid != self._object_uuid_in_inspection:
            return
        obj = self._game_manager.get_object(object_uuid)
        if obj is None:
            return
        progress = self._find_widget(self._container_layout, 'progress')
        if progress:
            progress.blockSignals(True)
            progress.setValue(float(getattr(obj, 'progress', 0)))
            progress.blockSignals(False)
        for attr in ('background_color', 'foreground_color'):
            widget = self._find_widget(self._container_layout, attr)
            if widget:
                widget.set_color(tuple(int(c) for c in getattr(obj, attr, (0, 0, 0, 255))))
        for attr in ('background_image_path', 'foreground_image_path'):
            widget = self._find_widget(self._container_layout, attr)
            if widget:
                widget.blockSignals(True)
                path = getattr(obj, attr, '') or ''
                widget.setText(Path(path).name if path else '')
                widget.setToolTip(Path(path).as_posix() if path else '')
                widget.blockSignals(False)

    def set_object_collision_parameter(self, attr, new_value):
        # The first time collision is switched on, materialize concrete
        # object-sized defaults so the fields never read as 0 x 0 (0 really
        # means a zero-sized shape, there is no "auto").
        if attr == 'collision_enabled' and new_value:
            obj = self._game_manager.get_object(self._object_uuid_in_inspection)
            if obj is not None:
                obj._ensure_collision_defaults(force=True, for_type=getattr(obj, 'collision_type', 'rect'))
        self._game_manager.set_collision_parameter(self._object_uuid_in_inspection, attr, new_value)

    def set_object_collision_type(self, type_code):
        """Change the collision shape type. The parameter-change handler
        rebuilds the inspector so only the fields relevant to the new type are
        shown; defaults for the new type are materialized first."""
        obj = self._game_manager.get_object(self._object_uuid_in_inspection)
        if obj is not None:
            obj._ensure_collision_defaults(force=True, for_type=type_code)
        self._game_manager.set_collision_parameter(
            self._object_uuid_in_inspection, 'collision_type', type_code)

    def _on_object_collision_parameter_changed(self, object_uuid):
        """Keep the collision editors in sync with an undone/redone change."""
        if object_uuid != self._object_uuid_in_inspection:
            return
        obj = self._game_manager.get_object(object_uuid)
        if obj is None:
            return

        enabled = self._find_widget(self._container_layout, 'collision_enabled')
        if enabled:
            enabled.blockSignals(True)
            enabled.setChecked(bool(getattr(obj, 'collision_enabled', False)))
            enabled.blockSignals(False)

        combo = self._find_widget(self._container_layout, 'collision_type')
        if combo:
            combo.set_collision_type(getattr(obj, 'collision_type', 'rect'))

        # Sync every numeric field that is currently shown (offset + box size
        # for rect/ellipse, offset for polygon). Stored values are concrete.
        for attr in ('collision_offset_x', 'collision_offset_y',
                     'collision_width', 'collision_height'):
            widget = self._find_widget(self._container_layout, attr)
            if widget:
                widget.blockSignals(True)
                widget.setValue(getattr(obj, attr, 0))
                widget.blockSignals(False)

        points = self._find_widget(self._container_layout, 'collision_points')
        if points:
            points.blockSignals(True)
            points.set_points(getattr(obj, 'collision_points', []))
            points.blockSignals(False)

        # Rebuild the inspector when the visible section no longer matches the
        # object's state - e.g. the enable checkbox was toggled (hide/show the
        # whole section) or the type changed through undo/redo (bypasses the
        # combo box).
        enabled = bool(getattr(obj, 'collision_enabled', False))
        ctype = getattr(obj, 'collision_type', 'rect')

        def shown(attr):
            return self._find_widget(self._container_layout, attr) is not None

        want_combo = enabled
        want_box_fields = enabled and ctype in ('rect', 'ellipse')
        want_polygon = enabled and ctype == 'polygon'
        mismatch = (
            (shown('collision_type') != want_combo) or
            (shown('collision_width') != want_box_fields) or
            (shown('collision_points') != want_polygon)
        )
        if mismatch:
            self._inspect_object(self._object_uuid_in_inspection)

    def _on_object_particle_parameter_changed(self, object_uuid):
        """Keep the particle parameter editors in sync with an undone/redone
        parameter change."""
        if object_uuid != self._object_uuid_in_inspection:
            return
        obj = self._game_manager.get_object(object_uuid)
        for attr in ('emission_rate', 'max_particles', 'particle_lifetime',
                     'particle_speed', 'particle_size', 'gravity',
                     'spread_angle'):
            widget = self._find_widget(self._container_layout, attr)
            if widget:
                widget.blockSignals(True)
                widget.setValue(getattr(obj, attr))
                widget.blockSignals(False)

        image_edit = self._find_widget(self._container_layout, 'particle_image')
        if image_edit:
            image_edit.blockSignals(True)
            image_path = getattr(obj, 'particle_image', '')
            image_edit.setText(Path(image_path).name if image_path else '')
            image_edit.setToolTip(Path(image_path).as_posix() if image_path else '')
            image_edit.blockSignals(False)

    def _on_object_text_input_parameter_changed(self, object_uuid):
        """Keep the text-input box editors in sync with an undone/
        redone parameter change (placeholder, password, box colors, ...)."""
        if object_uuid != self._object_uuid_in_inspection:
            return
        obj = self._game_manager.get_object(object_uuid)
        if obj is None:
            return

        for attr in ('placeholder', 'password', 'enter_newline',
                     'max_length', 'background_color', 'border_color'):
            widget = self._find_widget(self._container_layout, attr)
            if widget is None:
                continue
            value = getattr(obj, attr)
            widget.blockSignals(True)
            if attr == 'placeholder':
                widget.setText(value)
            elif attr in ('password', 'enter_newline'):
                widget.setChecked(bool(value))
            elif attr == 'max_length':
                widget.setValue(int(value))
            else:
                widget.set_color(tuple(int(c) for c in value))
            widget.blockSignals(False)

        for attr in ('text_align', 'text_valign'):
            widget = self._find_widget(self._container_layout, attr)
            if widget is not None:
                widget.set_value(getattr(obj, attr, 'left'))

    def _on_object_frame_sequence_parameter_changed(self, object_uuid):
        """Keep the frame-sequence editors in sync with an undone/redone
        parameter change."""
        if object_uuid != self._object_uuid_in_inspection:
            return
        obj = self._game_manager.get_object(object_uuid)

        for attr in ('frame_rate',):
            widget = self._find_widget(self._container_layout, attr)
            if widget:
                widget.blockSignals(True)
                widget.setValue(getattr(obj, attr))
                widget.blockSignals(False)

        for attr in ('auto_play', 'loop'):
            widget = self._find_widget(self._container_layout, attr)
            if widget:
                widget.blockSignals(True)
                widget.setChecked(bool(getattr(obj, attr)))
                widget.blockSignals(False)

        folder_edit = self._find_widget(self._container_layout, 'frame_folder')
        if folder_edit:
            folder_edit.blockSignals(True)
            frame_folder = getattr(obj, 'frame_folder', '')
            folder_edit.setText(Path(frame_folder).name if frame_folder else '')
            folder_edit.setToolTip(Path(frame_folder).as_posix() if frame_folder else '')
            folder_edit.blockSignals(False)

    def _on_object_tile_map_parameter_changed(self, object_uuid):
        """Keep the tile-map editors in sync with an undone/redone parameter
        change (tile size, grid size, derived pixel size, tileset path)."""
        if object_uuid != self._object_uuid_in_inspection:
            return
        obj = self._game_manager.get_object(object_uuid)
        if obj is None:
            return

        for attr in ('tile_width', 'tile_height', 'columns', 'rows'):
            widget = self._find_widget(self._container_layout, attr)
            if widget:
                widget.blockSignals(True)
                widget.setValue(getattr(obj, attr))
                widget.blockSignals(False)

        # The pixel size is derived from the grid, so refresh the read-only
        # size row too when the grid / tile size changes.
        for attr in ('width', 'height'):
            widget = self._find_widget(self._container_layout, attr)
            if widget:
                widget.blockSignals(True)
                widget.setValue(getattr(obj, attr))
                widget.blockSignals(False)

        tileset_edit = self._find_widget(self._container_layout, 'tileset_path')
        if tileset_edit:
            tileset_edit.blockSignals(True)
            tileset_path = getattr(obj, 'tileset_path', '')
            tileset_edit.setText(Path(tileset_path).name if tileset_path else '')
            tileset_edit.setToolTip(Path(tileset_path).as_posix() if tileset_path else '')
            tileset_edit.blockSignals(False)

    def show_color_picker(self, color_rgba, attr=''):
        """Open the shared color popup editing ``attr`` ('' = base color)."""
        self._color_attr_target = attr or None

        screen = QApplication.primaryScreen()
        screen_width = screen.geometry().width()
        screen_height = screen.geometry().height()

        pos = QCursor.pos()
        x = pos.x()
        y = pos.y()
        if x + self._color_picker.width() > screen_width:
            x = screen_width - self._color_picker.width()
        else:
            x = int(x - self._color_picker.width()/4)
        
        if y + self._color_picker.height() > screen_height:
            y = screen_height - self._color_picker.height()
        else:
            y = y + 20

        self._color_picker.set_rgba(color_rgba)
        self._color_picker.move(x, y)
        self._color_picker.show()
        self._color_picker.raise_()
        self._color_picker.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        
    def _on_scene_loaded(self):
        self._clear_selection_history()

    def _on_object_added(self, parent_uuid, object_uuid, inserted_pos):
        # Object will be selected when added, and it will be inspected in slot _on_object_selected.
        # self._inspect_object(object_uuid)
        ...

    def _on_object_deleted(self, object_uuid):
        self._clear_layout(self._container_layout)
        self._update_selection_history(object_uuid, action='delete')

    def _on_object_selected(self, object_uuid):
        self._inspect_object(object_uuid)

        if not self._is_selected_from_inspector:
            self._update_selection_history(object_uuid, action='add')

        self._is_selected_from_inspector = False

    def _on_object_deselected(self, object_uuid):
        ...

    def _on_object_resized(self, object_uuid):
        obj = self._game_manager.get_object(object_uuid)
        spinbox_width = self._find_widget(self._container_layout, 'width')
        spinbox_height = self._find_widget(self._container_layout, 'height')
        if spinbox_width:
            spinbox_width.blockSignals(True)
            spinbox_width.setValue(obj.width)
            spinbox_width.blockSignals(False)
        if spinbox_height:
            spinbox_height.blockSignals(True)
            spinbox_height.setValue(obj.height)
            spinbox_height.blockSignals(False)

    def _on_object_renamed(self, object_uuid):
        obj = self._game_manager.get_object(object_uuid)
        name_lineedit = self._find_widget(self._container_layout, 'name')
        name_lineedit.blockSignals(True)
        name_lineedit.setText(obj.name)
        name_lineedit.blockSignals(False)

    def _on_object_moved(self, object_uuid):
        obj = self._game_manager.get_object(object_uuid)
        spinbox_x = self._find_widget(self._container_layout, 'x')
        spinbox_y = self._find_widget(self._container_layout, 'y')

        if spinbox_x and spinbox_y:
            spinbox_x.blockSignals(True)
            spinbox_y.blockSignals(True)
            spinbox_x.setValue(obj.x)
            spinbox_y.setValue(obj.y)
            spinbox_x.blockSignals(False)
            spinbox_y.blockSignals(False)

        if obj.type == OBJECT_LINE:
            spinbox_start_x = self._find_widget(self._container_layout, 'start_x')
            spinbox_start_y = self._find_widget(self._container_layout, 'start_y')
            spinbox_end_x = self._find_widget(self._container_layout, 'end_x')
            spinbox_end_y = self._find_widget(self._container_layout, 'end_y')

            if spinbox_start_x and spinbox_start_y and spinbox_end_x and spinbox_end_y:
                spinbox_start_x.blockSignals(True)
                spinbox_start_y.blockSignals(True)
                spinbox_end_x.blockSignals(True)
                spinbox_end_y.blockSignals(True)
                spinbox_start_x.setValue(obj.start_x)
                spinbox_start_y.setValue(obj.start_y)
                spinbox_end_x.setValue(obj.end_x)
                spinbox_end_y.setValue(obj.end_y)
                spinbox_start_x.blockSignals(False)
                spinbox_start_y.blockSignals(False)
                spinbox_end_x.blockSignals(False)
                spinbox_end_y.blockSignals(False)

        elif obj.type == OBJECT_POLYGON:
            # Moving a polygon translates every vertex (see ObjectPolygon), so
            # the vertex editor must show the translated values too.
            points_widget = self._find_widget(self._container_layout, 'points')
            if points_widget:
                points_widget.blockSignals(True)
                points_widget.set_points(obj.points)
                points_widget.blockSignals(False)

    def _on_object_scaled(self, object_uuid):
        obj = self._game_manager.get_object(object_uuid)
        spinbox_scale_x = self._find_widget(self._container_layout, 'scale_x')
        spinbox_scale_y = self._find_widget(self._container_layout, 'scale_y')
        spinbox_scale_x.blockSignals(True)
        spinbox_scale_y.blockSignals(True)
        spinbox_scale_x.setValue(obj.scale_x)
        spinbox_scale_y.setValue(obj.scale_y)
        spinbox_scale_x.blockSignals(False)
        spinbox_scale_y.blockSignals(False)

    def _on_object_rotated(self, object_uuid):
        obj = self._game_manager.get_object(object_uuid)
        spinbox_angle = self._find_widget(self._container_layout, 'angle')
        spinbox_angle.blockSignals(True)
        spinbox_angle.setValue(obj.angle)
        spinbox_angle.blockSignals(False)

    def _on_object_showed(self, object_uuid):
        if object_uuid != self._object_uuid_in_inspection:
            return
        
        checkbox = self._find_widget(self._container_layout, 'visible')
        checkbox.setChecked(True)

    def _on_object_hidden(self, object_uuid):
        if object_uuid != self._object_uuid_in_inspection:
            return
        
        checkbox = self._find_widget(self._container_layout, 'visible')
        checkbox.setChecked(False)

    def _on_object_color_changed(self, object_uuid):
        if object_uuid != self._object_uuid_in_inspection:
            return
        
        obj = self._game_manager.get_object(object_uuid)
        color_picker = self._find_widget(self._container_layout, 'color')
        color_picker.set_color(obj.color)

    def _on_object_rect_border_radius_changed(self, object_uuid, attr):
        if object_uuid != self._object_uuid_in_inspection:
            return
        
        obj = self._game_manager.get_object(object_uuid)
        spinbox_radius = self._find_widget(self._container_layout, attr)
        spinbox_radius.blockSignals(True)
        spinbox_radius.setValue(getattr(obj, attr))
        spinbox_radius.blockSignals(False)

    def _on_object_line_thickness_changed(self, object_uuid):
        if object_uuid != self._object_uuid_in_inspection:
            return
        
        obj = self._game_manager.get_object(object_uuid)
        spinbox_thickness = self._find_widget(self._container_layout, 'thickness')
        spinbox_thickness.blockSignals(True)
        spinbox_thickness.setValue(obj.thickness)
        spinbox_thickness.blockSignals(False)

    def _on_object_line_start_point_changed(self, object_uuid):
        if object_uuid != self._object_uuid_in_inspection:
            return
        
        obj = self._game_manager.get_object(object_uuid)
        spinbox_start_point_x = self._find_widget(self._container_layout, 'start_x')
        spinbox_start_point_y = self._find_widget(self._container_layout, 'start_y')
        spinbox_start_point_x.blockSignals(True)
        spinbox_start_point_y.blockSignals(True)
        spinbox_start_point_x.setValue(getattr(obj, 'start_x'))
        spinbox_start_point_y.setValue(getattr(obj, 'start_y'))
        spinbox_start_point_x.blockSignals(False)
        spinbox_start_point_y.blockSignals(False)

        if hasattr(obj, '_update_bounding_box'):
            obj._update_bounding_box()
        self._on_object_resized(object_uuid)
        self._on_object_moved(object_uuid)

    def _on_object_line_end_point_changed(self, object_uuid):
        if object_uuid != self._object_uuid_in_inspection:
            return
        
        obj = self._game_manager.get_object(object_uuid)
        spinbox_end_point_x = self._find_widget(self._container_layout, 'end_x')
        spinbox_end_point_y = self._find_widget(self._container_layout, 'end_y')
        spinbox_end_point_x.blockSignals(True)
        spinbox_end_point_y.blockSignals(True)
        spinbox_end_point_x.setValue(getattr(obj, 'end_x'))
        spinbox_end_point_y.setValue(getattr(obj, 'end_y'))
        spinbox_end_point_x.blockSignals(False)
        spinbox_end_point_y.blockSignals(False)

        if hasattr(obj, '_update_bounding_box'):
            obj._update_bounding_box()
        self._on_object_resized(object_uuid)
        self._on_object_moved(object_uuid)

    def _on_object_image_path_changed(self, object_uuid):
        obj = self._game_manager.get_object(object_uuid)
        image_path_lineedit = self._find_widget(self._container_layout, 'image_path')
        image_path_lineedit.blockSignals(True)
        image_path_lineedit.setText(Path(obj.image_path).name)
        image_path_lineedit.setToolTip(Path(obj.image_path).as_posix() if obj.image_path else '')
        image_path_lineedit.blockSignals(False)

    def _on_object_font_path_changed(self, object_uuid):
        obj = self._game_manager.get_object(object_uuid)
        font_path_lineedit = self._find_widget(self._container_layout, 'font_path')
        font_path_lineedit.blockSignals(True)
        font_path_lineedit.setText(Path(obj.font_path).name)
        font_path_lineedit.setToolTip(Path(obj.font_path).as_posix() if obj.font_path else '')
        font_path_lineedit.blockSignals(False)

    def _on_object_script_path_changed(self, object_uuid):
        obj = self._game_manager.get_object(object_uuid)
        script_path_lineedit = self._find_widget(self._container_layout, 'script_path')
        script_path_lineedit.blockSignals(True)
        script_path_lineedit.setText(Path(obj.script_path).name)
        script_path_lineedit.setToolTip(Path(obj.script_path).as_posix() if obj.script_path else '')
        script_path_lineedit.blockSignals(False)

    def _on_object_points_changed(self, object_uuid):
        if object_uuid != self._object_uuid_in_inspection:
            return
        obj = self._game_manager.get_object(object_uuid)

        # Keep the vertex editor in sync with the (possibly undone/redone)
        # vertex list.
        points_widget = self._find_widget(self._container_layout, 'points')
        if points_widget:
            points_widget.blockSignals(True)
            points_widget.set_points(obj.points)
            points_widget.blockSignals(False)

        # A polygon's size is derived from its vertices, so the (read-only)
        # size spin boxes must follow. Recompute the bounding box here so the
        # displayed values don't depend on signal-handler ordering with the
        # scene view.
        if hasattr(obj, '_update_bounding_box'):
            obj._update_bounding_box()
        self._on_object_resized(object_uuid)
        self._on_object_moved(object_uuid)

    def _find_widget(self, layout, component_attribute):
        for i in range(layout.count()):
            item = layout.itemAt(i)
            
            widget = item.widget()
            if widget and widget.property('component_attribute') == component_attribute:
                return widget
            
            sub_layout = item.layout()
            if sub_layout:
                result = self._find_widget(sub_layout, component_attribute)
                if result:
                    return result
        
        return None
        
    def _inspect_object(self, object_uuid):
        obj = self._game_manager.get_object(object_uuid)
        if not obj:
            return
        
        self._object_uuid_in_inspection = object_uuid
        self._clear_layout(self._container_layout)

        if obj.type == OBJECT_CANVAS:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_CANVAS)
        elif obj.type == OBJECT_RECT:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_RECT)
        elif obj.type == OBJECT_ELLIPSE:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_ELLIPSE)
        elif obj.type == OBJECT_POLYGON:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_POLYGON)
        elif obj.type == OBJECT_LINE:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_LINE)
        elif obj.type == OBJECT_TEXT:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_TEXT)
        elif obj.type == OBJECT_IMAGE:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_IMAGE)
        elif obj.type == OBJECT_BUTTON:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_BUTTON)
        elif obj.type == OBJECT_PARTICLE:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_PARTICLE)
        elif obj.type == OBJECT_TEXT_INPUT:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_TEXT_INPUT)
        elif obj.type == OBJECT_PROGRESS_BAR:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_PROGRESS_BAR)
        elif obj.type == OBJECT_SLIDER:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_SLIDER)
        elif obj.type == OBJECT_FRAME_SEQUENCE:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_FRAME_SEQUENCE)
        elif obj.type == OBJECT_TILE_MAP:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_TILE_MAP)

        # Every object (except the canvas root) can carry a collision body.
        if obj.type != OBJECT_CANVAS:
            # Materialize defaults on first use only (never force): explicit
            # values - including a deliberate 0 - are never overwritten.
            if obj.collision_enabled:
                obj._ensure_collision_defaults()
            self._add_layout_for_specific_object(
                obj, build_collision_layout(obj.collision_enabled, obj.collision_type))

    def _clear_layout(self, layout):
        if layout is None:
            return
    
        while layout.count():
            item = layout.takeAt(0)
            
            if item.widget():
                widget = item.widget()
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
                item.layout().deleteLater()
            elif item.spacerItem():
                layout.removeItem(item)

    def _add_layout_for_specific_object(self, obj, layout_data):
        for property_detail in layout_data.values():
            text = T.tr(property_detail['i18n']['key'], property_detail['i18n']['default'])
            attribute_list = property_detail['component']['attribute']
            widget_list = property_detail['component']['widget']
            enabled_list = property_detail['component']['enabled']

            label = PropertyLabel(self, text)
            self._container_layout.addWidget(label, self._container_row, 0, 1, 1)

            if property_detail['i18n']['default'] in ('Points', 'Collision Points'):
                label.setAlignment(Qt.AlignmentFlag.AlignTop)
                label.setContentsMargins(0, 4, 0, 0)

            for i, widget in enumerate(widget_list):
                w = widget(self, getattr(obj, attribute_list[i]), attribute_list[i])
                if not w.property('component_attribute'):
                    w.setProperty('component_attribute', attribute_list[i])
                w.setEnabled(enabled_list[i])

                row = i // 2
                column = i%2+1

                column_stretch = 2 if len(widget_list) == 1 else 1
                self._container_layout.addWidget(w, self._container_row+row, column, 1, column_stretch)

            self._container_row += row+1

    def _clear_selection_history(self):
        self._current_selected_object_uuid_index = -1
        self._selected_objects_uuids_in_history = []
        self.selection_history_changed.emit(len(self._selected_objects_uuids_in_history), self._current_selected_object_uuid_index)

    def _update_selection_history(self, object_uuid, action='add'):
        if action == 'add':
            if not self._selected_objects_uuids_in_history or object_uuid != self._selected_objects_uuids_in_history[-1]:
                self._selected_objects_uuids_in_history.append(object_uuid)
                self._current_selected_object_uuid_index = len(self._selected_objects_uuids_in_history) - 1
                self.selection_history_changed.emit(len(self._selected_objects_uuids_in_history), self._current_selected_object_uuid_index)
        else:
            if self._selected_objects_uuids_in_history and object_uuid in self._selected_objects_uuids_in_history:
                self._selected_objects_uuids_in_history = [ele for ele in self._selected_objects_uuids_in_history if ele!=object_uuid]
                self._current_selected_object_uuid_index = len(self._selected_objects_uuids_in_history) - 1
                self.selection_history_changed.emit(len(self._selected_objects_uuids_in_history), self._current_selected_object_uuid_index)

    def select_previous_object(self):
        self._current_selected_object_uuid_index -= 1
        if self._current_selected_object_uuid_index <= 0:
            self._current_selected_object_uuid_index = 0

        self._is_selected_from_inspector = True
        self._game_manager.deselect_all()
        self._game_manager.select(self._selected_objects_uuids_in_history[self._current_selected_object_uuid_index])
        self.selection_index_changed.emit(len(self._selected_objects_uuids_in_history), self._current_selected_object_uuid_index)

    def select_next_object(self):
        self._current_selected_object_uuid_index += 1
        if self._current_selected_object_uuid_index >= len(self._selected_objects_uuids_in_history) - 1:
            self._current_selected_object_uuid_index = len(self._selected_objects_uuids_in_history) - 1

        self._is_selected_from_inspector = True
        self._game_manager.deselect_all()
        self._game_manager.select(self._selected_objects_uuids_in_history[self._current_selected_object_uuid_index])
        self.selection_index_changed.emit(len(self._selected_objects_uuids_in_history), self._current_selected_object_uuid_index)

    def retranslate(self):
        self._inspect_object(self._object_uuid_in_inspection)

