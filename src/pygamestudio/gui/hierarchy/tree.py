from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.game.object.type import *
from pygamestudio.gui.console.logger import Logger
from pygamestudio.gui.hierarchy.menu import ContextMenu
from pygamestudio.gui.hierarchy.delegate import HierarchyTreeViewDelegate
from pygamestudio.common.i18n.translator import Translator as T


class HierarchyTreeView(QTreeView):
    def __init__(self, parent, game_manager):
        super().__init__(parent)
        self._hierarchy_window = parent
        self._game_manager = game_manager

        self._standard_model = QStandardItemModel()
        self._proxy_model = QSortFilterProxyModel()
        self._delegate = HierarchyTreeViewDelegate(self, self._proxy_model, self._standard_model)

        self._is_cut = False
        self._clipboard_items = []
        self._items_to_delete_by_cut = []

        self._canvas_item = None
        self._context_menu = ContextMenu('', self)
        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_object_name()

    def _set_widget(self):
        self._standard_model.setColumnCount(1)
        self._proxy_model.setSourceModel(self._standard_model)
        self._proxy_model.setRecursiveFilteringEnabled(True)
        self._proxy_model.setFilterKeyColumn(0)
        self._proxy_model.setDynamicSortFilter(True)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.setModel(self._proxy_model)
        self.setItemDelegate(self._delegate)

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
        self.header().setStretchLastSection(False)
        self.header().setMinimumSectionSize(self.viewport().width())
        self.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def _set_signal(self):
        self.selectionModel().selectionChanged.connect(self._on_item_selection_changed)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._standard_model.itemChanged.connect(self._on_item_changed)
        self.expanded.connect(self._on_item_expanded)
        self.collapsed.connect(self._on_item_collapsed)

        self._context_menu.add_signal.connect(self._add)
        self._context_menu.cut_signal.connect(self._cut)
        self._context_menu.copy_signal.connect(self._copy)
        self._context_menu.paste_signal.connect(self._paste)
        self._context_menu.delete_signal.connect(self._delete)
        self._context_menu.rename_signal.connect(self._rename)
        self._context_menu.duplicate_signal.connect(self._duplicate)
        self._context_menu.copy_uuid_signal.connect(self._copy_uuid)
        self._context_menu.copy_path_signal.connect(self._copy_path)
        self._context_menu.copy_name_signal.connect(self._copy_name)

        self._game_manager.object_added.connect(self._on_object_added)
        self._game_manager.object_selected.connect(self._on_object_selected)
        self._game_manager.object_deselected.connect(self._on_object_deselected)
        self._game_manager.object_renamed.connect(self._on_object_renamed)
        self._game_manager.object_deleted.connect(self._on_object_deleted)
        self._game_manager.object_cut.connect(self._on_object_cut)
        self._game_manager.object_showed.connect(self._on_object_showed)
        self._game_manager.object_hidden.connect(self._on_object_hidden)

    def _set_object_name(self):
        self.setObjectName('hierarchyTreeView')

    def _on_item_selection_changed(self, selected, deselected):
        for index in selected.indexes():
            index_uuid = index.data(Qt.ItemDataRole.UserRole+1)
            self._game_manager.select(index_uuid)
 
        for index in deselected.indexes():
            index_uuid = index.data(Qt.ItemDataRole.UserRole+1)
            self._game_manager.deselect(index_uuid)

    def _on_object_selected(self, object_uuid):
        self.selectionModel().blockSignals(True)
        item = self._get_matched_item(object_uuid)
        index = self._proxy_model.mapFromSource(self._standard_model.indexFromItem(item))
        self.selectionModel().select(index, QItemSelectionModel.SelectionFlag.Select)
        self.viewport().update()
        self.selectionModel().blockSignals(False)

    def _on_object_deselected(self, object_uuid):
        self.selectionModel().blockSignals(True)
        item = self._get_matched_item(object_uuid)
        index = self._proxy_model.mapFromSource(self._standard_model.indexFromItem(item))
        self.selectionModel().select(index, QItemSelectionModel.SelectionFlag.Deselect)
        self.selectionModel().blockSignals(False)

    def _show_context_menu(self, pos):
        item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(self.indexAt(pos)))
        item_type = self._game_manager.get_object(item.data(Qt.ItemDataRole.UserRole+1)).type if item else None
        
        global_pos = self.mapToGlobal(pos)
        self._context_menu.show(global_pos, item_type)

    def _on_item_changed(self, item):
        item_uuid = item.data(Qt.ItemDataRole.UserRole+1)
        if not item_uuid:
            return

        new_name = item.text()
        self._game_manager.rename(item_uuid, new_name)

    def _on_object_renamed(self, object_uuid):
        self._standard_model.itemChanged.disconnect(self._on_item_changed)
        obj = self._game_manager.get_object(object_uuid)
        matched_item = self._get_matched_item(object_uuid)
        matched_item.setText(obj.name)
        self._standard_model.itemChanged.connect(self._on_item_changed)

    def _on_item_expanded(self, index):
        item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index))
        item_uuid = item.data(Qt.ItemDataRole.UserRole+1)
        obj = self._game_manager.get_object(item_uuid)

        if obj.is_expanded == False:
            self._game_manager.expand(item_uuid)

    def _on_item_collapsed(self, index):
        item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index))
        item_uuid = item.data(Qt.ItemDataRole.UserRole+1)
        obj = self._game_manager.get_object(item_uuid)

        if obj.is_expanded == True:
            self._game_manager.collapse(item_uuid)

    def get_ready_for_project(self):
        # No selection at start.
        self.selectionModel().clearSelection()

        # Restore the expanded / collapsed status from last time.
        self.blockSignals(True)
        self.expandAll()
        self._restore_collapsed_items()
        self.blockSignals(False)

    def clean_up(self):
        self._is_cut = False
        self._clipboard_items = []
        self._items_to_delete_by_cut = []
        self._canvas_item = None
        
        self.selectionModel().blockSignals(True)
        self._standard_model.clear()
        self.selectionModel().blockSignals(False)

    def add(self, item_type):
        return self._add(item_type)
    
    def _add(self, item_type):
        if self.selectedIndexes():
            parent_item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(self.selectedIndexes()[-1]))
        else:
            parent_item = self._canvas_item
        
        parent_uuid = parent_item.data(Qt.ItemDataRole.UserRole+1)
        self._game_manager.add(parent_uuid, item_type)
    
    def _on_object_added(self, parent_uuid, object_uuid, inserted_pos):
        obj = self._game_manager.get_object(object_uuid)

        if obj.type == OBJECT_CANVAS:
            self._on_canvas_object_added(obj)
        else:
            self._on_regular_object_added(parent_uuid, obj, inserted_pos)
        
    def _on_canvas_object_added(self, obj):
        self._canvas_item = QStandardItem()
        self._canvas_item.setText(obj.name)
        self._canvas_item.setIcon(QIcon(obj.icon))
        self._canvas_item.setData(obj.uuid, Qt.ItemDataRole.UserRole+1)
        self._canvas_item.setFlags(self._canvas_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
        self._standard_model.appendRow(self._canvas_item)

    def _on_regular_object_added(self, parent_uuid, obj, inserted_pos):
        parent_item = self._get_matched_item(parent_uuid)
        if not parent_item:
            parent_item = self._canvas_item

        item = QStandardItem()
        item.setText(obj.name)
        item.setIcon(QIcon(obj.icon))
        item.setData(obj.uuid, Qt.ItemDataRole.UserRole+1)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
    
        if inserted_pos == -1:
            parent_item.appendRow(item)
        else:
            # insertRow(inserted_pos, item) doesn't work. The inserted item disappears.
            parent_item.insertRow(inserted_pos, QStandardItem())
            parent_item.setChild(inserted_pos, item)

        index = self._proxy_model.mapFromSource(self._standard_model.indexFromItem(item))

        # Ensure that the is_selected property of objects is not changed while loading the scene file.
        # if self._game_manager.is_project_ready:
        self.setCurrentIndex(index)
        self.scrollTo(index)

    def _cut(self):
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        
        item_uuid_list = []
        for index in self.selectedIndexes():
            item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index))
            item_uuid_list.append(item.data(Qt.ItemDataRole.UserRole+1))

        self._game_manager.cut(item_uuid_list)

    def _on_object_cut(self):
        # To remove transparent effet.
        self.viewport().update()
        
    def _copy(self):
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
    
        item_uuid_list = []
        for index in self.selectedIndexes():
            item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index))
            item_uuid_list.append(item.data(Qt.ItemDataRole.UserRole+1))

        self._game_manager.copy(item_uuid_list)

    def _paste(self):
        selected_indexes = self.selectedIndexes()
        if selected_indexes:
            parent_item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(selected_indexes[-1]))
        else:
            parent_item = self._canvas_item
        
        parent_uuid = parent_item.data(Qt.ItemDataRole.UserRole+1)
        self._game_manager.paste(parent_uuid)

    def _duplicate(self):
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            return
        
        item_uuid_list = []
        for index in self.selectedIndexes():
            item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index))
            item_uuid = item.data(Qt.ItemDataRole.UserRole+1)
            item_uuid_list.append(item_uuid)
        
        self._game_manager.duplicate(item_uuid_list)
    
    def _delete(self):
        items_to_delete = []
        selected_indexes = self.selectedIndexes()
        for index in selected_indexes:
            items_to_delete.append(self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index)))
        
        if not items_to_delete or len(items_to_delete)==1 and items_to_delete[0]==self._canvas_item:
            return
    
        content = T.tr('message_box.question_delete_hierarchy_item_content', 'Delete the selected item(s)')
        reply = QMessageBox.question(self, T.tr('message_box.quesiton_title', 'Confirm'), content, QMessageBox.Yes | QMessageBox.No)
            
        if reply == QMessageBox.StandardButton.No:
            return
        
        item_uuid_list = []
        for item in items_to_delete:
            item_uuid_list.append(item.data(Qt.ItemDataRole.UserRole+1))

        self.clearSelection()
        self._game_manager.delete(item_uuid_list)
    
    def _on_object_deleted(self, object_uuid):
        matched_item = self._get_matched_item(object_uuid)
        if matched_item == self._canvas_item:
            self.selectionModel().blockSignals(True)
            self._standard_model.clear()
            self.selectionModel().blockSignals(False)
        else:
            matched_item.parent().takeRow(matched_item.row())
    
    def _rename(self):
        self.edit(self.currentIndex())

    def _on_object_showed(self):
        self.viewport().update()

    def _on_object_hidden(self):
        self.viewport().update()

    def _copy_uuid(self):
        item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(self.currentIndex()))
        item_uuid = item.data(Qt.ItemDataRole.UserRole+1)
        QApplication.clipboard().setText(item_uuid)
        Logger.info(item_uuid)

    def _copy_path(self):
        def get_path(item):
            current = item
            path = current.text()
            while current.parent():
                path = f'{current.parent().text()}/' + path
                current = current.parent()

            return path
            
        item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(self.currentIndex()))
        path = get_path(item)
        QApplication.clipboard().setText(path)
        Logger.info(path)

    def _copy_name(self):
        item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(self.currentIndex()))
        name = item.text()
        QApplication.clipboard().setText(name)
        Logger.info(name)

    def _restore_collapsed_items(self):
        def _restore(parent_item):
            item_uuid = parent_item.data(Qt.ItemDataRole.UserRole+1)
            obj = self._game_manager.get_object(item_uuid)
            if not obj.is_expanded:
                index = self._proxy_model.mapFromSource(self._standard_model.indexFromItem(parent_item))
                self.collapse(index)

            for i in range(parent_item.rowCount()):
                child_item = parent_item.child(i)
                _restore(child_item)

        _restore(self._canvas_item)

    def _search(self, keyword):
        self.blockSignals(True)

        self._proxy_model.setFilterFixedString('')
        self.expandAll()
    
        if not keyword:
            self._restore_collapsed_items()
        else:        
            self._proxy_model.setFilterFixedString(keyword)

        self.blockSignals(False)

    def search(self, keyword):
        return self._search(keyword)
    
    def get_clipboard_content(self):
        return self._game_manager.get_clipboard_content()
    
    def is_item_visible(self, item):
        return self._is_item_visible(item)

    def _is_item_visible(self, item):
        item_uuid = item.data(Qt.ItemDataRole.UserRole+1)
        obj = self._game_manager.get_object(item_uuid)
        return obj.is_visible
    
    def is_ancestor_item_visible(self, item):
        current = item.parent()
        while current:
            if not self._is_item_visible(current):
                return False
            current = current.parent()
        return True
    
    def toggle_item_visibility(self, item):
        if self._is_item_visible(item):
            self._game_manager.hide(item.data(Qt.ItemDataRole.UserRole+1))
        else:
            self._game_manager.show(item.data(Qt.ItemDataRole.UserRole+1))

        self.viewport().update()

    def expand_or_collapse_all(self):
        current_index = self.currentIndex()
        if not current_index:
            return
        
        self.blockSignals(True)
        index_uuid = current_index.data(Qt.ItemDataRole.UserRole+1)
        obj = self._game_manager.get_object(index_uuid)

        if obj.is_expanded:
            def collapse_recursively(parent_index):
                self.setExpanded(parent_index, False)
                parent_index_uuid = parent_index.data(Qt.ItemDataRole.UserRole+1)
                self._game_manager.collapse(parent_index_uuid)

                for i in range(self._standard_model.rowCount(self._proxy_model.mapToSource(parent_index))):
                    child_index = self._proxy_model.mapFromSource(self._standard_model.index(i, 0, self._proxy_model.mapToSource(parent_index)))
                    collapse_recursively(child_index)
            
            collapse_recursively(current_index)
        else:
            def expand_recursively(parent_index):
                self.setExpanded(parent_index, True)
                parent_index_uuid = parent_index.data(Qt.ItemDataRole.UserRole+1)
                self._game_manager.expand(parent_index_uuid)
    
                for i in range(self._standard_model.rowCount(self._proxy_model.mapToSource(parent_index))):
                    child_index = self._proxy_model.mapFromSource(self._standard_model.index(i, 0, self._proxy_model.mapToSource(parent_index)))
                    expand_recursively(child_index)
            
            expand_recursively(current_index)

        self.blockSignals(False)

    def _get_matched_items(self, item_uuid_list):
        def _get(item_uuid_list, parent_item):
            match_items = []
            if parent_item.data(Qt.ItemDataRole.UserRole+1) in item_uuid_list:
                match_items.append(parent_item)
            
            for i in range(parent_item.rowCount()):
                child_item = parent_item.child(i)
                match_items.extend(_get(item_uuid_list, child_item))

            return match_items
        
        return _get(item_uuid_list, self._canvas_item)
    
    def _get_matched_item(self, item_uuid):
        def _get(item_uuid, parent_item):
            if parent_item.data(Qt.ItemDataRole.UserRole+1) == item_uuid:
                return parent_item
            
            for i in range(parent_item.rowCount()):
                child_item = parent_item.child(i)
                result = _get(item_uuid, child_item)
                if result:
                    return result

            return None
        
        return _get(item_uuid, self._canvas_item)

    def drawRow(self, painter, options, index):
        super().drawRow(painter, options, index)

        item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index))
        item_uuid = item.data(Qt.ItemDataRole.UserRole+1)

        painter.save()
        if self._game_manager.is_cut() and item_uuid in self._game_manager.get_all_uuid_from_clipboard_content():
            painter.setOpacity(0.5)
        painter.restore()

    def dropEvent(self, event):
        # Rewirte the drop event. The logic is like cut and paste.
        parent_item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(self.indexAt(event.pos())))
        if not parent_item:
            parent_item  = self._canvas_item

        item_uuid_list = []
        for index in self.selectedIndexes():
            item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index))
            item_uuid_list.append(item.data(Qt.ItemDataRole.UserRole+1))

        self._game_manager.cut(item_uuid_list)

        parent_uuid = parent_item.data(Qt.ItemDataRole.UserRole+1)
        self._game_manager.paste(parent_uuid)

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_A:
                self.selectAll()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_X:
                self._cut()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_C:
                self._copy()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_V:
                self._paste()
                event.accept()
                return
        
        elif event.key() == Qt.Key.Key_Delete:
            self._delete()
            event.accept()
            return
        
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.header().setMinimumSectionSize(self.viewport().width())