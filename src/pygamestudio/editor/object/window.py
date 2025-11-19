from PySide6.QtWidgets import QWidget, QVBoxLayout
from pygamestudio.editor.object.tree import ObjectTreeWidget
from pygamestudio.editor.object.search import SearchLineEdit


class ObjectManagerWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__object_tree_widget = ObjectTreeWidget(self)
        self.__search_line_edit = SearchLineEdit(self)

        self.__set_up()
    
    def __set_up(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_layout()

    def __set_widget(self):
        ...

    def __set_signal(self):
        self.__search_line_edit.search_signal.connect(self.__object_tree_widget.search_items)

    def __set_layout(self):
        v_layout = QVBoxLayout(self)
        v_layout.addWidget(self.__search_line_edit)
        v_layout.addWidget(self.__object_tree_widget)
