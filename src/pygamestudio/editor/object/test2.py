from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtCore import Qt
import sys

class SingleRootTreeWidget(QTreeWidget):
    def __init__(self):
        super().__init__()
        self.root_item = None
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setSelectionMode(QTreeWidget.SingleSelection)
        
    def setRootItem(self, root_item):
        """设置唯一的根节点"""
        self.root_item = root_item
        # 根节点不可拖拽
        root_item.setFlags(root_item.flags() & ~Qt.ItemIsDragEnabled)
        self.addTopLevelItem(root_item)
        root_item.setExpanded(True)
    
    def addItem(self, text, parent=None):
        """添加项目到指定父节点，默认为根节点"""
        if parent is None:
            parent = self.root_item
        item = QTreeWidgetItem([text])
        parent.addChild(item)
        return item
    
    def dragMoveEvent(self, event):
        """控制拖拽移动事件"""
        # 如果拖拽的是根节点，拒绝拖拽
        if self.currentItem() == self.root_item:
            event.ignore()
            return
        
        # 检查是否尝试拖拽到顶层（根节点之外）
        pos = event.position().toPoint()
        target_item = self.itemAt(pos)
        
        # 如果目标位置是None（空白区域）或根节点，允许拖拽
        if target_item is None or target_item == self.root_item:
            event.accept()
        else:
            # 其他情况正常处理
            super().dragMoveEvent(event)
    
    def dropEvent(self, event):
        """处理拖放事件"""
        pos = event.position().toPoint()
        target_item = self.itemAt(pos)
        dragged_items = self.selectedItems()
        
        # 如果没有选中项目，正常处理
        if not dragged_items:
            super().dropEvent(event)
            return
            
        dragged_item = dragged_items[0]
        
        # 如果拖拽的是根节点，拒绝
        if dragged_item == self.root_item:
            event.ignore()
            return
        
        # 如果目标位置是None（空白区域）或根节点，强制放到根节点下
        if target_item is None or target_item == self.root_item:
            self._moveItemToRoot(dragged_item)
            event.accept()
        else:
            # 其他情况正常处理
            super().dropEvent(event)
    
    def _moveItemToRoot(self, item):
        """将项目移动到根节点下"""
        # 如果项目已经在根节点下，不做任何操作
        if item.parent() == self.root_item:
            return
            
        # 从原位置移除
        if item.parent():
            item.parent().removeChild(item)
        else:
            # 如果是顶层项目（除了根节点）
            index = self.indexOfTopLevelItem(item)
            if index >= 0:
                self.takeTopLevelItem(index)
        
        # 添加到根节点下
        self.root_item.addChild(item)
        self.root_item.setExpanded(True)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("单根节点树控件")
        self.setGeometry(100, 100, 600, 400)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 创建树控件
        self.tree = SingleRootTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["名称", "值"])
        
        # 设置根节点
        root_item = QTreeWidgetItem(["根节点", "root"])
        self.tree.setRootItem(root_item)
        
        # 添加一些初始数据
        self._setupInitialData()
        
        layout.addWidget(self.tree)
    
    def _setupInitialData(self):
        """设置初始数据"""
        # 添加一些子节点
        category1 = self.tree.addItem("分类1")
        category2 = self.tree.addItem("分类2")
        
        # 在分类1下添加项目
        self.tree.addItem("项目1-1", category1)
        self.tree.addItem("项目1-2", category1)
        
        # 在分类2下添加项目
        self.tree.addItem("项目2-1", category2)
        self.tree.addItem("项目2-2", category2)
        
        # 添加一些独立的项目
        self.tree.addItem("独立项目1")
        self.tree.addItem("独立项目2")
        
        # 展开所有
        self.tree.root_item.setExpanded(True)

def main():
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()