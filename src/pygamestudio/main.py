import sys
import os
sys.path.insert(0, 'D:\\Github\\pygamestudio\\src')
# print(os.path.join(os.path.dirname(__file__)))

from pygamestudio.editor.object.window import ObjectWindow
from pygamestudio.editor.asset.window import AssetWindow
from pygamestudio.editor.console.window import ConsoleWindow

from PySide6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)
# import os

# # 设置应用程序样式
# # app.setStyle("Fusion")

window = ConsoleWindow()
# window = ObjectWindow()
# window = AssetTreeView()
window.show()

sys.exit(app.exec())