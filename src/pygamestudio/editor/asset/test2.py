import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, 
                               QVBoxLayout, QWidget, QMenu, QInputDialog, QMessageBox,
                               QToolBar, QFileDialog)
from PySide6.QtCore import Qt, QMimeData, QByteArray
from PySide6.QtGui import QAction, QIcon, QKeySequence

class FileSystemItem(QTreeWidgetItem):
    def __init__(self, name, is_folder=False, parent=None):
        super().__init__(parent)
        self.name = name
        self.is_folder = is_folder
        
        # 设置显示文本
        self.setText(0, name)
        
        # # 设置图标
        # if is_folder:
        #     self.setIcon(0, QApplication.style().standardIcon(QApplication.style().SP_DirIcon))
        # else:
        #     self.setIcon(0, QApplication.style().standardIcon(QApplication.style().SP_FileIcon))
    
    def get_full_path(self):
        """获取项目的完整路径"""
        path_parts = [self.name]
        parent = self.parent()
        while parent:
            path_parts.insert(0, parent.name)
            parent = parent.parent()
        return "/".join(path_parts)


class ResourceManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("资源管理器")
        self.setGeometry(100, 100, 800, 600)
        
        # 撤销/重做栈
        self.undo_stack = []
        self.redo_stack = []
        
        self.init_ui()
        
    def init_ui(self):
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        
        # 创建工具栏
        self.create_toolbar()
        
        # 创建树形控件
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("资源管理器")
        self.tree_widget.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree_widget.setDragEnabled(True)
        self.tree_widget.setAcceptDrops(True)
        self.tree_widget.setDropIndicatorShown(True)
        self.tree_widget.setDragDropMode(QTreeWidget.InternalMove)
        
        # 设置右键菜单
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.show_context_menu)
        
        # 连接信号
        self.tree_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        layout.addWidget(self.tree_widget)
        
        # 添加根目录
        root_item = FileSystemItem("根目录", is_folder=True)
        self.tree_widget.addTopLevelItem(root_item)
        root_item.setExpanded(True)
        
    def create_toolbar(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # 新建文件夹动作
        new_folder_action = QAction("新建文件夹", self)
        new_folder_action.triggered.connect(self.create_new_folder)
        toolbar.addAction(new_folder_action)
        
        # 新建文件动作
        new_file_action = QAction("新建文件", self)
        new_file_action.triggered.connect(self.create_new_file)
        toolbar.addAction(new_file_action)
        
        toolbar.addSeparator()
        
        # 撤销动作
        undo_action = QAction("撤销", self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self.undo)
        toolbar.addAction(undo_action)
        
        # 重做动作
        redo_action = QAction("重做", self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.triggered.connect(self.redo)
        toolbar.addAction(redo_action)
        
        toolbar.addSeparator()
        
        # 删除动作
        delete_action = QAction("删除", self)
        delete_action.setShortcut(QKeySequence.Delete)
        delete_action.triggered.connect(self.delete_selected_items)
        toolbar.addAction(delete_action)
        
    def show_context_menu(self, position):
        item = self.tree_widget.itemAt(position)
        menu = QMenu(self)
        
        new_folder_action = QAction("新建文件夹", self)
        new_folder_action.triggered.connect(self.create_new_folder)
        menu.addAction(new_folder_action)
        
        new_file_action = QAction("新建文件", self)
        new_file_action.triggered.connect(self.create_new_file)
        menu.addAction(new_file_action)
        
        if item:
            menu.addSeparator()
            delete_action = QAction("删除", self)
            delete_action.triggered.connect(self.delete_selected_items)
            menu.addAction(delete_action)
            
            rename_action = QAction("重命名", self)
            rename_action.triggered.connect(lambda: self.rename_item(item))
            menu.addAction(rename_action)
        
        menu.exec_(self.tree_widget.mapToGlobal(position))
    
    def create_new_folder(self):
        parent_item = self.tree_widget.currentItem() or self.tree_widget.topLevelItem(0)
        if not parent_item or not parent_item.is_folder:
            parent_item = self.tree_widget.topLevelItem(0)
            
        name, ok = QInputDialog.getText(self, "新建文件夹", "文件夹名称:")
        if ok and name:
            # 检查名称是否已存在
            for i in range(parent_item.childCount()):
                if parent_item.child(i).name == name:
                    QMessageBox.warning(self, "错误", f"名称 '{name}' 已存在!")
                    return
                    
            new_folder = FileSystemItem(name, is_folder=True, parent=parent_item)
            parent_item.addChild(new_folder)
            
            # 记录操作到撤销栈
            self.undo_stack.append({
                'type': 'create',
                'item': new_folder,
                'parent': parent_item,
                'name': name
            })
            # 清空重做栈
            self.redo_stack.clear()
    
    def create_new_file(self):
        parent_item = self.tree_widget.currentItem() or self.tree_widget.topLevelItem(0)
        if not parent_item or not parent_item.is_folder:
            parent_item = self.tree_widget.topLevelItem(0)
            
        name, ok = QInputDialog.getText(self, "新建文件", "文件名称:")
        if ok and name:
            # 检查名称是否已存在
            for i in range(parent_item.childCount()):
                if parent_item.child(i).name == name:
                    QMessageBox.warning(self, "错误", f"名称 '{name}' 已存在!")
                    return
                    
            new_file = FileSystemItem(name, is_folder=False, parent=parent_item)
            parent_item.addChild(new_file)
            
            # 记录操作到撤销栈
            self.undo_stack.append({
                'type': 'create',
                'item': new_file,
                'parent': parent_item,
                'name': name
            })
            # 清空重做栈
            self.redo_stack.clear()
    
    def delete_selected_items(self):
        items = self.tree_widget.selectedItems()
        if not items:
            return
            
        reply = QMessageBox.question(self, "确认删除", 
                                    f"确定要删除选中的 {len(items)} 个项目吗?",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            for item in items:
                # 记录操作到撤销栈
                self.undo_stack.append({
                    'type': 'delete',
                    'item': item,
                    'parent': item.parent() or self.tree_widget,
                    'index': item.parent().indexOfChild(item) if item.parent() else self.tree_widget.indexOfTopLevelItem(item)
                })
                
                # 从父项中移除
                if item.parent():
                    item.parent().removeChild(item)
                else:
                    self.tree_widget.takeTopLevelItem(self.tree_widget.indexOfTopLevelItem(item))
            
            # 清空重做栈
            self.redo_stack.clear()
    
    def rename_item(self, item):
        old_name = item.name
        new_name, ok = QInputDialog.getText(self, "重命名", "新名称:", text=old_name)
        if ok and new_name and new_name != old_name:
            # 检查名称是否已存在
            parent = item.parent() or self.tree_widget
            if parent:
                for i in range(parent.childCount()):
                    if parent.child(i).name == new_name and parent.child(i) != item:
                        QMessageBox.warning(self, "错误", f"名称 '{new_name}' 已存在!")
                        return
            
            item.name = new_name
            item.setText(0, new_name)
            
            # 记录操作到撤销栈
            self.undo_stack.append({
                'type': 'rename',
                'item': item,
                'old_name': old_name,
                'new_name': new_name
            })
            # 清空重做栈
            self.redo_stack.clear()
    
    def on_item_double_clicked(self, item, column):
        if item.is_folder:
            item.setExpanded(not item.isExpanded())
    
    def undo(self):
        if not self.undo_stack:
            return
            
        action = self.undo_stack.pop()
        self.redo_stack.append(action)
        
        if action['type'] == 'create':
            # 撤销创建操作 = 删除
            if action['item'].parent():
                action['item'].parent().removeChild(action['item'])
            else:
                self.tree_widget.takeTopLevelItem(self.tree_widget.indexOfTopLevelItem(action['item']))
                
        elif action['type'] == 'delete':
            # 撤销删除操作 = 恢复
            if isinstance(action['parent'], QTreeWidget):
                self.tree_widget.insertTopLevelItem(action['index'], action['item'])
            else:
                action['parent'].insertChild(action['index'], action['item'])
                
        elif action['type'] == 'rename':
            # 撤销重命名操作 = 恢复旧名称
            action['item'].name = action['old_name']
            action['item'].setText(0, action['old_name'])
    
    def redo(self):
        if not self.redo_stack:
            return
            
        action = self.redo_stack.pop()
        self.undo_stack.append(action)
        
        if action['type'] == 'create':
            # 重做创建操作 = 重新创建
            action['parent'].addChild(action['item'])
                
        elif action['type'] == 'delete':
            # 重做删除操作 = 再次删除
            if action['item'].parent():
                action['item'].parent().removeChild(action['item'])
            else:
                self.tree_widget.takeTopLevelItem(self.tree_widget.indexOfTopLevelItem(action['item']))
                
        elif action['type'] == 'rename':
            # 重做重命名操作 = 恢复新名称
            action['item'].name = action['new_name']
            action['item'].setText(0, action['new_name'])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ResourceManager()
    window.show()
    sys.exit(app.exec())