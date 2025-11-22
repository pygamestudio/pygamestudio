from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from pygamestudio.editor.object.tree import ObjectTreeWidget
from pygamestudio.editor.object.search import SearchLineEdit
from pygamestudio.editor.object.widget import ExpandCollapseAllButton, CreateItemButton


class ObjectManagerWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__object_tree_widget = ObjectTreeWidget(self)
        self.__search_line_edit = SearchLineEdit(self)

        self.__create_item_button = CreateItemButton(self)
        self.__expand_collapse_all_button = ExpandCollapseAllButton(self)

        self.__set_up()
    
    def __set_up(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_layout()

    def __set_widget(self):
        ...

    def __set_signal(self):
        self.__search_line_edit.search_signal.connect(self.__object_tree_widget.search_items)

        self.__create_item_button.create_signal.connect(self.__object_tree_widget.create_item)
        self.__expand_collapse_all_button.clicked.connect(self.__object_tree_widget.expand_or_collapse_all)

    def __set_layout(self):
        h_layout = QHBoxLayout()
        v_layout = QVBoxLayout(self)
        h_layout.addWidget(self.__create_item_button)
        h_layout.addWidget(self.__search_line_edit)
        h_layout.addWidget(self.__expand_collapse_all_button)
        h_layout.setSpacing(0)
        h_layout.setContentsMargins(0, 0, 0, 0)

        v_layout.addLayout(h_layout)
        v_layout.addWidget(self.__object_tree_widget)
