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
from pygamestudio.game.core.manager import GameManager
from pathlib import Path

class EditorBody(QMainWindow):
    new_project_signal = Signal()
    open_project_signal = Signal()
    quit_editor_signal = Signal()

    def __init__(self, game_manager):
        super().__init__()
        self._game_manager = game_manager
        self._scene_widnow = SceneWindow(self, game_manager)
        self._asset_window = AssetWindow(self, game_manager)
        self._console_window = ConsoleWindow(self, game_manager)
        self._hierarchy_window = HierarchyWindow(self, game_manager)
        self._inspector_window = InspectorWindow(self, game_manager)

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
        # self._panel_menu = self.menuBar().addMenu('面板')
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

        # 调整菜单栏间距
        # self.menuBar().setStyleSheet("""
        #     QMenuBar::item {
        #         padding: 6px 6px;
        #         margin: 0px 6px;  /* 菜单项之间的间距 */
        #         border-radius: 4px;
        #     }
        # """)

    def _set_signal(self):
        ...

    def _set_layout(self):
        main_layout = QHBoxLayout(self._central_widget)
        main_layout.addWidget(self._main_horizontal_splitter)
        main_layout.setContentsMargins(0, 0, 0, 0)

    def _set_menu(self):
        self._set_file_menu()
        self._set_edit_menu()
        self._set_project_menu()
        self._set_help_menu()

    def _set_file_menu(self):
        new_project_action = QAction('新建项目', self)
        open_project_action = QAction('打开项目', self)
        new_scene_action = QAction('新建场景', self)
        save_scene_action = QAction('保存场景', self)
        editor_settings_action = QAction('编辑器设置', self)
        quit_editor_action = QAction('退出', self)

        new_project_action.triggered.connect(self.new_project_signal.emit)
        open_project_action.triggered.connect(self.open_project_signal.emit)
        new_scene_action.triggered.connect(lambda: self._game_manager.load_scene(''))
        save_scene_action.triggered.connect(self._game_manager.save_scene)
        quit_editor_action.triggered.connect(self.quit_editor_signal.emit)

        self._file_menu.addAction(new_project_action)
        self._file_menu.addAction(open_project_action)
        self._file_menu.addSeparator()
        self._file_menu.addAction(new_scene_action)
        self._file_menu.addAction(save_scene_action)
        self._file_menu.addSeparator()
        # self._file_menu.addAction(editor_settings_action)
        # self._file_menu.addSeparator()
        self._file_menu.addAction(quit_editor_action)

    def _set_edit_menu(self):
        undo_action = QAction('撤销', self)
        redo_action = QAction('重做', self)
        cut_action = QAction('剪切', self)
        copy_action = QAction('复制', self)
        paste_action = QAction('粘贴', self)
        select_all_action = QAction('全选', self)
        self._edit_menu.addAction(undo_action)
        self._edit_menu.addAction(redo_action)
        self._edit_menu.addAction(cut_action)
        self._edit_menu.addAction(copy_action)
        self._edit_menu.addSeparator()
        self._edit_menu.addAction(paste_action)
        self._edit_menu.addAction(select_all_action)

    def _set_project_menu(self):
        run_action = QAction('运行', self)
        package_action = QAction('打包', self)
        # package_action.triggered.connect()

        self._project_menu.addAction(run_action)
        self._project_menu.addAction(package_action)

    def _set_help_menu(self):
        doc_action = QAction('在线文档', self)
        update_log_action = QAction('更新日志', self)
        github_action = QAction('Github仓库', self)
        about_action = QAction('关于Pygame Studio', self)

        self._help_menu.addAction(doc_action)
        self._help_menu.addSeparator()
        self._help_menu.addAction(update_log_action)
        self._help_menu.addAction(github_action)
        self._help_menu.addSeparator()
        self._help_menu.addAction(about_action)

    def get_ready_for_project(self, project_path):
        self._game_manager.get_ready_for_project(project_path)
        self._asset_window.get_ready_for_project()
        self._console_window.get_ready_for_project()
        self._hierarchy_window.get_ready_for_project()
        self._inspector_window.get_ready_for_project()

    def clean_up(self):
        self._scene_widnow.clean_up()
        self._asset_window.clean_up()
        self._console_window.clean_up()
        self._hierarchy_window.clean_up()
        self._inspector_window.clean_up()
        self._game_manager.clean_up()

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().enterEvent(event)


class Editor(WindowBase):
    close_signal = Signal()
    
    def __init__(self, parent):
        super().__init__()
        self._parent = parent
        self._game_manager = GameManager()
        self._editor_body = EditorBody(self._game_manager)

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.resize(1420, 930)
        self._center()
        self.set_window_body(self._editor_body)

    def _set_signal(self):
        self._editor_body.new_project_signal.connect(self._new_project)
        self._editor_body.open_project_signal.connect(self._open_project)
        self._editor_body.quit_editor_signal.connect(self.close)

        self._game_manager.scene_saved_signal.connect(self._update_window_title)
        self._game_manager.scene_loaded_signal.connect(self._update_window_title)
        self._game_manager.scene_renamed_signal.connect(self._update_window_title)

    def _new_project(self):
        self._parent.show_dashboard_and_create_project_window()

    def _open_project(self):
        self._parent.show_dashboard()

    def _center(self):
        screen = QApplication.primaryScreen()
        screen_width = screen.availableGeometry().width()
        screen_height = screen.availableGeometry().height()
 
        pos_x = screen_width/2 - self.frameGeometry().width()/2
        pos_y = screen_height/2 - self.frameGeometry().height()/2
 
        self.move(int(pos_x), int(pos_y))

    def _update_window_title(self):
        """Set the window title (Pygame Studio + current scene name + project path)"""
        project_path = self._game_manager.get_project_path()
        current_scene_name = Path(self._game_manager.current_scene_file_path).name if self._game_manager.current_scene_file_path else 'untitled.scene'
        self.window_title.set_title_name(f'Pygame Studio - {current_scene_name} - {project_path}')

    def get_ready_for_project(self, project_path):
        self._editor_body.get_ready_for_project(project_path)
        self._update_window_title()

    def clean_up(self):
        self._editor_body.clean_up()

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_S:
                print('保存')
                self._game_manager.save_scene()
            elif event.key() == Qt.Key.Key_Z:
                print('撤销')
                self._game_manager.undo_stack.undo()
            elif event.key() == Qt.Key.Key_Y:
                print('重做')
                self._game_manager.undo_stack.redo()

        elif event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            if event.key() == Qt.Key.Key_Z:
                print('重做')
                self._game_manager.undo_stack.redo()

        super().keyPressEvent(event)

    def closeEvent(self, event):
        if not self._game_manager.is_current_scene_saved():
            choice = QMessageBox.warning(self, '保存提醒', '当前场景数据已修改，是否保存？', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            if choice == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            
            if choice == QMessageBox.StandardButton.Yes:
                self._game_manager.save_scene()

        self.clean_up()
        self._parent.show_dashboard()
        event.accept()