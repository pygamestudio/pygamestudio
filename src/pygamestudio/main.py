import sys
sys.path.insert(0, 'D:\\Github\\pygamestudio\\src')
from PySide6.QtWidgets import QApplication
from pygamestudio.gui.main import PygameStudio


if __name__ == '__main__':
    app = QApplication([])
    pygame_studio = PygameStudio()
    pygame_studio.start()
    sys.exit(app.exec())