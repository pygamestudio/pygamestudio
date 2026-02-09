from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from pygamestudio.editor.gui.inspector.component.label import PropertyLabel
from pygamestudio.editor.gui.inspector.layout.common import INSPECTOR_LAYOUT_COMMON_PREFIX, INSPECTOR_LAYOUT_COMMON_SUFFIX

from pygamestudio.game.object.type import *
from pygamestudio.game.object.rect import ObjectRect


class InspectorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.__inspector_layout = QVBoxLayout(self)
        # self.__object = GameObjectRect('Rect', 100 ,100)
        # self.inspect_object(self.__object)
        
    def inspect_object(self, game_object):
        self.__clear_layout(self.__inspector_layout)

        self.__add_commom_layout_prefix(game_object)

        if game_object.object_type == ObjectRect:
            self.__add_layout_for_rect(game_object)

        self.__add_common_layout_suffix(game_object)

    def __clear_layout(self, layout):
        if layout is None:
            return
    
        while layout.count():
            item = layout.takeAt(0)
            
            if item.widget():
                widget = item.widget()
                widget.deleteLater()
            elif item.layout():
                self.__clear_layout(item.layout())
                item.layout().deleteLater()
            elif item.spacerItem():
                layout.removeItem(item)

    def __add_commom_layout_prefix(self, game_object):
        for property_detail in INSPECTOR_LAYOUT_COMMON_PREFIX.values():
            name = property_detail['i18n']['en'] # 这里的名称要根据设置来修改
            layout_type = property_detail['component']['layout']
            widget_list = property_detail['component']['widget']
            attribute_list = property_detail['component']['attribute']

            layout = QHBoxLayout() if layout_type == 'horizontal' else QVBoxLayout()
            label = PropertyLabel(name)
            layout.addWidget(label)

            for i, widget in enumerate(widget_list):
                w = widget(getattr(game_object, attribute_list[i]))
                layout.addWidget(w)
            
            self.__inspector_layout.addLayout(layout)

    def __add_common_layout_suffix(self, game_object):
        ...

    def __add_layout_for_rect(self, game_object):
        ...



