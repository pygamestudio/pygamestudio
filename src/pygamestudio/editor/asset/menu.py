from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtGui import QAction
from PySide6.QtCore import Signal
from pygamestudio.editor.asset.type import *


class ContextMenu(QMenu):
    create_signal = Signal(str)
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
        self.__parent = parent

    def __add_actions(self, item_type, is_root_item=False):
        edit_action = QAction('编辑', self)
        create_folder_action = QAction('文件夹', self)
        create_script_action = QAction('脚本', self)
        create_scene_action = QAction('场景', self)
        create_txt_action = QAction('TXT', self)
        create_json_action = QAction('JSON', self)
        cut_action = QAction('剪切', self)
        copy_action = QAction('复制', self)
        paste_action = QAction('粘贴', self)
        delete_action = QAction('删除', self)
        rename_action = QAction('重命名', self)
        duplicate_action = QAction('生成副本', self)
        copy_uuid_action = QAction('复制UUID', self)
        copy_path_action = QAction('复制路径', self)
        copy_name_action = QAction('复制名称', self)
        open_in_terminal_action = QAction('在终端中打开', self)
        open_externally_action = QAction('在外部程序中打开', self)
        show_in_explorer_action = QAction('在文件管理器中显示', self)

        edit_action.triggered.connect(self.open_externally_signal.emit)
        create_folder_action.triggered.connect(lambda: self.create_signal.emit(ITEM_FOLDER))
        create_script_action.triggered.connect(lambda: self.create_signal.emit(ITEM_SCRIPT))
        create_scene_action.triggered.connect(lambda: self.create_signal.emit(ITEM_SCENE))
        create_txt_action.triggered.connect(lambda: self.create_signal.emit(ITEM_TXT))
        create_json_action.triggered.connect(lambda: self.create_signal.emit(ITEM_JSON))
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
        
        create_menu = QMenu(title='创建')
        text_file_sub_menu = QMenu(title='文本文件')

        # Create actions are for all item types.
        self.addMenu(create_menu)
        create_menu.addAction(create_folder_action)
        create_menu.addAction(create_script_action)
        create_menu.addAction(create_scene_action)
        text_file_sub_menu.addAction(create_txt_action)
        text_file_sub_menu.addAction(create_json_action)
        create_menu.addMenu(text_file_sub_menu)

        # Right click on the blank area.
        if item_type is None or is_root_item:
            self.addSeparator()
            self.addAction(paste_action)
            self.addSeparator()
            self.addAction(open_in_terminal_action)
            self.addAction(show_in_explorer_action)

        # Right click on the folder or file item.
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
            copy_menu = QMenu(title='复制路径 | 名称 | UUID')
            copy_menu.addAction(copy_path_action)
            copy_menu.addAction(copy_name_action)
            copy_menu.addAction(copy_uuid_action)
            self.addMenu(copy_menu)

            self.addSeparator()
            self.addAction(open_in_terminal_action)
            self.addAction(show_in_explorer_action)

        # Right click on the specific file item.
        if item_type != None and item_type != ITEM_FOLDER:
            self.insertAction(create_menu.menuAction(), edit_action)
            self.insertSeparator(create_menu.menuAction())
            self.insertAction(show_in_explorer_action, open_externally_action)
        
        self.__set_paste_action_status(paste_action)

    def __set_paste_action_status(self, paste_action):
        if self.__parent.get_clipboard_items():
            paste_action.setEnabled(True)
        else:
            paste_action.setEnabled(False)
        
    def show(self, pos, item_type, is_root_item):
        self.clear()
        self.__add_actions(item_type, is_root_item)
        self.exec(pos)