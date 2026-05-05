from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.game.object.type import *
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.gui.inspector.component.label import PropertyLabel
from pygamestudio.gui.inspector.layout.rect import INSPECTOR_LAYOUT_RECT
from pygamestudio.gui.inspector.layout.ellipse import INSPECTOR_LAYOUT_ELLIPSE
from pygamestudio.gui.inspector.layout.line import INSPECTOR_LAYOUT_LINE
from pygamestudio.gui.inspector.layout.canvas import INSPECTOR_LAYOUT_CANVAS
from pygamestudio.gui.inspector.layout.text import INSPECTOR_LAYOUT_TEXT


class Container(QFrame):
    def __init__(self, parent, game_manager):
        super().__init__(parent)
        self._inspector_window = parent
        self._game_manager = game_manager

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
        # self._game_manager.object_added.connect(self._on_object_added)
        self._game_manager.object_deleted.connect(self._on_object_deleted)
        self._game_manager.object_selected.connect(self._on_object_selected)
        # self._game_manager.object_deselected.connect(self._on_object_deselected)
        self._game_manager.object_renamed.connect(self._on_object_renamed)
        self._game_manager.object_moved.connect(self._on_object_moved)
        self._game_manager.object_scaled.connect(self._on_object_scaled)
        self._game_manager.object_rotated.connect(self._on_object_rotated)
        self._game_manager.object_showed.connect(self._on_object_showed)
        self._game_manager.object_hidden.connect(self._on_object_hidden)
        self._game_manager.object_color_changed.connect(self._on_object_color_changed)
        self._game_manager.object_rect_border_radius_changed.connect(self._on_object_rect_border_radius_changed)
        self._game_manager.object_line_start_point_changed.connect(self._on_object_line_start_point_changed)
        self._game_manager.object_line_end_point_changed.connect(self._on_object_line_end_point_changed)
        self._game_manager.object_line_thickness_changed.connect(self._on_object_line_thickness_changed)

    def _set_layout(self):
        self._container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._container_layout.setVerticalSpacing(10)
        self._container_layout.setContentsMargins(8, 4, 8, 4)

    def _set_object_name(self):
        self.setObjectName('inspectorContainer')

    def get_ready_for_project(self):
        ...
        
    def clean_up(self):
        self._object_uuid_in_inspection = None
        self._container_row = 0
        self._max_column = 1
        self._clear_layout(self._container_layout)

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
        checkbox_bold = self._find_widget(self._container_layout, 'is_bold')
        new_bold_state = checkbox_bold.isChecked()
        self._game_manager.set_bold_state(self._object_uuid_in_inspection, new_bold_state)

    def set_object_italic_state(self):
        checkbox_italic = self._find_widget(self._container_layout, 'is_italic')
        new_italic_state = checkbox_italic.isChecked()
        self._game_manager.set_italic_state(self._object_uuid_in_inspection, new_italic_state)

    def set_object_underline_state(self):
        checkbox_underline = self._find_widget(self._container_layout, 'is_underline')
        new_underline_state = checkbox_underline.isChecked()
        self._game_manager.set_underline_state(self._object_uuid_in_inspection, new_underline_state)

    def set_object_strikethrough_state(self):
        checkbox_strikethrough = self._find_widget(self._container_layout, 'is_strikethrough')
        new_strikethrough_state = checkbox_strikethrough.isChecked()
        self._game_manager.set_strikethrough_state(self._object_uuid_in_inspection, new_strikethrough_state)

    def _on_object_added(self, parent_uuid, object_uuid, inserted_pos):
        # Object will be selected when added, and it will be inspected in slot _on_object_selected.
        # self._inspect_object(object_uuid)
        ...

    def _on_object_deleted(self, object_uuid):
        self._clear_layout(self._container_layout)

    def _on_object_selected(self, object_uuid):
        self._inspect_object(object_uuid)

    def _on_object_deselected(self, object_uuid):
        ...

    def _on_object_resized(self, object_uuid):
        obj = self._game_manager.get_object(object_uuid)
        spinbox_width = self._find_widget(self._container_layout, 'width')
        spinbox_height = self._find_widget(self._container_layout, 'height')
        spinbox_width.blockSignals(True)
        spinbox_height.blockSignals(True)
        spinbox_width.setValue(obj.x)
        spinbox_height.setValue(obj.y)
        spinbox_width.blockSignals(False)
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
        
        checkbox = self._find_widget(self._container_layout, 'is_visible')
        checkbox.setChecked(True)

    def _on_object_hidden(self, object_uuid):
        if object_uuid != self._object_uuid_in_inspection:
            return
        
        checkbox = self._find_widget(self._container_layout, 'is_visible')
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

    def _find_widget(self, layout, widget_name):
        for i in range(layout.count()):
            item = layout.itemAt(i)
            
            widget = item.widget()
            if widget and widget.objectName() == widget_name:
                return widget
            
            sub_layout = item.layout()
            if sub_layout:
                result = self._find_widget(sub_layout, widget_name)
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
        elif obj.type == OBJECT_LINE:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_LINE)
        elif obj.type == OBJECT_TEXT:
            self._add_layout_for_specific_object(obj, INSPECTOR_LAYOUT_TEXT)

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

            for i, widget in enumerate(widget_list):
                w = widget(self, getattr(obj, attribute_list[i]), attribute_list[i])
                w.setObjectName(attribute_list[i])
                w.setEnabled(enabled_list[i])

                row = i // 2
                column = i%2+1

                column_stretch = 2 if len(widget_list) == 1 else 1
                self._container_layout.addWidget(w, self._container_row+row, column, 1, column_stretch)

            self._container_row += row+1

    def retranslate(self):
        self._inspect_object(self._object_uuid_in_inspection)

