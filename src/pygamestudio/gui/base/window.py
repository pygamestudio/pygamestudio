from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.utils.theme import set_editor_theme
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
        pixmap = QPixmap(':/images/logo.png')
        scaled_pixmap = pixmap.scaled(self._icon.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._icon.setPixmap(scaled_pixmap)
        self._icon.setScaledContents(True)
        
        self._minimize_btn.setIcon(QIcon(':/images/minimize.png'))
        self._maximize_btn.setIcon(QIcon(':/images/maximize.png'))
        self._close_btn.setIcon(QIcon(':/images/close.png'))
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
            self._maximize_btn.setIcon(QIcon(':/images/maximize.png'))
        else:
            self.window_maximized.emit()
            self._is_maximized = True
            self._maximize_btn.setIcon(QIcon(':/images/normalize.png'))

    def _close_window(self):
        self.window_closed.emit()

    def set_maximize_button_disabled(self):
        self._maximize_btn.setEnabled(False)
        self._maximize_btn.setIcon(QIcon(':/images/maximize_disabled.png'))

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
        self._start_geometry = None
        self._start_global_pos = None

        self.__setup()

    def __setup(self):
        self.__set_widget()
        self.__set_signal()
        self.__set_object_name()
        set_editor_theme()

    def __set_widget(self):
        self.setMouseTracking(True)
        self.central_widget.setMouseTracking(True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setWindowIcon(QIcon(':/images/logo.png'))
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
            self._start_geometry = self.geometry()
            self._start_global_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        self._stretch_type = self._get_stretch_type(event.position().x(), event.position().y())

        if self._is_stretching and self._stretch_type:
            self._resize_window(event.globalPosition().toPoint())

    def _resize_window(self, global_pos):
        start = self._start_geometry
        if start is None or self._start_global_pos is None:
            return

        min_w = self.minimumWidth() or 200
        min_h = self.minimumHeight() or 150

        dx = global_pos.x() - self._start_global_pos.x()
        dy = global_pos.y() - self._start_global_pos.y()

        new_rect = QRect(start)

        if self._stretch_type == 'RIGHT':
            new_rect.setWidth(max(min_w, start.width() + dx))

        elif self._stretch_type == 'LEFT':
            new_x = start.x() + dx
            new_width = start.width() - dx
            if new_width < min_w:
                new_width = min_w
                new_x = start.x() + start.width() - min_w
            new_rect.setX(new_x)
            new_rect.setWidth(new_width)

        elif self._stretch_type == 'BOTTOM':
            new_rect.setHeight(max(min_h, start.height() + dy))

        elif self._stretch_type == 'TOP':
            new_y = start.y() + dy
            new_height = start.height() - dy
            if new_height < min_h:
                new_height = min_h
                new_y = start.y() + start.height() - min_h
            new_rect.setY(new_y)
            new_rect.setHeight(new_height)

        elif self._stretch_type == 'BOTTOM_RIGHT':
            new_rect.setWidth(max(min_w, start.width() + dx))
            new_rect.setHeight(max(min_h, start.height() + dy))

        elif self._stretch_type == 'BOTTOM_LEFT':
            new_x = start.x() + dx
            new_width = start.width() - dx
            if new_width < min_w:
                new_width = min_w
                new_x = start.x() + start.width() - min_w
            new_rect.setX(new_x)
            new_rect.setWidth(new_width)
            new_rect.setHeight(max(min_h, start.height() + dy))

        elif self._stretch_type == 'TOP_LEFT':
            new_x = start.x() + dx
            new_width = start.width() - dx
            if new_width < min_w:
                new_width = min_w
                new_x = start.x() + start.width() - min_w
            new_rect.setX(new_x)
            new_rect.setWidth(new_width)

            new_y = start.y() + dy
            new_height = start.height() - dy
            if new_height < min_h:
                new_height = min_h
                new_y = start.y() + start.height() - min_h
            new_rect.setY(new_y)
            new_rect.setHeight(new_height)

        elif self._stretch_type == 'TOP_RIGHT':
            new_rect.setWidth(max(min_w, start.width() + dx))

            new_y = start.y() + dy
            new_height = start.height() - dy
            if new_height < min_h:
                new_height = min_h
                new_y = start.y() + start.height() - min_h
            new_rect.setY(new_y)
            new_rect.setHeight(new_height)

        self.setGeometry(new_rect)

    def mouseReleaseEvent(self, event):
        self._is_stretching = False
        self._stretch_type = None
        self._start_geometry = None
        self._start_global_pos = None


class DetachButton(QPushButton):
    """Icon-only button that toggles a panel between its tab and its own window.

    Docked panels show ``detatch.png`` (the click pops the panel out into a
    standalone window), detached ones show ``attach.png`` (the click puts it
    back into its tab). The tooltip follows the editor language.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_detached = False
        self.setObjectName('codeEditorDetachBtn')  # shared QSS look
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(16, 16))
        T.add_observer(self)
        self.refresh()

    def set_detached(self, detached):
        """Switch the icon/tooltip to the detached (or docked) state."""
        detached = bool(detached)
        changed = detached != self._is_detached
        self._is_detached = detached
        self.refresh()
        if changed:
            # a real detach/attach reparented the button: drop the stale
            # hover/press highlight (see clear_press_state)
            self.clear_press_state()

    def clear_press_state(self):
        """Drop the hover/pressed highlighting after the window changed.

        Detaching (or re-docking) reparents the button WHILE it is still
        "under the mouse": the widget moves out from under the cursor instead
        of the cursor leaving it, so Qt never delivers the matching leave
        event and the button would keep its highlighted/hover look forever.
        """
        self.setDown(False)
        self.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
        self.update()

    def is_detached(self):
        return self._is_detached

    def refresh(self):
        self.setIcon(QIcon(':/images/attach.png' if self._is_detached
                           else ':/images/detatch.png'))
        if self._is_detached:
            self.setToolTip(T.tr('panel.attach_to_tabs', 'Attach to Tabs'))
        else:
            self.setToolTip(T.tr('panel.detach', 'Detach into Its Own Window'))

    def retranslate(self):
        self.refresh()


class PanelStandaloneWindow(WindowBase):
    """Frameless top-level window hosting a panel while it is detached."""

    def __init__(self, panel, title, size=(900, 600)):
        super().__init__()
        self._panel = panel
        self.resize(*size)
        self.set_window_body(panel)
        self.window_title.set_title_name(title)

    def closeEvent(self, event):
        # Closing the standalone window re-docks the panel into its tab.
        if self._panel is not None:
            self._panel.attach()
            event.ignore()
            return
        super().closeEvent(event)


class DetachablePanel:
    """Mixin giving a docked panel "detach into its own window" behaviour.

    Mix it in BEFORE the widget base (``class Panel(DetachablePanel, QWidget)``):
    the mixin creates the ``DetachButton`` (``detach_button()``) and implements
    detach/attach, the standalone window, re-docking on close and the
    tab/standalone titles. The panel only places the button, implements
    ``_tab_title()`` and calls ``set_tab_widget()`` (the editor body does that
    when it docks the panel).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tab_widget = None
        self._detached = False
        self._standalone_window = None
        self._detach_btn = DetachButton()
        self._detach_btn.clicked.connect(self.toggle_detached)

    # ------------------------------------------------------------------ api
    def detach_button(self):
        """The button that toggles the standalone window (the panel places it)."""
        return self._detach_btn

    def set_tab_widget(self, tab_widget):
        """The tab widget this panel is docked into."""
        self._tab_widget = tab_widget

    def is_detached(self):
        return self._detached

    # -------------------------------------------------------------- titles
    def _tab_title(self):
        return T.tr('panel.window', 'Pygame Studio')

    def _window_title(self):
        return ' Pygame Studio - {}'.format(self._tab_title())

    def update_window_titles(self):
        """Refresh the tab label and/or the standalone window title."""
        if self._detached:
            if self._standalone_window is not None:
                self._standalone_window.window_title.set_title_name(self._window_title())
            return
        if self._tab_widget is not None and self._tab_widget.indexOf(self) >= 0:
            self._tab_widget.setTabText(self._tab_widget.indexOf(self), self._tab_title())

    # ------------------------------------------------------ detach / attach
    def toggle_detached(self):
        if self._detached:
            self.attach()
        else:
            self.detach()

    def detach(self):
        """Undock the panel into its own frameless top-level window."""
        if self._detached or self._tab_widget is None:
            return
        index = self._tab_widget.indexOf(self)
        if index >= 0:
            self._tab_widget.removeTab(index)
        self.setParent(None)
        self._standalone_window = PanelStandaloneWindow(
            self, self._window_title(), self.standalone_window_size())
        self.show()
        self._standalone_window.show()
        self._detached = True
        self._detach_btn.set_detached(True)

    def attach(self):
        """Re-dock the panel into its tab widget."""
        if not self._detached or self._tab_widget is None:
            return
        standalone = self._standalone_window
        self._standalone_window = None
        if standalone is not None:
            standalone._panel = None
            standalone.hide()
            standalone.deleteLater()
        if self._tab_widget.indexOf(self) < 0:
            self._tab_widget.insertTab(self._dock_index(), self, self._tab_title())
        self._tab_widget.setCurrentWidget(self)
        self.show()
        self._detached = False
        self._detach_btn.set_detached(False)

    def redock(self):
        """Re-dock unless the panel is already docked (project close/switch)."""
        if self._detached:
            self.attach()

    def _dock_index(self):
        """Tab index the panel returns to when it is re-docked."""
        return 0

    def standalone_window_size(self):
        """Initial size of the standalone window."""
        return (900, 600)

    def raise_editor(self):
        """Bring the panel to the front (its tab, or its standalone window)."""
        if self._detached:
            if self._standalone_window is not None:
                self._standalone_window.show()
                self._standalone_window.raise_()
                self._standalone_window.activateWindow()
        elif self._tab_widget is not None:
            self._tab_widget.setCurrentWidget(self)

    def closeEvent(self, event):
        # Closing the detached window returns the panel to its tab.
        if self._detached:
            self.attach()
            event.ignore()
            return
        super().closeEvent(event)