from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.game.object.type import *
from pygamestudio.common.i18n.translator import Translator as T


class ExpandCollapseAllButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.setToolTip(T.tr('hierarchy.expand_or_collapse_all', 'Expand or Collapse All'))
        self.setIcon(QIcon(':/images/expand_or_collapse_all.png'))

    def _set_signal(self):
        T.add_observer(self)

    def retranslate(self):
        self.setToolTip(T.tr('hierarchy.expand_or_collapse_all', 'Expand or Collapse All'))


class AddItemButton(QPushButton):
    add_signal = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
    
    def _set_widget(self):
        self.setToolTip(T.tr('hierarchy.add', 'Add'))
        self.setIcon(QIcon(':/images/add_item.png'))

    def _set_signal(self):
        T.add_observer(self)
 
    def retranslate(self):
        self.setToolTip(T.tr('hierarchy.add', 'Add'))

    def mousePressEvent(self, event):
        self._show_context_menu(event.pos())
        super().mousePressEvent(event)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        # add_line_action = QAction(T.tr('item.line', 'Line'), self)
        add_rect_action = QAction(T.tr('item.rect', 'Rect'), self)
        add_ellipse_action = QAction(T.tr('item.ellipse', 'Ellipse'), self)
        add_text_action = QAction(T.tr('item.text', 'Text'), self)

        # add_line_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_LINE))
        add_rect_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_RECT))
        add_ellipse_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_ELLIPSE))
        add_text_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_TEXT))

        add_shape_sub_menu = QMenu(title=T.tr('item.shape', 'Shape'), parent=self)
        add_ui_sub_menu = QMenu(title='UI', parent=self)
        menu.addMenu(add_shape_sub_menu)
        menu.addMenu(add_ui_sub_menu)

        # add_shape_sub_menu.addAction(add_line_action)
        add_shape_sub_menu.addAction(add_rect_action)
        add_shape_sub_menu.addAction(add_ellipse_action)
        add_ui_sub_menu.addAction(add_text_action)

        menu.exec(self.mapToGlobal(pos))

