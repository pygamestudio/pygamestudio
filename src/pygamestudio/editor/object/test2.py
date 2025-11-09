from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QStyledItemDelegate, 
                              QApplication, QMainWindow, QVBoxLayout, QWidget)
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QMouseEvent
from PySide6.QtCore import Qt, QRect, QModelIndex, QSize

class EyeIconDelegate(QStyledItemDelegate):
    def __init__(self, tree_widget):
        super().__init__(tree_widget)
        self.tree_widget = tree_widget
        self.icon_size = QSize(16, 16)
        self.hovered_index = None  # 记录当前悬停的item索引
    
    def paint(self, painter, option, index):
        """绘制委托"""
        if index.column() == 1:  # 只在第二列绘制眼睛图标
            # 绘制默认背景
            super().paint(painter, option, index)
            
            # 获取item和可见状态
            item = self.tree_widget.itemFromIndex(index)
            if item:
                # 获取item自身的可见状态（不考虑父级）
                item_own_visible = item.data(0, Qt.UserRole + 1)
                # 检查是否悬停
                is_hovered = index == self.hovered_index
                self.draw_eye_icon(painter, option.rect, item_own_visible, is_hovered)
        else:
            super().paint(painter, option, index)
    
    def draw_eye_icon(self, painter, rect, is_visible, is_hovered):
        """绘制眼睛图标（带悬停效果）"""
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 计算图标位置（居中）
        icon_rect = QRect(0, 0, self.icon_size.width(), self.icon_size.height())
        icon_rect.moveCenter(rect.center())
        
        # 悬停效果：稍微放大和改变颜色
        if is_hovered:
            # 轻微放大效果
            icon_rect.adjust(-1, -1, 1, 1)
            
        if is_visible:
            # 绘制睁眼图标
            self.draw_open_eye(painter, icon_rect, is_hovered)
        else:
            # 绘制闭眼图标
            self.draw_closed_eye(painter, icon_rect, is_hovered)
        
        painter.restore()
    
    def draw_open_eye(self, painter, rect, is_hovered):
        """绘制睁眼图标（带悬停效果）"""
        if is_hovered:
            # 悬停状态：更深的颜色和轮廓
            eye_color = QColor(40, 40, 40)
            bg_color = QColor(220, 220, 220)
            pupil_color = QColor(20, 20, 20)
            outline_width = 2.0
        else:
            # 正常状态
            eye_color = QColor(80, 80, 80)
            bg_color = QColor(240, 240, 240)
            pupil_color = QColor(60, 60, 60)
            outline_width = 1.5
        
        # 眼睛轮廓
        painter.setPen(QPen(eye_color, outline_width))
        painter.setBrush(QBrush(bg_color))
        painter.drawEllipse(rect.x() + 2, rect.y() + 4, 12, 8)
        
        # 眼球
        painter.setBrush(QBrush(pupil_color))
        painter.drawEllipse(rect.x() + 6, rect.y() + 6, 4, 4)
        
        # 高光
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(rect.x() + 7, rect.y() + 7, 1, 1)
        
        # 悬停时添加外圈光晕效果
        if is_hovered:
            painter.setPen(QPen(QColor(100, 150, 255, 80), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(rect.x() + 1, rect.y() + 3, 14, 10)
    
    def draw_closed_eye(self, painter, rect, is_hovered):
        """绘制闭眼图标（带悬停效果）"""
        if is_hovered:
            # 悬停状态：更深的颜色
            eye_color = QColor(120, 120, 120)
            line_width = 2.5
            lash_color = QColor(100, 100, 100)
        else:
            # 正常状态
            eye_color = QColor(150, 150, 150)
            line_width = 2.0
            lash_color = QColor(120, 120, 120)
        
        # 绘制一条横线表示闭眼
        painter.setPen(QPen(eye_color, line_width))
        painter.drawLine(rect.x() + 3, rect.y() + 8, 
                        rect.x() + 13, rect.y() + 8)
        
        # 睫毛效果
        painter.setPen(QPen(lash_color, 1))
        # 上睫毛
        painter.drawLine(rect.x() + 4, rect.y() + 6, rect.x() + 4, rect.y() + 5)
        painter.drawLine(rect.x() + 8, rect.y() + 5, rect.x() + 8, rect.y() + 4)
        painter.drawLine(rect.x() + 12, rect.y() + 6, rect.x() + 12, rect.y() + 5)
        
        # 悬停时添加外圈光晕效果
        if is_hovered:
            painter.setPen(QPen(QColor(255, 100, 100, 80), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(rect.x() + 1, rect.y() + 3, 14, 10)
    
    def editorEvent(self, event, model, option, index):
        """处理鼠标事件"""
        if index.column() == 1:
            if event.type() == QMouseEvent.MouseMove:
                # 鼠标移动事件：更新悬停状态
                old_hovered = self.hovered_index
                if self.is_click_on_icon(event.pos(), option.rect):
                    self.hovered_index = index
                else:
                    self.hovered_index = None
                
                # 如果悬停状态改变，触发重绘
                if old_hovered != self.hovered_index:
                    self.tree_widget.viewport().update()
                return True
                
            elif (event.type() == QMouseEvent.MouseButtonRelease and 
                  event.button() == Qt.LeftButton):
                
                # 检查点击是否在图标区域内
                item = self.tree_widget.itemFromIndex(index)
                if item and self.is_click_on_icon(event.pos(), option.rect):
                    self.tree_widget.toggle_item_visibility(item)
                    return True  # 事件已处理
        
        # 清除悬停状态
        self.hovered_index = None
        return super().editorEvent(event, model, option, index)
    
    def is_click_on_icon(self, click_pos, cell_rect):
        """检查点击是否在图标区域内"""
        icon_rect = QRect(0, 0, self.icon_size.width(), self.icon_size.height())
        icon_rect.moveCenter(cell_rect.center())
        # 稍微扩大点击区域，提升用户体验
        icon_rect.adjust(-2, -2, 2, 2)
        return icon_rect.contains(click_pos)

class EyeTreeWidget(QTreeWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(2)
        self.setHeaderLabels(["项目名称", "可见性"])
        
        # 设置列宽
        self.setColumnWidth(0, 200)
        self.setColumnWidth(1, 60)
        
        # 设置鼠标跟踪
        self.setMouseTracking(True)
        
        # 设置自定义委托
        self.delegate = EyeIconDelegate(self)
        self.setItemDelegate(self.delegate)
        
        # 初始化数据
        self.setup_data()
        
        # 连接信号
        self.itemExpanded.connect(self.on_item_expanded_collapsed)
        self.itemCollapsed.connect(self.on_item_expanded_collapsed)
    
    def mouseMoveEvent(self, event):
        """处理鼠标移动事件，确保悬停效果正常工作"""
        super().mouseMoveEvent(event)
        # 触发委托的鼠标移动事件处理
        index = self.indexAt(event.pos())
        if index.isValid():
            # 创建一个鼠标事件传递给委托
            self.delegate.editorEvent(event, self.model(), 
                                    self.visualRect(index), index)
    
    def leaveEvent(self, event):
        """鼠标离开控件时清除所有悬停状态"""
        self.delegate.hovered_index = None
        self.viewport().update()
        super().leaveEvent(event)
    
    def setup_data(self):
        """初始化示例数据"""
        items_data = [
            "背景图层",
            "文本标题", 
            "图片内容",
            "装饰元素",
            "水印图层"
        ]
        
        for name in items_data:
            item = QTreeWidgetItem([name, ""])
            item.setData(0, Qt.UserRole + 1, True)
            self.addTopLevelItem(item)
            
            # 添加一些子项示例
            for i in range(2):
                child = QTreeWidgetItem([f"{name} - 子项 {i+1}", ""])
                child.setData(0, Qt.UserRole + 1, True)
                item.addChild(child)
            
            item.setExpanded(True)
    
    def toggle_item_visibility(self, item):
        """切换item的可见性"""
        current_visible = item.data(0, Qt.UserRole + 1)
        new_visible = not current_visible
        
        item.setData(0, Qt.UserRole + 1, new_visible)
        self.update_all_items_appearance()
        
        print(f"{item.text(0)} 自身状态: {'显示' if new_visible else '隐藏'}")
    
    def is_item_effectively_visible(self, item):
        """计算item的实际显示状态（考虑父级链）"""
        current = item
        while current:
            if not current.data(0, Qt.UserRole + 1):
                return False
            current = current.parent()
        return True
    
    def update_all_items_appearance(self):
        """更新所有item的显示外观"""
        def update_item_recursive(item):
            if item:
                effectively_visible = self.is_item_effectively_visible(item)
                
                if effectively_visible:
                    item.setForeground(0, QColor(0, 0, 0))
                    item.setBackground(0, QColor(255, 255, 255))
                else:
                    item.setForeground(0, QColor(150, 150, 150))
                    item.setBackground(0, QColor(245, 245, 245))
                
                for i in range(item.childCount()):
                    update_item_recursive(item.child(i))
        
        for i in range(self.topLevelItemCount()):
            update_item_recursive(self.topLevelItem(i))
        
        self.viewport().update()
    
    def on_item_expanded_collapsed(self, item):
        """当item展开或收缩时更新显示"""
        self.viewport().update()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("树形控件 - 带悬停反馈的眼睛图标")
        self.setGeometry(100, 100, 400, 400)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        self.tree_widget = EyeTreeWidget()
        layout.addWidget(self.tree_widget)

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()