from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.game.object.manager import ObjectManager
from pygamestudio.editor.gui.hierarchy.window import HierarchyWindow
from pygamestudio.editor.gui.asset.window import AssetWindow
from pygamestudio.editor.gui.console.window import ConsoleWindow
from pygamestudio.editor.gui.inspector.window import InspectorWindow
from pygamestudio.editor.gui.scene.window import SceneWindow


class EditorTitle(QWidget):
    window_minimized = Signal()
    window_maximized = Signal()
    window_normalized = Signal()
    window_closed = Signal()
    window_moved = Signal(int, int)

    def __init__(self):
        super().__init__()
        self._icon = QLabel()
        self._name_label = QLabel()
        self._minimize_btn = QPushButton()
        self._maximize_btn = QPushButton()
        self._close_btn = QPushButton()

        self._is_maximized = False
        self._start_x = None
        self._start_y = None

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self.resize(1420, 30)
        self.setFixedHeight(30)

        self._name_label.setText('Pygame Studio')

        self._icon.setFixedSize(20, 20)
        pixmap = QPixmap(str(RES_PATH / 'images/logo.png'))
        scaled_pixmap = pixmap.scaled(self._icon.size())
        self._icon.setPixmap(scaled_pixmap)

        self._minimize_btn.setIcon(QIcon(str(RES_PATH / 'images/minimize.png')))
        self._maximize_btn.setIcon(QIcon(str(RES_PATH / 'images/maximize.png')))
        self._close_btn.setIcon(QIcon(str(RES_PATH / 'images/close.png')))
        self._minimize_btn.setToolTip('Minimize')
        self._maximize_btn.setToolTip('Maximize')
        self._close_btn.setToolTip('Close')

    def _set_signal(self):
        self._minimize_btn.clicked.connect(self._minimize_window)
        self._maximize_btn.clicked.connect(self._maximize_or_normalize_window)
        self._close_btn.clicked.connect(self._close_window)

    def _set_layout(self):
        main_h_layout = QHBoxLayout(self)
        
        left_h_layout = QHBoxLayout()
        left_h_layout.addWidget(self._icon)
        left_h_layout.addWidget(self._name_label)

        right_h_layout = QHBoxLayout()
        right_h_layout.addWidget(self._minimize_btn)
        right_h_layout.addWidget(self._maximize_btn)
        right_h_layout.addWidget(self._close_btn)
        right_h_layout.setSpacing(10)

        main_h_layout.addLayout(left_h_layout)
        main_h_layout.addStretch(1)
        main_h_layout.addLayout(right_h_layout)
        main_h_layout.setContentsMargins(5, 8, 5, 5)

    def _set_object_name(self):
        self.setObjectName('editorTitle')
        self._name_label.setObjectName('editorTitleNameLabel')
        self._minimize_btn.setObjectName('editorTitleMinimizeBtn')
        self._maximize_btn.setObjectName('editorTitleMaximizeBtn')
        self._close_btn.setObjectName('editorTitleCloseBtn')

    def _minimize_window(self):
        self.window_minimized.emit()

    def _maximize_or_normalize_window(self):
        if self._is_maximized:
            self.window_normalized.emit()
            self._is_maximized = False
            self._maximize_btn.setIcon(QIcon(str(RES_PATH / 'images/maximize.png')))
        else:
            self.window_maximized.emit()
            self._is_maximized = True
            self._maximize_btn.setIcon(QIcon(str(RES_PATH / 'images/normalize.png')))

    def _close_window(self):
        self.window_closed.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_x = event.position().x()
            self._start_y = event.position().y()
    
    def mouseMoveEvent(self, event):
        if self._start_x is not None and self._start_y is not None:
            dis_x = event.position().x() - self._start_x
            dis_y = event.position().y() - self._start_y
            self.window_moved.emit(dis_x, dis_y)

    def mouseReleaseEvent(self, event):
        self._start_x = None
        self._start_y = None

    def mouseDoubleClickEvent(self, event):
        self._maximize_or_normalize_window()

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().enterEvent(event)
    

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


class Editor(QWidget):
    def __init__(self):
        super().__init__()
        self._object_manager = ObjectManager()
        self._editor_title = EditorTitle()
        self._editor_body = EditorBody(self._object_manager)
        self._central_widget = QWidget()

        self._stretch_type = None
        self._is_stretching = False
        self._stretch_area_offset = 10

        self._setup()
        self.move(50, 50)   # 改成屏幕居中

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()
        self._set_editor_theme()

    def _set_widget(self):
        self.resize(1420, 930)
        self.setMouseTracking(True)
        self._central_widget.setMouseTracking(True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def _set_signal(self):
        self._editor_title.window_moved.connect(self._move)
        self._editor_title.window_closed.connect(self.close)
        self._editor_title.window_normalized.connect(self.showNormal)
        self._editor_title.window_maximized.connect(self.showMaximized)
        self._editor_title.window_minimized.connect(self.showMinimized)

    def _set_layout(self):
        central_v_layout = QVBoxLayout(self._central_widget)
        central_v_layout.addWidget(self._editor_title)
        central_v_layout.addWidget(self._editor_body)
        central_v_layout.setContentsMargins(5, 5, 5, 5)

        main_v_layout = QVBoxLayout(self)
        main_v_layout.addWidget(self._central_widget)
        main_v_layout.setContentsMargins(0, 0, 0, 0)

    def _set_object_name(self):
        self.setObjectName('editor')
        self._central_widget.setObjectName('editorCentralWidget')

    def _set_editor_theme(self, theme='white'):
        theme_qss_path = RES_PATH / f'qss/{theme}.qss'
        if not theme_qss_path.exists():
            QMessageBox.critical(self, '错误', '该主题QSS文件不存在！')
            return
        
        with open(theme_qss_path, 'r', encoding='utf-8') as f:
            self.setStyleSheet(f.read())

    def _move(self, dis_x, dis_y):
        self.move(self.x() + dis_x, self.y() + dis_y)

    def _get_stretch_type(self, x, y):
        if self._is_stretching and self._stretch_type:
            return self._stretch_type
        
        stretch_type = None

        # right border
        if x >= self.width() - self._stretch_area_offset and self._stretch_area_offset <= y <= self.height() - self._stretch_area_offset:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            stretch_type = 'RIGHT'
        
        # left border
        elif x <= self._stretch_area_offset and self._stretch_area_offset <= y <= self.height() - self._stretch_area_offset:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            stretch_type = 'LEFT'

        # bottom border
        elif self._stretch_area_offset <= x <= self.width() - self._stretch_area_offset and y >= self.height() - self._stretch_area_offset:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            stretch_type = 'BOTTOM'

        # top border
        elif self._stretch_area_offset <= x <= self.width() - self._stretch_area_offset and y <= self._stretch_area_offset:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            stretch_type = 'TOP'
        
        # bottom right corner
        elif x > self.width() - self._stretch_area_offset and y > self.height() - self._stretch_area_offset:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            stretch_type = 'BOTTOM_RIGHT'
        
        # bottom left corner
        elif x < self._stretch_area_offset and y > self.height() - self._stretch_area_offset:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            stretch_type = 'BOTTOM_LEFT'

        # top left corner
        elif x < self._stretch_area_offset and y < self._stretch_area_offset:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            stretch_type = 'TOP_LEFT'

        # top right corner
        elif x > self.width() - self._stretch_area_offset and y < self._stretch_area_offset:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            stretch_type = 'TOP_RIGHT'

        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            stretch_type = None

        return stretch_type

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._stretch_type:
            self._is_stretching = True

    def mouseMoveEvent(self, event):
        self._stretch_type = self._get_stretch_type(event.position().x(), event.position().y())

        if self._is_stretching and self._stretch_type:
            if self._stretch_type == 'RIGHT':
                self.resize(event.position().x(), self.height())

            if self._stretch_type == 'LEFT':
                if self.width()-event.position().x() < self.minimumWidth():
                    self.setGeometry(self.geometry().x(), self.geometry().y(), self.minimumWidth(), self.height())
                else:
                    self.setGeometry(self.geometry().x()+event.position().x(), self.geometry().y(), self.width()-event.position().x(), self.height())

            elif self._stretch_type == 'BOTTOM':
                self.resize(self.width(), event.position().y())
            
            elif self._stretch_type == 'TOP':
                if self.height()-event.position().y() < self.minimumHeight():
                    self.setGeometry(self.geometry().x(), self.geometry().y(), self.width(), self.minimumHeight())
                else:
                    self.setGeometry(self.geometry().x(), self.geometry().y()+event.position().y(), self.width(), self.height()-event.position().y())
            
            elif self._stretch_type == 'BOTTOM_RIGHT':
                self.resize(event.position().x(), event.position().y())
            
            elif self._stretch_type == 'BOTTOM_LEFT':
                if self.width()-event.position().x() < self.minimumWidth():
                    self.setGeometry(self.geometry().x(), self.geometry().y(), self.minimumWidth(), event.position().y())
                else:
                    self.setGeometry(self.geometry().x()+event.position().x(), self.geometry().y(), self.width()-event.position().x(), event.position().y())

            elif self._stretch_type == 'TOP_LEFT':
                if self.width()-event.position().x() < self.minimumWidth() and  self.height()-event.position().y() >= self.minimumHeight():
                    self.setGeometry(self.geometry().x(), self.geometry().y()+event.position().y(), self.minimumWidth(), self.height()-event.position().y())                
                elif self.height()-event.position().y() < self.minimumHeight() and self.width()-event.position().x() >= self.minimumWidth():
                    self.setGeometry(self.geometry().x()+event.position().x(), self.geometry().y(), self.width()-event.position().x(), self.minimumHeight())                
                elif self.width()-event.position().x() < self.minimumWidth() and self.height()-event.position().y() < self.minimumHeight():
                    self.setGeometry(self.geometry().x(), self.geometry().y(), self.minimumWidth(), self.minimumHeight())                
                else:
                    self.setGeometry(self.geometry().x()+event.position().x(), self.geometry().y()+event.position().y(), self.width()-event.position().x(), self.height()-event.position().y())                
            
            elif self._stretch_type == 'TOP_RIGHT':
                if self.height()-event.position().y() < self.minimumHeight():
                    self.setGeometry(self.geometry().x(), self.geometry().y(), event.position().x(), self.minimumHeight())
                else:
                    self.setGeometry(self.geometry().x(), self.geometry().y()+event.position().y(), event.position().x(), self.height()-event.position().y())

    def mouseReleaseEvent(self, event):
        self._is_stretching = False

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