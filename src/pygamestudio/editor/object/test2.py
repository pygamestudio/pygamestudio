import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QTreeWidget, 
                               QTreeWidgetItem, QVBoxLayout, QWidget, 
                               QMenu, QMessageBox)
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtCore import Qt

class TreeWidgetWithClipboard(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.clipboard_items = []  # 存储复制/剪切的项
        self.is_cut_operation = False  # 标记是否为剪切操作
        
        # 添加快捷键
        self.setup_shortcuts()
        
        # 启用上下文菜单
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def setup_shortcuts(self):
        # 复制快捷键 Ctrl+C
        copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        copy_shortcut.activated.connect(self.copy_items)
        
        # 剪切快捷键 Ctrl+X
        cut_shortcut = QShortcut(QKeySequence("Ctrl+X"), self)
        cut_shortcut.activated.connect(self.cut_items)
        
        # 粘贴快捷键 Ctrl+V
        paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        paste_shortcut.activated.connect(self.paste_items)
    
    def show_context_menu(self, position):
        menu = QMenu(self)
        
        copy_action = QAction("复制", self)
        copy_action.triggered.connect(self.copy_items)
        menu.addAction(copy_action)
        
        cut_action = QAction("剪切", self)
        cut_action.triggered.connect(self.cut_items)
        menu.addAction(cut_action)
        
        paste_action = QAction("粘贴", self)
        paste_action.triggered.connect(self.paste_items)
        menu.addAction(paste_action)
        
        menu.exec_(self.mapToGlobal(position))
    
    def copy_items(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return
        
        self.clipboard_items = []
        self.is_cut_operation = False
        
        for item in selected_items:
            # 深拷贝项及其所有子项
            copied_item = self.deep_copy_item(item)
            self.clipboard_items.append(copied_item)
        
        print(f"已复制 {len(self.clipboard_items)} 个项")
    
    def cut_items(self):
        selected_items = self.selectedItems()
        if not selected_items:
            return
        
        self.clipboard_items = []
        self.is_cut_operation = True
        
        for item in selected_items:
            # 深拷贝项及其所有子项
            copied_item = self.deep_copy_item(item)
            self.clipboard_items.append(copied_item)
        
        print(f"已剪切 {len(self.clipboard_items)} 个项")
    
    def paste_items(self):
        if not self.clipboard_items:
            return
        
        # 获取当前选中项作为父项，如果没有选中则添加到根节点
        current_item = self.currentItem()
        parent_item = current_item if current_item else None
        
        for item in self.clipboard_items:
            # 深拷贝剪贴板中的项
            new_item = self.deep_copy_item(item)
            
            if parent_item:
                parent_item.addChild(new_item)
            else:
                self.addTopLevelItem(new_item)
        
        # 如果是剪切操作，粘贴后清除剪贴板
        if self.is_cut_operation:
            self.clipboard_items = []
            self.is_cut_operation = False
            
            # 删除原始项（在剪切操作中）
            for item in self.selectedItems():
                if item.parent():
                    item.parent().removeChild(item)
                else:
                    self.takeTopLevelItem(self.indexOfTopLevelItem(item))
        
        print("粘贴完成")
    
    def deep_copy_item(self, item):
        """深拷贝 QTreeWidgetItem 及其所有子项"""
        # 创建新项并复制数据
        new_item = QTreeWidgetItem()
        
        # 复制所有列的数据
        for column in range(item.columnCount()):
            new_item.setText(column, item.text(column))
            new_item.setIcon(column, item.icon(column))
            # 可以添加更多属性的复制，如字体、颜色等
        
        # 递归复制所有子项
        for i in range(item.childCount()):
            child_item = item.child(i)
            new_child = self.deep_copy_item(child_item)
            new_item.addChild(new_child)
        
        return new_item

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QTreeWidget 剪切复制粘贴示例")
        self.setGeometry(100, 100, 600, 400)
        
        # 创建中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        
        # 创建树控件
        self.tree_widget = TreeWidgetWithClipboard()
        self.tree_widget.setHeaderLabels(["名称", "类型", "大小"])
        
        # 添加一些示例数据
        self.populate_tree()
        
        layout.addWidget(self.tree_widget)
    
    def populate_tree(self):
        # 添加顶级项
        for i in range(3):
            top_item = QTreeWidgetItem(self.tree_widget)
            top_item.setText(0, f"文件夹 {i+1}")
            top_item.setText(1, "文件夹")
            top_item.setText(2, "")
            
            # 添加子项
            for j in range(3):
                child_item = QTreeWidgetItem(top_item)
                child_item.setText(0, f"文件 {j+1}")
                child_item.setText(1, "文件")
                child_item.setText(2, f"{j+1} KB")
                
                # 添加孙项
                for k in range(2):
                    grandchild_item = QTreeWidgetItem(child_item)
                    grandchild_item.setText(0, f"子文件 {k+1}")
                    grandchild_item.setText(1, "文件")
                    grandchild_item.setText(2, f"{k+0.5} KB")
        
        # 展开所有项
        self.tree_widget.expandAll()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())