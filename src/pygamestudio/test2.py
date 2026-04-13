import sys
from PySide6.QtWidgets import QMainWindow, QApplication, QComboBox, QLabel
from PySide6.QtGui import QAction

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("菜单栏添加控件示例")
        self.resize(400, 300)

        # 1. 获取窗口的菜单栏
        menubar = self.menuBar()

        # 2. 添加一个普通的“文件”菜单作为示例
        file_menu = menubar.addMenu("文件")
        file_menu.addAction("打开")
        file_menu.addAction("保存")

        # 3. 创建一个要放在菜单栏上的控件（以下拉框为例）
        combo_box = QComboBox(self)
        combo_box.addItems(["选项 A", "选项 B", "选项 C"])
        # 设置占位符文本，让它在菜单栏上看起来更协调
        combo_box.setPlaceholderText("请选择...")

        # 4. 关键步骤：将控件设置到菜单栏的右上角
        menubar.setCornerWidget(combo_box)

        # 你也可以使用 Qt.TopLeftCorner 将其放在左上角
        # menubar.setCornerWidget(combo_box, Qt.TopLeftCorner)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())