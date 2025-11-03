from PySide6.QtWidgets import QTreeWidget
from PySide6.QtCore import Qt

from menu import ObjectManagerMenu


class ObjectTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__object_manager_menu = ObjectManagerMenu()

        self.__setup()

    def __setup(self):
        self.__set_widget()
        self.__set_signal()

    def __set_widget(self):
        self.setHeaderLabel('Object')
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def __set_signal(self):
        self.customContextMenuRequested.connect(self.__show_context_menu)
        self.itemSelectionChanged.connect(self.__on_item_selection_changed)
        self.itemChanged.connect(self.__on_item_changed)

    def __show_context_menu(self, pos):
        item = self.itemAt(pos)
        global_pos = self.mapToGlobal(pos)

        is_right_click_on_item = True if item else False
        self.__object_manager_menu.show(global_pos, is_right_click_on_item)

    def __on_item_changed(self):
        ...

    def __on_item_selection_changed(self):
        ...

    def __rename_item(self, item):
        ...

    def __move_to_group(self, item):
        ...


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    # app.setStyle("Fusion")
    
    window = ObjectTreeWidget()
    window.show()
    
    sys.exit(app.exec())