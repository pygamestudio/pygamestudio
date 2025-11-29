from PySide6.QtGui import QUndoCommand, QColor
from PySide6.QtCore import Qt
from pathlib import Path
import shutil


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
    def __init__(self, tree_widget, parent_item, item, description='Added item'):
        super().__init__(description)
        self.__tree_widget = tree_widget
        self.__parent_item = parent_item
        self.__item = item

    def redo(self):
        self.__tree_widget.blockSignals(True)
        
        item_data = self.__item.data(0, Qt.ItemDataRole.UserRole)
        path = Path(item_data['path'])
        path.mkdir(exist_ok=False) if path.is_dir() else path.touch(exist_ok=False)

        index = self.__tree_widget.get_insert_index_by_name(self.__parent_item, item_data['name'])        
        self.__parent_item.insertChild(index, self.__item)
        self.__tree_widget.setCurrentItem(self.__item)
        self.__tree_widget.scrollToItem(self.__item)

        isExpanded = item_data['isExpanded']
        self.__item.setExpanded(isExpanded)
        self.__parent_item.setExpanded(True)

        self.__tree_widget.blockSignals(False)
        
    def undo(self):
        self.__tree_widget.blockSignals(True)
        self.__parent_item.removeChild(self.__item)
        path = Path(self.__item.data(0, Qt.ItemDataRole.UserRole).get('path'))
        shutil.rmtree(path) if path.is_dir() else path.unlink()                
        self.__tree_widget.blockSignals(False)


class PasteItemCommand(QUndoCommand):
    def __init__(self, tree_widget, parent_item, item, __is_cut_action=False, description='Added item'):
        super().__init__(description)
        self.__tree_widget = tree_widget
        self.__parent_item = parent_item
        self.__item = item
        self.__is_cut_action = False

    def redo(self):
        self.__tree_widget.blockSignals(True)
        
        item_data = self.__item.data(0, Qt.ItemDataRole.UserRole)
        source_path = Path(item_data['path'])
        parent_item_path = self.__parent_item.data(0, Qt.ItemDataRole.UserRole).get('path')
        target_name, target_path = self.__tree_widget.get_unique_path(item_data['name'], Path(parent_item_path))
        
        if self.__is_cut_action:
            shutil.move(source_path, target_path)
        else:
            shutil.copytree(source_path, target_path) if target_path.is_dir() else shutil.copy2(source_path, target_path)

        item_data['name'] = target_name
        item_data['path'] = str(target_path)
        self.__item.setText(0, target_name)
        self.__item.setData(0, Qt.ItemDataRole.UserRole, item_data)

        index = self.__tree_widget.get_insert_index_by_name(self.__parent_item, target_name)        
        self.__parent_item.insertChild(index, self.__item)
        self.__tree_widget.setCurrentItem(self.__item)
        self.__tree_widget.scrollToItem(self.__item)

        isExpanded = item_data.get('isExpanded')
        self.__item.setExpanded(isExpanded)
        self.__parent_item.setExpanded(True)

        self.__tree_widget.blockSignals(False)
        
    def undo(self):
        self.__tree_widget.blockSignals(True)
        self.__parent_item.removeChild(self.__item)
        path = Path(self.__item.data(0, Qt.ItemDataRole.UserRole).get('path'))
        shutil.rmtree(path) if path.is_dir() else path.unlink()                
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
        item_path = Path(self.__item.data(0, Qt.ItemDataRole.UserRole).get('path'))
        if item_path.is_dir():
            item_path.rmdir()
        else:
            item_path.unlink()
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