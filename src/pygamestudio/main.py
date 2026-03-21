import os
import sys
# import os
sys.path.insert(0, 'D:\\Github\\pygamestudio\\src')
# # print(os.path.join(os.path.dirname(__file__)))

from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout
from PySide6.QtCore import Qt
from pygamestudio.gui.window import Editor
from pygamestudio.gui.dashboard.window import DashboardWindow
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.gui.main import PygameStudio

os.environ['PROJECT_PATH'] = 'C:/Users/louis/Desktop/pygamestudio-test'

if __name__ == '__main__':
    app = QApplication([])
    pygame_studio = PygameStudio()
    pygame_studio.start()
    sys.exit(app.exec())


# from pygamestudio.editor.gui.dashboard.window import DashboardWindow

# from pygamestudio.editor.gui.dashboard.create import CreatePorjectWindow

# if __name__ == '__main__':
#     app = QApplication([])
#     editor = DashboardWindow()
#     editor.show()
#     sys.exit(app.exec())