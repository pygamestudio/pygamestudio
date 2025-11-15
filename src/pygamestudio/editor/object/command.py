from PySide6.QtGui import QUndoCommand, QColor
from PySide6.QtCore import Qt
import copy


class CompositeCommand(QUndoCommand):
    def __init__(self, description):
        super().__init__(description)
        self.__commands = []
    
    def add_command(self, command):
        self.__commands.append(command)
    
    def redo(self):
        for command in self.__commands:
            command.redo()
    
    def undo(self):
        for command in reversed(self.__commands):
            command.undo()


class AddItemCommand(QUndoCommand):
    def __init__(self, tree_widget, parent_item, item, index, description='Added item'):
        super().__init__(description)
        self.__tree_widget = tree_widget
        self.__parent_item = parent_item
        self.__item = item
        self.__index = index

    def redo(self):
        self.__tree_widget.blockSignals(True)
        self.__parent_item.insertChild(self.__index, self.__item)
        self.__tree_widget.setCurrentItem(self.__item)
        isExpanded = self.__item.data(0, Qt.ItemDataRole.UserRole).get('isExpanded')
        self.__item.setExpanded(isExpanded)
        self.__tree_widget.blockSignals(False)
        
    def undo(self):
        self.__tree_widget.blockSignals(True)
        self.__parent_item.removeChild(self.__item)
        self.__tree_widget.blockSignals(False)


class DeleteItemCommand(QUndoCommand):
    def __init__(self, tree_widget, item, description='Deleted item'):
        super().__init__(description)
        self.__tree_widget = tree_widget
        self.__item = item
        self.__parent_item = item.parent()
        self.__index = self.__parent_item.indexOfChild(item)

    def redo(self):
        self.__tree_widget.blockSignals(True)
        self.__parent_item.removeChild(self.__item)
        self.__tree_widget.blockSignals(False)

    def undo(self):
        self.__tree_widget.blockSignals(True)
        self.__parent_item.insertChild(self.__index, self.__item)
        isExpanded = self.__item.data(0, Qt.ItemDataRole.UserRole).get('isExpanded')
        self.__item.setExpanded(isExpanded)
        self.__tree_widget.blockSignals(False)


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
        if self.__key == 'name':
            self.__item.setText(0,value)
                
        elif self.__key == 'isVisible':
            # The delegate will update the item foreground.
            self.__tree_widget.viewport().update()

        elif self.__key == 'foreground':
            self.__item.setForeground(0, value.getRgb())
            self.__tree_widget.viewport().update()

        elif self.__key == 'isExpanded':
            self.__item.setExpanded(value)