import sys
import shutil
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
                               QMenu, QInputDialog, QMessageBox, QVBoxLayout,
                               QWidget, QToolBar, QLineEdit, QHBoxLayout, QPushButton)
from PySide6.QtCore import Qt, QMimeData, QUrl, QPoint, QObject, Signal
from PySide6.QtGui import QDrag, QAction

# 操作类型枚举
class OperationType:
    CREATE = "create"
    DELETE = "delete"
    MOVE = "move"
    RENAME = "rename"

# 操作记录类
class Operation:
    def __init__(self, op_type, paths, target_path=None, old_name=None, new_name=None):
        self.op_type = op_type  # 操作类型
        self.paths = paths      # 涉及的路径列表（源路径）
        self.target_path = target_path  # 目标路径（用于移动操作）
        self.old_name = old_name  # 旧名称（用于重命名）
        self.new_name = new_name  # 新名称（用于重命名）

class ResourceExplorer(QMainWindow):
    def __init__(self, initial_path=None):
        super().__init__()
        # 1
        self.setWindowTitle("高级资源管理器")
        self.setGeometry(100, 100, 1000, 700)
        
        # 初始化路径（优先使用传入的路径，否则使用当前工作目录）
        # 1
        self.initial_path = Path(initial_path) if initial_path else Path.cwd()
        if not self.initial_path.exists() or not self.initial_path.is_dir():
            self.initial_path = Path.cwd()
        
        # 撤销重做栈
        # 1
        self.undo_stack = []
        self.redo_stack = []
        
        # 设置中心部件
        # 1
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 创建路径输入区域
        # 1
        self.create_path_input_area(main_layout)
        
        # 创建工具栏
        self.create_toolbar()
        
        # 创建树状视图
        # 1
        self.tree_widget = QTreeWidget() #1
        self.tree_widget.setHeaderLabel("文件系统")#1
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)#1
        self.tree_widget.customContextMenuRequested.connect(self.show_context_menu)#1
        self.tree_widget.setSelectionMode(QTreeWidget.ExtendedSelection)#1  # 支持多选
        self.tree_widget.setDragEnabled(True)#1
        self.tree_widget.setAcceptDrops(True)#1
        self.tree_widget.setDropIndicatorShown(True)#1

        #########################
        self.tree_widget.setDragDropMode(QTreeWidget.DragDrop)
        
        # 连接展开信号，实现动态加载子目录
        # 1
        self.tree_widget.itemExpanded.connect(self.load_subdirectories)
        
        main_layout.addWidget(self.tree_widget)
        
        # 加载文件系统
        # 1
        self.load_file_system()
        
        # 更新撤销重做按钮状态
        # 1
        self.update_undo_redo_buttons()
    
    # 1
    def create_path_input_area(self, parent_layout):
        """创建路径输入区域"""
        path_layout = QHBoxLayout()
        
        self.path_edit = QLineEdit(str(self.initial_path))
        self.path_edit.setPlaceholderText("输入初始路径...")
        path_layout.addWidget(self.path_edit)
        
        self.apply_path_btn = QPushButton("应用路径")
        self.apply_path_btn.clicked.connect(self.apply_custom_path)
        path_layout.addWidget(self.apply_path_btn)
        
        parent_layout.addLayout(path_layout)
    
    # 1
    def create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar("操作")
        self.addToolBar(toolbar)
        
        # 撤销按钮
        self.undo_action = QAction("撤销", self)
        self.undo_action.triggered.connect(self.undo_last_operation)
        self.undo_action.setEnabled(False)
        toolbar.addAction(self.undo_action)
        
        # 重做按钮
        self.redo_action = QAction("重做", self)
        self.redo_action.triggered.connect(self.redo_last_operation)
        self.redo_action.setEnabled(False)
        toolbar.addAction(self.redo_action)
        
        toolbar.addSeparator()
        
        # 刷新按钮
        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self.refresh_tree)
        toolbar.addAction(refresh_action)
        
        toolbar.addSeparator()
        
        # 创建文件夹按钮
        new_folder_action = QAction("新建文件夹", self)
        new_folder_action.triggered.connect(self.create_new_folder)
        toolbar.addAction(new_folder_action)
        
        # 创建文件按钮
        new_file_action = QAction("新建文件", self)
        new_file_action.triggered.connect(self.create_new_file)
        toolbar.addAction(new_file_action)
        
        toolbar.addSeparator()
        
        # 删除按钮
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(self.delete_selected)
        toolbar.addAction(delete_action)
    
    def apply_custom_path(self):
        """应用自定义路径"""
        path_str = self.path_edit.text().strip()
        new_path = Path(path_str)
        
        if new_path.exists() and new_path.is_dir():
            self.initial_path = new_path
            self.load_file_system()
            QMessageBox.information(self, "提示", f"已切换到路径：{str(new_path)}")
        else:
            QMessageBox.warning(self, "警告", "无效的目录路径！")
    
    def load_file_system(self):
        """加载指定路径的文件系统"""
        self.tree_widget.clear()
        
        # 创建根节点（初始路径）
        root_name = self.initial_path.name if self.initial_path.name else str(self.initial_path)
        root_item = QTreeWidgetItem([root_name])
        root_item.setData(0, Qt.UserRole, str(self.initial_path))
        root_item.setFlags(root_item.flags() | Qt.ItemIsEditable)
        self.tree_widget.addTopLevelItem(root_item)
        
        # 添加占位符并展开根节点
        self.add_placeholder(root_item)
        root_item.setExpanded(True)

    # 1
    def add_placeholder(self, item):
        """添加占位符，表示有子目录"""
        placeholder = QTreeWidgetItem(["正在加载..."])
        item.addChild(placeholder)
    
    def load_subdirectories(self, item):
        """加载子目录（延迟加载，提高性能）"""
        # 清除占位符
        if item.childCount() == 1 and item.child(0).text(0) == "正在加载...":
            item.takeChild(0)
        
        path_str = item.data(0, Qt.UserRole)
        path = Path(path_str)
        
        if not path.is_dir():
            return
            
        try:
            # 遍历目录项
            for entry in path.iterdir():
                entry_path_str = str(entry)
                # 检查项目是否已存在
                exists = False
                for i in range(item.childCount()):
                    child = item.child(i)
                    if child.data(0, Qt.UserRole) == entry_path_str:
                        exists = True
                        break
                if not exists:
                    child_item = QTreeWidgetItem([entry.name])
                    child_item.setData(0, Qt.UserRole, entry_path_str)
                    child_item.setFlags(child_item.flags() | Qt.ItemIsEditable)
                    item.addChild(child_item)
                    
                    # 如果是目录，添加占位符
                    if entry.is_dir():
                        self.add_placeholder(child_item)
        except PermissionError:
            QMessageBox.warning(self, "权限不足", f"无法访问目录：{str(path)}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载目录失败：{str(e)}")
    
    def refresh_tree(self):
        """刷新树状视图"""
        self.load_file_system()
        QMessageBox.information(self, "提示", "已刷新文件系统")
    
    def show_context_menu(self, position):
        """显示右键菜单"""
        item = self.tree_widget.itemAt(position)
        if not item:
            return
        
        menu = QMenu()
        
        # 撤销/重做
        undo_action = QAction("撤销", self)
        undo_action.triggered.connect(self.undo_last_operation)
        undo_action.setEnabled(len(self.undo_stack) > 0)
        menu.addAction(undo_action)
        
        redo_action = QAction("重做", self)
        redo_action.triggered.connect(self.redo_last_operation)
        redo_action.setEnabled(len(self.redo_stack) > 0)
        menu.addAction(redo_action)
        
        menu.addSeparator()
        
        # 新建文件夹
        new_folder_action = QAction("新建文件夹", self)
        new_folder_action.triggered.connect(self.create_new_folder)
        menu.addAction(new_folder_action)
        
        # 新建文件
        new_file_action = QAction("新建文件", self)
        new_file_action.triggered.connect(self.create_new_file)
        menu.addAction(new_file_action)
        
        menu.addSeparator()
        
        # 重命名
        rename_action = QAction("重命名", self)
        rename_action.triggered.connect(lambda: self.rename_item(item))
        menu.addAction(rename_action)
        
        # 删除
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(self.delete_selected)
        menu.addAction(delete_action)
        
        menu.exec_(self.tree_widget.viewport().mapToGlobal(position))
    
    def get_parent_for_new_item(self):
        """获取用于创建新项的父目录"""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            # 如果没有选中项，使用根节点
            return self.tree_widget.topLevelItem(0)
        
        # 取第一个选中的项作为父目录
        parent_item = selected_items[0]
        parent_path = Path(parent_item.data(0, Qt.UserRole))
        
        # 检查父路径是否为目录
        if not parent_path.is_dir():
            # 如果选中的是文件，则使用其父目录
            parent_item = parent_item.parent()
        
        return parent_item if parent_item else self.tree_widget.topLevelItem(0)
    
    # 1
    def create_new_folder(self):
        """创建新文件夹"""
        parent_item = self.get_parent_for_new_item()
        parent_path = Path(parent_item.data(0, Qt.UserRole))
        
        folder_name, ok = QInputDialog.getText(self, "新建文件夹", "文件夹名称:")
        if ok and folder_name:
            new_folder_path = parent_path / folder_name
            
            try:
                new_folder_path.mkdir(exist_ok=False)  # 不允许创建已存在的文件夹
                
                # 添加到树中
                new_item = QTreeWidgetItem([folder_name])
                new_item.setData(0, Qt.UserRole, str(new_folder_path))
                new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)
                parent_item.addChild(new_item)
                self.add_placeholder(new_item)  # 添加占位符
                parent_item.setExpanded(True)
                
                # 记录操作（用于撤销）
                self.record_operation(OperationType.CREATE, [str(new_folder_path)])
                
                # 清空重做栈
                self.redo_stack.clear()
                self.update_undo_redo_buttons()
                
            except FileExistsError:
                QMessageBox.warning(self, "错误", "文件夹已存在！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法创建文件夹: {str(e)}")
    
    # 1
    def create_new_file(self):
        """创建新文件"""
        parent_item = self.get_parent_for_new_item()
        parent_path = Path(parent_item.data(0, Qt.UserRole))
        
        file_name, ok = QInputDialog.getText(self, "新建文件", "文件名称:")
        if ok and file_name:
            new_file_path = parent_path / file_name
            
            try:
                new_file_path.touch(exist_ok=False)  # 不允许创建已存在的文件
                
                # 添加到树中
                new_item = QTreeWidgetItem([file_name])
                new_item.setData(0, Qt.UserRole, str(new_file_path))
                new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)
                parent_item.addChild(new_item)
                parent_item.setExpanded(True)
                
                # 记录操作（用于撤销）
                self.record_operation(OperationType.CREATE, [str(new_file_path)])
                
                # 清空重做栈
                self.redo_stack.clear()
                self.update_undo_redo_buttons()
                
            except FileExistsError:
                QMessageBox.warning(self, "错误", "文件已存在！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法创建文件: {str(e)}")
    
    # 1
    def rename_item(self, item):
        """重命名项目"""
        old_name = item.text(0)
        old_path = Path(item.data(0, Qt.UserRole))
        parent_item = item.parent()
        
        if not parent_item:
            QMessageBox.warning(self, "警告", "根目录不能重命名")
            return
        
        parent_path = Path(parent_item.data(0, Qt.UserRole))
        
        new_name, ok = QInputDialog.getText(self, "重命名", "新名称:", text=old_name)
        if ok and new_name and new_name != old_name:
            new_path = parent_path / new_name
            
            try:
                old_path.rename(new_path)
                item.setText(0, new_name)
                item.setData(0, Qt.UserRole, str(new_path))
                
                # 记录操作（用于撤销）
                self.record_operation(OperationType.RENAME, [str(old_path)], 
                                    new_name=new_name, old_name=old_name)
                
                # 清空重做栈
                self.redo_stack.clear()
                self.update_undo_redo_buttons()
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法重命名: {str(e)}")
    
    def delete_selected(self):
        """删除选中的项目"""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "警告", "请先选择要删除的项目")
            return
        
        # 确认删除
        count = len(selected_items)
        reply = QMessageBox.question(self, "确认删除", 
                                     f"确定要删除这 {count} 个项目吗？\n删除后可以通过撤销恢复。",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            deleted_paths = []
            
            for item in selected_items:
                path = Path(item.data(0, Qt.UserRole))
                parent_item = item.parent()
                
                if not parent_item:
                    QMessageBox.warning(self, "警告", "无法删除根目录")
                    continue
                
                try:
                    # 记录路径用于撤销
                    deleted_paths.append(str(path))
                    
                    # 删除文件/目录
                    if path.is_dir():
                        # 删除目录及其内容
                        shutil.rmtree(path)
                    else:
                        # 删除文件
                        path.unlink()
                    
                    # 从树中移除
                    parent_item.removeChild(item)
                    
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"无法删除 {path}: {str(e)}")
            
            # 记录删除操作
            if deleted_paths:
                self.record_operation(OperationType.DELETE, deleted_paths)
                self.redo_stack.clear()
                self.update_undo_redo_buttons()
    
    def startDrag(self, supported_actions):
        """开始拖曳操作"""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return super().startDrag(supported_actions)
        
        mime_data = QMimeData()
        urls = []
        
        for item in selected_items:
            path = item.data(0, Qt.UserRole)
            urls.append(QUrl.fromLocalFile(path))
        
        mime_data.setUrls(urls)
        
        drag = QDrag(self.tree_widget)
        drag.setMimeData(mime_data)
        
        result = drag.exec_(supported_actions)
    
    def dragEnterEvent(self, event):
        """拖曳进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)
    
    def dropEvent(self, event):
        """拖放事件"""
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.MoveAction)
            event.accept()
            
            # 获取目标路径
            target_item = self.tree_widget.itemAt(event.position().toPoint())
            if not target_item:
                return
            
            target_path = Path(target_item.data(0, Qt.UserRole))
            
            # 确保目标是目录
            if not target_path.is_dir():
                # 如果目标是文件，使用其父目录
                target_item = target_item.parent()
                if not target_item:
                    return
                target_path = Path(target_item.data(0, Qt.UserRole))
            
            # 获取源文件/目录
            source_items = self.tree_widget.selectedItems()
            if not source_items:
                return
            
            # 记录移动操作信息
            move_info = []
            
            # 处理每个拖曳的文件/目录
            for item in source_items:
                source_path = Path(item.data(0, Qt.UserRole))
                if not source_path.exists():
                    continue
                
                # 构建目标路径
                file_name = source_path.name
                dest_path = target_path / file_name
                
                # 检查是否是同一个位置
                if source_path.resolve() == dest_path.resolve():
                    continue
                
                try:
                    # 记录原始路径和目标路径
                    move_info.append((str(source_path), str(dest_path)))
                    
                    # 移动文件/目录
                    shutil.move(str(source_path), str(dest_path))
                    
                    # 从原位置移除
                    parent_item = item.parent()
                    if parent_item:
                        parent_item.removeChild(item)
                    
                    # 添加到新位置
                    new_item = QTreeWidgetItem([file_name])
                    new_item.setData(0, Qt.UserRole, str(dest_path))
                    new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)
                    target_item.addChild(new_item)
                    
                    # 如果是目录，添加占位符
                    if dest_path.is_dir():
                        self.add_placeholder(new_item)
                    
                    target_item.setExpanded(True)
                    
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"无法移动 {source_path}: {str(e)}")
            
            # 记录移动操作
            if move_info:
                # 提取源路径列表和目标路径（所有项的目标目录相同）
                source_paths = [info[0] for info in move_info]
                self.record_operation(OperationType.MOVE, source_paths, 
                                    target_path=str(target_path))
                self.redo_stack.clear()
                self.update_undo_redo_buttons()
        else:
            super().dropEvent(event)
    
    def record_operation(self, op_type, paths, target_path=None, old_name=None, new_name=None):
        """记录操作到撤销栈"""
        operation = Operation(op_type, paths, target_path, old_name, new_name)
        self.undo_stack.append(operation)
        self.update_undo_redo_buttons()
    
    def undo_last_operation(self):
        """撤销上一个操作"""
        if not self.undo_stack:
            return
        
        operation = self.undo_stack.pop()
        self.redo_stack.append(operation)
        
        try:
            if operation.op_type == OperationType.CREATE:
                # 撤销创建：删除创建的文件/目录
                for path_str in operation.paths:
                    path = Path(path_str)
                    if path.exists():
                        if path.is_dir():
                            shutil.rmtree(path)
                        else:
                            path.unlink()
                        # 从树中移除
                        self.remove_item_from_tree(path_str)
            
            elif operation.op_type == OperationType.DELETE:
                # 撤销删除：重新创建文件/目录
                for path_str in operation.paths:
                    path = Path(path_str)
                    parent_path = path.parent
                    
                    # 确保父目录存在
                    parent_path.mkdir(parents=True, exist_ok=True)
                    
                    if path.suffix:  # 有后缀，视为文件
                        path.touch()
                    else:  # 无后缀，视为目录
                        path.mkdir(exist_ok=True)
                    
                    # 添加到树中
                    self.add_item_to_tree(str(parent_path), path.name, str(path))
            
            elif operation.op_type == OperationType.MOVE:
                # 撤销移动：移回原位置
                target_path = Path(operation.target_path)
                for source_path_str in operation.paths:
                    source_path = Path(source_path_str)
                    # 原位置路径
                    original_path = source_path.parent / source_path.name
                    # 目标位置的当前路径
                    current_path = target_path / source_path.name
                    
                    if current_path.exists():
                        # 移回原位置
                        shutil.move(str(current_path), str(original_path))
                        
                        # 从目标位置移除
                        self.remove_item_from_tree(str(current_path))
                        
                        # 添加到原位置
                        parent_item = self.find_item_by_path(str(source_path.parent))
                        if parent_item:
                            self.add_item_to_tree(str(source_path.parent), 
                                                source_path.name, 
                                                str(original_path))
            
            elif operation.op_type == OperationType.RENAME:
                # 撤销重命名：改回原来的名称
                for path_str in operation.paths:
                    # path_str 是旧路径
                    old_path = Path(path_str)
                    parent_path = old_path.parent
                    # 新路径（当前路径）
                    new_path = parent_path / operation.new_name
                    
                    if new_path.exists():
                        # 改回旧名称
                        new_path.rename(old_path)
                        
                        # 更新树中的名称
                        item = self.find_item_by_path(str(new_path))
                        if item:
                            item.setText(0, operation.old_name)
                            item.setData(0, Qt.UserRole, str(old_path))
            
            QMessageBox.information(self, "成功", "已撤销上一步操作")
            self.refresh_tree()  # 刷新树状视图
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"撤销操作失败: {str(e)}")
        
        self.update_undo_redo_buttons()
    
    def redo_last_operation(self):
        """重做上一个操作"""
        if not self.redo_stack:
            return
        
        operation = self.redo_stack.pop()
        self.undo_stack.append(operation)
        
        try:
            if operation.op_type == OperationType.CREATE:
                # 重做创建：重新创建文件/目录
                for path_str in operation.paths:
                    path = Path(path_str)
                    parent_path = path.parent
                    
                    parent_path.mkdir(parents=True, exist_ok=True)
                    
                    if path.is_dir():
                        path.mkdir(exist_ok=True)
                    else:
                        path.touch(exist_ok=True)
                    
                    self.add_item_to_tree(str(parent_path), path.name, str(path))
            
            elif operation.op_type == OperationType.DELETE:
                # 重做删除：再次删除文件/目录
                for path_str in operation.paths:
                    path = Path(path_str)
                    if path.exists():
                        if path.is_dir():
                            shutil.rmtree(path)
                        else:
                            path.unlink()
                        self.remove_item_from_tree(path_str)
            
            elif operation.op_type == OperationType.MOVE:
                # 重做移动：再次移动到目标位置
                target_path = Path(operation.target_path)
                for source_path_str in operation.paths:
                    source_path = Path(source_path_str)
                    dest_path = target_path / source_path.name
                    
                    if source_path.exists():
                        shutil.move(str(source_path), str(dest_path))
                        self.remove_item_from_tree(source_path_str)
                        self.add_item_to_tree(str(target_path), source_path.name, str(dest_path))
            
            elif operation.op_type == OperationType.RENAME:
                # 重做重命名：再次重命名
                for path_str in operation.paths:
                    old_path = Path(path_str)
                    parent_path = old_path.parent
                    new_path = parent_path / operation.new_name
                    
                    if old_path.exists():
                        old_path.rename(new_path)
                        item = self.find_item_by_path(path_str)
                        if item:
                            item.setText(0, operation.new_name)
                            item.setData(0, Qt.UserRole, str(new_path))
            
            QMessageBox.information(self, "成功", "已重做上一步操作")
            self.refresh_tree()  # 刷新树状视图
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"重做操作失败: {str(e)}")
        
        self.update_undo_redo_buttons()
    
    def find_item_by_path(self, path_str):
        """根据路径查找树节点"""
        def search_item(item):
            if item.data(0, Qt.UserRole) == path_str:
                return item
            for i in range(item.childCount()):
                child_item = search_item(item.child(i))
                if child_item:
                    return child_item
            return None
        
        # 搜索所有顶层节点
        for i in range(self.tree_widget.topLevelItemCount()):
            result = search_item(self.tree_widget.topLevelItem(i))
            if result:
                return result
        return None
    
    def add_item_to_tree(self, parent_path_str, item_name, item_path_str):
        """添加节点到树中"""
        parent_item = self.find_item_by_path(parent_path_str)
        if not parent_item:
            return
        
        # 检查是否已存在
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child.data(0, Qt.UserRole) == item_path_str:
                return
        
        new_item = QTreeWidgetItem([item_name])
        new_item.setData(0, Qt.UserRole, item_path_str)
        new_item.setFlags(new_item.flags() | Qt.ItemIsEditable)
        parent_item.addChild(new_item)
        
        # 如果是目录，添加占位符
        if Path(item_path_str).is_dir():
            self.add_placeholder(new_item)
        
        parent_item.setExpanded(True)
    
    def remove_item_from_tree(self, path_str):
        """从树中移除节点"""
        item = self.find_item_by_path(path_str)
        if item:
            parent_item = item.parent()
            if parent_item:
                parent_item.removeChild(item)
    
    def update_undo_redo_buttons(self):
        """更新撤销重做按钮状态"""
        self.undo_action.setEnabled(len(self.undo_stack) > 0)
        self.redo_action.setEnabled(len(self.redo_stack) > 0)

def main():
    app = QApplication(sys.argv)
    
    # 支持命令行参数指定初始路径
    initial_path = None
    if len(sys.argv) > 1:
        initial_path = sys.argv[1]
    
    window = ResourceExplorer(initial_path=initial_path)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()