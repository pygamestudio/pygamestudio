import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLineEdit, QPushButton, QLabel)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter


class SearchLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_mode = "name"  # 默认按名称搜索
        self.init_ui()
        
    def init_ui(self):
        # 设置输入框样式，为图标和按钮预留空间
        self.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding-left: 25px;
                padding-right: 60px;
                font-size: 14px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        
        # 创建切换按钮
        self.toggle_button = QPushButton("名称", self)
        self.toggle_button.setFixedSize(50, 20)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        
        # 设置按钮无边框样式
        self.toggle_button.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                color: #666;
                font-size: 12px;
                padding: 0px;
            }
            QPushButton:checked {
                color: #0078d4;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #333;
            }
            QPushButton:checked:hover {
                color: #005a9e;
            }
        """)
        
        # 连接信号
        self.toggle_button.toggled.connect(self.on_toggle_changed)
        
        # 更新占位符文本
        self.update_placeholder()
        
    def resizeEvent(self, event):
        """重写resizeEvent来定位按钮"""
        super().resizeEvent(event)
        
        # 定位按钮在右侧
        button_x = self.width() - self.toggle_button.width() - 5
        button_y = (self.height() - self.toggle_button.height()) // 2
        self.toggle_button.move(button_x, button_y)
        
    def paintEvent(self, event):
        """重写paintEvent来绘制搜索图标"""
        super().paintEvent(event)
        
        # 绘制搜索图标
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 设置图标颜色
        if self.hasFocus():
            painter.setPen(QColor("#0078d4"))
        else:
            painter.setPen(QColor("#666"))
        
        # 绘制放大镜图标
        icon_x = 8
        icon_y = (self.height() - 12) // 2
        
        # 绘制放大镜圆圈
        painter.drawEllipse(icon_x, icon_y, 6, 6)
        # 绘制放大镜手柄
        painter.drawLine(icon_x + 5, icon_y + 5, icon_x + 9, icon_y + 9)
        
    def on_toggle_changed(self, checked):
        """切换按钮状态改变时的处理"""
        if checked:
            self.search_mode = "uuid"
            self.toggle_button.setText("UUID")
        else:
            self.search_mode = "name"
            self.toggle_button.setText("名称")
        
        self.update_placeholder()
        
    def update_placeholder(self):
        """更新占位符文本"""
        if self.search_mode == "name":
            self.setPlaceholderText("按名称搜索...")
        else:
            self.setPlaceholderText("按UUID搜索...")
        
    def get_search_mode(self):
        """获取当前搜索模式"""
        return self.search_mode


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("搜索框示例")
        self.setGeometry(100, 100, 400, 200)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # 添加说明标签
        label = QLabel("集成搜索框示例：")
        label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(label)
        
        # 添加搜索框
        self.search_edit = SearchLineEdit()
        layout.addWidget(self.search_edit)
        
        # 添加结果显示标签
        self.result_label = QLabel("搜索结果显示在这里")
        self.result_label.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                font-size: 13px;
                color: #333;
            }
        """)
        self.result_label.setMinimumHeight(60)
        layout.addWidget(self.result_label)
        
        # 添加搜索按钮
        search_btn = QPushButton("执行搜索")
        search_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        search_btn.clicked.connect(self.perform_search)
        layout.addWidget(search_btn)
        
        # 添加清空按钮
        clear_btn = QPushButton("清空搜索")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #333;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        clear_btn.clicked.connect(self.clear_search)
        layout.addWidget(clear_btn)
        
    def perform_search(self):
        """执行搜索操作"""
        search_text = self.search_edit.text().strip()
        search_mode = self.search_edit.get_search_mode()
        
        if search_text:
            if search_mode == "name":
                self.result_label.setText(f"🔍 按名称搜索: '{search_text}'\n\n模拟搜索结果:\n• 项目 '{search_text}'\n• {search_text} 文档\n• {search_text} 配置")
            else:
                self.result_label.setText(f"🔍 按UUID搜索: '{search_text}'\n\n模拟搜索结果:\n• UUID: {search_text}\n• 关联对象: 示例对象\n• 创建时间: 2024-01-01")
        else:
            self.result_label.setText("⚠️ 请输入搜索关键词")
            
    def clear_search(self):
        """清空搜索"""
        self.search_edit.clear()
        self.result_label.setText("搜索结果显示在这里")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())