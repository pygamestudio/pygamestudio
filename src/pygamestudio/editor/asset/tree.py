from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem, QAbstractItemView, QHeaderView, QInputDialog
from PySide6.QtCore import Qt, QTimeLine, QSize, Signal
from PySide6.QtGui import QIcon, QColor, QUndoStack

from pygamestudio.editor.asset.menu import ContextMenu
from pygamestudio.editor.asset.command import *


from pygamestudio.editor.asset.search import SEARCH_BY_NAME, SEARCH_BY_UUID
from pygamestudio.editor.asset.data import *
from pygamestudio.editor.asset.type import *
from pathlib import Path
import shutil
import uuid
import copy



class AssetTreeWidget(QTreeWidget):
    trigger_search_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.__undo_stack = QUndoStack(self)

        self.__initial_path = Path('C:/Users/louis/Desktop/demo')
        
        self.__clipboard_items = []
        self.__is_cut_action = False
        self.__items_to_delete_by_cut = []

        self.__root_item = None
        self.__context_menu = ContextMenu('', self)


        self.__set_up()
    
    def __set_up(self):
        self.__set_widget()
        self.__set_signal()
        self.__load_file_system()

    def __set_widget(self):
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setHeaderHidden(True)
        self.setMouseTracking(True)
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
        # self.__context_menu.cut_signal.connect(self.__cut_items)
        # self.__context_menu.copy_signal.connect(self.__copy_items)
        # self.__context_menu.paste_signal.connect(self.__paste_items)
        # self.__context_menu.delete_signal.connect(self.__delete_items)
        self.__context_menu.rename_signal.connect(self.__rename_item)
        # self.__context_menu.duplicate_signal.connect(self.__duplicate_items)
        # self.__context_menu.copy_uuid_signal.connect(self.__copy_item_uuid)

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
        
        # Push a rename command.
        old_name = item_data['name']
        new_name = item.text(column)
        print(old_name)
        print(new_name)
        if old_name != new_name:
            key = 'name'
            # item_data['name'] = new_text 
            self.__undo_stack.push(ModifyItemDataCommand(self, item, key, old_name, new_name, 'Renamed'))
            
            # if self.__is_searching:
            #     self.search_items(self.__search_text)
        
            # item.setData(0, Qt.ItemDataRole.UserRole, item_data)

    def __on_item_expanded(self, item):
        item_data = item.data(0, Qt.ItemDataRole.UserRole)

        # Push an expand command and update the item data.
        if item_data['isExpanded'] == False:
            key = 'isExpanded'
            description = 'Expanded item' 
            self.__undo_stack.push(ModifyItemDataCommand(self, item, key, False, True, description))
            
            self.__load_subdirectories(item)

    def __on_item_collapsed(self, item):
        item_data = item.data(0, Qt.ItemDataRole.UserRole)

        # Push a collapse command and update the item data.
        if item_data['isExpanded'] == True:
            key = 'isExpanded'
            description = 'Collapsed item'
            self.__undo_stack.push(ModifyItemDataCommand(self, item, key, True, False, description))

    def __set_root_item(self):
        item_data = copy.deepcopy(DEFAULT_FOLDER_ITEM_DATA)
        item_id = str(uuid.uuid4())
        item_data['uuid'] = item_id
        item_data['isRootItem'] = True
        item_data['name'] = self.__initial_path.name
        item_data['path'] = str(self.__initial_path)

        self.__root_item = QTreeWidgetItem()
        self.__root_item.setText(0, item_data['name'])
        self.__root_item.setIcon(0, QIcon(item_data['icon']))
        self.__root_item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        self.__root_item.setFlags(self.__root_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
        
        self.addTopLevelItem(self.__root_item)

    def __load_file_system(self):
        self.clear()
        self.__set_root_item()
        self.__add_placeholder(self.__root_item)
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

    def __load_subdirectories(self, item):
        # 要放在__on_item_expanded槽函数中

        # Remove the placeholder item.
        if item.childCount() == 1 and item.child(0).text(0) == '正在加载...':
            item.takeChild(0)

        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        folder_path = Path(item_data['path'])
        
        for entry in folder_path.iterdir():
            exists = False
            for i in range(item.childCount()):
                child = item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole).get('path') == str(entry):
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
            child_item.setData(0, Qt.ItemDataRole.UserRole, item_data)
            child_item.setFlags(child_item.flags() | Qt.ItemFlag.ItemIsEditable)
            item.addChild(child_item)

            if entry.is_dir():
                self.__add_placeholder(child_item)

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

        # # If it is druing search, search again after creating a new item.
        # if self.__is_searching:
        #     self.search_items(self.__search_text, self.__search_type)

    def __create_folder(self):
        item_data = copy.deepcopy(DEFAULT_FOLDER_ITEM_DATA)

        parent_item = self.__get_parent_for_new_item()
        parent_item_path = Path(parent_item.data(0, Qt.ItemDataRole.UserRole).get('path'))

        # Make sure the created folder name is different.
        suffix = 0
        new_folder_name = item_data['name']
        new_folder_path = parent_item_path / new_folder_name
        while new_folder_path.exists():
            suffix += 1
            new_folder_name = f"{item_data['name']}-{suffix}"
            new_folder_path = parent_item_path / new_folder_name
        
        new_folder_path.mkdir(exist_ok=False)

        item_data['name'] = new_folder_name
        item_data['uuid'] = str(uuid.uuid4())

        item = QTreeWidgetItem()
        item.setText(0, item_data['name'])
        item.setIcon(0, QIcon(item_data['icon']))
        item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

        parent_item.addChild(item)
        parent_item.setExpanded(True)
        self.scrollToItem(item)

        self.__add_placeholder(item)

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
        parent_item_path = Path(parent_item.data(0, Qt.ItemDataRole.UserRole).get('path'))

        # Make sure the created file name is different.
        suffix = 0
        new_file_name = item_data['name']
        new_file_path = parent_item_path / new_file_name
        while new_file_path.exists():
            suffix += 1
            new_file_name = f"{item_data['name']}-{suffix}"
            new_file_path = parent_item_path / new_file_name

        new_file_path.touch(exist_ok=False)

        item_data['name'] = new_file_name
        item_data['uuid'] = str(uuid.uuid4())

        item = QTreeWidgetItem()
        item.setText(0, item_data['name'])
        item.setIcon(0, QIcon(item_data['icon']))
        item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

        parent_item.addChild(item)
        parent_item.setExpanded(True)
        self.scrollToItem(item)
    
    def __rename_item(self):
        self.editItem(self.currentItem())

    def get_clipboard_items(self):
        return self.__clipboard_items
    
    
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
            elif event.key() == Qt.Key.Key_Z and self.__undo_stack.canUndo():
                self.__undo_stack.undo()
                print(self.__undo_stack.index())
                print('撤销')

        elif event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            if event.key() == Qt.Key.Key_Z and self.__undo_stack.canRedo():
                print('重做')
                self.__undo_stack.redo()
                print(self.__undo_stack.index())
        
        elif event.key() == Qt.Key.Key_Delete:
            self.__delete_items()
            event.accept()
            return
        
        super().keyPressEvent(event)