from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import Qt, QTimer


class CompositeCommand(QUndoCommand):
    def __init__(self, description):
        super().__init__(description)
        self._commands = []
    
    def add_command(self, command):
        self._commands.append(command)
    
    def redo(self):
        for command in self._commands:
            command.redo()
    
    def undo(self):
        for command in reversed(self._commands):
            command.undo()


class AddItemCommand(QUndoCommand):
    def __init__(self, tree_view, proxy_model, standard_model, parent_item, item, row, description='Added item'):
        super().__init__(description)
        self._tree_view = tree_view
        self._hierarchy_window = self._tree_view.parent()
        self._proxy_model = proxy_model
        self._standard_model = standard_model
        self._parent_item = parent_item
        self._item = item
        self._row = row


    def redo(self):
        self._tree_view.blockSignals(True)
        
        parent_index = self._proxy_model.mapFromSource(self._standard_model.indexFromItem(self._parent_item))
        index = self._proxy_model.mapFromSource(self._standard_model.indexFromItem(self._item))
        self._parent_item.insertRow(self._row, self._item)
        self._tree_view.setExpanded(parent_index, True)
        self._tree_view.restore_expanded_items(self._item)
        self._tree_view.setCurrentIndex(index)
        self._tree_view.scrollTo(index)

        item_data = self._item.data(Qt.ItemDataRole.UserRole+1)
        self._hierarchy_window.hierarchy_to_scene_create_signal.emit(item_data)

        self._tree_view.blockSignals(False)
        
    def undo(self):
        self._tree_view.blockSignals(True)

        item_data = self._item.data(Qt.ItemDataRole.UserRole+1)
        self._hierarchy_window.hierarchy_to_scene_delete_signal.emit(item_data['uuid'])
        self._parent_item.takeRow(self._row)

        self._tree_view.blockSignals(False)


class DeleteItemCommand(QUndoCommand):
    def __init__(self, tree_view, proxy_model, standard_model, item, description='Deleted item'):
        super().__init__(description)
        self._tree_view = tree_view
        self._hierarchy_window = self._tree_view.parent()
        self._proxy_model = proxy_model
        self._standard_model = standard_model
        self._item = item
        self._parent_item = item.parent()
        self._row = item.row()
        
    def redo(self):
        self._tree_view.blockSignals(True)

        item_data = self._item.data(Qt.ItemDataRole.UserRole+1)
        self._hierarchy_window.hierarchy_to_scene_delete_signal.emit(item_data['uuid'])
        self._parent_item.takeRow(self._row)

        self._tree_view.blockSignals(False)

    def undo(self):
        self._tree_view.blockSignals(True)
        
        item_data = self._item.data(Qt.ItemDataRole.UserRole+1)
        self._parent_item.insertRow(self._row, self._item)
        is_expanded = item_data.get('is_expanded')
        self._tree_view.setExpanded(self._proxy_model.mapFromSource(self._standard_model.indexFromItem(self._item)), is_expanded)
        
        self._hierarchy_window.hierarchy_to_scene_create_signal.emit(item_data)
    
        self._tree_view.blockSignals(False)


class ModifyItemDataCommand(QUndoCommand):
    def __init__(self, tree_view, proxy_model, standard_model, item, key, old_value, new_value, description='Modified item data'):
        super().__init__(description)
        self._tree_view = tree_view
        self._hierarchy_window = self._tree_view.parent()
        self._proxy_model = proxy_model
        self._standard_model = standard_model
        self._item = item
        self._key = key
        self._old_value = old_value
        self._new_value = new_value
        
    def redo(self):
        self._tree_view.blockSignals(True)
        self._standard_model.blockSignals(True)
        self._apply_value(self._new_value)
        self._tree_view.blockSignals(False)
        self._standard_model.blockSignals(False)
        
    def undo(self):
        self._tree_view.blockSignals(True)
        self._standard_model.blockSignals(True)
        self._apply_value(self._old_value)
        self._tree_view.blockSignals(False)
        self._standard_model.blockSignals(False)

    def _apply_value(self, value):
        item_data = self._item.data(Qt.ItemDataRole.UserRole+1)

        if self._key == 'name':
            self._item.setText(value)
            item_data[self._key] = value
            self._hierarchy_window.hierarchy_to_scene_update_data_signal.emit(item_data['uuid'], self._key, item_data)
                
        elif self._key == 'is_visible':
            item_data[self._key] = value
            self._hierarchy_window.hierarchy_to_scene_update_data_signal.emit(item_data['uuid'], self._key, item_data)

        elif self._key == 'is_expanded':
            QTimer.singleShot(10, lambda:self._tree_view.setExpanded(self._proxy_model.mapFromSource(self._standard_model.indexFromItem(self._item)), value))
            item_data[self._key] = value

        self._item.setData(item_data, Qt.ItemDataRole.UserRole+1)
        self._tree_view.viewport().update()