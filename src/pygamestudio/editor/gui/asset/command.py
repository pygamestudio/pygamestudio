from PySide6.QtGui import QUndoCommand, QColor
from PySide6.QtCore import Qt
from pathlib import Path
import shutil


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
    def __init__(self, tree_widget, parent_item, item, description='Added item'):
        super().__init__(description)
        self._tree_widget = tree_widget
        self._parent_item = parent_item
        self._item = item

    def redo(self):
        self._tree_widget.blockSignals(True)
        
        item_data = self._item.data(0, Qt.ItemDataRole.UserRole)
        path = Path(item_data['path'])
        path.mkdir(exist_ok=False) if path.is_dir() else path.touch(exist_ok=False)

        index = self._tree_widget.get_insert_index_by_name(self._parent_item, item_data['name'])        
        self._parent_item.insertChild(index, self._item)
        self._tree_widget.setCurrentItem(self._item)
        self._tree_widget.scrollToItem(self._item)

        isExpanded = item_data['isExpanded']
        self._item.setExpanded(isExpanded)
        self._parent_item.setExpanded(True)

        self._tree_widget.blockSignals(False)
        
    def undo(self):
        self._tree_widget.blockSignals(True)
        self._parent_item.removeChild(self._item)
        path = Path(self._item.data(0, Qt.ItemDataRole.UserRole).get('path'))
        shutil.rmtree(path) if path.is_dir() else path.unlink()                
        self._tree_widget.blockSignals(False)


class PasteItemCommand(QUndoCommand):
    def __init__(self, tree_widget, parent_item, item, _is_cut_action=False, description='Added item'):
        super().__init__(description)
        self._tree_widget = tree_widget
        self._parent_item = parent_item
        self._item = item
        self._is_cut_action = False

    def redo(self):
        self._tree_widget.blockSignals(True)
        
        item_data = self._item.data(0, Qt.ItemDataRole.UserRole)
        source_path = Path(item_data['path'])
        parent_item_path = self._parent_item.data(0, Qt.ItemDataRole.UserRole).get('path')
        target_name, target_path = self._tree_widget.get_unique_path(item_data['name'], Path(parent_item_path))
        
        if self._is_cut_action:
            shutil.move(source_path, target_path)
        else:
            shutil.copytree(source_path, target_path) if target_path.is_dir() else shutil.copy2(source_path, target_path)

        item_data['name'] = target_name
        item_data['path'] = str(target_path)
        self._item.setText(0, target_name)
        self._item.setData(0, Qt.ItemDataRole.UserRole, item_data)

        index = self._tree_widget.get_insert_index_by_name(self._parent_item, target_name)        
        self._parent_item.insertChild(index, self._item)
        self._tree_widget.setCurrentItem(self._item)
        self._tree_widget.scrollToItem(self._item)

        isExpanded = item_data.get('isExpanded')
        self._item.setExpanded(isExpanded)
        self._parent_item.setExpanded(True)

        self._tree_widget.blockSignals(False)
        
    def undo(self):
        self._tree_widget.blockSignals(True)
        self._parent_item.removeChild(self._item)
        path = Path(self._item.data(0, Qt.ItemDataRole.UserRole).get('path'))
        shutil.rmtree(path) if path.is_dir() else path.unlink()                
        self._tree_widget.blockSignals(False)


class DeleteItemCommand(QUndoCommand):
    def __init__(self, tree_widget, item, description='Deleted item'):
        super().__init__(description)
        self._tree_widget = tree_widget
        self._item = item
        self._parent_item = item.parent()
        self._index = self._parent_item.indexOfChild(item)

    def redo(self):
        self._tree_widget.blockSignals(True)
        self._parent_item.removeChild(self._item)
        item_path = Path(self._item.data(0, Qt.ItemDataRole.UserRole).get('path'))
        if item_path.is_dir():
            item_path.rmdir()
        else:
            item_path.unlink()
        self._tree_widget.blockSignals(False)

    def undo(self):
        self._tree_widget.blockSignals(True)
        self._parent_item.insertChild(self._index, self._item)
        isExpanded = self._item.data(0, Qt.ItemDataRole.UserRole).get('isExpanded')
        self._item.setExpanded(isExpanded)
        self._tree_widget.blockSignals(False)


class ModifyItemDataCommand(QUndoCommand):
    def __init__(self, tree_widget, item, key, old_value, new_value, description='Modified item data'):
        super().__init__(description)
        self._tree_widget = tree_widget
        self._item = item
        self._key = key
        self._old_value = old_value
        self._new_value = new_value
        
    def redo(self):
        self._tree_widget.blockSignals(True)
        self._apply_value(self._new_value)
        self._tree_widget.blockSignals(False)
        
    def undo(self):
        self._tree_widget.blockSignals(True)
        self._apply_value(self._old_value)
        self._tree_widget.blockSignals(False)

    def _apply_value(self, value):
        item_data = self._item.data(0, Qt.ItemDataRole.UserRole)

        if self._key == 'name':
            parent_item = self._item.parent()
            parent_item_path = Path(parent_item.data(0, Qt.ItemDataRole.UserRole).get('path'))
            
            old_item_path = Path(item_data['path'])
            new_item_path = parent_item_path / value
            old_item_path.rename(new_item_path)

            self._item.setText(0, value)
            item_data[self._key] = value
            item_data['path'] = str(new_item_path)

        elif self._key == 'isExpanded':
            self._item.setExpanded(value)
            item_data[self._key] = value

        self._item.setData(0, Qt.ItemDataRole.UserRole, item_data)