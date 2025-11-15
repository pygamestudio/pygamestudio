import sys
import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QTreeWidget, 
                               QTreeWidgetItem, QVBoxLayout, QWidget, 
                               QPushButton, QHBoxLayout, QFileDialog,
                               QMessageBox)
from PySide6.QtCore import Qt

class TreeWidgetManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('QTreeWidget 节点保存与恢复')
        self.setGeometry(100, 100, 800, 600)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        
        # 创建按钮布局
        button_layout = QHBoxLayout()
        
        # 创建按钮
        self.add_node_btn = QPushButton('添加节点')
        self.add_child_btn = QPushButton('添加子节点')
        self.save_btn = QPushButton('保存树结构')
        self.load_btn = QPushButton('加载树结构')
        self.clear_btn = QPushButton('清空树')
        
        button_layout.addWidget(self.add_node_btn)
        button_layout.addWidget(self.add_child_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.load_btn)
        button_layout.addWidget(self.clear_btn)
        
        # 创建树控件
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(['名称', '数据1', '数据2'])
        self.tree_widget.setColumnCount(3)
        
        # 添加到布局
        layout.addLayout(button_layout)
        layout.addWidget(self.tree_widget)
        
        # 连接信号
        self.add_node_btn.clicked.connect(self.add_root_node)
        self.add_child_btn.clicked.connect(self.add_child_node)
        self.save_btn.clicked.connect(self.save_tree)
        self.load_btn.clicked.connect(self.load_tree)
        self.clear_btn.clicked.connect(self.tree_widget.clear)
        
        # 添加一些示例数据
        self.add_sample_data()
    
    def add_sample_data(self):
        """添加示例数据"""
        root1 = QTreeWidgetItem(self.tree_widget, ['根节点1', '数据A', '数据B'])
        child1 = QTreeWidgetItem(root1, ['子节点1', '子数据A', '子数据B'])
        child2 = QTreeWidgetItem(root1, ['子节点2', '子数据C', '子数据D'])
        
        grandchild1 = QTreeWidgetItem(child1, ['孙节点1', '孙数据A', '孙数据B'])
        grandchild2 = QTreeWidgetItem(child1, ['孙节点2', '孙数据C', '孙数据D'])
        
        root2 = QTreeWidgetItem(self.tree_widget, ['根节点2', '数据E', '数据F'])
        child3 = QTreeWidgetItem(root2, ['子节点3', '子数据E', '子数据F'])
        
        # 展开所有节点
        self.tree_widget.expandAll()
    
    def add_root_node(self):
        """添加根节点"""
        item = QTreeWidgetItem(self.tree_widget, ['新根节点', '新数据1', '新数据2'])
        self.tree_widget.setCurrentItem(item)
    
    def add_child_node(self):
        """添加子节点"""
        current_item = self.tree_widget.currentItem()
        if current_item:
            item = QTreeWidgetItem(current_item, ['新子节点', '子数据1', '子数据2'])
            current_item.setExpanded(True)
            self.tree_widget.setCurrentItem(item)
        else:
            QMessageBox.warning(self, '警告', '请先选择一个节点！')
    
    def save_tree(self):
        """保存树结构到文件"""
        try:
            # 获取保存文件路径
            file_path, _ = QFileDialog.getSaveFileName(
                self, '保存树结构', '', 'JSON Files (*.json)'
            )
            
            if file_path:
                # 构建树结构数据
                tree_data = self.tree_to_dict()
                
                # 保存到文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(tree_data, f, ensure_ascii=False, indent=2)
                
                QMessageBox.information(self, '成功', '树结构保存成功！')
                
        except Exception as e:
            QMessageBox.critical(self, '错误', f'保存失败：{str(e)}')
    
    def load_tree(self):
        """从文件加载树结构"""
        try:
            # 获取加载文件路径
            file_path, _ = QFileDialog.getOpenFileName(
                self, '加载树结构', '', 'JSON Files (*.json)'
            )
            
            if file_path:
                # 从文件读取数据
                with open(file_path, 'r', encoding='utf-8') as f:
                    tree_data = json.load(f)
                
                # 清空当前树
                self.tree_widget.clear()
                
                # 重建树结构
                self.dict_to_tree(tree_data)
                
                # 展开所有节点
                self.tree_widget.expandAll()
                
                QMessageBox.information(self, '成功', '树结构加载成功！')
                
        except Exception as e:
            QMessageBox.critical(self, '错误', f'加载失败：{str(e)}')
    
    def tree_to_dict(self):
        """将QTreeWidget转换为字典结构"""
        def item_to_dict(item):
            """递归将QTreeWidgetItem转换为字典"""
            item_data = {
                'text': [item.text(i) for i in range(item.columnCount())],
                'children': []
            }
            
            # 递归处理子节点
            for i in range(item.childCount()):
                child_item = item.child(i)
                item_data['children'].append(item_to_dict(child_item))
            
            return item_data
        
        # 构建根节点数据
        root_data = []
        for i in range(self.tree_widget.topLevelItemCount()):
            top_item = self.tree_widget.topLevelItem(i)
            root_data.append(item_to_dict(top_item))
        
        return {
            'headers': [self.tree_widget.headerItem().text(i) 
                       for i in range(self.tree_widget.columnCount())],
            'data': root_data
        }
    
    def dict_to_tree(self, tree_data):
        """从字典结构重建QTreeWidget"""
        def dict_to_item(item_data, parent=None):
            """递归从字典创建QTreeWidgetItem"""
            item = QTreeWidgetItem(parent, item_data['text'])
            
            # 递归处理子节点
            for child_data in item_data['children']:
                dict_to_item(child_data, item)
            
            return item
        
        # 设置表头
        if 'headers' in tree_data:
            self.tree_widget.setHeaderLabels(tree_data['headers'])
        
        # 重建树结构
        if 'data' in tree_data:
            for root_data in tree_data['data']:
                dict_to_item(root_data, self.tree_widget)

class AdvancedTreeWidgetManager(TreeWidgetManager):
    """增强版的树控件管理器，支持更多数据类型的保存"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle('增强版 QTreeWidget 节点保存与恢复')
    
    def tree_to_dict(self):
        """增强的树结构转换，支持自定义数据"""
        def item_to_dict(item):
            """递归将QTreeWidgetItem转换为字典，包含更多信息"""
            item_data = {
                'text': [item.text(i) for i in range(item.columnCount())],
                'is_expanded': item.isExpanded(),
                'is_selected': item.isSelected(),
                'children': []
            }
            
            # 可以在这里添加更多需要保存的属性
            # 例如：字体、颜色、图标等
            
            # 递归处理子节点
            for i in range(item.childCount()):
                child_item = item.child(i)
                item_data['children'].append(item_to_dict(child_item))
            
            return item_data
        
        # 构建根节点数据
        root_data = []
        for i in range(self.tree_widget.topLevelItemCount()):
            top_item = self.tree_widget.topLevelItem(i)
            root_data.append(item_to_dict(top_item))
        
        return {
            'headers': [self.tree_widget.headerItem().text(i) 
                       for i in range(self.tree_widget.columnCount())],
            'column_count': self.tree_widget.columnCount(),
            'data': root_data,
            'metadata': {
                'version': '1.0',
                'total_nodes': self.count_total_nodes()
            }
        }
    
    def dict_to_tree(self, tree_data):
        """从字典结构重建QTreeWidget，支持更多属性"""
        def dict_to_item(item_data, parent=None):
            """递归从字典创建QTreeWidgetItem，恢复更多属性"""
            item = QTreeWidgetItem(parent, item_data['text'])
            
            # 恢复展开状态
            if item_data.get('is_expanded', False):
                item.setExpanded(True)
            
            # 恢复选中状态
            if item_data.get('is_selected', False):
                item.setSelected(True)
            
            # 递归处理子节点
            for child_data in item_data['children']:
                dict_to_item(child_data, item)
            
            return item
        
        # 设置表头
        if 'headers' in tree_data:
            self.tree_widget.setHeaderLabels(tree_data['headers'])
        
        # 设置列数
        if 'column_count' in tree_data:
            self.tree_widget.setColumnCount(tree_data['column_count'])
        
        # 重建树结构
        if 'data' in tree_data:
            for root_data in tree_data['data']:
                dict_to_item(root_data, self.tree_widget)
    
    def count_total_nodes(self):
        """计算树中的总节点数"""
        def count_children(item):
            count = 1  # 当前节点
            for i in range(item.childCount()):
                count += count_children(item.child(i))
            return count
        
        total = 0
        for i in range(self.tree_widget.topLevelItemCount()):
            total += count_children(self.tree_widget.topLevelItem(i))
        
        return total

def main():
    app = QApplication(sys.argv)
    
    # 使用基础版本
    # window = TreeWidgetManager()
    
    # 使用增强版本
    window = AdvancedTreeWidgetManager()
    
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()