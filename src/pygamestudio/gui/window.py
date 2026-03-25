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

from pygamestudio.gui.base.window import WindowBase


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

        self._file_menu = self.menuBar().addMenu('文件')
        self._edit_menu = self.menuBar().addMenu('编辑')
        self._project_menu = self.menuBar().addMenu('项目')
        self._panel_menu = self.menuBar().addMenu('面板')
        self._help_menu = self.menuBar().addMenu('帮助')
        
        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_menu()

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
        self._main_horizontal_splitter.setSizes([260, 900, 260])

        self.setCentralWidget(self._central_widget)

    def _set_signal(self):
        ...

    def _set_layout(self):
        main_layout = QHBoxLayout(self._central_widget)
        main_layout.addWidget(self._main_horizontal_splitter)
        main_layout.setContentsMargins(0, 0, 0, 0)

    def _set_menu(self):
        self._set_file_menu()

    def _set_file_menu(self):
        new_project_action = QAction('新建项目', self)
        open_project_action = QAction('打开项目', self)

        self._file_menu.addAction(new_project_action)
        self._file_menu.addAction(open_project_action)

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().enterEvent(event)


class Editor(WindowBase):
    
    def __init__(self, parent, object_manager):
        super().__init__()
        self._parent = parent
        self._object_manager = object_manager
        self._editor_body = EditorBody(object_manager)

        self._setup()

    def _setup(self):
        self._set_widget()

    def _set_widget(self):
        self.resize(1420, 930)
        self._center()
        self.set_window_body(self._editor_body)
    
    def _center(self):
        screen = QApplication.primaryScreen()
        screen_width = screen.availableGeometry().width()
        screen_height = screen.availableGeometry().height()
 
        pos_x = screen_width/2 - self.frameGeometry().width()/2
        pos_y = screen_height/2 - self.frameGeometry().height()/2
 
        self.move(int(pos_x), int(pos_y))

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

    def closeEvent(self, event):
        super().closeEvent(event)
        self._parent.show_dashboard()