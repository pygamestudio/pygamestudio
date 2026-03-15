from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from pygamestudio.editor.gui.dashboard.menu import ContextMenu
from pygamestudio.editor.gui.dashboard.delegate import DashboardDelegate
from pygamestudio.editor.gui.dashboard.config import save_projects, load_projects

from pathlib import Path

class DashboardListView(QListView):
    ProjectIconRole = Qt.ItemDataRole.UserRole + 1
    ProjectNameRole = Qt.ItemDataRole.UserRole + 2
    ProjectPathRole = Qt.ItemDataRole.UserRole + 3
    ProjectDateRole = Qt.ItemDataRole.UserRole + 4

    def __init__(self, parent):
        super().__init__(parent)
        self._dashboard_window = parent
        self._standard_model = QStandardItemModel()
        self._proxy_model = QSortFilterProxyModel()
        self._delegate = DashboardDelegate(self)
        self._context_menu = ContextMenu('', self)

        self._setup()

        self._add_item({})
        self._add_item({})

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self._proxy_model.setSourceModel(self._standard_model)
        self._proxy_model.setRecursiveFilteringEnabled(False)
        self._proxy_model.setFilterKeyColumn(0)
        self._proxy_model.setDynamicSortFilter(True)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.setModel(self._proxy_model)
        self.setItemDelegate(self._delegate)

        self.setMouseTracking(True)
        self.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def _set_signal(self):
        self.doubleClicked.connect(self._open_project)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._delegate.menuRequested.connect(self._show_context_menu)

        self._context_menu.create_signal.connect(self._create_project)
        self._context_menu.import_signal.connect(self._import_project)
        self._context_menu.open_signal.connect(self._open_project)
        self._context_menu.rename_signal.connect(self._rename_project)
        self._context_menu.delete_signal.connect(self._delete_project)

    def _set_layout(self):
        ...

    def _set_object_name(self):
        self.setObjectName('dashboardListView')
        self.setStyleSheet("""
            QListView::item {
                height: 80px;
                padding: 2px;
            }
        """)

    def _add_item(self, project_data):
        item = QStandardItem()
        item.setEditable(False)

        project_icon = project_data.get('icon', '')
        project_name = project_data.get('name', '')
        project_path = project_data.get('path', '')
        project_date = project_data.get('date', '')
        item.setData(project_icon, self.ProjectIconRole)
        item.setData(project_name, self.ProjectNameRole)
        item.setData(project_path, self.ProjectPathRole)
        item.setData(project_date, self.ProjectDateRole)
        
        self._standard_model.appendRow(item)
        self.scrollToBottom()

    def _delete_item(self, row):
        self._standard_model.removeRow(row)

    def _show_context_menu(self, pos):
        index = self.indexAt(pos)
        global_pos = self.mapToGlobal(pos)
        self._context_menu.show(global_pos, index.isValid())

    def create_projecct(self):
        return self._create_project()
    
    def _create_project(self):
        new_project_dir_path = QFileDialog.getExistingDirectory(self, '选择新项目目录', '.', QFileDialog.Option.ReadOnly | QFileDialog.Option.ShowDirsOnly)
        if not new_project_dir_path:
            return
        
        try:
            next(Path(new_project_dir_path).iterdir())
            # 不为空，提示
        except StopIteration:
            # 闯将
            ...

    def import_project(self):
        return self._import_project()

    def _import_project(self):
        path = QFileDialog.getExistingDirectory(self, '请选择项目', '.', QFileDialog.Option.ReadOnly)

    def open_project(self):
        return self._open_project()

    def _open_project(self):
        # project_path = index.data(self.ProjectPathRole)
        # # self._dashboard_window.hide()
        # print(project_path)
        ...

    def rename_project(self):
        return self._rename_project()

    def _rename_project(self):
        ...

    def delete_project(self):
        return self._delete_project()

    def _delete_project(self):
        ...

    def search(self):
        ...

    def sort(self):
        ...

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().enterEvent(event)