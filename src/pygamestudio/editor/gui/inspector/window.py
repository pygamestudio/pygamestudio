from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from pygamestudio.editor.gui.inspector.component.label import PropertyLabel
from pygamestudio.editor.gui.inspector.layout.common import INSPECTOR_LAYOUT_COMMON_PREFIX, INSPECTOR_LAYOUT_COMMON_SUFFIX

from pygamestudio.game.object.type import *


class InspectorWindow(QWidget):
    def __init__(self, parent=None, object_manager=None):
        super().__init__(parent)
        self._object_manager = object_manager
        self._object_uuid_in_inspection = None
        self._inspector_layout = QVBoxLayout(self)

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        ...

    def _set_signal(self):
        self._object_manager.object_added.connect(self._on_object_added)
        self._object_manager.object_deleted.connect(self._on_object_deleted)
        self._object_manager.object_selected.connect(self._on_object_selected)
        self._object_manager.object_deselected.connect(self._on_object_deselected)
        self._object_manager.object_moved.connect(self._on_object_moved)
        self._object_manager.object_scaled.connect(self._on_object_scaled)
        self._object_manager.object_rotated.connect(self._on_object_rotated)
        self._object_manager.object_showed.connect(self._on_object_showed)
        self._object_manager.object_hidden.connect(self._on_object_hidden)
        self._object_manager.object_color_changed.connect(self._on_object_color_changed)
    
    def rename(self):
        lineedit = self._find_widget(self._inspector_layout, 'name')
        self._object_manager.rename(self._object_uuid_in_inspection, lineedit.text().strip())

    def resize(self):
        spinbox_width = self._find_widget(self._inspector_layout, 'width')
        spinbox_height = self._find_widget(self._inspector_layout, 'height')
        new_size = (spinbox_width.value(), spinbox_height.value())
        self._object_manager.resize(self._object_uuid_in_inspection, new_size)

    def move(self):
        spinbox_x = self._find_widget(self._inspector_layout, 'x')
        spinbox_y = self._find_widget(self._inspector_layout, 'y')
        new_pos = (spinbox_x.value(), spinbox_y.value())
        self._object_manager.move(self._object_uuid_in_inspection, new_pos)

    def scale(self):
        spinbox_scale_x = self._find_widget(self._inspector_layout, 'scale_x')
        spinbox_scale_y = self._find_widget(self._inspector_layout, 'scale_y')
        new_scale = (spinbox_scale_x.value(), spinbox_scale_y.value())
        self._object_manager.scale(self._object_uuid_in_inspection, new_scale)

    def rotate(self):
        spinbox_angle = self._find_widget(self._inspector_layout, 'angle')
        new_angle = spinbox_angle.value()
        self._object_manager.rotate(self._object_uuid_in_inspection, new_angle)

    def show(self):
        self._object_manager.show(self._object_uuid_in_inspection)

    def hide(self):
        self._object_manager.hide(self._object_uuid_in_inspection)

    def set_color(self, new_color):
        self._object_manager.set_color(self._object_uuid_in_inspection, new_color)

    def _on_object_added(self, parent_uuid, object_uuid, inserted_pos):
        # Object will be selected when added, and it will be inspected in slot _on_object_selected.
        # self._inspect_object(object_uuid)
        ...

    def _on_object_deleted(self, object_uuid):
        self._clear_layout(self._inspector_layout)

    def _on_object_selected(self, object_uuid):
        self._inspect_object(object_uuid)

    def _on_object_deselected(self, object_uuid):
        ...

    def _on_object_resized(self, object_uuid):
        # 等待gizmo实现
        obj = self._object_manager.get_object(object_uuid)
        spinbox_width = self._find_widget(self._inspector_layout, 'width')
        spinbox_height = self._find_widget(self._inspector_layout, 'height')
        spinbox_width.blockSignals(True)
        spinbox_height.blockSignals(True)
        spinbox_width.setValue(obj.x)
        spinbox_height.setValue(obj.y)
        spinbox_width.blockSignals(False)
        spinbox_height.blockSignals(False)

    def _on_object_moved(self, object_uuid):
        obj = self._object_manager.get_object(object_uuid)
        spinbox_x = self._find_widget(self._inspector_layout, 'x')
        spinbox_y = self._find_widget(self._inspector_layout, 'y')
        spinbox_x.blockSignals(True)
        spinbox_y.blockSignals(True)
        spinbox_x.setValue(obj.x)
        spinbox_y.setValue(obj.y)
        spinbox_x.blockSignals(False)
        spinbox_y.blockSignals(False)

    def _on_object_scaled(self, object_uuid):
        obj = self._object_manager.get_object(object_uuid)
        spinbox_scale_x = self._find_widget(self._inspector_layout, 'scale_x')
        spinbox_scale_y = self._find_widget(self._inspector_layout, 'scale_y')
        spinbox_scale_x.blockSignals(True)
        spinbox_scale_y.blockSignals(True)
        spinbox_scale_x.setValue(obj.scale_x)
        spinbox_scale_y.setValue(obj.scale_y)
        spinbox_scale_x.blockSignals(False)
        spinbox_scale_y.blockSignals(False)

    def _on_object_rotated(self, object_uuid):
        obj = self._object_manager.get_object(object_uuid)
        spinbox_angle = self._find_widget(self._inspector_layout, 'angle')
        spinbox_angle.blockSignals(True)
        spinbox_angle.setValue(obj.angle)
        spinbox_angle.blockSignals(False)

    def _on_object_showed(self, object_uuid):
        if object_uuid != self._object_uuid_in_inspection:
            return
        
        checkbox = self._find_widget(self._inspector_layout, 'is_visible')
        checkbox.setChecked(True)

    def _on_object_hidden(self, object_uuid):
        if object_uuid != self._object_uuid_in_inspection:
            return
        
        checkbox = self._find_widget(self._inspector_layout, 'is_visible')
        checkbox.setChecked(False)

    def _on_object_color_changed(self, object_uuid):
        if object_uuid != self._object_uuid_in_inspection:
            return
        
        obj = self._object_manager.get_object(object_uuid)
        color_picker = self._find_widget(self._inspector_layout, 'color')
        color_picker.set_color(obj.color)

    def _find_widget(self, layout, widget_name):
        for i in range(layout.count()):
            item = layout.itemAt(i)
            
            # 如果是控件
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
        obj = self._object_manager.get_object(object_uuid)

        # 如果是场景对象，先暂时返回
        if obj.type == OBJECT_SCENE:
            return
        
        self._object_uuid_in_inspection = object_uuid
        self._clear_layout(self._inspector_layout)
        self._add_commom_layout_prefix(obj)

        if obj.type == OBJECT_RECT:
            self._add_layout_for_rect(obj)

        self._add_common_layout_suffix(obj)

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

    def _add_commom_layout_prefix(self, obj):
        for property_detail in INSPECTOR_LAYOUT_COMMON_PREFIX.values():
            name = property_detail['i18n']['en'] # 这里的名称要根据设置来修改
            layout_type = property_detail['component']['layout']
            attributes = property_detail['component']['attribute']
            widgets = property_detail['component']['widget']

            layout = QHBoxLayout() if layout_type == 'horizontal' else QVBoxLayout()
            label = PropertyLabel(self, name)
            layout.addWidget(label)

            for i, widget in enumerate(widgets):
                w = widget(self, getattr(obj, attributes[i]))
                w.setObjectName(attributes[i])
                layout.addWidget(w)
            
            self._inspector_layout.addLayout(layout)

    def _add_common_layout_suffix(self, obj):
        self._inspector_layout.addStretch(1)

    def _add_layout_for_rect(self, obj):
        ...


