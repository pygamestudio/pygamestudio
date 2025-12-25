from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from pygamestudio.editor.object.delegate import ObjectTreeViewDelegate
from pygamestudio.editor.object.menu import ContextMenu
from pygamestudio.editor.object.command import *

from pygamestudio.editor.object.data import *
from pygamestudio.editor.object.type import *
from pygamestudio.editor.object.model import *

import uuid
import copy


class ObjectTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__undo_stack = QUndoStack(self)
        self.__standard_model = QStandardItemModel()
        self.__proxy_model = ObjectSortFilterProxyModel(self, self.__standard_model)
        self.__delegate = ObjectTreeViewDelegate(self, self.__proxy_model, self.__standard_model)

        self.__is_cut = False
        self.__highlight_items = []
        self.__clipboard_items = []
        self.__items_to_delete_by_cut = []

        self.__root_item = None
        self.__context_menu = ContextMenu('', self)
        self.__setup()

    def __setup(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_root_item()
        
        # # 测试用
        # import json
        # with open('a.json', 'r', encoding='utf-8') as f:
        #     tree_dict = json.load(f)
        #     self.dict_to_tree(tree_dict)

    def __set_widget(self):
        self.__standard_model.setColumnCount(1)
        self.__proxy_model.setSourceModel(self.__standard_model)
        self.__proxy_model.setRecursiveFilteringEnabled(True)
        self.__proxy_model.setFilterKeyColumn(0)
        self.__proxy_model.setDynamicSortFilter(True)
        self.__proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.setModel(self.__proxy_model)
        self.setItemDelegate(self.__delegate)
        
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setHeaderHidden(True)
        self.setMouseTracking(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QTreeView.DragDropMode.InternalMove)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        self.setStyleSheet("""
        QTreeView {
            border: none !important;
            outline: none !important;
            background-color: transparent;
        } 
                                              
        QTreeView::item:hover {
            background-color: #e5f3ff;
        }
                           
        QTreeView::item:selected {
            background-color: #cce8ff;
        }

        QTreeView::item:selected:active {
            background-color: #cce8ff;
            color: black;
        }

        QTreeView::item:selected:!active {
            background-color: #d9d9d9;
            color: black;
        }
        """)

    def __set_signal(self):
        self.selectionModel().selectionChanged.connect(self.__clear_highlight_items)
        self.customContextMenuRequested.connect(self.__show_context_menu)
        self.__standard_model.itemChanged.connect(self.__on_item_changed)
        self.expanded.connect(self.__on_index_expanded)
        self.collapsed.connect(self.__on_index_collapsed)

        self.__context_menu.create_signal.connect(self.__create)
        self.__context_menu.cut_signal.connect(self.__cut)
        self.__context_menu.copy_signal.connect(self.__copy)
        self.__context_menu.paste_signal.connect(self.__paste)
        self.__context_menu.delete_signal.connect(self.__delete)
        self.__context_menu.rename_signal.connect(self.__rename)
        self.__context_menu.duplicate_signal.connect(self.__duplicate)
        self.__context_menu.copy_uuid_signal.connect(self.__copy_uuid)
        self.__context_menu.copy_path_signal.connect(self.__copy_path)
        self.__context_menu.copy_name_signal.connect(self.__copy_name)

    def __set_root_item(self):
        """The root item will exist at start and forever."""
        item_data = copy.deepcopy(DEFAULT_ROOT_ITEM_DATA)
        item_id = str(uuid.uuid4())
        item_data['uuid'] = item_id

        self.__root_item = QStandardItem()
        self.__root_item.setText(item_data['name'])
        self.__root_item.setIcon(QIcon(item_data['icon']))
        self.__root_item.setData(item_data, Qt.ItemDataRole.UserRole+1)
        self.__root_item.setFlags(self.__root_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
        
        self.__standard_model.appendRow(self.__root_item)

    def __show_context_menu(self, pos):
        item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(self.indexAt(pos)))
        global_pos = self.mapToGlobal(pos)
        item_type = item.data(Qt.ItemDataRole.UserRole+1).get('type') if item else None
        self.__context_menu.show(global_pos, item_type)

    def __on_item_changed(self, item):
        item_data = item.data(Qt.ItemDataRole.UserRole+1)
        if not item_data:
            return

        # Push a rename command.
        old_name = item_data['name']
        new_name = item.text()
        if old_name != new_name:
            key = 'name'
            self.__undo_stack.push(ModifyItemDataCommand(self, self.__proxy_model, self.__standard_model, item, key, old_name, new_name, 'Renamed'))

            # # 测试用
            # if new_name== 'save':
            #     import json
            #     with open('a.json', 'w', encoding='utf-8') as f:
            #         f.write(json.dumps(self.tree_to_dict(), indent=4))

    def __on_index_expanded(self, index):
        item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(index))
        item_data = item.data(Qt.ItemDataRole.UserRole+1)

        # Push an expand command and update the item data.
        if item_data['isExpanded'] == False:
            key = 'isExpanded'
            description = 'Expanded item' 
            self.__undo_stack.push(ModifyItemDataCommand(self, self.__proxy_model, self.__standard_model, item, key, False, True, description))
            
    def __on_index_collapsed(self, index):
        item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(index))
        item_data = item.data(Qt.ItemDataRole.UserRole+1)

        # Push a collapse command and update the item data.
        if item_data['isExpanded'] == True:
            key = 'isExpanded'
            description = 'Collapsed item'
            self.__undo_stack.push(ModifyItemDataCommand(self, self.__proxy_model, self.__standard_model, item, key, True, False, description))

    def create(self, item_type):
        return self.__create(item_type)
    
    def __create(self, item_type):
        self.__highlight_items = []

        if self.selectedIndexes():
            parent_item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(self.selectedIndexes()[-1]))
        else:
            parent_item = self.__root_item

        if item_type == ITEM_RECT:
            item_data = copy.deepcopy(DEFAULT_RECT_ITEM_DATA)
        elif item_type == ITEM_TEXT:
            item_data = copy.deepcopy(DEFAULT_TEXT_ITEM_DATA)
        elif item_type == ITEM_CIRCLE:
            item_data = copy.deepcopy(DEFAULT_CIRCLE_ITEM_DATA)

        # Update the uuid value.
        item_id = str(uuid.uuid4())
        item_data['uuid'] = item_id

        # Set the properties of this new item.
        item = QStandardItem()
        self.__set_new_item_properties(item, item_data)
        self.__add_new_item_to_tree_view(parent_item, item)

        self.__highlight_items.append(item)

    def __set_new_item_properties(self, item, item_data):
        item.setText(item_data['name'])
        item.setIcon(QIcon(item_data['icon']))
        item.setData(item_data, Qt.ItemDataRole.UserRole+1)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

    def __add_new_item_to_tree_view(self, parent_item, item):
        add_item_command = AddItemCommand(self, self.__proxy_model, self.__standard_model, parent_item, item, parent_item.rowCount())
        self.__undo_stack.push(add_item_command)

    def __cut(self):
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        
        def is_to_cut(index, selected_indexes):
            current = index
            while current.parent() and current.parent() != self.rootIndex():
                if current.parent() in selected_indexes:
                    return False
                current = current.parent()
            return True
        
        self.__is_cut = True
        self.__clipboard_items = []
        self.__items_to_delete_by_cut = []
        for index in self.selectedIndexes():
            if not is_to_cut(index, selected_indexes):
                continue

            item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(index))
            if item == self.__root_item:
                continue
            
            self.__clipboard_items.append(item)
            self.__items_to_delete_by_cut.append(item)

        # To show transparent effet when keys Ctrl+X are pressed.
        self.viewport().update()
        
    def __copy(self):
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        
        def is_to_copy(index, selected_indexes):
            current = index
            while current.parent() and current.parent() != self.rootIndex():
                if current.parent() in selected_indexes:
                    return False
                current = current.parent()
            return True
        
        self.__clipboard_items = []
        self.__is_cut = False
        
        for index in self.selectedIndexes():
            if not is_to_copy(index, selected_indexes):
                continue

            item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(index))
            if item == self.__root_item:
                continue
            
            copied_item = self.__deep_copy_item(item, is_copy_child=True, is_new_uuid=True)
            self.__clipboard_items.append(copied_item)
            
        # To remove transparent effet.
        self.viewport().update()

    def __is_item1_ancestor_of_item2(self, item1, item2):
        current = item2
        while current.parent() and current.parent() != self.__root_item:
            if current.parent() == item1:
                return True
            current = current.parent()
        return False

    def __paste(self):
        if self.__is_cut:
            self.__paste_for_cut()
        else:
            self.__paste_for_copy()

    def __paste_for_cut(self):
        if not self.__clipboard_items:
            return

        self.__highlight_items = []
        selected_indexes = self.selectedIndexes()
        if selected_indexes:
            parent_item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(selected_indexes[-1]))
        else:
            parent_item = self.__root_item

        clipboard_items_filtered = []
        for item in self.__clipboard_items:
            if item != parent_item and not self.__is_item1_ancestor_of_item2(item, parent_item):
                clipboard_items_filtered.append(item)
        
        if not clipboard_items_filtered:
            return

        self.__undo_stack.beginMacro('Paste')
        composite_command = CompositeCommand('Added item')
        for item in clipboard_items_filtered:
            new_item = self.__deep_copy_item(item, is_copy_child=True, is_new_uuid=False)
            composite_command.add_command(AddItemCommand(self, self.__proxy_model, self.__standard_model, parent_item, new_item, parent_item.rowCount()))
            self.__highlight_items.append(new_item)

        self.__undo_stack.push(composite_command)

        self.__delete(self.__items_to_delete_by_cut, False)
        self.__items_to_delete_by_cut = []
        self.__clipboard_items = []
        self.__is_cut = False

        self.__undo_stack.endMacro()

    def __paste_for_copy(self):
        if not self.__clipboard_items:
            return

        self.__highlight_items = []

        selected_indexes = self.selectedIndexes()
        if selected_indexes:
            parent_item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(selected_indexes[-1]))
        else:
            parent_item = self.__root_item

        self.__undo_stack.beginMacro('Paste')
        composite_command = CompositeCommand('Added item')

        for item in self.__clipboard_items:
            new_item = self.__deep_copy_item(item, is_copy_child=True, is_new_uuid=True)
            composite_command.add_command(AddItemCommand(self, self.__proxy_model, self.__standard_model, parent_item, new_item, parent_item.rowCount()))
            self.__highlight_items.append(new_item)

        self.__undo_stack.push(composite_command)
        self.__undo_stack.endMacro()

    def __duplicate(self):
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        
        selected_items = []
        for index in self.selectedIndexes():
            item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(index))
            selected_items.append(item)
        
        composite_command = CompositeCommand('Added item')

        for item in selected_items:
            if item == self.__root_item:
                continue
            new_item = self.__deep_copy_item(item, is_copy_child=True, is_new_uuid=True)
            parent_item = item.parent()
            composite_command.add_command(AddItemCommand(self, self.__proxy_model, self.__standard_model, parent_item, new_item, parent_item.rowCount()))
            self.__highlight_items.append(new_item)

        self.__undo_stack.push(composite_command)

    def __deep_copy_item(self, item, is_copy_child=True, is_new_uuid=False):
        """Copy item and its children"""
        new_item = QStandardItem()
        
        new_item.setFlags(item.flags())
        new_item.setText(item.text())
        new_item.setIcon(item.icon())

        item_data = item.data(Qt.ItemDataRole.UserRole+1)
        if is_new_uuid:
            item_id = str(uuid.uuid4())
            item_data['uuid'] = item_id
            new_item.setData(item_data, Qt.ItemDataRole.UserRole+1)
        else:
            new_item.setData(item_data, Qt.ItemDataRole.UserRole+1)

        if is_copy_child:
            for i in range(item.rowCount()):
                child_item = item.child(i)
                new_child_item = self.__deep_copy_item(child_item, is_copy_child, is_new_uuid)
                new_item.appendRow(new_child_item)
        
        return new_item
    
    def restore_expanded_items(self, parent_item):
        return self.__restore_expanded_items(parent_item)
    
    def __restore_expanded_items(self, parent_item):
        parent_item_data = parent_item.data(Qt.ItemDataRole.UserRole+1)
        if not parent_item_data['isExpanded']:
            return
        
        QTimer.singleShot(10, lambda:self.setExpanded(self.__proxy_model.mapFromSource(self.__standard_model.indexFromItem(parent_item)), True))
                
        for i in range(parent_item.rowCount()):
            item = parent_item.child(i)
            item_data = item.data(Qt.ItemDataRole.UserRole+1)
            
            if item_data['isExpanded']:
                QTimer.singleShot(10, lambda:self.setExpanded(self.__proxy_model.mapFromSource(self.__standard_model.indexFromItem(item)), True))

                if item.rowCount() > 0:
                    self.__restore_expanded_items(item)

    def __restore_collapsed_items(self, parent_item):
        parent_item_data = parent_item.data(Qt.ItemDataRole.UserRole+1)
        if not parent_item_data['isExpanded']:
            self.setExpanded(self.__proxy_model.mapFromSource(self.__standard_model.indexFromItem(parent_item)), False)

        for i in range(parent_item.rowCount()):
            item = parent_item.child(i)
            item_data = item.data(Qt.ItemDataRole.UserRole+1)
            
            if not item_data['isExpanded']:
                self.setExpanded(self.__proxy_model.mapFromSource(self.__standard_model.indexFromItem(item)), False)

            if item.rowCount() > 0:
                self.__restore_collapsed_items(item)
    
    def __delete(self, items=None, need_to_confirm=True):
        items_to_delete = []
        if items:
            items_to_delete = items
        else:
            selected_indexes = self.selectedIndexes()
            for index in selected_indexes:
                items_to_delete.append(self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(index)))

            if not items_to_delete:
                return

        reply = QMessageBox.StandardButton.Yes
        if need_to_confirm:
            content = '是否要删除当前选中对象?'
            reply = QMessageBox.question(self, '请确认...', content, QMessageBox.Yes | QMessageBox.No)
            
        if reply == QMessageBox.StandardButton.No:
            return

        composite_command = CompositeCommand('Delete item')

        # Detele the deepest items first.
        items_to_delete.sort(key=lambda x: self.__get_item_depth(x), reverse=True)
        for item in items_to_delete:
            if item == self.__root_item:
                continue

            composite_command.add_command(DeleteItemCommand(self, self.__proxy_model, self.__standard_model, item))

        self.__undo_stack.push(composite_command)

    def __get_item_depth(self, item):
        depth = 0
        current = item
        while current.parent() is not None:
            depth += 1
            current = current.parent()
        return depth
    
    def __rename(self):
        self.edit(self.currentIndex())
        
    def __copy_uuid(self):
        item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(self.currentIndex()))
        item_data = item.data(Qt.ItemDataRole.UserRole+1)
        QApplication.clipboard().setText(item_data['uuid'])

    def __copy_path(self):
        def get_path(item):
            current = item
            path = current.text()
            while current.parent():
                path = f'{current.parent().text()}/' + path
                current = current.parent()

            return path
            
        item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(self.currentIndex()))
        path = get_path(item)
        QApplication.clipboard().setText(path)

    def __copy_name(self):
        item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(self.currentIndex()))
        QApplication.clipboard().setText(item.text())

    def __search(self, keyword):
        self.__proxy_model.setFilterFixedString('')

        self.blockSignals(True)
        self.expandAll()
        self.blockSignals(False)
    
        if not keyword:
            self.__restore_collapsed_items(self.__root_item)
            return
        
        self.__proxy_model.setFilterFixedString(keyword)

    def search(self, keyword):
        return self.__search(keyword)
    
    def get_clipboard_items(self):
        return self.__clipboard_items
    
    def is_ancestor_item_visible(self, item):
        current = item.parent()
        while current:
            if not current.data(Qt.ItemDataRole.UserRole+1).get('isVisible'):
                return False
            current = current.parent()
        return True
    
    def toggle_item_visibility_on_scene(self, item):
        item_data = item.data(Qt.ItemDataRole.UserRole+1)
        old_is_visible = item_data['isVisible']
        new_is_visible = not item_data['isVisible']

        key = 'isVisible'
        modify_item_data_command = ModifyItemDataCommand(self, self.__proxy_model, self.__standard_model, item, key, old_is_visible, new_is_visible, 'Toggled item visibility on the scene')
        self.__undo_stack.push(modify_item_data_command)

    def __clear_highlight_items(self):
        self.__highlight_items = []
        self.viewport().update()

    def expand_or_collapse_all(self):
        current_index = self.currentIndex()
        if not current_index:
            return
        
        self.blockSignals(True)

        if self.isExpanded(current_index):
            def collapse(index):
                self.setExpanded(index, False)
                item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(index))
                item_data = item.data(Qt.ItemDataRole.UserRole+1)
                item_data['isExpanded'] = False
                item.setData(item_data, Qt.ItemDataRole.UserRole+1)
    
                for i in range(item.rowCount()):
                    child_item = item.child(i)
                    child_index = self.__proxy_model.mapFromSource(self.__standard_model.indexFromItem(child_item))
                    collapse(child_index)

            collapse(current_index)

        else:
            def expand(index):
                self.setExpanded(index, True)
                item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(index))
                item_data = item.data(Qt.ItemDataRole.UserRole+1)
                item_data['isExpanded'] = True
                item.setData(item_data, Qt.ItemDataRole.UserRole+1)
    
                for i in range(item.rowCount()):
                    child_item = item.child(i)
                    child_index = self.__proxy_model.mapFromSource(self.__standard_model.indexFromItem(child_item))
                    expand(child_index)

            expand(current_index)
        
        self.blockSignals(False)

    def tree_to_dict(self):
        def item_to_dict(item):
            item_dict = {
                'data': item.data(Qt.ItemDataRole.UserRole+1),
                'children': []
            }

            for i in range(item.rowCount()):
                child_item = item.child(i)
                item_dict['children'].append(item_to_dict(child_item))
            
            return item_dict
     
        tree_dict = item_to_dict(self.__root_item)
        return tree_dict

    def dict_to_tree(self, tree_dict):
        def dict_to_item(item_dict, parent=None):
            item_data = item_dict['data']

            item = QStandardItem()
            if not parent:
                self.__root_item = item
                self.__standard_model.appendRow(self.__root_item)
                self.__root_item.setFlags(self.__root_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            else:
                parent.appendRow(item)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

            item.setText(item_data['name'])
            item.setIcon(QIcon(item_data['icon']))
            item.setData(item_data, Qt.ItemDataRole.UserRole+1)
            self.setExpanded(self.__proxy_model.mapFromSource(self.__standard_model.indexFromItem(item)), item_data['isExpanded'])
        
            for child_item_dict in item_dict['children']:
                dict_to_item(child_item_dict, item)

            return item
    
        self.blockSignals(True)
        dict_to_item(tree_dict, None)
        self.blockSignals(False)

    def drawRow(self, painter, options, index):
        item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(index))

        painter.save()
        if self.__is_cut and item in self.__clipboard_items:
            painter.setOpacity(0.5)

        if item in self.__highlight_items:
            painter.setPen(QPen(QColor(229, 243, 255, 255)))
            painter.setBrush(QColor(229, 243, 255, 255))
            painter.drawRect(options.rect)

        super().drawRow(painter, options, index)
        painter.restore()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        index = self.indexAt(event.pos())
        if not index.isValid():
            self.__clear_highlight_items()

    def dropEvent(self, event):
        # Rewirte the drop event. The logic is like cut and paste.
        parent_item = self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(self.indexAt(event.pos())))
        if not parent_item:
            parent_item  = self.__root_item

        source_items = []
        selected_indexes = self.selectedIndexes()
        for index in selected_indexes:
            source_items.append(self.__standard_model.itemFromIndex(self.__proxy_model.mapToSource(index)))
        source_item_filtered = [item for item in source_items if item != self.__root_item and item.parent() != parent_item]

        if not source_item_filtered:
            event.ignore()
            return
        
        self.__undo_stack.beginMacro('Paste')
        composite_command = CompositeCommand('Added item')

        for item in source_item_filtered:
            new_item = self.__deep_copy_item(item, is_copy_child=True, is_new_uuid=False)
            composite_command.add_command(AddItemCommand(self, self.__proxy_model, self.__standard_model, parent_item, new_item, parent_item.rowCount()))

        self.__undo_stack.push(composite_command)

        self.__delete(source_item_filtered, False)
        self.__undo_stack.endMacro()

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_X:
                self.__cut()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_C:
                self.__copy()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_V:
                self.__paste()
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