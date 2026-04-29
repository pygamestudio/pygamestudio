from PySide6.QtWidgets import (QApplication, QMainWindow, QTextEdit,
                               QVBoxLayout, QWidget)
import sys

class DarkTextEditDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QTextEdit 深色美化示例")
        self.resize(600, 400)

        # 主窗口背景 #282828（你要的底色）
        self.setStyleSheet("QMainWindow { background-color: #282828; }")

        # 创建中心部件 + 布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # ========== 美化后的 QTextEdit ==========
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("这里是美化后的 QTextEdit，支持输入、换行、滚动条...")
        layout.addWidget(self.text_edit)

        # ========== QSS 样式（核心美化代码） ==========
        self.text_edit.setStyleSheet("""
            /* 文本框主体 */
            QTextEdit {
                background-color: #333333;      /* 控件背景（推荐色） */
                color: #e0e0e0;                 /* 文字颜色（柔和白） */
                border: 1px solid white;      /* 细边框，提升质感 */
                border-radius: 6px;             /* 圆角，现代UI */
                padding: 8px;                   /* 内边距，文字不贴边 */
                font-size: 14px;
                font-family: "Microsoft YaHei";
            }

            /* 鼠标悬浮时 */
            QTextEdit:hover {
                background-color: #383838;
                border-color: #555555;
            }

            /* 获得焦点时 */
            QTextEdit:focus {
                background-color: #3a3a3a;
                border-color: #0078d4;  /* 微软蓝，清晰不刺眼 */
            }

            /* 滚动条整体 */
            QScrollBar:vertical {
                background-color: #333333;
                width: 10px;
                border-radius: 5px;
            }

            /* 滚动条滑块 */
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 5px;
                min-height: 20px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #777777;
            }

            /* 滚动条箭头（隐藏更干净） */
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DarkTextEditDemo()
    window.show()
    sys.exit(app.exec())