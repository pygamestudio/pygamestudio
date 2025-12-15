
from PySide6.QtWidgets import QApplication, QTreeWidget, QMessageBox, QTreeWidgetItem, QAbstractItemView, QHeaderView, QInputDialog
from PySide6.QtCore import Qt, QTimeLine, QSize, Signal
from PySide6.QtGui import QIcon, QColor

from pygamestudio.editor.asset.menu import ContextMenu
from pygamestudio.editor.asset.command import *

from pygamestudio.editor.asset.delegate import AssetTreeWidgetDelegate
from pygamestudio.editor.asset.data import *
from pygamestudio.editor.asset.type import *
from pathlib import Path
import subprocess
import platform
import shutil
import uuid
import copy
import os



class AssetTreeWidget(QTreeWidget):
    trigger_search_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.__delegate = AssetTreeWidgetDelegate(self)

        self.__initial_path = Path('C:/Users/louis/Desktop/demo')
        
        self.__clipboard_items = []
        self.__is_cut_action = False
        self.__items_to_delete_by_cut = []

        self.__search_text = ''
        self.__is_searching = False
        self.__match_items_after_search = []
        self.__original_indentation = self.indentation()

        self.__root_item = None
        self.__context_menu = ContextMenu('', self)

        self.__hover_item_in_drag_move = None


        self.__set_up()
    
    def __set_up(self):
        self.__set_widget()
        self.__set_signal()
        self.__load_file_system()

    def __set_widget(self):
        self.setItemDelegate(self.__delegate)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setHeaderHidden(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def __set_signal(self):
        self.customContextMenuRequested.connect(self.__show_context_menu)
        self.itemChanged.connect(self.__on_item_changed)
        self.itemExpanded.connect(self.__on_item_expanded)
        self.itemCollapsed.connect(self.__on_item_collapsed)

        self.__context_menu.create_signal.connect(self.__create_item)
        self.__context_menu.cut_signal.connect(self.__cut_items)
        self.__context_menu.copy_signal.connect(self.__copy_items)
        self.__context_menu.paste_signal.connect(self.__paste_items)
        self.__context_menu.delete_signal.connect(self.__delete_items)
        self.__context_menu.rename_signal.connect(self.__rename_item)
        self.__context_menu.duplicate_signal.connect(self.__duplicate_items)
        self.__context_menu.copy_uuid_signal.connect(self.__copy_item_uuid)
        self.__context_menu.copy_path_signal.connect(self.__copy_item_path)
        self.__context_menu.copy_name_signal.connect(self.__copy_item_name)
        self.__context_menu.open_in_terminal_signal.connect(self.__open_in_terminal)
        self.__context_menu.open_externally_signal.connect(self.__open_externally)
        self.__context_menu.show_in_explorer_signal.connect(self.__show_in_explorer)

    def __show_context_menu(self, pos):
        item = self.itemAt(pos)
        global_pos = self.mapToGlobal(pos)
        
        item_type = item.data(0, Qt.ItemDataRole.UserRole).get('type') if item else None
        is_root_item = item.data(0, Qt.ItemDataRole.UserRole).get('isRootItem') if item else True
        self.__context_menu.show(global_pos, item_type, is_root_item)

    def __on_item_changed(self, item, column):
        item_data = item.data(column, Qt.ItemDataRole.UserRole)
        if not item_data:
            return
        
        parent_item = item.parent() if item.parent() else self.__root_item
        parent_item_path = Path(parent_item.data(0, Qt.ItemDataRole.UserRole).get('path'))

        old_name = item_data['name']
        new_name = item.text(column)
        old_item_path = Path(item_data['path'])
        new_item_path = parent_item_path / new_name

        if old_name == new_name or not new_name.strip() or not new_item_path.suffix:
            item.setText(0, old_name)
            return

        # Can't change the suffix.
        if old_item_path.suffix != new_item_path.suffix:
            item.setText(0, old_name)
            QMessageBox.information(self, '不可操作', '无法在编辑器中修改文件后缀名！')
            return

        old_item_path.rename(new_item_path)

        item.setText(0, new_name)
        item_data['name'] = new_name
        item_data['path'] = str(new_item_path)
        item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        
        if self.__is_searching:
            self.search_items(self.__search_text)

    def __on_item_expanded(self, item):
        item_data = item.data(0, Qt.ItemDataRole.UserRole)

        # Push an expand command and update the item data.
        if item_data['isExpanded'] == False:
            item.setExpanded(True)
            item_data['isExpanded'] = True
            item.setData(0, Qt.ItemDataRole.UserRole, item_data)
            # self.__load_subdirectories(item)

    def __on_item_collapsed(self, item):
        item_data = item.data(0, Qt.ItemDataRole.UserRole)

        # Push a collapse command and update the item data.
        if item_data['isExpanded'] == True:
            item.setExpanded(False)
            item_data['isExpanded'] = False
            item.setData(0, Qt.ItemDataRole.UserRole, item_data)
            # self.__load_subdirectories(item)

    def __set_root_item(self):
        item_data = copy.deepcopy(DEFAULT_FOLDER_ITEM_DATA)
        item_id = str(uuid.uuid4())
        item_data['uuid'] = item_id
        item_data['isRootItem'] = True
        item_data['isExpanded'] = True
        item_data['name'] = self.__initial_path.name
        item_data['path'] = str(self.__initial_path)

        self.__root_item = QTreeWidgetItem()
        self.__root_item.setText(0, item_data['name'])
        self.__root_item.setIcon(0, QIcon(item_data['icon']))
        self.__root_item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        self.__root_item.setFlags(self.__root_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
        
        self.addTopLevelItem(self.__root_item)
        self.__root_item.setExpanded(True)

    def __load_file_system(self):
        self.clear()
        self.__set_root_item()
        # self.__add_placeholder(self.__root_item)
        self.__load_subdirectories(self.__root_item)

    def __add_placeholder(self, item):
        placeholder = QTreeWidgetItem()
        placeholder.setText(0, '正在加载...')
        item.addChild(placeholder)

    def __get_item_data_by_path(self, path):
        if path.is_dir():
            return copy.deepcopy(DEFAULT_FOLDER_ITEM_DATA)
        elif path.suffix.lower() == ITEM_SCENE:
            return copy.deepcopy(DEFAULT_FILE_SCENE_ITEM_DATA)
        elif path.suffix.lower() == ITEM_SCRIPT:
            return copy.deepcopy(DEFAULT_FILE_SCRIPT_ITEM_DATA)
        elif path.suffix.lower() == ITEM_TXT:
            return copy.deepcopy(DEFAULT_FILE_TXT_ITEM_DATA)
        elif path.suffix.lower() == ITEM_JSON:
            return copy.deepcopy(DEFAULT_FILE_JSON_ITEM_DATA)
        else:
            return copy.deepcopy(DEFAULT_OTHER_FILE_ITEM_DATA)

    def __iter_sorted(self, path):
        # Get all folders and sort them.
        directories = [d for d in path.iterdir() if d.is_dir()]
        directories.sort(key=lambda x: x.name.lower())
        
        # Get all files and sort them.
        files = [f for f in path.iterdir() if f.is_file()]
        files.sort(key=lambda x: x.name.lower())
        
        return directories + files
    
    def __load_subdirectories(self, item):
        # Remove the placeholder item.
        # if item.childCount() == 1 and item.child(0).text(0) == '正在加载...':
        #     item.takeChild(0)

        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        folder_path = Path(item_data['path'])
        
        for entry in self.__iter_sorted(folder_path):
            exists = False
            for i in range(item.childCount()):
                child_item = item.child(i)
                if child_item.data(0, Qt.ItemDataRole.UserRole).get('path') == str(entry):
                    exists = True
                    break
        
            if exists:
                continue
            
            item_data = self.__get_item_data_by_path(entry)
            item_id = str(uuid.uuid4())
            item_data['uuid'] = item_id
            item_data['name'] = entry.name
            item_data['path'] = str(entry)

            child_item = QTreeWidgetItem()
            child_item.setText(0, entry.name)
            child_item.setIcon(0, QIcon(item_data['icon']))
            child_item.setData(0, Qt.ItemDataRole.UserRole, item_data)
            child_item.setFlags(child_item.flags() | Qt.ItemFlag.ItemIsEditable)
            item.addChild(child_item)

            # If the folder is not empty, add a placeholder item to show the expand triangle.
            if entry.is_dir() and any(entry.iterdir()):
                # self.__add_placeholder(child_item)
                self.__load_subdirectories(child_item)

    def __refresh_tree(self):
        self.load_file_system()

    def __get_parent_for_new_item(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return self.__root_item
        
        parent_item = selected_items[-1]
        parent_item_path = Path(parent_item.data(0, Qt.ItemDataRole.UserRole).get('path'))
        
        if not parent_item_path.is_dir():
            parent_item = parent_item.parent()
        
        return parent_item if parent_item else self.__root_item

    def __create_item(self, item_type):
        if item_type == ITEM_FOLDER:
            self.__create_folder()
        else:
            self.__create_file(item_type)

        # If it is druing search, search again after creating a new item.
        if self.__is_searching:
            self.search_items(self.__search_text)

    def __create_folder(self):
        item_data = copy.deepcopy(DEFAULT_FOLDER_ITEM_DATA)

        parent_item = self.__get_parent_for_new_item()
        parent_item.setExpanded(True)
        parent_item_path = Path(parent_item.data(0, Qt.ItemDataRole.UserRole).get('path'))

        # Make sure the created folder name is different.
        folder_name, folder_path = self.__get_unique_path(item_data['name'], parent_item_path)
        folder_path.mkdir(exist_ok=False)

        item_data['name'] = folder_name
        item_data['uuid'] = str(uuid.uuid4())
        item_data['path'] = str(folder_path)

        item = QTreeWidgetItem()
        item.setText(0, item_data['name'])
        item.setIcon(0, QIcon(item_data['icon']))
        item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

        index = self.__get_insert_index_by_name(parent_item, item_data['name'], item_data['type'])
        parent_item.insertChild(index, item)
        self.__hightlight_item(item)
        self.scrollToItem(item)

    def __create_file(self, item_type):
        if item_type == ITEM_SCENE:
            item_data = copy.deepcopy(DEFAULT_FILE_SCENE_ITEM_DATA)
        elif item_type == ITEM_SCRIPT:
            item_data = copy.deepcopy(DEFAULT_FILE_SCRIPT_ITEM_DATA)
        elif item_type == ITEM_TXT:
            item_data = copy.deepcopy(DEFAULT_FILE_TXT_ITEM_DATA)
        elif item_type == ITEM_JSON:
            item_data = copy.deepcopy(DEFAULT_FILE_JSON_ITEM_DATA)

        parent_item = self.__get_parent_for_new_item()
        parent_item.setExpanded(True)
        parent_item_path = Path(parent_item.data(0, Qt.ItemDataRole.UserRole).get('path'))

        # Make sure the created file name is different.
        file_name, file_path = self.__get_unique_path(item_data['name'], parent_item_path)
        file_path.touch(exist_ok=False)

        item_data['name'] = file_name
        item_data['uuid'] = str(uuid.uuid4())
        item_data['path'] = str(file_path)

        item = QTreeWidgetItem()
        item.setText(0, item_data['name'])
        item.setIcon(0, QIcon(item_data['icon']))
        item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

        index = self.__get_insert_index_by_name(parent_item, item_data['name'], item_data['type'])
        parent_item.insertChild(index, item)
        self.__hightlight_item(item)
        self.scrollToItem(item)

    def __rename_item(self):
        self.editItem(self.currentItem())

    def __delete_items(self, items=None, need_to_confirm=True):
        selected_items = items if items else self.selectedItems()
        if not selected_items:
            return
        
        def is_to_delete(item, selected_items):
            """
            Check if the item needs to be deleted (no ancestor in the selected items list).
            E.g., if a file-type item has a folder-type ancestor item, we only need to delete the folder item as the file in the folder will be deleted together.
            """
            current = item
            while current.parent() and current.parent() != self.__root_item:
                if current.parent() in selected_items:
                    return False
                current = current.parent()
            return True
        
        items_to_delete = [item for item in selected_items if is_to_delete(item, selected_items)]

        reply = QMessageBox.StandardButton.Yes
        if need_to_confirm:
            item_names = [item.text(0) for item in items_to_delete]
            content = '确定要删除这 {} 个项目吗？此操作不可撤销。\n{}'.format(str(len(items_to_delete)), ('\n').join(item_names))
            reply = QMessageBox.question(self, '请确认...', content, QMessageBox.Yes | QMessageBox.No)
            
        if reply == QMessageBox.StandardButton.No:
            return
        
        for item in items_to_delete:
            if item == self.__root_item:
                continue

            parent = item.parent()
            parent.removeChild(item)
            item_path = Path(item.data(0, Qt.ItemDataRole.UserRole).get('path'))
            if item_path.exists():
                shutil.rmtree(item_path) if item_path.is_dir() else item_path.unlink()                

        del items_to_delete
        self.clearSelection()

    def __cut_items(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return
        
        def is_to_cut(item, selected_items):
            """
            Check if the item needs to be cut (no ancestor in the selected items list).
            E.g., if a file-type item has a folder-type ancestor item, we only need to cut the folder item as the file in the folder will be cut together.
            """
            current = item
            while current.parent() and current.parent() != self.__root_item:
                if current.parent() in selected_items:
                    return False
                current = current.parent()
            return True
        
        self.__clipboard_items = []
        self.__is_cut_action = True
        self.__items_to_delete_by_cut = selected_items
            
        for item in selected_items:
            if item == self.__root_item:
                continue
            self.__hightlight_item(item)
            if is_to_cut(item, selected_items):
                copied_item = self.__deep_copy_item(item)
                self.__clipboard_items.append(copied_item)

    def __copy_items(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return
        
        def is_to_copy(item, selected_items):
            """
            Check if the item needs to be copied (no ancestor in the selected items list).
            E.g., if a file-type item has a folder-type ancestor item, we only need to copy the folder item as the file in the folder will be copied together.
            """
            current = item
            while current.parent() and current.parent() != self.__root_item:
                if current.parent() in selected_items:
                    return False
                current = current.parent()
            return True
        
        self.__clipboard_items = []
        self.__is_cut_action = False
            
        for item in selected_items:
            if item == self.__root_item:
                continue
            self.__hightlight_item(item)
            if is_to_copy(item, selected_items):
                copied_item = self.__deep_copy_item(item)
                self.__clipboard_items.append(copied_item)
    
    def __deep_copy_item(self, item, is_copy_child=True):
        """Copy item and its children"""
        new_item = QTreeWidgetItem()
        
        new_item.setFlags(item.flags())
        new_item.setText(0, item.text(0))
        new_item.setIcon(0, item.icon(0))
        new_item.setData(0, Qt.ItemDataRole.UserRole, item.data(0, Qt.ItemDataRole.UserRole))

        if is_copy_child:
            for i in range(item.childCount()):
                child_item = item.child(i)
                new_child_item = self.__deep_copy_item(child_item)
                new_item.addChild(new_child_item)
        
        return new_item
    
    def __paste_items(self):
        if not self.__clipboard_items:
            return

        parent_item = self.__get_parent_for_new_item()
        parent_item.setExpanded(True)

        for item in self.__clipboard_items:
            new_item = self.__deep_copy_item(item)
            item_data = new_item.data(0, Qt.ItemDataRole.UserRole)
            source_path = Path(item_data['path'])
            parent_item_path = Path(parent_item.data(0, Qt.ItemDataRole.UserRole).get('path'))
            target_name, target_path = self.__get_unique_path(item_data['name'], parent_item_path)
            
            if self.__is_cut_action:
                shutil.move(source_path, target_path)
            else:
                shutil.copytree(source_path, target_path) if source_path.is_dir() else shutil.copy2(source_path, target_path)
                
            item_data['name'] = target_name
            item_data['path'] = str(target_path)
            new_item.setText(0, target_name)
            new_item.setData(0, Qt.ItemDataRole.UserRole, item_data)

            index = self.__get_insert_index_by_name(parent_item, target_name, item_data['type'])        
            parent_item.insertChild(index, new_item)
            self.__hightlight_item(new_item)
            self.scrollToItem(new_item)

            self.__restore_expanded_items(new_item)
           
        if self.__is_cut_action:
            self.__delete_items(self.__items_to_delete_by_cut, False)
            self.__items_to_delete_by_cut = []
            self.__clipboard_items = []
            self.__is_cut_action = False

    def __restore_expanded_items(self, parent_item):
        parent_item_data = parent_item.data(0, Qt.ItemDataRole.UserRole)
        if not parent_item_data['isExpanded']:
            return
        parent_item.setExpanded(True)
                
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            item_data = item.data(0, Qt.ItemDataRole.UserRole)
            
            if item_data['isExpanded']:
                item.setExpanded(True)

                if item.childCount() > 0:
                    self.__restore_expanded_items(item)

    def __restore_collapsed_items(self, parent_item):
        parent_item_data = parent_item.data(0, Qt.ItemDataRole.UserRole)
        if not parent_item_data['isExpanded']:
            parent_item.setExpanded(False)
                
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            item_data = item.data(0, Qt.ItemDataRole.UserRole)
            
            if not item_data['isExpanded']:
                item.setExpanded(False)

            if item.childCount() > 0:
                self.__restore_collapsed_items(item)

    def __hightlight_item(self, item):
        """Highlight item for some actions, e.g., copy action."""
        original_fg = item.foreground(0)
        original_r = original_fg.color().red()
        original_g = original_fg.color().green()
        original_b = original_fg.color().blue()

        timeline = QTimeLine(1500, self)
        timeline.setFrameRange(0, 100)        
        
        def update_frame(frame):
            # progress: 0 -> 1 -> 0
            progress = frame / 100.0
            
            if progress > 0.5:
                value = -(255-original_r) * progress
            else:
                value = (255-original_r) * progress
            
            fg_color = item.foreground(0).color()
            r = fg_color.red()
            g = fg_color.green() + value
            b = fg_color.blue() + value

            # Limit the result to [0, 255].
            r = max(original_g, min(r, 255))
            g = max(original_g, min(g, 255))
            b = max(original_b, min(b, 255))

            item.setForeground(0, QColor(r, g, b, 255))
        
        def animation_finished():
            item.setForeground(0, original_fg)
            timeline.deleteLater()
        
        timeline.frameChanged.connect(update_frame)
        timeline.finished.connect(animation_finished)
        timeline.start()

    def __get_insert_index_by_name(self, parent_item, new_item_name, new_item_type):
        directory_item_names = []
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            if item.text(0) == '正在加载...':
                continue
            item_name = item.text(0)
            item_type = item.data(0, Qt.ItemDataRole.UserRole)['type']
            if item_type == ITEM_FOLDER:
                directory_item_names.append(item_name)

        file_item_names = []
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            if item.text(0) == '正在加载...':
                continue
            item_name = item.text(0)
            item_type = item.data(0, Qt.ItemDataRole.UserRole)['type']
            if item_type != ITEM_FOLDER:
                file_item_names.append(item_name)

        if new_item_type == ITEM_FOLDER:
            for i, name in enumerate(directory_item_names):
                if name.lower() > new_item_name.lower():
                    return i
            
            return len(directory_item_names)

        else:
            for i, name in enumerate(file_item_names):
                if name.lower() > new_item_name.lower():
                    return i+len(directory_item_names)
                
            return len(file_item_names)+len(directory_item_names)
    
    def __get_unique_path(self, name, parent_item_path):
        num = 0
        new_name = name
        new_path = parent_item_path / new_name
        while new_path.exists():
            num += 1
            stem = Path(name).stem
            suffix = Path(name).suffix
            new_name = f"{stem}-{num}{suffix}"
            new_path = parent_item_path / new_name
        return new_name, new_path
    
    def __duplicate_items(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return
        
        for item in selected_items:
            if item == self.__root_item:
                continue
            new_item = self.__deep_copy_item(item)
            parent_item = item.parent()
            parent_item.setExpanded(True)

            item_data = new_item.data(0, Qt.ItemDataRole.UserRole)
            source_path = Path(item_data['path'])
            parent_item_path = Path(parent_item.data(0, Qt.ItemDataRole.UserRole).get('path'))
            target_name, target_path = self.__get_unique_path(item_data['name'], parent_item_path)
            shutil.copytree(source_path, target_path) if source_path.is_dir() else shutil.copy2(source_path, target_path)
                
            item_data['name'] = target_name
            item_data['path'] = str(target_path)
            new_item.setText(0, target_name)
            new_item.setData(0, Qt.ItemDataRole.UserRole, item_data)

            index = self.__get_insert_index_by_name(parent_item, target_name, item_data['type'])        
            parent_item.insertChild(index, new_item)
            self.__hightlight_item(new_item)
            self.scrollToItem(new_item)

            self.__restore_expanded_items(new_item)
    
    def __copy_item_uuid(self):
        item_data = self.currentItem().data(0, Qt.ItemDataRole.UserRole)
        QApplication.clipboard().setText(item_data['uuid'])

    def __copy_item_path(self):
        item_data = self.currentItem().data(0, Qt.ItemDataRole.UserRole)
        QApplication.clipboard().setText(item_data['path'])

    def __copy_item_name(self):
        item_data = self.currentItem().data(0, Qt.ItemDataRole.UserRole)
        QApplication.clipboard().setText(item_data['name'])

    def __open_in_terminal(self):
        selected_items = self.selectedItems()
        target_item = selected_items[-1] if selected_items else self.__root_item
        target_item_path = Path(target_item.data(0, Qt.ItemDataRole.UserRole)['path'])
        if not target_item_path.is_dir():
            target_item_path = target_item_path.parent

        system = platform.system()
        if system == 'Windows':
            subprocess.Popen(f'start cmd /k "cd /d {target_item_path}"', shell=True)
        elif system == 'Darwin':
            subprocess.Popen(['open', '-a', 'Terminal', target_item_path])
        elif system == 'Linux':
            try:
                subprocess.Popen(['gnome-terminal', '--working-directory', target_item_path])
            except:
                QMessageBox.information(self, '提示', '不支持的操作系统')
        else:
            QMessageBox.information(self, '提示', '不支持的操作系统')

    def __open_externally(self):
        """Open with VS Code by default. If it's not installed, open with txt."""
        selected_items = self.selectedItems()
        target_item = selected_items[-1] if selected_items else self.__root_item
        target_item_path = target_item.data(0, Qt.ItemDataRole.UserRole)['path']

        # VS Code's install path should be configured in the settings. If not, open the file with txt.
        system = platform.system()
        if system == 'Windows':
            subprocess.Popen(['notepad', target_item_path])
            # subprocess.Popen(['code', target_item_path])
        elif system == 'Darwin':
            subprocess.Popen(['open', '-a', 'TextEdit', target_item_path])
            # subprocess.Popen(['open', '-a', 'Visual Studio Code', target_item_path])

        elif system == 'Linux':
            # subprocess.Popen(['code', target_item_path])
            try:
                subprocess.Popen(['gedit', target_item_path])
            except FileNotFoundError:
                subprocess.Popen(['xdg-open', target_item_path])
        else:
            QMessageBox.information(self, '提示', '不支持的操作系统')
            
    def __show_in_explorer(self):
        selected_items = self.selectedItems()
        target_item = selected_items[-1] if selected_items else self.__root_item
        target_item_path = target_item.data(0, Qt.ItemDataRole.UserRole)['path']
    
        system = platform.system()
        if system == 'Windows':
            subprocess.run(['explorer', target_item_path])
        elif system == 'Darwin':
            subprocess.run(['open', target_item_path])
        elif system == 'Linux':
            subprocess.run(["xdg-open", target_item_path])
        else:
            QMessageBox.information(self, '提示', '不支持的操作系统')

    def __find_match_items(self, search_text):
        # The children of collapsed items can not show by default during searching.
        # We have to expand all items first.
        self.blockSignals(True)
        self.expandAll()
        self.blockSignals(False)

        def match_item(item):
            item_data = item.data(0, Qt.ItemDataRole.UserRole)
            item_name = item_data['name'].lower()
            item_uuid = item_data['uuid'].lower()
            if search_text in item_name:
                index = self.indexFromItem(item)
                self.__match_items_after_search.append(index)

                # The size hint event only triggers at the creation of an item, 
                # so we need to trigger it actively to reset the size of unmatched items.
                # self.__delegate.sizeHintChanged.emit(index)

            for i in range(item.childCount()):
                match_item(item.child(i))

        match_item(self.__root_item)

    def __clear_match_items(self):
        self.__match_items_after_search = []

    def get_match_items(self):
        return self.__match_items_after_search
    
    def get_clipboard_items(self):
        return self.__clipboard_items
    
    def get_hover_item_in_drag_move(self):
        return self.__hover_item_in_drag_move
    
    def search_items(self, search_text):
        self.__search_text = search_text
        self.__clear_match_items()

        if not search_text:
            # Trigger the size hint event to update the view.
            self.__delegate.sizeHintChanged.emit(self.indexFromItem(self.__root_item))
            self.setIndentation(self.__original_indentation)
            self.setRootIsDecorated(True)
            self.__is_searching = False
            self.__restore_collapsed_items(self.__root_item)
            return
        
        self.__is_searching = True
        self.setIndentation(0)
        self.setRootIsDecorated(False)
        self.__find_match_items(search_text)

    def expand_or_collapse_all(self):
        current_item = self.currentItem()
        if not current_item:
            return
        
        if current_item.isExpanded():
            def collapse_item(item):
                item.setExpanded(False)
                item_data = item.data(0, Qt.ItemDataRole.UserRole)
                item_data['isExpanded'] = False
                for i in range(item.childCount()):
                    child_item = item.child(i)
                    collapse_item(child_item)

            collapse_item(current_item)

        else:
            def expand_item(item):
                item.setExpanded(True)
                item_data = item.data(0, Qt.ItemDataRole.UserRole)
                item_data['isExpanded'] = True
                for i in range(item.childCount()):
                    child_item = item.child(i)
                    expand_item(child_item)   

            expand_item(current_item)

    def dragEnterEvent(self, event):
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        self.__hover_item_in_drag_move = self.itemAt(event.pos())
        return super().dragMoveEvent(event)
    
    def dragLeaveEvent(self, event):
        self.__hover_item_in_drag_move = None
        return super().dragLeaveEvent(event)
    
    def dropEvent(self, event):
        self.__hover_item_in_drag_move = None

        parent_item = self.itemAt(event.pos())
        if not parent_item:
            parent_item  = self.__root_item
        elif parent_item and parent_item != self.__root_item and parent_item.data(0, Qt.ItemDataRole.UserRole)['type'] != ITEM_FOLDER:
            parent_item = parent_item.parent()
    
        parent_item_path = Path(parent_item.data(0, Qt.ItemDataRole.UserRole)['path'])
        parent_item.setExpanded(True)

        urls = event.mimeData().urls()
        if urls:
            # parent_item.setExpanded(True)

            for url in urls:
                source_path = Path(url.toLocalFile())
                _, target_path = self.__get_unique_path(source_path.name, parent_item_path)
                shutil.copytree(source_path, target_path) if source_path.is_dir() else shutil.copy2(source_path, target_path)

                item_data = self.__get_item_data_by_path(target_path)
                item_id = str(uuid.uuid4())
                item_data['uuid'] = item_id
                item_data['name'] = target_path.name
                item_data['path'] = str(target_path)

                item = QTreeWidgetItem()
                item.setText(0, target_path.name)
                item.setIcon(0, QIcon(item_data['icon']))
                item.setData(0, Qt.ItemDataRole.UserRole, item_data)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                
                index = self.__get_insert_index_by_name(parent_item, item_data['name'], item_data['type'])        
                parent_item.insertChild(index, item)
                self.__hightlight_item(item)
                self.scrollToItem(item)

                # If the folder is not empty, add a placeholder item to show the expand triangle.
                if source_path.is_dir() and any(source_path.iterdir()):
                    self.__add_placeholder(item)

        else:
            source_items = self.selectedItems()
            source_item_filtered = [item for item in source_items if item != self.__root_item and item.parent() != parent_item]
            
            if not source_item_filtered:
                event.ignore()
                return

            for item in source_item_filtered:
                new_item = self.__deep_copy_item(item)
                item_data = new_item.data(0, Qt.ItemDataRole.UserRole)
                source_path = Path(item_data['path'])
                parent_item_path = Path(parent_item.data(0, Qt.ItemDataRole.UserRole).get('path'))
                target_name, target_path = self.__get_unique_path(item_data['name'], parent_item_path)
                
                shutil.move(source_path, target_path)
                    
                item_data['name'] = target_name
                item_data['path'] = str(target_path)
                new_item.setText(0, target_name)
                new_item.setData(0, Qt.ItemDataRole.UserRole, item_data)

                index = self.__get_insert_index_by_name(parent_item, target_name, item_data['type'])        
                parent_item.insertChild(index, new_item)
                self.__hightlight_item(new_item)
                self.scrollToItem(new_item)

                self.__restore_expanded_items(new_item)

            self.__delete_items(source_item_filtered, False)
    
    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_X:
                self.__cut_items()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_C:
                self.__copy_items()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_V:
                self.__paste_items()
                event.accept()
                return
        
        elif event.key() == Qt.Key.Key_Delete:
            self.__delete_items()
            event.accept()
            return
        
        super().keyPressEvent(event)

    def wheelEvent(self, arg__1):
        self.viewport().update()
        return super().wheelEvent(arg__1)