import sys
import pygame
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                               QWidget, QTreeWidget, QTreeWidgetItem, QMenu, 
                               QInputDialog, QMessageBox, QLabel)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QAction, QPixmap, QImage, QMouseEvent

class PygameObjectManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_pygame()
        
        # 存储对象和分组
        self.objects = {}  # {id: {type, data, visible, selected}}
        self.groups = {}
        self.next_id = 1
        
        # 鼠标状态
        self.dragging = False
        self.drag_object_id = None
        self.last_mouse_pos = None
        
        # 定时器用于更新 Pygame 显示
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_pygame)
        self.timer.start(30)  # 约30fps
        
    def init_ui(self):
        self.setWindowTitle("Pygame 对象管理器")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 创建左侧的对象管理器
        self.object_tree = QTreeWidget()
        self.object_tree.setHeaderLabel("对象管理器")
        self.object_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.object_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.object_tree.itemChanged.connect(self.on_item_changed)
        self.object_tree.itemSelectionChanged.connect(self.on_selection_changed)
        
        # 创建右侧的 Pygame 显示区域
        self.pygame_widget = QWidget()
        self.pygame_widget.setMinimumSize(400, 400)
        
        # 创建 Pygame 显示标签
        self.pygame_label = QLabel()
        self.pygame_label.setAlignment(Qt.AlignCenter)
        self.pygame_label.setStyleSheet("border: 1px solid gray;")
        
        # 设置鼠标跟踪
        self.pygame_label.setMouseTracking(True)
        self.pygame_label.mousePressEvent = self.on_pygame_mouse_press
        self.pygame_label.mouseMoveEvent = self.on_pygame_mouse_move
        self.pygame_label.mouseReleaseEvent = self.on_pygame_mouse_release
        
        # 布局 Pygame 部件
        pygame_layout = QVBoxLayout(self.pygame_widget)
        pygame_layout.addWidget(QLabel("Pygame 预览 (可拖动对象)"))
        pygame_layout.addWidget(self.pygame_label)
        
        # 添加到主布局
        main_layout.addWidget(self.object_tree, 1)
        main_layout.addWidget(self.pygame_widget, 1)
        
    def init_pygame(self):
        # 初始化 Pygame
        pygame.init()
        
        # 创建 Pygame 表面
        self.pygame_surface = pygame.Surface((400, 400))
        self.pygame_surface.fill((50, 50, 50))
        
    def update_pygame(self):
        # 更新 Pygame 显示
        self.pygame_surface.fill((50, 50, 50))
        
        # 按照树形视图中的顺序绘制对象（从下到上）
        visible_objects = []
        
        # 收集所有可见对象
        def collect_objects(item):
            if item is None:
                return
                
            # 如果是分组，递归处理子项
            data = item.data(0, Qt.UserRole)
            if data and "group" in data:
                for i in range(item.childCount()):
                    collect_objects(item.child(i))
            else:
                # 如果是对象
                if data and "object" in data:
                    obj_id = int(data.split("_")[1])
                    if obj_id in self.objects and self.objects[obj_id]["visible"]:
                        visible_objects.append(obj_id)
        
        # 从树形视图底部开始收集（确保顶部对象最后绘制）
        root = self.object_tree.invisibleRootItem()
        for i in range(root.childCount()-1, -1, -1):
            collect_objects(root.child(i))
        
        # 绘制所有可见对象（按照正确的z-order）
        for obj_id in visible_objects:
            obj_data = self.objects[obj_id]
            obj_type = obj_data["type"]
            
            # 根据选择状态设置颜色
            color = obj_data["color"]
            if obj_data.get("selected", False):
                # 被选中的对象用高亮边框
                if obj_type == "矩形":
                    pygame.draw.rect(self.pygame_surface, (255, 255, 0), obj_data["rect"], 2)
                elif obj_type == "圆形":
                    pygame.draw.circle(self.pygame_surface, (255, 255, 0), 
                                      obj_data["center"], obj_data["radius"] + 2, 2)
            
            # 绘制对象本身
            if obj_type == "矩形":
                pygame.draw.rect(self.pygame_surface, color, obj_data["rect"])
            elif obj_type == "圆形":
                pygame.draw.circle(self.pygame_surface, color, 
                                  obj_data["center"], obj_data["radius"])
            elif obj_type == "文本":
                font = pygame.font.SysFont(None, 24)
                text_surface = font.render(obj_data["text"], True, color)
                self.pygame_surface.blit(text_surface, obj_data["position"])
        
        # 将 Pygame 表面转换为 Qt 图像并显示
        pygame_image = pygame.image.tostring(self.pygame_surface, 'RGB')
        qt_image = QImage(pygame_image, self.pygame_surface.get_width(), 
                         self.pygame_surface.get_height(), QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        self.pygame_label.setPixmap(pixmap)
        
    def on_pygame_mouse_press(self, event: QMouseEvent):
        # 鼠标按下事件
        mouse_pos = (event.pos().x(), event.pos().y())
        
        # 检查是否点击了对象（从顶部对象开始检查）
        clicked_object = None
        
        # 从树形视图顶部开始检查（确保点击检测顺序与绘制顺序一致）
        def check_objects(item):
            nonlocal clicked_object
            if item is None or clicked_object:
                return
                
            # 如果是分组，递归处理子项
            data = item.data(0, Qt.UserRole)
            if data and "group" in data:
                for i in range(item.childCount()-1, -1, -1):
                    check_objects(item.child(i))
            else:
                # 如果是对象
                if data and "object" in data:
                    obj_id = int(data.split("_")[1])
                    if obj_id in self.objects and self.objects[obj_id]["visible"]:
                        obj_data = self.objects[obj_id]
                        if self.is_point_in_object(mouse_pos, obj_data):
                            clicked_object = obj_id
        
        root = self.object_tree.invisibleRootItem()
        for i in range(root.childCount()-1, -1, -1):
            check_objects(root.child(i))
        
        if clicked_object:
            # 清除之前的选择
            for obj_id in self.objects:
                self.objects[obj_id]["selected"] = False
            
            # 选择点击的对象
            self.objects[clicked_object]["selected"] = True
            self.drag_object_id = clicked_object
            self.dragging = True
            self.last_mouse_pos = mouse_pos
            
            # 更新树形视图选择
            self.update_tree_selection()
        
    def on_pygame_mouse_move(self, event: QMouseEvent):
        # 鼠标移动事件
        if self.dragging and self.drag_object_id:
            current_mouse_pos = (event.pos().x(), event.pos().y())
            
            # 计算鼠标移动距离
            dx = current_mouse_pos[0] - self.last_mouse_pos[0]
            dy = current_mouse_pos[1] - self.last_mouse_pos[1]
            
            # 移动对象
            obj_data = self.objects[self.drag_object_id]
            if obj_data["type"] == "矩形":
                obj_data["rect"].x += dx
                obj_data["rect"].y += dy
            elif obj_data["type"] == "圆形":
                obj_data["center"] = (
                    obj_data["center"][0] + dx,
                    obj_data["center"][1] + dy
                )
            elif obj_data["type"] == "文本":
                obj_data["position"] = (
                    obj_data["position"][0] + dx,
                    obj_data["position"][1] + dy
                )
            
            self.last_mouse_pos = current_mouse_pos
            
    def on_pygame_mouse_release(self, event: QMouseEvent):
        # 鼠标释放事件
        self.dragging = False
        self.drag_object_id = None
        
    def is_point_in_object(self, point, obj_data):
        # 检查点是否在对象内
        obj_type = obj_data["type"]
        
        if obj_type == "矩形":
            return obj_data["rect"].collidepoint(point)
        elif obj_type == "圆形":
            center = obj_data["center"]
            radius = obj_data["radius"]
            distance = ((point[0] - center[0]) ** 2 + (point[1] - center[1]) ** 2) ** 0.5
            return distance <= radius
        elif obj_type == "文本":
            # 文本对象使用近似矩形检测
            text_rect = pygame.Rect(obj_data["position"][0], obj_data["position"][1], 
                                   len(obj_data["text"]) * 10, 20)
            return text_rect.collidepoint(point)
        
        return False
        
    def update_tree_selection(self):
        # 更新树形视图中的选择状态
        for i in range(self.object_tree.topLevelItemCount()):
            item = self.object_tree.topLevelItem(i)
            self.update_item_selection(item)
            
    def update_item_selection(self, item):
        # 更新单个项目的选择状态
        if item is None:
            return
            
        data = item.data(0, Qt.UserRole)
        if data and "object" in data:
            obj_id = int(data.split("_")[1])
            if obj_id in self.objects:
                # 更新字体粗细来显示选择状态
                font = item.font(0)
                font.setBold(self.objects[obj_id].get("selected", False))
                item.setFont(0, font)
        
        # 递归处理子项
        for i in range(item.childCount()):
            self.update_item_selection(item.child(i))
        
    def show_context_menu(self, position):
        # 获取右键点击的项目
        item = self.object_tree.itemAt(position)
        
        # 创建上下文菜单
        menu = QMenu(self)
        
        # 添加创建对象的动作
        create_rect_action = QAction("创建矩形", self)
        create_rect_action.triggered.connect(lambda: self.create_object("矩形"))
        menu.addAction(create_rect_action)
        
        create_circle_action = QAction("创建圆形", self)
        create_circle_action.triggered.connect(lambda: self.create_object("圆形"))
        menu.addAction(create_circle_action)
        
        create_text_action = QAction("创建文本", self)
        create_text_action.triggered.connect(lambda: self.create_object("文本"))
        menu.addAction(create_text_action)
        
        menu.addSeparator()
        
        # 添加创建分组的动作
        create_group_action = QAction("创建分组", self)
        create_group_action.triggered.connect(self.create_group)
        menu.addAction(create_group_action)
        
        # 如果点击了项目，添加删除和重命名选项
        if item:
            menu.addSeparator()
            
            delete_action = QAction("删除", self)
            delete_action.triggered.connect(lambda: self.delete_item(item))
            menu.addAction(delete_action)
            
            rename_action = QAction("重命名", self)
            rename_action.triggered.connect(lambda: self.rename_item(item))
            menu.addAction(rename_action)
            
            # 如果是对象，添加移动到分组的选项
            if item.data(0, Qt.UserRole) and "object" in item.data(0, Qt.UserRole):
                menu.addSeparator()
                move_to_group_action = QAction("移动到分组...", self)
                move_to_group_action.triggered.connect(lambda: self.move_to_group(item))
                menu.addAction(move_to_group_action)
                
                # 添加置顶选项
                bring_to_front_action = QAction("置顶", self)
                bring_to_front_action.triggered.connect(lambda: self.bring_to_front(item))
                menu.addAction(bring_to_front_action)
        
        # 显示菜单
        menu.exec_(self.object_tree.mapToGlobal(position))
        
    def create_object(self, obj_type):
        # 创建新对象
        obj_id = self.next_id
        self.next_id += 1
        
        # 根据对象类型设置默认属性
        if obj_type == "矩形":
            obj_data = {
                "type": obj_type,
                "rect": pygame.Rect(50, 50, 100, 80),
                "color": (255, 0, 0),
                "visible": True,
                "selected": False
            }
        elif obj_type == "圆形":
            obj_data = {
                "type": obj_type,
                "center": (150, 150),
                "radius": 50,
                "color": (0, 255, 0),
                "visible": True,
                "selected": False
            }
        elif obj_type == "文本":
            obj_data = {
                "type": obj_type,
                "text": f"文本对象 {obj_id}",
                "position": (200, 200),
                "color": (255, 255, 255),
                "visible": True,
                "selected": False
            }
        
        # 存储对象
        self.objects[obj_id] = obj_data
        
        # 在树形视图中创建项目
        item = QTreeWidgetItem([f"{obj_type} {obj_id}"])
        item.setData(0, Qt.UserRole, f"object_{obj_id}")
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(0, Qt.Checked)
        
        # 添加到树形视图顶部（新对象显示在最上面）
        self.object_tree.insertTopLevelItem(0, item)
        
    def create_group(self):
        # 创建新分组
        group_name, ok = QInputDialog.getText(self, "创建分组", "输入分组名称:")
        if ok and group_name:
            group_id = f"group_{self.next_id}"
            self.next_id += 1
            
            # 存储分组
            self.groups[group_id] = {
                "name": group_name,
                "objects": []
            }
            
            # 在树形视图中创建项目
            item = QTreeWidgetItem([group_name])
            item.setData(0, Qt.UserRole, group_id)
            
            # 添加到树形视图顶部
            self.object_tree.insertTopLevelItem(0, item)
            
    def delete_item(self, item):
        # 删除项目
        data = item.data(0, Qt.UserRole)
        
        if data and "object" in data:
            # 删除对象
            obj_id = int(data.split("_")[1])
            if obj_id in self.objects:
                del self.objects[obj_id]
        elif data and "group" in data:
            # 删除分组
            if data in self.groups:
                # 先删除分组中的所有对象
                for obj_id in self.groups[data]["objects"]:
                    if obj_id in self.objects:
                        del self.objects[obj_id]
                del self.groups[data]
        
        # 从树形视图中删除项目
        root = self.object_tree.invisibleRootItem()
        (item.parent() or root).removeChild(item)
        
    def rename_item(self, item):
        # 重命名项目
        current_name = item.text(0)
        new_name, ok = QInputDialog.getText(self, "重命名", "输入新名称:", text=current_name)
        if ok and new_name:
            item.setText(0, new_name)
            
            # 如果是分组，更新分组名称
            data = item.data(0, Qt.UserRole)
            if data and "group" in data and data in self.groups:
                self.groups[data]["name"] = new_name
                
    def move_to_group(self, item):
        # 将对象移动到分组
        obj_data = item.data(0, Qt.UserRole)
        if not obj_data or "object" not in obj_data:
            return
            
        # 获取可用分组
        group_names = [group["name"] for group in self.groups.values()]
        if not group_names:
            QMessageBox.information(self, "无分组", "没有可用的分组。请先创建分组。")
            return
            
        group_name, ok = QInputDialog.getItem(self, "移动到分组", "选择分组:", group_names, 0, False)
        if ok and group_name:
            # 找到对应的分组ID
            group_id = None
            for gid, group in self.groups.items():
                if group["name"] == group_name:
                    group_id = gid
                    break
                    
            if group_id:
                # 从当前父级移除
                parent = item.parent()
                if parent:
                    parent.removeChild(item)
                else:
                    self.object_tree.takeTopLevelItem(self.object_tree.indexOfTopLevelItem(item))
                
                # 添加到分组
                for i in range(self.object_tree.topLevelItemCount()):
                    top_item = self.object_tree.topLevelItem(i)
                    if top_item.data(0, Qt.UserRole) == group_id:
                        top_item.addChild(item)
                        # 将对象移动到分组顶部
                        top_item.removeChild(item)
                        top_item.insertChild(0, item)
                        break
                
                # 更新分组中的对象列表
                obj_id = int(obj_data.split("_")[1])
                if obj_id not in self.groups[group_id]["objects"]:
                    self.groups[group_id]["objects"].append(obj_id)
    
    def bring_to_front(self, item):
        # 将对象置顶
        data = item.data(0, Qt.UserRole)
        if not data or "object" not in data:
            return
            
        # 从当前位置移除
        parent = item.parent()
        if parent:
            parent.removeChild(item)
        else:
            self.object_tree.takeTopLevelItem(self.object_tree.indexOfTopLevelItem(item))
        
        # 添加到顶部
        if parent:
            parent.insertChild(0, item)
        else:
            self.object_tree.insertTopLevelItem(0, item)
                
    def on_item_changed(self, item, column):
        # 当项目状态改变时调用
        if column == 0:
            data = item.data(0, Qt.UserRole)
            if data and "object" in data:
                obj_id = int(data.split("_")[1])
                if obj_id in self.objects:
                    # 更新对象的可见性
                    self.objects[obj_id]["visible"] = (item.checkState(0) == Qt.Checked)
                    
    def on_selection_changed(self):
        # 当树形视图选择改变时更新对象选择状态
        selected_items = self.object_tree.selectedItems()
        
        # 清除所有选择
        for obj_id in self.objects:
            self.objects[obj_id]["selected"] = False
        
        # 设置新选择
        for item in selected_items:
            data = item.data(0, Qt.UserRole)
            if data and "object" in data:
                obj_id = int(data.split("_")[1])
                if obj_id in self.objects:
                    self.objects[obj_id]["selected"] = True

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle("Fusion")
    
    window = PygameObjectManager()
    window.show()
    
    sys.exit(app.exec())