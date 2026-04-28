from PySide6.QtGui import QAction
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu
from pygamestudio.gui.asset.type import *
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
    open_in_terminal_signal = Signal()
    open_externally_signal = Signal()
    show_in_explorer_signal = Signal()

    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
        self._tree_view = parent

    def _add_actions(self, index_type):
        edit_action = QAction(T.tr('menu.edit', 'Edit'), self)
        add_folder_action = QAction(T.tr('menu.folder', 'Folder'), self)
        add_script_action = QAction(T.tr('menu.script', 'Script'), self)
        add_scene_action = QAction(T.tr('menu.scene', 'Scene'), self)
        add_txt_action = QAction('TXT', self)
        add_json_action = QAction('JSON', self)
        cut_action = QAction(T.tr('menu.cut', 'Cut'), self)
        copy_action = QAction(T.tr('menu.copy', 'Copy'), self)
        paste_action = QAction(T.tr('menu.paste', 'Paste'), self)
        delete_action = QAction(T.tr('menu.delete', 'Delete'), self)
        rename_action = QAction(T.tr('menu.rename', 'Rename'), self)
        duplicate_action = QAction(T.tr('menu.duplicate', 'Duplicate'), self)
        copy_uuid_action = QAction(T.tr('menu.copy_uuid', 'Copy UUID'), self)
        copy_path_action = QAction(T.tr('menu.copy_path', 'Copy Path'), self)
        copy_name_action = QAction(T.tr('menu.copy_name', 'Copy Name'), self)
        open_in_terminal_action = QAction(T.tr('menu.open_in_terminal', 'Open in Terminal'), self)
        open_externally_action = QAction(T.tr('menu.open_externally', 'Open Externally'), self)
        show_in_explorer_action = QAction(T.tr('menu.show_in_explorer', 'Show in Explorer'), self)

        edit_action.triggered.connect(self.open_externally_signal.emit)
        add_folder_action.triggered.connect(lambda: self.add_signal.emit(INDEX_FOLDER))
        add_script_action.triggered.connect(lambda: self.add_signal.emit(INDEX_SCRIPT))
        add_scene_action.triggered.connect(lambda: self.add_signal.emit(INDEX_SCENE))
        add_txt_action.triggered.connect(lambda: self.add_signal.emit(INDEX_TXT))
        add_json_action.triggered.connect(lambda: self.add_signal.emit(INDEX_JSON))
        cut_action.triggered.connect(self.cut_signal.emit)
        copy_action.triggered.connect(self.copy_signal.emit)
        paste_action.triggered.connect(self.paste_signal.emit)
        delete_action.triggered.connect(self.delete_signal.emit)
        rename_action.triggered.connect(self.rename_signal.emit)
        duplicate_action.triggered.connect(self.duplicate_signal.emit)
        copy_uuid_action.triggered.connect(self.copy_uuid_signal.emit)
        copy_path_action.triggered.connect(self.copy_path_signal.emit)
        copy_name_action.triggered.connect(self.copy_name_signal.emit)
        open_in_terminal_action.triggered.connect(self.open_in_terminal_signal.emit)
        open_externally_action.triggered.connect(self.open_externally_signal.emit)
        show_in_explorer_action.triggered.connect(self.show_in_explorer_signal.emit)
        
        add_menu = QMenu(title=T.tr('menu.add', 'Add'), parent=self)
        text_file_sub_menu = QMenu(title=T.tr('menu.text_file', 'Text File'), parent=self)

        # Create actions that are for all index types.
        self.addMenu(add_menu)
        add_menu.addAction(add_folder_action)
        add_menu.addAction(add_script_action)
        add_menu.addAction(add_scene_action)
        text_file_sub_menu.addAction(add_txt_action)
        text_file_sub_menu.addAction(add_json_action)
        add_menu.addMenu(text_file_sub_menu)

        # Right click on the blank area.
        if index_type == INDEX_INVALID:
            self.addSeparator()
            self.addAction(paste_action)
            self.addSeparator()
            self.addAction(open_in_terminal_action)
            self.addAction(show_in_explorer_action)

        # Right click on the folder or file index.
        else:
            self.addSeparator()
            self.addAction(cut_action)
            self.addAction(copy_action)
            self.addAction(duplicate_action)
            self.addAction(paste_action)
            self.addAction(rename_action)

            self.addSeparator()
            self.addAction(delete_action)

            self.addSeparator()
            copy_menu = QMenu(title=T.tr('menu.copy_menu_title', 'Copy Path | Name | UUID'), parent=self)
            copy_menu.addAction(copy_path_action)
            copy_menu.addAction(copy_name_action)
            copy_menu.addAction(copy_uuid_action)
            self.addMenu(copy_menu)

            self.addSeparator()
            self.addAction(open_in_terminal_action)
            self.addAction(show_in_explorer_action)

        # Right click on the specific file index.
        if index_type == INDEX_FILE:
            self.insertAction(add_menu.menuAction(), edit_action)
            self.insertSeparator(add_menu.menuAction())
            self.insertAction(show_in_explorer_action, open_externally_action)
        
        self._set_paste_action_status(paste_action)

    def _set_paste_action_status(self, paste_action):
        if self._tree_view.get_clipboard_content():
            paste_action.setEnabled(True)
        else:
            paste_action.setEnabled(False)
        
    def show(self, pos, index_type):
        self.clear()
        self._add_actions(index_type)
        self.exec(pos)