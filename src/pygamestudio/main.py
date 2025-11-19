import sys
import os
sys.path.insert(0, 'D:\\Github\\pygamestudio\\src')
# print(os.path.join(os.path.dirname(__file__)))

from pygamestudio.editor.object.window import ObjectManagerWindow

from PySide6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)
# import os

# # 设置应用程序样式
# # app.setStyle("Fusion")

window = ObjectManagerWindow()
window.show()

sys.exit(app.exec())