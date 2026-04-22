import shutil
from datetime import datetime
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.dashboard.type import *
from pygamestudio.gui.dashboard.config import *
from pygamestudio.gui.dashboard.menu import ContextMenu
from pygamestudio.gui.dashboard.delegate import DashboardDelegate
from pygamestudio.gui.dashboard.dialog import CreatePorjectWindow, RenameProjectWindow
from pygamestudio.gui.dashboard.model import DashboardSortFilterProxyModel
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.common.i18n.translator import Translator as T


class DashboardListView(QListView):
    open_project_signal = Signal(str)

    ProjectIconRole = Qt.ItemDataRole.UserRole + 1
    ProjectNameRole = Qt.ItemDataRole.UserRole + 2
    ProjectPathRole = Qt.ItemDataRole.UserRole + 3
    ProjectDateRole = Qt.ItemDataRole.UserRole + 4

    def __init__(self, parent):
        super().__init__(parent)
        self._dashboard_window = parent
        self._standard_model = QStandardItemModel()
        self._proxy_model = DashboardSortFilterProxyModel(self)
        self._delegate = DashboardDelegate(self)
        self._context_menu = ContextMenu('', self)
        self._create_project_window = CreatePorjectWindow()
        self._rename_project_window = RenameProjectWindow()

        self._sort_type = SORT_BY_TIME

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_object_name()
        self._load_projects()

    def _set_widget(self):
        self._proxy_model.setSourceModel(self._standard_model)
        self._proxy_model.setRecursiveFilteringEnabled(False)
        self._proxy_model.setFilterKeyColumn(0)
        self._proxy_model.setDynamicSortFilter(True)
        self._proxy_model.sort(0, Qt.SortOrder.AscendingOrder)
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

        self._create_project_window.create_project_signal.connect(self._create_project)
        self._rename_project_window.rename_project_signal.connect(self._rename_project)
        
        self._context_menu.open_project_signal.connect(self._open_project)
        self._context_menu.rename_project_signal.connect(self._show_rename_project_window)
        self._context_menu.delete_project_signal.connect(self._delete_project)
        self._context_menu.create_project_signal.connect(self._show_create_project_window)
        self._context_menu.import_project_signal.connect(self._import_project)

    def _set_object_name(self):
        self.setObjectName('dashboardListView')

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
        
        self._standard_model.insertRow(0, item)
        self.scrollToBottom()

    def _delete_item(self, row):
        self._proxy_model.removeRow(row)

    def _load_projects(self):
        project_list = load_projects_from_dashboard_config()
        for project_data in project_list:
            self._add_item(project_data)

    def _show_context_menu(self, pos):
        index = self.indexAt(pos)
        global_pos = self.mapToGlobal(pos)
        self._context_menu.show(global_pos, index)

    def create_project(self, project_path):
        return self._create_project(project_path)
    
    def _create_project(self, project_path):
        project_data = {
            'icon': str(RES_PATH / 'images/project_icon.png'),
            'name': Path(project_path).name,
            'path': Path(project_path).as_posix(),
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self._add_item(project_data)
        
        # Add new project data to PygameStudio dashboard.pygs.
        add_project_to_dashboard_config(project_data)
    
    def show_create_project_window(self):
        return self._show_create_project_window()

    def _show_create_project_window(self):
        self._create_project_window.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._create_project_window.show()

    def import_project(self):
        return self._import_project()

    def _import_project(self):
        project_path = QFileDialog.getExistingDirectory(self, T.tr('dialog.get_dir_title', 'Select Project'), '.', QFileDialog.Option.ReadOnly)
        if not project_path:
            return

        if not (Path(project_path) / 'project.pygs').exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_open_project', "Failed to open the project. Couldn't find project.pygs."))
            return
        
        project_data = {
            'icon': str(RES_PATH / 'images/project_icon.png'),
            'name': Path(project_path).name,
            'path': project_path,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        add_project_to_dashboard_config(project_data)

    def _open_project(self, index):
        project_path = index.data(self.ProjectPathRole)
        if not Path(project_path).exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_find_project', "Couldn't find the project."))
            return
        
        self.open_project_signal.emit(project_path)
        
        # Update the project date.
        new_project_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index))
        item.setData(new_project_date, self.ProjectDateRole)
        update_project_date_in_dashboard_config(project_path, new_project_date)
    
    def _show_rename_project_window(self, index):
        project_path = index.data(self.ProjectPathRole)
        if not Path(project_path).exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_find_project', "Couldn't find the project."))
            return
        
        self._rename_project_window.set_index_and_old_project_path(index, project_path)
        self._rename_project_window.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._rename_project_window.show()

    def _rename_project(self, index, old_project_path, new_project_path):
        update_project_name_in_dashboard_config(old_project_path, new_project_path)

        item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index))
        item.setData(Path(new_project_path).name, self.ProjectNameRole)
        item.setData(Path(new_project_path).as_posix(), self.ProjectPathRole)
        
    def _delete_project(self, index):
        chocie = QMessageBox.question(self, T.tr('message_box.question_title', 'Confirm'), T.tr('message_box.question_delete_project_content', 'Delete the project?'), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if chocie == QMessageBox.StandardButton.No:
            return
        
        project_path = index.data(self.ProjectPathRole)
        delete_project_from_dashboard_config(project_path)
        self._delete_item(index.row())

        try:
            shutil.rmtree(project_path)
        except:
            pass

    def search(self, keyword):
        self._proxy_model.setFilterFixedString(keyword)

    def set_sort_type(self, i):
        if i == 0:
            self._sort_type = SORT_BY_TIME
        elif i == 1:
            self._sort_type = SORT_BY_NAME
        elif i == 2:
            self._sort_type = SORT_BY_PATH
        
        self._proxy_model.invalidate()

    def get_sort_type(self):
        return self._sort_type

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().enterEvent(event)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        
        model = self.model()
        if not model or model.rowCount() == 0:
            painter = QPainter(self.viewport())
            painter.save()
            
            painter.setPen(QColor(128, 128, 128))
            font = QFont()
            font.setPointSize(15)
            painter.setFont(font)
            
            rect = self.viewport().rect()
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, T.tr('dashboard.create_project_guide', "You don't have any projects yet.\nPlease click the button to create or import one."))
            
            painter.restore()
