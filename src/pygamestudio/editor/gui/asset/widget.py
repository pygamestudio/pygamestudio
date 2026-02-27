from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *

from pygamestudio.editor.gui.asset.type import *
from pygamestudio.common.utils.path import RES_PATH


class RefreshAssetButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_up()

    def _set_up(self):
        self._set_widget()
    
    def _set_widget(self):
        self.setIcon(QIcon(str(RES_PATH / 'images/refresh.png')))
        self.setStyleSheet("""
        QPushButton {
            border: none;
            border-radius: 5px;
        }

        QPushButton:hover {
            background-color: red;
        }    

        QPushButton:pressed {
            background-color: cyan;
        }                            
        """)


class SortAssetButton(QPushButton):
    sort_signal = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sort_type = SORT_BY_NAME_ASC  # 项目配置文件
        self._set_up()

    def _set_up(self):
        self._set_widget()
    
    def _set_widget(self):
        self.setIcon(QIcon(str(RES_PATH / 'images/sort.png')))
        self.setStyleSheet("""
        QPushButton {
            border: none;
            border-radius: 5px;
        }

        QPushButton:hover {
            background-color: red;
        }    

        QPushButton:pressed {
            background-color: cyan;
        }                            
        """)

    def mousePressEvent(self, event):
        self._show_context_menu(event.pos())
        super().mousePressEvent(event)

    def _show_context_menu(self, pos):
        menu = QMenu()

        action_group = QActionGroup(self)
        action_group.setExclusive(True)

        action_text_list = [
            ('按名称(升序)', SORT_BY_NAME_ASC), 
            ('按名称(降序)', SORT_BY_NAME_DESC),
            ('按类型(升序)', SORT_BY_TYPE_ASC),
            ('按类型(降序)', SORT_BY_TYPE_DESC),
            ('按大小(升序)', SORT_BY_SIZE_ASC),
            ('按大小(降序)', SORT_BY_SIZE_DESC),
            ('按修改时间(升序)', SORT_BY_TIME_ASC),
            ('按修改时间(降序)', SORT_BY_TIME_DESC),
        ]
        for (text, sort_type) in action_text_list:
            action = QAction(text, self)
            action.setData(sort_type)
            action.setCheckable(True)
            action.setChecked(True) if sort_type == self._sort_type else action.setChecked(False)
            action.triggered.connect(self._set_sort_type)
            menu.addAction(action)
            action_group.addAction(action)

        menu.exec(self.mapToGlobal(pos))

    def _set_sort_type(self):
        self._sort_type = self.sender().data()
        self.sort_signal.emit(self._sort_type)


class CreateAssetButton(QPushButton):
    create_signal = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_up()

    def _set_up(self):
        self._set_widget()
    
    def _set_widget(self):
        self.setIcon(QIcon(str(RES_PATH / 'images/create.png')))
        self.setStyleSheet("""
        QPushButton {
            border: none;
            border-radius: 5px;
        }

        QPushButton:hover {
            background-color: red;
        }                       
        """)

    def mousePressEvent(self, event):
        self._show_context_menu(event.pos())
        super().mousePressEvent(event)

    def _show_context_menu(self, pos):
        create_menu = QMenu()
        text_file_sub_menu = QMenu(title='文本文件')

        create_folder_action = QAction('文件夹', self)
        create_script_action = QAction('脚本', self)
        create_scene_action = QAction('场景', self)
        create_txt_action = QAction('TXT', self)
        create_json_action = QAction('JSON', self)

        create_folder_action.triggered.connect(lambda: self.create_signal.emit(INDEX_FOLDER))
        create_script_action.triggered.connect(lambda: self.create_signal.emit(INDEX_SCRIPT))
        create_scene_action.triggered.connect(lambda: self.create_signal.emit(INDEX_SCENE))
        create_txt_action.triggered.connect(lambda: self.create_signal.emit(INDEX_TXT))
        create_json_action.triggered.connect(lambda: self.create_signal.emit(INDEX_JSON))

        create_menu.addAction(create_folder_action)
        create_menu.addAction(create_script_action)
        create_menu.addAction(create_scene_action)
        text_file_sub_menu.addAction(create_txt_action)
        text_file_sub_menu.addAction(create_json_action)
        create_menu.addMenu(text_file_sub_menu)
    
        create_menu.exec(self.mapToGlobal(pos))