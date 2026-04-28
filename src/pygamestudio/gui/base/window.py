
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.common.i18n.translator import Translator as T


class WindowTitleBase(QWidget):
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
        self._name_label.setText('Pygame Studio')

        self._icon.setFixedSize(20, 20)
        pixmap = QPixmap(str(RES_PATH / 'images/logo.png'))
        scaled_pixmap = pixmap.scaled(self._icon.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._icon.setPixmap(scaled_pixmap)
        
        self._minimize_btn.setIcon(QIcon(str(RES_PATH / 'images/minimize.png')))
        self._maximize_btn.setIcon(QIcon(str(RES_PATH / 'images/maximize.png')))
        self._close_btn.setIcon(QIcon(str(RES_PATH / 'images/close.png')))
        self._minimize_btn.setFixedSize(20, 20)
        self._maximize_btn.setFixedSize(20, 20)
        self._close_btn.setFixedSize(20, 20)
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
        main_h_layout.setContentsMargins(3, 3, 0, 3)

    def _set_object_name(self):
        self._name_label.setObjectName('windowTitleBaseNameLabel')
        self._minimize_btn.setObjectName('windowTitleBaseMinimizeBtn')
        self._maximize_btn.setObjectName('windowTitleBaseMaximizeBtn')
        self._close_btn.setObjectName('windowTitleBaseCloseBtn')

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

    def set_title_name(self, name):
        self._name_label.setText(name)

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
    

class WindowBase(QWidget):
    def __init__(self):
        super().__init__()
        self.window_title = WindowTitleBase()
        self.window_body = QWidget()
        self.central_widget = QWidget()
        self.central_v_layout = QVBoxLayout(self.central_widget)

        self._stretch_type = None
        self._is_stretching = False
        self._stretch_area_offset = 10

        self.__setup()

    def __setup(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_object_name()
        self.__set_editor_theme()

    def __set_widget(self):
        self.setMouseTracking(True)
        self.central_widget.setMouseTracking(True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setWindowIcon(QIcon(str(RES_PATH/'images/logo.png')))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def __set_signal(self):
        self.window_title.window_moved.connect(self._move)
        self.window_title.window_closed.connect(self.close)
        self.window_title.window_normalized.connect(self.showNormal)
        self.window_title.window_maximized.connect(self.showMaximized)
        self.window_title.window_minimized.connect(self.showMinimized)

    def __set_layout(self):
        self.central_v_layout.addWidget(self.window_title)
        self.central_v_layout.addWidget(self.window_body)
        self.central_v_layout.setContentsMargins(5, 5, 5, 5)

        main_v_layout = QVBoxLayout(self)
        main_v_layout.addWidget(self.central_widget)
        main_v_layout.setContentsMargins(0, 0, 0, 0)
    
    def __set_object_name(self):
        self.central_widget.setObjectName('windowBaseCentralWidget')

    def __set_editor_theme(self, theme='dark'):
        theme_qss_path = RES_PATH / f'qss/{theme}.qss'
        if not theme_qss_path.exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_read_qss_content', 'The theme QSS file {}.qss does not exist!').format(theme))
            return
        
        with open(theme_qss_path, 'r', encoding='utf-8') as f:
            self.setStyleSheet(f.read())

    def set_window_body(self, window_body):
        self.window_body = window_body
        self.__set_layout()

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