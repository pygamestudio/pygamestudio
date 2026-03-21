from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.gui.hierarchy.window import HierarchyWindow
from pygamestudio.gui.asset.window import AssetWindow
from pygamestudio.gui.console.window import ConsoleWindow
from pygamestudio.gui.inspector.window import InspectorWindow
from pygamestudio.gui.scene.window import SceneWindow
from pygamestudio.gui.dashboard.window import DashboardWindow

from pygamestudio.gui.template.window import WindowBase


class EditorBody(QMainWindow):
    def __init__(self, object_manager):
        super().__init__()
        self._scene_widnow = SceneWindow(self, object_manager)
        self._asset_window = AssetWindow(self, object_manager)
        self._console_window = ConsoleWindow(self, object_manager)
        self._hierarchy_window = HierarchyWindow(self, object_manager)
        self._inspector_window = InspectorWindow(self, object_manager)

        self._left_top_tab_widget = QTabWidget()
        self._left_bottom_tab_widget = QTabWidget()
        self._center_top_tab_widget = QTabWidget()
        self._center_bottom_tab_widget = QTabWidget()
        self._right_top_tab_widget = QTabWidget()
        self._right_bottom_tab_widget = QTabWidget()

        self._left_vertical_splitter = QSplitter()
        self._center_vertical_splitter = QSplitter()
        self._right_vertical_splitter = QSplitter()
        self._main_horizontal_splitter = QSplitter()

        self._central_widget = QWidget()
        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

    def _set_widget(self):
        self.resize(1420, 900)
        self._left_top_tab_widget.addTab(self._hierarchy_window, '层级')
        self._left_bottom_tab_widget.addTab(self._asset_window, '资源')
        self._center_top_tab_widget.addTab(self._scene_widnow, '场景')
        self._center_bottom_tab_widget.addTab(self._console_window, '日志')
        self._right_top_tab_widget.addTab(self._inspector_window, '属性')
        self._right_bottom_tab_widget.setHidden(True)

        self._left_vertical_splitter.setOrientation(Qt.Orientation.Vertical)
        self._center_vertical_splitter.setOrientation(Qt.Orientation.Vertical)
        self._right_vertical_splitter.setOrientation(Qt.Orientation.Vertical)
        self._left_vertical_splitter.addWidget(self._left_top_tab_widget)
        self._left_vertical_splitter.addWidget(self._left_bottom_tab_widget)
        self._center_vertical_splitter.addWidget(self._center_top_tab_widget)
        self._center_vertical_splitter.addWidget(self._center_bottom_tab_widget)
        self._right_vertical_splitter.addWidget(self._right_top_tab_widget)
        self._right_vertical_splitter.addWidget(self._right_bottom_tab_widget)
        self._main_horizontal_splitter.addWidget(self._left_vertical_splitter)
        self._main_horizontal_splitter.addWidget(self._center_vertical_splitter)
        self._main_horizontal_splitter.addWidget(self._right_vertical_splitter)

        self.setCentralWidget(self._central_widget)

    def _set_signal(self):
        ...

    def _set_layout(self):
        main_layout = QHBoxLayout(self._central_widget)
        main_layout.addWidget(self._main_horizontal_splitter)
        main_layout.setContentsMargins(0, 0, 0, 0)

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().enterEvent(event)


class Editor(WindowBase):
    def __init__(self, object_manager):
        super().__init__()
        self._object_manager = object_manager
        self._editor_body = EditorBody(object_manager)

        self._setup()
        self.move(50, 50)   # 改成屏幕居中

    def _setup(self):
        self._set_widget()

    def _set_widget(self):
        self.resize(1420, 930)
        self.set_window_body(self._editor_body)

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_S:
                print('保存')
                self._object_manager.save()
            elif event.key() == Qt.Key.Key_Z:
                print('撤销')
                self._object_manager.undo_stack.undo()
            elif event.key() == Qt.Key.Key_Y:
                print('重做')
                self._object_manager.undo_stack.redo()

        elif event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            if event.key() == Qt.Key.Key_Z:
                print('重做')
                self._object_manager.undo_stack.redo()

        super().keyPressEvent(event)
