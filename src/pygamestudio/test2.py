from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
import sys

# 自定义角色，用于存储不同类型的数据
class ItemRoles:
    TitleRole = Qt.UserRole + 1      # 标题
    SubtitleRole = Qt.UserRole + 2   # 副标题
    DescriptionRole = Qt.UserRole + 3 # 描述
    DateRole = Qt.UserRole + 4        # 日期
    StatusRole = Qt.UserRole + 5      # 状态
    IconPathRole = Qt.UserRole + 6    # 图标路径

class MenuButton:
    """自定义菜单按钮类，用于跟踪按钮状态"""
    def __init__(self):
        self.rect = QRect()
        self.hovered = False
        self.pressed = False
        self.visible = False

class CustomItemDelegate(QStyledItemDelegate):
    """自定义项代理，实现右下角菜单按钮"""
    
    # 自定义信号
    menuRequested = Signal(QModelIndex, QPoint)  # 菜单请求信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置边距和尺寸
        self.padding = 10
        self.icon_size = 48
        self.item_height = 80
        
        # 按钮尺寸
        self.button_size = 30
        self.button_margin = 5
        
        # 存储每个索引的按钮状态
        self.button_states = {}  # {row: MenuButton}
        
        # 启用鼠标跟踪
        if parent:
            parent.setMouseTracking(True)
    
    def get_button_for_index(self, index):
        """获取或创建索引对应的按钮状态"""
        row = index.row()
        if row not in self.button_states:
            self.button_states[row] = MenuButton()
        return self.button_states[row]
    
    def paint(self, painter, option, index):
        """绘制自定义项"""
        painter.save()
        
        # 获取按钮状态
        button = self.get_button_for_index(index)
        
        # 获取存储的数据
        title = index.data(ItemRoles.TitleRole) or "默认标题"
        subtitle = index.data(ItemRoles.SubtitleRole) or ""
        description = index.data(ItemRoles.DescriptionRole) or ""
        date = index.data(ItemRoles.DateRole) or ""
        status = index.data(ItemRoles.StatusRole) or "normal"
        icon_data = index.data(ItemRoles.IconPathRole)
        
        # 绘制背景
        if option.state & QStyle.State_Selected:
            # 选中状态
            painter.fillRect(option.rect, QColor(52, 152, 219, 100))
            painter.setPen(QPen(QColor(41, 128, 185), 2))
            painter.drawRect(option.rect.adjusted(1, 1, -2, -2))
        elif option.state & QStyle.State_MouseOver:
            # 鼠标悬停状态
            painter.fillRect(option.rect, QColor(240, 240, 240, 150))
        else:
            # 正常状态
            painter.fillRect(option.rect, Qt.white)
        
        # 绘制下划线
        painter.setPen(QColor(220, 220, 220))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        
        # 绘制图标
        if icon_data:
            if isinstance(icon_data, QIcon):
                icon = icon_data
            elif isinstance(icon_data, QPixmap):
                icon = QIcon(icon_data)
            elif isinstance(icon_data, str):
                pixmap = QPixmap(icon_data)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(self.icon_size, self.icon_size, 
                                          Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    icon = QIcon(pixmap)
                else:
                    icon = self.create_default_icon()
            else:
                icon = self.create_default_icon()
        else:
            icon = self.create_default_icon()
        
        # 计算图标区域
        icon_rect = QRect(option.rect.x() + self.padding,
                         option.rect.y() + (option.rect.height() - self.icon_size) // 2,
                         self.icon_size, self.icon_size)
        
        # 绘制图标背景
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(245, 245, 245))
        painter.drawRoundedRect(icon_rect, 8, 8)
        painter.restore()
        
        # 绘制图标
        if isinstance(icon, QIcon):
            icon.paint(painter, icon_rect, Qt.AlignCenter)
        
        # 计算文本区域（预留按钮空间）
        text_x = icon_rect.right() + self.padding
        text_width = option.rect.width() - text_x - self.padding - self.button_size - self.button_margin * 2
        text_rect = QRect(text_x, option.rect.y() + 5, text_width, option.rect.height() - 10)
        
        # 绘制标题
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        painter.setFont(title_font)
        painter.setPen(QColor(50, 50, 50))
        painter.drawText(text_rect, Qt.AlignTop, 
                        painter.fontMetrics().elidedText(title, Qt.ElideRight, text_width))
        
        # 绘制副标题
        if subtitle:
            subtitle_rect = QRect(text_x, option.rect.y() + 25, text_width, 20)
            subtitle_font = QFont()
            subtitle_font.setPointSize(10)
            painter.setFont(subtitle_font)
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(subtitle_rect, Qt.AlignTop, 
                            painter.fontMetrics().elidedText(subtitle, Qt.ElideRight, text_width))
        
        # 绘制描述
        if description:
            desc_rect = QRect(text_x, option.rect.y() + 45, text_width, 20)
            desc_font = QFont()
            desc_font.setPointSize(9)
            painter.setFont(desc_font)
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(desc_rect, Qt.AlignTop, 
                            painter.fontMetrics().elidedText(description, Qt.ElideRight, text_width))
        
        # 计算按钮区域（右下角）
        button_x = option.rect.right() - self.button_size - self.button_margin
        button_y = option.rect.bottom() - self.button_size - self.button_margin
        button_rect = QRect(button_x, button_y, self.button_size, self.button_size)
        
        # 更新按钮矩形
        button.rect = button_rect
        
        # 检查鼠标是否在项区域内，决定按钮是否可见
        if option.state & QStyle.State_MouseOver:
            button.visible = True
        else:
            button.visible = False
        
        # 绘制按钮（如果可见）
        if button.visible:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 根据按钮状态设置颜色
            if button.pressed:
                # 按下状态
                painter.setBrush(QColor(200, 200, 200))
                painter.setPen(QPen(QColor(100, 100, 100), 1))
            elif button.hovered:
                # 悬停状态
                painter.setBrush(QColor(230, 230, 230))
                painter.setPen(QPen(QColor(150, 150, 150), 1))
            else:
                # 正常状态
                painter.setBrush(QColor(245, 245, 245))
                painter.setPen(QPen(QColor(200, 200, 200), 1))
            
            # 绘制按钮背景（圆角矩形）
            painter.drawRoundedRect(button_rect, 5, 5)
            
            # 绘制三个点的文本
            painter.setPen(QColor(80, 80, 80))
            font = QFont()
            font.setPointSize(16)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(button_rect, Qt.AlignCenter, "⋮")
            
            painter.restore()
        
        painter.restore()
    
    def create_default_icon(self):
        """创建默认图标"""
        pixmap = QPixmap(self.icon_size, self.icon_size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(200, 200, 200))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(5, 5, self.icon_size - 10, self.icon_size - 10)
        painter.end()
        return QIcon(pixmap)
    
    def sizeHint(self, option, index):
        """返回项的大小提示"""
        return QSize(400, self.item_height)
    
    def editorEvent(self, event, model, option, index):
        """处理鼠标事件"""
        button = self.get_button_for_index(index)
        
        if event.type() == QEvent.MouseMove:
            # 处理鼠标移动
            pos = event.pos()
            
            # 检查是否在按钮上
            was_hovered = button.hovered
            button.hovered = button.rect.contains(pos)
            
            # 如果悬停状态改变，需要重绘
            if was_hovered != button.hovered:
                # 触发重绘
                self.parent().update(index)
            
            # 继续传递事件
            return super().editorEvent(event, model, option, index)
        
        elif event.type() == QEvent.MouseButtonPress:
            # 处理鼠标按下
            if event.button() == Qt.LeftButton:
                pos = event.pos()
                if button.rect.contains(pos):
                    button.pressed = True
                    self.parent().update(index)
                    return True  # 事件已处理
        
        elif event.type() == QEvent.MouseButtonRelease:
            # 处理鼠标释放
            if event.button() == Qt.LeftButton:
                pos = event.pos()
                if button.pressed and button.rect.contains(pos):
                    # 按钮被点击，发送菜单请求信号
                    button.pressed = False
                    global_pos = self.parent().viewport().mapToGlobal(button.rect.bottomRight())
                    self.menuRequested.emit(index, global_pos)
                    self.parent().update(index)
                    return True
                else:
                    button.pressed = False
                    self.parent().update(index)
        
        elif event.type() == QEvent.Leave:
            # 鼠标离开项
            button.hovered = False
            button.pressed = False
            self.parent().update(index)
        
        return super().editorEvent(event, model, option, index)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Delegate with Menu Button")
        self.setGeometry(100, 100, 600, 500)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        
        # 创建列表视图
        self.list_view = QListView()
        self.list_view.setSpacing(5)  # 设置项之间的间距
        self.list_view.setMouseTracking(True)  # 启用鼠标跟踪
        
        # 设置自定义代理
        self.delegate = CustomItemDelegate(self.list_view)
        self.list_view.setItemDelegate(self.delegate)
        
        # 连接菜单请求信号
        self.delegate.menuRequested.connect(self.show_context_menu)
        
        # 创建模型
        self.model = QStandardItemModel()
        self.list_view.setModel(self.model)
        
        # 添加数据
        self.populate_data()
        
        # 添加控制按钮
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加项目")
        add_btn.clicked.connect(self.add_item)
        clear_btn = QPushButton("清空列表")
        clear_btn.clicked.connect(self.clear_items)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        layout.addWidget(self.list_view)
    
    def populate_data(self):
        """填充初始数据"""
        items_data = [
            {
                "title": "项目 Alpha",
                "subtitle": "主要开发项目",
                "description": "正在进行中的核心功能开发",
                "date": "2024-01-15",
                "status": "active",
                "icon": self.create_colored_icon(QColor(52, 152, 219))
            },
            {
                "title": "项目 Beta",
                "subtitle": "测试项目",
                "description": "需要尽快完成测试",
                "date": "2024-01-20",
                "status": "warning",
                "icon": self.create_colored_icon(QColor(241, 196, 15))
            },
            {
                "title": "项目 Gamma",
                "subtitle": "已暂停项目",
                "description": "等待资源分配",
                "date": "2024-01-10",
                "status": "inactive",
                "icon": self.create_colored_icon(QColor(189, 195, 199))
            },
            {
                "title": "项目 Delta",
                "subtitle": "紧急修复",
                "description": "需要立即处理的问题",
                "date": "2024-01-18",
                "status": "error",
                "icon": self.create_colored_icon(QColor(231, 76, 60))
            }
        ]
        
        for data in items_data:
            self.create_item(data)
    
    def create_colored_icon(self, color):
        """创建彩色图标"""
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制渐变背景
        gradient = QLinearGradient(0, 0, 48, 48)
        gradient.setColorAt(0, color.lighter())
        gradient.setColorAt(1, color)
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(5, 5, 38, 38, 10, 10)
        
        # 绘制图标内部的简单图形
        painter.setPen(QPen(Qt.white, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(15, 15, 18, 18)
        
        painter.end()
        return QIcon(pixmap)
    
    def create_item(self, data):
        """创建自定义项"""
        item = QStandardItem()
        
        # 设置数据到不同的角色
        item.setData(data.get("title", ""), ItemRoles.TitleRole)
        item.setData(data.get("subtitle", ""), ItemRoles.SubtitleRole)
        item.setData(data.get("description", ""), ItemRoles.DescriptionRole)
        item.setData(data.get("date", ""), ItemRoles.DateRole)
        item.setData(data.get("status", "normal"), ItemRoles.StatusRole)
        
        # 设置图标
        if "icon" in data:
            item.setData(data["icon"], ItemRoles.IconPathRole)
        
        # 设置不可编辑
        item.setEditable(False)
        
        # 添加到模型
        self.model.appendRow(item)
        
        return item
    
    def add_item(self):
        """添加新项目"""
        import random
        
        statuses = ["active", "warning", "error", "inactive"]
        colors = [QColor(52, 152, 219), QColor(241, 196, 15), 
                 QColor(231, 76, 60), QColor(189, 195, 199)]
        
        index = random.randint(0, len(statuses) - 1)
        
        new_item_data = {
            "title": f"新项目 {self.model.rowCount() + 1}",
            "subtitle": f"随机状态: {statuses[index]}",
            "description": f"这是第 {self.model.rowCount() + 1} 个新添加的项目",
            "date": "2024-01-{:02d}".format(random.randint(1, 30)),
            "status": statuses[index],
            "icon": self.create_colored_icon(colors[index])
        }
        
        self.create_item(new_item_data)
        
        # 自动滚动到新项
        index = self.model.index(self.model.rowCount() - 1, 0)
        self.list_view.scrollTo(index)
    
    def clear_items(self):
        """清空所有项目"""
        self.model.clear()
        self.delegate.button_states.clear()  # 清空按钮状态
    
    def show_context_menu(self, index, pos):
        """显示右键菜单"""
        menu = QMenu(self)
        
        # 获取项目数据
        title = index.data(ItemRoles.TitleRole)
        
        # 添加菜单项
        edit_action = menu.addAction("编辑")
        edit_action.setIcon(QIcon.fromTheme("document-edit"))
        
        copy_action = menu.addAction("复制")
        copy_action.setIcon(QIcon.fromTheme("edit-copy"))
        
        menu.addSeparator()
        
        delete_action = menu.addAction("删除")
        delete_action.setIcon(QIcon.fromTheme("edit-delete"))
        delete_action.setEnabled(True)
        
        menu.addSeparator()
        
        # 添加子菜单
        status_menu = menu.addMenu("更改状态")
        status_menu.setIcon(QIcon.fromTheme("dialog-information"))
        
        active_action = status_menu.addAction("活跃")
        warning_action = status_menu.addAction("警告")
        error_action = status_menu.addAction("错误")
        inactive_action = status_menu.addAction("未激活")
        
        # 显示菜单并处理选择
        action = menu.exec(pos)
        
        if action == edit_action:
            QMessageBox.information(self, "编辑", f"编辑项目: {title}")
        elif action == copy_action:
            QMessageBox.information(self, "复制", f"复制项目: {title}")
        elif action == delete_action:
            reply = QMessageBox.question(self, "确认删除", 
                                       f"确定要删除项目 '{title}' 吗？",
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.model.removeRow(index.row())
                # 清理按钮状态
                if index.row() in self.delegate.button_states:
                    del self.delegate.button_states[index.row()]
        elif action == active_action:
            index.model().setData(index, "active", ItemRoles.StatusRole)
            self.list_view.update(index)
        elif action == warning_action:
            index.model().setData(index, "warning", ItemRoles.StatusRole)
            self.list_view.update(index)
        elif action == error_action:
            index.model().setData(index, "error", ItemRoles.StatusRole)
            self.list_view.update(index)
        elif action == inactive_action:
            index.model().setData(index, "inactive", ItemRoles.StatusRole)
            self.list_view.update(index)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())