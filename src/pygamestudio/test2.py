from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QComboBox
from PySide6.QtCore import Qt
import sys

class ComboBoxDemo(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QComboBox QSS 美化示例")
        self.setGeometry(300, 300, 400, 300)
        
        layout = QVBoxLayout(self)
        
        # 创建组合框并添加选项
        combo = QComboBox()
        combo.addItems(["选项 1", "选项 2", "选项 3", "选项 4", "这是一个很长的选项文本"])
        combo.setCurrentIndex(0)
        
        # 设置样式表
        combo.setStyleSheet("""
            QComboBox {
                /* 整体外观 */
                border: 2px solid #5a9eff;
                border-radius: 5px;
                padding: 5px 10px;
                min-height: 30px;
                font-size: 14px;
                font-family: "Microsoft YaHei";
                background-color: white;
                color: #333333;
            }
            
            /* 下拉按钮区域 - 关键！需要指定宽度和样式 */
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border-left: 1px solid #5a9eff;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
                background-color: #e8f0fe;
            }
            
            /* 下拉箭头 - 必须显式指定 */
            QComboBox::down-arrow {
                image: url(none);  /* 清除默认图标 */
                width: 12px;
                height: 12px;
                border: none;
            }
            
            /* 使用自定义箭头（绘制三角形） */
            QComboBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid #5a9eff;
                margin: 2px;
            }
            
            /* 下拉按钮悬停效果 */
            QComboBox::drop-down:hover {
                background-color: #d0e2ff;
            }
            
            QComboBox::drop-down:hover::down-arrow {
                border-top-color: #2d6fd4;
            }
            
            /* 下拉列表框样式 */
            QComboBox QAbstractItemView {
                border: 2px solid #5a9eff;
                border-radius: 5px;
                background-color: white;
                selection-background-color: #5a9eff;
                selection-color: white;
                outline: 0px;
                padding: 5px;
            }
            
            /* 下拉列表项样式 */
            QComboBox QAbstractItemView::item {
                min-height: 30px;
                padding: 5px 10px;
                border-bottom: 1px solid #eeeeee;
            }
            
            QComboBox QAbstractItemView::item:selected {
                background-color: #5a9eff;
                color: white;
            }
            
            /* 编辑状态（可编辑组合框） */
            QComboBox:editable {
                background-color: white;
            }
            
            /* 焦点状态 */
            QComboBox:focus {
                border-color: #2d6fd4;
            }
            
            /* 禁用状态 */
            QComboBox:disabled {
                background-color: #f5f5f5;
                color: #999999;
                border-color: #cccccc;
            }
            
            QComboBox:disabled::drop-down {
                background-color: #e8e8e8;
            }
            
            QComboBox:disabled::down-arrow {
                border-top-color: #cccccc;
            }
        """)
        
        layout.addWidget(combo)
        layout.addStretch()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ComboBoxDemo()
    window.show()
    sys.exit(app.exec())