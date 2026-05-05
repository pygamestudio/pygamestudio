from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.asset.type import *
from pygamestudio.common.utils.config import get_project_config
from pygamestudio.common.i18n.translator import Translator as T


class RefreshAssetButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
    
    def _set_widget(self):
        self.setToolTip(T.tr('asset.refresh', 'Refresh'))
        self.setIcon(QIcon(':/images/refresh_asset.png'))

    def _set_signal(self):
        T.add_observer(self)

    def retranslate(self):
        self.setToolTip(T.tr('asset.refresh', 'Refresh'))


class SortAssetButton(QPushButton):
    sort_signal = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
    
    def _set_widget(self):
        self.setToolTip(T.tr('asset.sort', 'Sort'))
        self.setIcon(QIcon(':/images/sort.png'))

    def _set_signal(self):
        T.add_observer(self)

    def retranslate(self):
        self.setToolTip(T.tr('asset.sort', 'Sort'))

    def mousePressEvent(self, event):
        self._show_context_menu(event.pos())
        super().mousePressEvent(event)

    def _show_context_menu(self, pos):
        config_sort_type = get_project_config()['asset']['sort_type']
        menu = QMenu(self)

        action_group = QActionGroup(self)
        action_group.setExclusive(True)

        action_text_list = [
            (T.tr('asset.sort_by_name_asc', 'Sort By Name (ASC)'), SORT_BY_NAME_ASC), 
            (T.tr('asset.sort_by_name_desc', 'Sort By Name (DESC)'), SORT_BY_NAME_DESC),
            (T.tr('asset.sort_by_type_asc', 'Sort By Type (ASC)'), SORT_BY_TYPE_ASC),
            (T.tr('asset.sort_by_type_desc', 'Sort By Type (DESC)'), SORT_BY_TYPE_DESC),
            (T.tr('asset.sort_by_size_asc', 'Sort By Size (ASC)'), SORT_BY_SIZE_ASC),
            (T.tr('asset.sort_by_size_desc', 'Sort By Size (DESC)'), SORT_BY_SIZE_DESC),
            (T.tr('asset.sort_by_time_asc', 'Sort By Time (ASC)'), SORT_BY_TIME_ASC),
            (T.tr('asset.sort_by_time_desc', 'Sort By Time (DESC)'), SORT_BY_TIME_DESC),
        ]
        for (text, sort_type) in action_text_list:
            action = QAction(text, self)
            action.setData(sort_type)
            action.setCheckable(True)
            action.setChecked(True) if sort_type == config_sort_type else action.setChecked(False)
            action.triggered.connect(self._set_sort_type)
            menu.addAction(action)
            action_group.addAction(action)

        menu.exec(self.mapToGlobal(pos))

    def _set_sort_type(self):
        sort_type = self.sender().data()
        self.sort_signal.emit(sort_type)


class AddAssetButton(QPushButton):
    add_signal = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_object_name()
    
    def _set_widget(self):
        self.setToolTip(T.tr('asset.add', 'Add'))
        self.setIcon(QIcon(':/images/add.png'))

    def _set_signal(self):
        T.add_observer(self)

    def _set_object_name(self):
        self.setObjectName('assetAddBtn')

    def retranslate(self):
        self.setToolTip(T.tr('asset.add', 'Add'))
        
    def mousePressEvent(self, event):
        self._show_context_menu(event.pos())
        super().mousePressEvent(event)

    def _show_context_menu(self, pos):
        add_menu = QMenu(self)
        text_file_sub_menu = QMenu(title=T.tr('menu.text_file', 'Text File'), parent=self)

        add_folder_action = QAction(T.tr('menu.folder', 'Folder'), self)
        add_script_action = QAction(T.tr('menu.script', 'Script'), self)
        add_scene_action = QAction(T.tr('menu.scene', 'Scene'), self)
        add_txt_action = QAction('TXT', self)
        add_json_action = QAction('JSON', self)

        add_folder_action.triggered.connect(lambda: self.add_signal.emit(INDEX_FOLDER))
        add_script_action.triggered.connect(lambda: self.add_signal.emit(INDEX_SCRIPT))
        add_scene_action.triggered.connect(lambda: self.add_signal.emit(INDEX_SCENE))
        add_txt_action.triggered.connect(lambda: self.add_signal.emit(INDEX_TXT))
        add_json_action.triggered.connect(lambda: self.add_signal.emit(INDEX_JSON))

        add_menu.addAction(add_folder_action)
        add_menu.addAction(add_script_action)
        add_menu.addAction(add_scene_action)
        text_file_sub_menu.addAction(add_txt_action)
        text_file_sub_menu.addAction(add_json_action)
        add_menu.addMenu(text_file_sub_menu)
    
        add_menu.exec(self.mapToGlobal(pos))