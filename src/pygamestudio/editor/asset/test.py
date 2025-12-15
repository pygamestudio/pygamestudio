import os
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

class FileSystemProxyModel(QSortFilterProxyModel):
    """自定义代理模型，支持搜索时显示匹配项的所有子项"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_pattern = ""
        self.matching_items = set()
        
    def setSearchPattern(self, pattern):
        """设置搜索模式"""
        self.search_pattern = pattern.lower()
        self.matching_items.clear()
        self.invalidateFilter()
        
    def filterAcceptsRow(self, source_row, source_parent):
        """重写过滤逻辑"""
        if not self.search_pattern:
            return True
            
        source_model = self.sourceModel()
        source_index = source_model.index(source_row, 0, source_parent)
        
        # 检查当前项是否匹配
        if self.isItemMatch(source_index):
            # 当前项匹配，接受该项及其所有子项
            self.markAncestorsAsMatching(source_index)
            return True
            
        # 检查是否有子项匹配
        if self.hasMatchingChild(source_index):
            self.markAncestorsAsMatching(source_index)
            return True
            
        return False
        
    def isItemMatch(self, source_index):
        """检查项是否匹配搜索条件"""
        if not self.search_pattern:
            return False
            
        source_model = self.sourceModel()
        file_name = source_model.fileName(source_index).lower()
        
        if self.search_pattern in file_name:
            # 记录匹配项
            self.matching_items.add(source_index)
            return True
        return False
        
    def hasMatchingChild(self, source_index):
        """检查是否有子项匹配"""
        source_model = self.sourceModel()
        
        # 递归检查子项
        for row in range(source_model.rowCount(source_index)):
            child_index = source_model.index(row, 0, source_index)
            if self.isItemMatch(child_index):
                return True
            if self.hasMatchingChild(child_index):
                return True
        return False
        
    def markAncestorsAsMatching(self, source_index):
        """标记所有祖先项为匹配"""
        source_model = self.sourceModel()
        parent = source_index.parent()
        
        while parent.isValid():
            self.matching_items.add(parent)
            parent = parent.parent()

class FileExplorer(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.original_expanded_state = {}
        
    def initUI(self):
        # 创建主布局
        layout = QVBoxLayout(self)
        
        # 创建搜索框
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索文件...")
        self.search_edit.textChanged.connect(self.onSearchTextChanged)
        search_layout.addWidget(QLabel("搜索:"))
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)
        
        # 创建树视图
        self.tree_view = QTreeView()
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setSortingEnabled(True)
        
        # 创建文件系统模型
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath("")
        self.file_model.setFilter(QDir.AllEntries | QDir.NoDotAndDotDot)
        
        # 创建代理模型
        self.proxy_model = FileSystemProxyModel()
        self.proxy_model.setSourceModel(self.file_model)
        self.proxy_model.setDynamicSortFilter(True)
        
        # 设置树视图使用代理模型
        self.tree_view.setModel(self.proxy_model)
        
        # 隐藏不需要的列
        for column in range(1, self.file_model.columnCount()):
            self.tree_view.hideColumn(column)
            
        layout.addWidget(self.tree_view)
        
        # 设置窗口属性
        self.setWindowTitle("文件浏览器")
        self.setGeometry(100, 100, 800, 600)
        
        # 连接展开/折叠信号
        self.tree_view.expanded.connect(self.onItemExpanded)
        self.tree_view.collapsed.connect(self.onItemCollapsed)
        
    def onSearchTextChanged(self, text):
        """处理搜索文本变化"""
        if text:
            # 搜索时保存当前展开状态
            self.saveExpandedState()
            
            # 设置搜索模式
            self.proxy_model.setSearchPattern(text)
            
            # 搜索时自动展开所有匹配项及其祖先
            self.expandMatchingItems()
        else:
            # 搜索结束时恢复原始展开状态
            self.restoreExpandedState()
            self.proxy_model.setSearchPattern("")
            
    def saveExpandedState(self):
        """保存当前的展开状态"""
        self.original_expanded_state.clear()
        self.saveExpandedStateRecursive(QModelIndex())
        
    def saveExpandedStateRecursive(self, parent_index):
        """递归保存展开状态"""
        for row in range(self.proxy_model.rowCount(parent_index)):
            index = self.proxy_model.index(row, 0, parent_index)
            path = self.getIndexPath(index)
            
            # 保存展开状态
            if self.tree_view.isExpanded(index):
                self.original_expanded_state[path] = True
                
            # 递归处理子项
            if self.proxy_model.rowCount(index) > 0:
                self.saveExpandedStateRecursive(index)
                
    def getIndexPath(self, index):
        """获取索引的路径"""
        if not index.isValid():
            return ""
            
        source_index = self.proxy_model.mapToSource(index)
        return self.file_model.filePath(source_index)
        
    def restoreExpandedState(self):
        """恢复原始展开状态"""
        self.restoreExpandedStateRecursive(QModelIndex())
        
    def restoreExpandedStateRecursive(self, parent_index):
        """递归恢复展开状态"""
        for row in range(self.proxy_model.rowCount(parent_index)):
            index = self.proxy_model.index(row, 0, parent_index)
            path = self.getIndexPath(index)
            
            # 恢复展开状态
            if path in self.original_expanded_state:
                self.tree_view.setExpanded(index, True)
            else:
                self.tree_view.setExpanded(index, False)
                
            # 递归处理子项
            if self.proxy_model.rowCount(index) > 0:
                self.restoreExpandedStateRecursive(index)
                
    def expandMatchingItems(self):
        """展开所有匹配项及其祖先"""
        # 获取所有匹配项的索引
        matching_paths = set()
        for source_index in self.proxy_model.matching_items:
            proxy_index = self.proxy_model.mapFromSource(source_index)
            if proxy_index.isValid():
                # 展开该项及其所有祖先
                self.expandAncestors(proxy_index)
                
    def expandAncestors(self, index):
        """展开索引的所有祖先"""
        parent = index.parent()
        while parent.isValid():
            self.tree_view.expand(parent)
            parent = parent.parent()
            
    def onItemExpanded(self, index):
        """处理项展开事件"""
        # 如果需要，可以在这里添加额外的逻辑
        pass
        
    def onItemCollapsed(self, index):
        """处理项折叠事件"""
        # 如果需要，可以在这里添加额外的逻辑
        pass

def main():
    app = QApplication([])
    
    # 设置样式
    app.setStyle("Fusion")
    
    # 创建文件浏览器
    explorer = FileExplorer()
    explorer.show()
    
    app.exec()

if __name__ == "__main__":
    main()