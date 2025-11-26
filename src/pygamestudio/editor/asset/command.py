from PySide6.QtGui import QUndoCommand, QColor
from PySide6.QtCore import Qt
from pathlib import Path


class ModifyItemDataCommand(QUndoCommand):
    def __init__(self, tree_widget, item, key, old_value, new_value, description='Modified item data'):
        super().__init__(description)
        self.__tree_widget = tree_widget
        self.__item = item
        self.__key = key
        self.__old_value = old_value
        self.__new_value = new_value
        
    def redo(self):
        self.__tree_widget.blockSignals(True)
        self.__apply_value(self.__new_value)
        self.__tree_widget.blockSignals(False)
        
    def undo(self):
        self.__tree_widget.blockSignals(True)
        self.__apply_value(self.__old_value)
        self.__tree_widget.blockSignals(False)

    def __apply_value(self, value):
        item_data = self.__item.data(0, Qt.ItemDataRole.UserRole)

        if self.__key == 'name':
            parent_item = self.__item.parent()
            parent_item_path = Path(parent_item.data(0, Qt.ItemDataRole.UserRole).get('path'))
            
            old_item_path = Path(item_data['path'])
            new_item_path = parent_item_path / value
            old_item_path.rename(new_item_path)

            self.__item.setText(0, value)
            item_data[self.__key] = value
            item_data['path'] = str(new_item_path)

        elif self.__key == 'isExpanded':
            self.__item.setExpanded(value)
            item_data[self.__key] = value

        self.__item.setData(0, Qt.ItemDataRole.UserRole, item_data)