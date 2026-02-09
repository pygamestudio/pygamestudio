import sys
import pygame
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

class GameObject:
    """游戏对象基类"""
    def __init__(self, name="GameObject", x=0, y=0):
        self.name = name
        self.x = x
        self.y = y
        self.width = 50
        self.height = 50
        self.color = "#3498db"
        self.visible = True
        self.type = "rectangle"
        
    def to_dict(self):
        return {
            'name': self.name,
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'color': self.color,
            'visible': self.visible,
            'type': self.type
        }

class InspectorWidget(QWidget):
    """属性检查器组件"""
    def __init__(self):
        super().__init__()
        self.current_object = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 标题
        title_label = QLabel("Inspector")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
                background-color: #2c3e50;
                color: white;
                border-radius: 5px;
            }
        """)
        layout.addWidget(title_label)
        
        # 表单区域
        self.form_widget = QWidget()
        self.form_layout = QFormLayout()
        self.form_widget.setLayout(self.form_layout)
        layout.addWidget(self.form_widget)
        
        # 占位提示
        self.placeholder = QLabel("Select an object to inspect")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("color: #7f8c8d; font-style: italic; padding: 20px;")
        layout.addWidget(self.placeholder)
        
        layout.addStretch()
        self.setLayout(layout)
        
    def create_color_picker(self, color):
        """创建颜色选择按钮"""
        button = QPushButton()
        button.setFixedSize(30, 30)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: 2px solid #34495e;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid #1abc9c;
            }}
        """)
        return button
        
    def create_spinbox(self, value, min_val=0, max_val=1000):
        """创建数值输入框"""
        spinbox = QSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(value)
        spinbox.setButtonSymbols(QSpinBox.NoButtons)
        spinbox.setStyleSheet("""
            QSpinBox {
                padding: 5px;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
            }
        """)
        return spinbox
        
    def inspect_object(self, game_object):
        """检查指定对象"""
        self.current_object = game_object
        self.placeholder.hide()
        
        # 清空表单
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # 对象名称
        name_edit = QLineEdit(game_object.name)
        name_edit.textChanged.connect(lambda text: setattr(game_object, 'name', text))
        self.form_layout.addRow("Name:", name_edit)
        
        # 位置
        x_spin = self.create_spinbox(game_object.x, -1000, 1000)
        x_spin.valueChanged.connect(lambda val: setattr(game_object, 'x', val))
        self.form_layout.addRow("X:", x_spin)
        
        y_spin = self.create_spinbox(game_object.y, -1000, 1000)
        y_spin.valueChanged.connect(lambda val: setattr(game_object, 'y', val))
        self.form_layout.addRow("Y:", y_spin)
        
        # 尺寸
        width_spin = self.create_spinbox(game_object.width, 1, 500)
        width_spin.valueChanged.connect(lambda val: setattr(game_object, 'width', val))
        self.form_layout.addRow("Width:", width_spin)
        
        height_spin = self.create_spinbox(game_object.height, 1, 500)
        height_spin.valueChanged.connect(lambda val: setattr(game_object, 'height', val))
        self.form_layout.addRow("Height:", height_spin)
        
        # 颜色选择
        color_button = self.create_color_picker(game_object.color)
        color_button.clicked.connect(lambda: self.pick_color(game_object))
        self.form_layout.addRow("Color:", color_button)
        
        # 可见性
        visible_check = QCheckBox()
        visible_check.setChecked(game_object.visible)
        visible_check.stateChanged.connect(
            lambda state: setattr(game_object, 'visible', bool(state))
        )
        self.form_layout.addRow("Visible:", visible_check)
        
        # 对象类型
        type_combo = QComboBox()
        type_combo.addItems(["rectangle", "circle"])
        type_combo.setCurrentText(game_object.type)
        type_combo.currentTextChanged.connect(
            lambda text: setattr(game_object, 'type', text)
        )
        type_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
            }
        """)
        self.form_layout.addRow("Type:", type_combo)
        
        # 导出按钮
        export_btn = QPushButton("Export JSON")
        export_btn.clicked.connect(lambda: self.export_object_data(game_object))
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 8px;
                border: none;
                border-radius: 4px;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        self.form_layout.addRow(export_btn)
        
    def pick_color(self, game_object):
        """颜色选择对话框"""
        color = QColorDialog.getColor(QColor(game_object.color))
        if color.isValid():
            game_object.color = color.name()
            self.inspect_object(game_object)  # 刷新显示
            
    def export_object_data(self, game_object):
        """导出对象数据"""
        import json
        data = game_object.to_dict()
        
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getSaveFileName(
            self, "Export Object Data", "", "JSON Files (*.json)"
        )
        
        if file_path:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Success", "Object data exported successfully!")

class GameViewWidget(QWidget):
    """游戏视图组件"""
    selection_changed = Signal(GameObject)
    
    def __init__(self):
        super().__init__()
        self.objects = []
        self.selected_object = None
        self.init_ui()
        
    def init_ui(self):
        self.setMinimumSize(600, 400)
        self.setStyleSheet("background-color: #ecf0f1;")
        
        # 创建一些示例对象
        self.create_sample_objects()
        
    def create_sample_objects(self):
        """创建示例游戏对象"""
        obj1 = GameObject("Player", 100, 100)
        obj1.color = "#e74c3c"
        
        obj2 = GameObject("Enemy", 300, 200)
        obj2.color = "#f39c12"
        obj2.width = 70
        obj2.height = 70
        
        obj3 = GameObject("Platform", 200, 300)
        obj3.color = "#2ecc71"
        obj3.width = 150
        obj3.height = 30
        
        self.objects = [obj1, obj2, obj3]
        
    def paintEvent(self, event):
        """绘制游戏对象"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制网格背景
        grid_size = 20
        painter.setPen(QPen(QColor("#d5dbdb"), 1))
        for x in range(0, self.width(), grid_size):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), grid_size):
            painter.drawLine(0, y, self.width(), y)
            
        # 绘制所有游戏对象
        for obj in self.objects:
            if obj.visible:
                color = QColor(obj.color)
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor("#34495e"), 2))
                
                if obj.type == "rectangle":
                    painter.drawRect(obj.x, obj.y, obj.width, obj.height)
                else:  # circle
                    painter.drawEllipse(obj.x, obj.y, obj.width, obj.height)
                    
                # 绘制对象名称
                painter.setPen(QPen(QColor("#2c3e50")))
                painter.drawText(
                    QRect(obj.x, obj.y - 20, obj.width, 20),
                    Qt.AlignCenter,
                    obj.name
                )
                
                # 如果被选中，绘制边框
                if obj == self.selected_object:
                    painter.setPen(QPen(QColor("#1abc9c"), 3))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(obj.x - 3, obj.y - 3, 
                                   obj.width + 6, obj.height + 6)
                    
    def mousePressEvent(self, event):
        """鼠标点击选择对象"""
        pos = event.pos()
        
        # 从后向前检查（最后绘制的在最上层）
        for obj in reversed(self.objects):
            if (obj.x <= pos.x() <= obj.x + obj.width and
                obj.y <= pos.y() <= obj.y + obj.height):
                self.selected_object = obj
                self.selection_changed.emit(obj)
                self.update()
                return
                
        # 点击空白处取消选择
        self.selected_object = None
        self.selection_changed.emit(None)
        self.update()

class HierarchyWidget(QListWidget):
    """对象层次结构组件"""
    selection_changed = Signal(GameObject)
    
    def __init__(self, game_view):
        super().__init__()
        self.game_view = game_view
        self.init_ui()
        
    def init_ui(self):
        self.setMaximumWidth(200)
        self.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: #34495e;
                color: white;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2c3e50;
            }
            QListWidget::item:selected {
                background-color: #1abc9c;
            }
            QListWidget::item:hover {
                background-color: #2980b9;
            }
        """)
        
        self.refresh_list()
        self.itemClicked.connect(self.on_item_clicked)
        
    def refresh_list(self):
        """刷新对象列表"""
        self.clear()
        for obj in self.game_view.objects:
            item = QListWidgetItem(obj.name)
            item.setData(Qt.UserRole, obj)
            self.addItem(item)
            
    def on_item_clicked(self, item):
        """列表项被点击"""
        obj = item.data(Qt.UserRole)
        self.selection_changed.emit(obj)

class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Pygame Visual Editor")
        self.setGeometry(100, 100, 1200, 700)
        
        # 创建中央部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # 左侧：层次结构
        self.game_view = GameViewWidget()
        self.hierarchy = HierarchyWidget(self.game_view)
        
        # 右侧：属性检查器
        self.inspector = InspectorWidget()
        
        # 连接信号
        self.game_view.selection_changed.connect(self.on_selection_changed)
        self.hierarchy.selection_changed.connect(self.on_selection_changed)
        
        # 工具栏
        self.create_toolbar()
        
        # 布局
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("Hierarchy"))
        left_panel.addWidget(self.hierarchy)
        
        main_layout.addLayout(left_panel, 1)
        main_layout.addWidget(self.game_view, 3)
        main_layout.addWidget(self.inspector, 1)
        
    def create_toolbar(self):
        """创建工具栏"""
        toolbar = self.addToolBar("Tools")
        
        # 添加对象按钮
        add_btn = QAction("➕ Add Object", self)
        add_btn.triggered.connect(self.add_new_object)
        toolbar.addAction(add_btn)
        
        toolbar.addSeparator()
        
        # 刷新按钮
        refresh_btn = QAction("🔄 Refresh", self)
        refresh_btn.triggered.connect(self.refresh_all)
        toolbar.addAction(refresh_btn)
        
    def add_new_object(self):
        """添加新对象"""
        import random
        colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6"]
        
        obj = GameObject(
            f"Object_{len(self.game_view.objects) + 1}",
            random.randint(50, 400),
            random.randint(50, 300)
        )
        obj.color = random.choice(colors)
        
        self.game_view.objects.append(obj)
        self.game_view.update()
        self.hierarchy.refresh_list()
        
    def refresh_all(self):
        """刷新所有视图"""
        self.game_view.update()
        self.hierarchy.refresh_list()
        
    def on_selection_changed(self, game_object):
        """处理选择变化"""
        if game_object:
            self.inspector.inspect_object(game_object)
            # 同步选择
            self.game_view.selected_object = game_object
            self.game_view.update()
        else:
            # 清除inspector显示
            while self.inspector.form_layout.count():
                item = self.inspector.form_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.inspector.placeholder.show()
            self.game_view.selected_object = None
            self.game_view.update()

def main():
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(52, 73, 94))
    palette.setColor(QPalette.WindowText, Qt.white)
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()