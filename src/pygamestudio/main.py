import sys
import os
sys.path.insert(0, 'D:\\Github\\pygamestudio\\src')
# print(os.path.join(os.path.dirname(__file__)))

from pygamestudio.editor.gui.hierarchy.window import HierarchyWindow
from pygamestudio.editor.gui.hierarchy.tree import HierarchyTreeView
from pygamestudio.editor.gui.asset.window import AssetWindow
from pygamestudio.editor.gui.console.window import ConsoleWindow
from pygamestudio.editor.gui.inspector.window import InspectorWindow
from pygamestudio.editor.gui.scene.window import SceneWindow

from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout
from pygamestudio.game.object.manager import ObjectManager
import sys
app = QApplication(sys.argv)
# import os

# # 设置应用程序样式
# # app.setStyle("Fusion")

window = QWidget()
# window = HierarchyWindow()
# window = AssetTreeView()
# window.show()

object_manager = ObjectManager()

hierarchy_window = HierarchyWindow(window, object_manager)
scene_widnow = SceneWindow(window, object_manager)
inspector_window = InspectorWindow(window, object_manager)

layout = QHBoxLayout(window)
layout.addWidget(hierarchy_window)
layout.addSpacing(10)
layout.addWidget(scene_widnow)
layout.addSpacing(10)
layout.addWidget(inspector_window)

window.show()

sys.exit(app.exec())