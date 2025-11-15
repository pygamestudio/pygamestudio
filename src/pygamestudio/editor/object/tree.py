from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem, QAbstractItemView, QHeaderView
from PySide6.QtCore import Qt, QTimeLine
from PySide6.QtGui import QIcon, QColor, QUndoStack

from pygamestudio.editor.object.delegate import ObjectTreeWidgetDelegate
from pygamestudio.editor.object.menu import ContextMenu
from pygamestudio.editor.object.command import *
from pygamestudio.editor.object.data import *
from pygamestudio.editor.object.type import *
import uuid
import copy


class ObjectTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 这个undo stack最终要从MainWindo中获取
        # 这样耦合性太高了
        self.__undo_stack = QUndoStack(self)
        
        self.__delegate = ObjectTreeWidgetDelegate(self)
        
        self.__clipboard_items = []
        self.__is_cut_action = False
        self.__items_to_delete_by_cut = []

        self.__root_item = None
        self.__right_clicked_item = None
        self.__context_menu = ContextMenu('', self)
        self.__setup()

    def __setup(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_root_item()

        # 测试用
        # import json
        # with open('a.json', 'r', encoding='utf-8') as f:
        #     tree_dict = json.load(f)
        #     self.dict_to_tree(tree_dict)

    def __set_widget(self):
        self.setItemDelegate(self.__delegate)
        
        self.setColumnCount(2)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        
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
        self.__context_menu.cut_signal.connect(self.__cut_items)
        self.__context_menu.copy_signal.connect(self.__copy_items)
        self.__context_menu.paste_signal.connect(self.__paste_items)
        self.__context_menu.delete_signal.connect(self.__delete_items)
        self.__context_menu.rename_signal.connect(self.__rename_item)
        self.__context_menu.copy_uuid_signal.connect(self.__copy_item_uuid)

    def __set_root_item(self):
        """The root item will exist at start and forever."""
        item_data = copy.deepcopy(DEFAULT_ROOT_ITEM_DATA)
        item_id = str(uuid.uuid4())
        item_data['uuid'] = item_id

        self.__root_item = QTreeWidgetItem()
        self.__root_item.setText(0, item_data['name'])
        self.__root_item.setIcon(0, QIcon(item_data['icon']))
        self.__root_item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        self.__root_item.setFlags(self.__root_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
        
        self.addTopLevelItem(self.__root_item)

    def __show_context_menu(self, pos):
        item = self.itemAt(pos)
        self.__right_clicked_item = item if item else self.__root_item
        global_pos = self.mapToGlobal(pos)
        
        item_type = item.data(0, Qt.ItemDataRole.UserRole).get('type') if item else None
        self.__context_menu.show(global_pos, item_type)
        
    def __on_item_changed(self, item, column):
        item_data = item.data(column, Qt.ItemDataRole.UserRole)
        if not item_data:
            return
        
        composite = CompositeCommand('Modify item data')

        # Push a rename command.
        old_text = item_data['name']
        new_text = item.text(column)
        if old_text != new_text:
            key = 'name'
            item_data['name'] = new_text 
            composite.add_command(ModifyItemDataCommand(self, item, key, old_text, new_text, 'Renamed'))
            
            # 测试用
            if item_data['name'] == 'save':
                import json
                with open('a.json', 'w', encoding='utf-8') as f:
                    f.write(json.dumps(self.tree_to_dict(), indent=4))
        
        item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        self.__undo_stack.push(composite)

    def __on_item_expanded(self, item):
        item_data = item.data(0, Qt.ItemDataRole.UserRole)

        # Push an expand command and update the item data.
        if item_data['isExpanded'] == False:
            key = 'isExpanded'
            description = 'Expanded item' 
            self.__undo_stack.push(ModifyItemDataCommand(self, item, key, False, True, description))
            
            self.__update_item_data(item, key, True)

    def __on_item_collapsed(self, item):
        item_data = item.data(0, Qt.ItemDataRole.UserRole)

        # Push a collapse command and update the item data.
        if item_data['isExpanded'] == True:
            key = 'isExpanded'
            description = 'Collapsed item'
            self.__undo_stack.push(ModifyItemDataCommand(self, item, key, True, False, description))

            self.__update_item_data(item, key, False)

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
            if item == self.__root_item:
                continue
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
            if item == self.__root_item:
                continue
            self.__hightlight_item(item)
            copied_item = self.__deep_copy_item(item)
            self.__clipboard_items.append(copied_item)

    def __paste_items(self):
        if not self.__clipboard_items:
            return

        selected_items = self.selectedItems()
        parent_item = selected_items[0] if selected_items else self.__root_item

        self.__undo_stack.beginMacro('Paste')
        composite_command = CompositeCommand('Added item')

        for item in self.__clipboard_items:
            new_item = self.__deep_copy_item(item)
            parent_item.addChild(new_item)
            parent_item.setExpanded(True)
            self.__restore_expanded_items(new_item)

            composite_command.add_command(AddItemCommand(self, parent_item, new_item, parent_item.childCount()-1))

        self.__undo_stack.push(composite_command)

        if self.__is_cut_action:
            self.__clipboard_items = []
            self.__is_cut_action = False

            self.__delete_items(self.__items_to_delete_by_cut)
            self.__items_to_delete_by_cut = []

        self.__undo_stack.endMacro()

    def __deep_copy_item(self, item):
        """Copy item and its children"""
        new_item = QTreeWidgetItem()
        
        new_item.setFlags(item.flags())
        new_item.setText(0, item.text(0))
        new_item.setIcon(0, item.icon(0))
        new_item.setForeground(0, item.foreground(0))
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

        composite_command = CompositeCommand('Delete item')

        # Detele the deepest items first.
        items_to_delete.sort(key=lambda x: self.__get_item_depth(x), reverse=True)
        for item in items_to_delete:
            if item == self.__root_item:
                continue

            composite_command.add_command(DeleteItemCommand(self, item))
            parent = item.parent()
            parent.removeChild(item)

        del items_to_delete
        self.clearSelection()
        self.__undo_stack.push(composite_command)

    def __get_item_depth(self, item):
        depth = 0
        current = item
        while current.parent() is not None:
            depth += 1
            current = current.parent()
        return depth
    
    def __rename_item(self):
        self.editItem(self.__right_clicked_item)

    def __copy_item_uuid(self):
        item_data = self.__right_clicked_item.data(0, Qt.ItemDataRole.UserRole)
        QApplication.clipboard().setText(item_data['uuid'])
    
    def __set_new_item_properties(self, item, item_data):
        item.setText(0, item_data['name'])
        item.setIcon(0, QIcon(item_data['icon']))
        item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

        # # Check whether the ancestor item is visible or not.
        # self.__right_clicked_item is itemAt(pos) or self.__root_item (see __show_context_menu())
        assert self.__right_clicked_item is not None, 'Right clicked item not found!'
        if not self.__right_clicked_item.data(0, Qt.ItemDataRole.UserRole).get('isVisible') or not self.is_ancestor_item_visible(self.__right_clicked_item):
            color = QColor(150, 150, 150)
            item.setForeground(0,  color)
            self.__update_item_data(item, 'foregroundColor', color.getRgb())

    def __add_new_item_to_tree_widget(self, item):
        parent_item = self.__right_clicked_item if self.__right_clicked_item else self.__root_item
        parent_item.addChild(item)
        parent_item.setExpanded(True)
        self.scrollToItem(item)

        add_item_command = AddItemCommand(self, parent_item, item, parent_item.childCount()-1)
        self.__undo_stack.push(add_item_command)

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
    
    def __update_item_visibility_appearance(self, item, is_visible):
        key = 'foregroundColor'
        old_color = item.foreground(0).color()

        if is_visible and self.is_ancestor_item_visible(item):
            item.setForeground(0, QColor(0, 0, 0))     
        else:
            item.setForeground(0, QColor(150, 150, 150))
        
        new_color = item.foreground(0).color()       
        if old_color.value() != new_color.value():
            self.__undo_stack.push(ModifyItemDataCommand(self, item, key, old_color, new_color, 'Modified foreground color'))
        
        self.__update_item_data(item, key, new_color.getRgb())

    def __update_children_visibility_appearance(self, parent_item):
        # The value of item_data['isVisible'] should not be influenced by item's parent.
        for i in range(parent_item.childCount()):
            item = parent_item.child(i)
            item_data = item.data(0, Qt.ItemDataRole.UserRole)
            self.__update_item_visibility_appearance(item, item_data.get('isVisible'))
            self.__update_children_visibility_appearance(item)

    def __update_item_data(self, item, key, value):
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        item_data[key] = value
        item.setData(0, Qt.ItemDataRole.UserRole, item_data)

    def toggle_item_visibility(self, item):
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        old_is_visible = item_data['isVisible']
        new_is_visible = not item_data['isVisible']

        key = 'isVisible'
        self.__undo_stack.beginMacro('Toggled item visibility')
        modify_item_data_command = ModifyItemDataCommand(self, item, key, old_is_visible, new_is_visible, 'Toggled item visibility')

        self.__update_item_data(item, key, new_is_visible)
        self.__update_item_visibility_appearance(item, new_is_visible)
        self.__update_children_visibility_appearance(item)

        self.__undo_stack.push(modify_item_data_command)
        self.__undo_stack.endMacro()

    def is_ancestor_item_visible(self, item):
        current = item.parent()
        while current:
            if not current.data(0, Qt.ItemDataRole.UserRole).get('isVisible'):
                return False
            current = current.parent()
        return True
    
    def get_clipboard_items(self):
        return self.__clipboard_items
    
    def tree_to_dict(self):
        def item_to_dict(item):
            item_dict = {
                'data': item.data(0, Qt.ItemDataRole.UserRole),
                'children': []
            }

            for i in range(item.childCount()):
                child_item = item.child(i)
                item_dict['children'].append(item_to_dict(child_item))
            
            return item_dict
     
        tree_dict = item_to_dict(self.__root_item)
        return tree_dict

    def dict_to_tree(self, tree_dict):
        def dict_to_item(item_dict, parent=None):
            item_data = item_dict['data']

            item = QTreeWidgetItem()
            if not parent:
                self.__root_item = item
                self.addTopLevelItem(item)
                self.__root_item.setFlags(self.__root_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            else:
                parent.addChild(item)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

            item.setText(0, item_data['name'])
            item.setIcon(0, QIcon(item_data['icon']))
            item.setExpanded(item_data['isExpanded'])
            item.setForeground(0, QColor(*item_data['foregroundColor']))
            item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        
            for child_item_dict in item_dict['children']:
                dict_to_item(child_item_dict, item)

            return item
    
        self.blockSignals(True)
        dict_to_item(tree_dict, None)
        self.blockSignals(False)

    def dropEvent(self, event):
        # Rewirte the drop event. The logic is like cut and paste.
        source_items = self.selectedItems()
        parent_item = self.itemAt(event.pos())
        if not parent_item:
            parent_item  = self.__root_item

        drop_items = []
        for item in source_items:
            if item == self.__root_item:
                continue
            copied_item = self.__deep_copy_item(item)
            drop_items.append(copied_item)
        
        self.__undo_stack.beginMacro('Paste')
        composite_command = CompositeCommand('Added item')

        for item in drop_items:
            new_item = self.__deep_copy_item(item)
            parent_item.addChild(new_item)
            parent_item.setExpanded(True)
            self.__restore_expanded_items(new_item)
            composite_command.add_command(AddItemCommand(self, parent_item, new_item, parent_item.childCount()-1))

        self.__undo_stack.push(composite_command)

        self.__delete_items(source_items)
        self.__undo_stack.endMacro()

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


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    # app.setStyle("Fusion")
    
    window = ObjectTreeWidget()
    window.show()
    
    sys.exit(app.exec())