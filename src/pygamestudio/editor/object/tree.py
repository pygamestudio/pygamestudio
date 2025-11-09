from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem, QAbstractItemView, QHeaderView
from PySide6.QtCore import Qt, QTimeLine
from PySide6.QtGui import QIcon, QColor

from pygamestudio.editor.object.delegate import ObjectTreeWidgetDelegate
from pygamestudio.editor.object.menu import ContextMenu
from pygamestudio.editor.object.data import *
from pygamestudio.editor.object.type import *
import uuid
import copy


class ObjectTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__delegate = ObjectTreeWidgetDelegate(self)
        
        self.__clipboard_items = []
        self.__is_cut_action = False
        self.__items_to_delete_by_cut = []

        self.__riight_clicked_item = None
        self.__context_menu = ContextMenu('', self)
        self.__setup()

    def __setup(self):
        self.__set_widget()
        self.__set_signal()

    def __set_widget(self):
        self.setItemDelegate(self.__delegate)
        
        self.setColumnCount(2)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        
        self.setMouseTracking(True)
        self.setHeaderHidden(True)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)


    def __set_signal(self):
        self.customContextMenuRequested.connect(self.__show_context_menu)
        self.itemSelectionChanged.connect(self.__on_item_selection_changed)
        self.itemChanged.connect(self.__on_item_changed)
        self.itemExpanded.connect(self.__on_item_expanded)
        self.itemCollapsed.connect(self.__on_item_collapsed)

        self.__context_menu.create_signal.connect(self.__create_item)
        self.__context_menu.cut_signal.connect(self.__cut_items)
        self.__context_menu.copy_signal.connect(self.__copy_items)
        self.__context_menu.paste_signal.connect(self.__paste_items)
        self.__context_menu.delete_signal.connect(self.__delete_items)
        self.__context_menu.rename_signal.connect(self.__rename_item)
        self.__context_menu.copy_uuid_signal.connect(self.__copy_item_uuid)

    def __show_context_menu(self, pos):
        item = self.itemAt(pos)
        self.__riight_clicked_item = item
        global_pos = self.mapToGlobal(pos)
        is_right_click_on_item = True if item else False
        self.__context_menu.show(global_pos, is_right_click_on_item)
        
    def __on_item_changed(self, item, column):
        item_data = item.data(column, Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        # Update the name value.
        item_data['name'] = item.text(column)
        
    def __on_item_expanded(self, item):
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        item_data['isExpanded'] = item.isExpanded()
        item.setData(0, Qt.ItemDataRole.UserRole, item_data)

    def __on_item_collapsed(self, item):
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        item_data['isExpanded'] = item.isExpanded()
        item.setData(0, Qt.ItemDataRole.UserRole, item_data)

    def __on_item_selection_changed(self):
        ...

    def __create_item(self, item_type):
        if item_type == ITEM_RECT:
            item_data = self.__create_rect()
        elif item_type == ITEM_TEXT:
            item_data = self.__create_text()
        elif item_type == ITEM_CIRCLE:
            item_data = self.__create_circle()

        # Update the uuid value.
        item_id = str(uuid.uuid4())
        item_data['uuid'] = item_id

        # Set the properties of this new item.
        item = QTreeWidgetItem()
        self.__set_new_item_properties(item, item_data)
        self.__add_new_item_to_tree_widget(item)
        
    def __create_rect(self):
        item_data = copy.deepcopy(DEFAULT_RECT_ITEM_DATA)
        return item_data

    def __create_text(self):
        item_data = copy.deepcopy(DEFAULT_TEXT_ITEM_DATA)
        return item_data
    
    def __create_circle(self):
        item_data = copy.deepcopy(DEFAULT_CIRCLE_ITEM_DATA)
        return item_data

    def __cut_items(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return
        
        self.__clipboard_items = []
        self.__is_cut_action = True
        self.__items_to_delete_by_cut = selected_items
            
        for item in selected_items:
            self.__hightlight_item(item)
            copied_item = self.__deep_copy_item(item)
            self.__clipboard_items.append(copied_item)

    def __copy_items(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return
        
        self.__clipboard_items = []
        self.__is_cut_action = False
            
        for item in selected_items:
            self.__hightlight_item(item)
            copied_item = self.__deep_copy_item(item)
            self.__clipboard_items.append(copied_item)

    def __paste_items(self):
        if not self.__clipboard_items:
            return

        selected_items = self.selectedItems()
        parent_item = selected_items[0] if selected_items else None

        for item in self.__clipboard_items:
            new_item = self.__deep_copy_item(item)
            if parent_item:
                parent_item.addChild(new_item)
                parent_item.setExpanded(True)
            else:
                self.addTopLevelItem(new_item)

            self.__restore_expanded_items(new_item)
                
        if self.__is_cut_action:
            self.__clipboard_items = []
            self.__is_cut_action = False

            self.__delete_items(self.__items_to_delete_by_cut)
            self.__items_to_delete_by_cut = []

    def __deep_copy_item(self, item):
        """Copy item and its children"""
        new_item = QTreeWidgetItem()
        
        new_item.setText(0, item.text(0))
        new_item.setIcon(0, item.icon(0))
        new_item.setData(0, Qt.ItemDataRole.UserRole, item.data(0, Qt.ItemDataRole.UserRole))

        for i in range(item.childCount()):
            child_item = item.child(i)
            new_child_item = self.__deep_copy_item(child_item)
            new_item.addChild(new_child_item)
        
        return new_item

    def __delete_items(self, items=None):
        items_to_delete = items if items else self.selectedItems()
        if not items_to_delete:
            return

        # Detele the deepest items first.
        items_to_delete.sort(key=lambda x: self.__get_item_depth(x), reverse=True)
        for item in items_to_delete:
            parent = item.parent()
            if parent:
                parent.removeChild(item)
            else:
                index = self.indexOfTopLevelItem(item)
                if index >= 0:
                    self.takeTopLevelItem(index)
    
        del items_to_delete
        self.clearSelection()

    def __get_item_depth(self, item):
        depth = 0
        current = item
        while current.parent() is not None:
            depth += 1
            current = current.parent()
        return depth
    
    def __rename_item(self):
        self.editItem(self.__riight_clicked_item)

    def __copy_item_uuid(self):
        item_data = self.__riight_clicked_item.data(0, Qt.ItemDataRole.UserRole)
        QApplication.clipboard().setText(item_data['uuid'])
    
    def __set_new_item_properties(self, item, item_data):
        item.setText(0, item_data['name'])
        item.setIcon(0, QIcon(item_data['icon']))
        item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

        # Check whether the parent item is visibl or not.
        if self.__riight_clicked_item and not self.__riight_clicked_item.data(0, Qt.ItemDataRole.UserRole).get('isVisible'):
            item.setForeground(0,  QColor(150, 150, 150))

    def __add_new_item_to_tree_widget(self, item):
        # Add it as the top level item if there is no right clicked item.
        if not self.__riight_clicked_item:
            self.addTopLevelItem(item)
            return
        
        self.__riight_clicked_item.addChild(item)
        self.__riight_clicked_item.setExpanded(True)

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

    def __hightlight_item(self, item):
        """Highlight item for some actions, e.g., copy action."""
        original_fg = item.foreground(0)

        timeline = QTimeLine(1500, self)
        timeline.setFrameRange(0, 100)        
        
        def update_frame(frame):
            # progress: 0 -> 1 -> 0
            progress = frame / 100.0
            if progress > 0.5:
                value = -20
            else:
                value = 20
            
            fg_color = item.foreground(0).color()
            r = fg_color.red()
            g = fg_color.green() + value
            b = fg_color.blue() + value

            # Limit the result to [0, 255].
            # r = max(0, min(r, 255))
            g = max(0, min(g, 255))
            b = max(0, min(b, 255))

            item.setForeground(0, QColor(r, g, b, 255))
        
        def animation_finished():
            item.setForeground(0, original_fg)
            timeline.deleteLater()
        
        timeline.frameChanged.connect(update_frame)
        timeline.finished.connect(animation_finished)
        timeline.start()
    
    def __update_item_visibility_appearance(self, item, is_visible):
        if is_visible and self.is_item_ancestor_visible(item):
            item.setForeground(0, QColor(0, 0, 0))            
        else:
            item.setForeground(0, QColor(150, 150, 150))
        self.viewport().update()

    def __update_children_visibility_appearance(self, parent_item, is_visible):
        # The value of item_data['isVisible'] should not be influenced by item's parent.
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            self.__update_item_visibility_appearance(item, is_visible)
            self.__update_children_visibility_appearance(item, is_visible)

    def toggle_item_visibility(self, item):
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        item_data['isVisible'] = not item_data.get('isVisible')
        item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        
        self.__update_item_visibility_appearance(item, item_data.get('isVisible'))
        self.__update_children_visibility_appearance(item, item_data.get('isVisible'))

    def is_item_ancestor_visible(self, item):
        current = item.parent()
        while current:
            if not current.data(0, Qt.ItemDataRole.UserRole).get('isVisible'):
                return False
            current = current.parent()
        return True
    
    def get_clipboard_items(self):
        return self.__clipboard_items

    def dropEvent(self, event):
        # Must get the drag items and target item before super().dropEvent(event)
        source_items = self.selectedItems()

        target_item = self.itemAt(event.pos())
        if target_item:
            target_item.setExpanded(True)

        super().dropEvent(event)

        # Keep the expanded or collapsed state
        for item in source_items:
            self.__restore_expanded_items(item)
    
    def keyPressEvent(self, event):
        if event.modifiers() == Qt.Modifier.CTRL:
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


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    # app.setStyle("Fusion")
    
    window = ObjectTreeWidget()
    window.show()
    
    sys.exit(app.exec())