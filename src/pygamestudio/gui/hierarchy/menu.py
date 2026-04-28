from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.game.object.type import *
from pygamestudio.common.i18n.translator import Translator as T


class ContextMenu(QMenu):
    add_signal = Signal(str)
    cut_signal = Signal()
    copy_signal = Signal()
    paste_signal = Signal()
    delete_signal = Signal()
    rename_signal = Signal()
    duplicate_signal = Signal()
    copy_uuid_signal = Signal()
    copy_path_signal = Signal()
    copy_name_signal = Signal()

    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
        self._parent = parent

    def _add_actions(self, item_type):
        # add_line_action = QAction(T.tr('item.line', 'Line'), self)
        add_rect_action = QAction(T.tr('item.rect', 'Rect'), self)
        add_ellipse_action = QAction(T.tr('item.ellipse', 'Ellipse'), self)
        add_text_action = QAction(T.tr('item.text', 'Text'), self)
        cut_action = QAction(T.tr('menu.cut', 'Cut'), self)
        copy_action = QAction(T.tr('menu.copy', 'Copy'), self)
        paste_action = QAction(T.tr('menu.paste', 'Paste'), self)
        delete_action = QAction(T.tr('menu.delete', 'Delete'), self)
        rename_action = QAction(T.tr('menu.rename', 'Rename'), self)
        duplicate_action = QAction(T.tr('menu.duplicate', 'Duplicate'), self)
        copy_uuid_action = QAction(T.tr('menu.copy_uuid', 'Copy UUID'), self)
        copy_path_action = QAction(T.tr('menu.copy_path', 'Copy Path'), self)
        copy_name_action = QAction(T.tr('menu.copy_name', 'Copy Name'), self)

        # add_line_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_LINE))
        add_rect_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_RECT))
        add_ellipse_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_ELLIPSE))
        add_text_action.triggered.connect(lambda: self.add_signal.emit(OBJECT_TEXT))
        cut_action.triggered.connect(self.cut_signal.emit)
        copy_action.triggered.connect(self.copy_signal.emit)
        paste_action.triggered.connect(self.paste_signal.emit)
        delete_action.triggered.connect(self.delete_signal.emit)
        rename_action.triggered.connect(self.rename_signal.emit)
        duplicate_action.triggered.connect(self.duplicate_signal.emit)
        copy_uuid_action.triggered.connect(self.copy_uuid_signal.emit)
        copy_path_action.triggered.connect(self.copy_path_signal.emit)
        copy_name_action.triggered.connect(self.copy_name_signal.emit)

        # Create actions that are for all object types.
        add_menu = QMenu(title=T.tr('menu.add', 'Add'), parent=self)
        add_shape_sub_menu = QMenu(title=T.tr('item.shape', 'Shape'), parent=self)
        add_ui_sub_menu = QMenu(title='UI', parent=self)

        self.addMenu(add_menu)
        add_menu.addMenu(add_shape_sub_menu)
        add_menu.addMenu(add_ui_sub_menu)

        # add_shape_sub_menu.addAction(add_line_action)
        add_shape_sub_menu.addAction(add_rect_action)
        add_shape_sub_menu.addAction(add_ellipse_action)
        add_ui_sub_menu.addAction(add_text_action)

        # Right click on the blank area.
        if item_type is None:
            self.addAction(paste_action)

        # Right click on the root object.
        elif item_type == OBJECT_CANVAS:
            self.addAction(paste_action)
            self.addSeparator()
            copy_menu = QMenu(title=T.tr('menu.copy_menu_title', 'Copy Path | Name | UUID'), parent=self)
            copy_menu.addAction(copy_path_action)
            copy_menu.addAction(copy_name_action)
            copy_menu.addAction(copy_uuid_action)
            self.addMenu(copy_menu)

        # Right click on the regular object.
        else:
            self.addSeparator()
            self.addAction(cut_action)
            self.addAction(copy_action)
            self.addAction(duplicate_action)
            self.addAction(paste_action)
            self.addSeparator()
            self.addAction(delete_action)
            self.addAction(rename_action)
            self.addSeparator()
            copy_menu = QMenu(title=T.tr('menu.copy_menu_title', 'Copy Path | Name | UUID'), parent=self)
            copy_menu.addAction(copy_path_action)
            copy_menu.addAction(copy_name_action)
            copy_menu.addAction(copy_uuid_action)
            self.addMenu(copy_menu)

        self._set_paste_action_status(paste_action)

    def _set_paste_action_status(self, paste_action):
        if self._parent.get_clipboard_content():
            paste_action.setEnabled(True)
        else:
            paste_action.setEnabled(False)
        
    def show(self, pos, object_type):
        self.clear()
        self._add_actions(object_type)
        self.exec(pos)