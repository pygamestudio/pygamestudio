from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import Qt, QTimer


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
    def __init__(self, tree_view, proxy_model, standard_model, parent_item, item, row, description='Added item'):
        super().__init__(description)
        self.__tree_view = tree_view
        self.__proxy_model = proxy_model
        self.__standard_model = standard_model
        self.__parent_item = parent_item
        self.__item = item
        self.__row = row

    def redo(self):
        self.__tree_view.blockSignals(True)
        
        parent_index = self.__proxy_model.mapFromSource(self.__standard_model.indexFromItem(self.__parent_item))
        index = self.__proxy_model.mapFromSource(self.__standard_model.indexFromItem(self.__item))
        self.__parent_item.insertRow(self.__row, self.__item)
        self.__tree_view.setExpanded(parent_index, True)
        self.__tree_view.restore_expanded_items(self.__item)
        self.__tree_view.setCurrentIndex(index)
        self.__tree_view.scrollTo(index)

        self.__tree_view.blockSignals(False)
        
    def undo(self):
        self.__tree_view.blockSignals(True)
        self.__parent_item.takeRow(self.__row)
        self.__tree_view.blockSignals(False)


class DeleteItemCommand(QUndoCommand):
    def __init__(self, tree_view, proxy_model, standard_model, item, description='Deleted item'):
        super().__init__(description)
        self.__tree_view = tree_view
        self.__proxy_model = proxy_model
        self.__standard_model = standard_model
        self.__item = item
        self.__parent_item = item.parent()
        self.__row = item.row()
        
    def redo(self):
        self.__tree_view.blockSignals(True)
        self.__parent_item.takeRow(self.__row)
        self.__tree_view.blockSignals(False)

    def undo(self):
        self.__tree_view.blockSignals(True)
        self.__parent_item.insertRow(self.__row, self.__item)
        isExpanded = self.__item.data(Qt.ItemDataRole.UserRole+1).get('isExpanded')
        self.__tree_view.setExpanded(self.__proxy_model.mapFromSource(self.__standard_model.indexFromItem(self.__item)), isExpanded)
        self.__tree_view.blockSignals(False)


class ModifyItemDataCommand(QUndoCommand):
    def __init__(self, tree_view, proxy_model, standard_model, item, key, old_value, new_value, description='Modified item data'):
        super().__init__(description)
        self.__tree_view = tree_view
        self.__proxy_model = proxy_model
        self.__standard_model = standard_model
        self.__item = item
        self.__key = key
        self.__old_value = old_value
        self.__new_value = new_value
        
    def redo(self):
        self.__tree_view.blockSignals(True)
        self.__standard_model.blockSignals(True)
        self.__apply_value(self.__new_value)
        self.__tree_view.blockSignals(False)
        self.__standard_model.blockSignals(False)
        
    def undo(self):
        self.__tree_view.blockSignals(True)
        self.__standard_model.blockSignals(True)
        self.__apply_value(self.__old_value)
        self.__tree_view.blockSignals(False)
        self.__standard_model.blockSignals(False)

    def __apply_value(self, value):
        item_data = self.__item.data(Qt.ItemDataRole.UserRole+1)

        if self.__key == 'name':
            self.__item.setText(value)
            item_data[self.__key] = value
                
        elif self.__key == 'isVisible':
            item_data[self.__key] = value

        elif self.__key == 'isExpanded':
            QTimer.singleShot(10, lambda:self.__tree_view.setExpanded(self.__proxy_model.mapFromSource(self.__standard_model.indexFromItem(self.__item)), value))
            item_data[self.__key] = value

        self.__item.setData(item_data, Qt.ItemDataRole.UserRole+1)
        self.__tree_view.viewport().update()