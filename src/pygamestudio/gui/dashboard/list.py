from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

from datetime import datetime
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.gui.dashboard.menu import ContextMenu
from pygamestudio.gui.dashboard.delegate import DashboardDelegate
from pygamestudio.gui.dashboard.dialog import CreatePorjectWindow, RenameProjectWindow
from pygamestudio.gui.dashboard.config import *
from pygamestudio.gui.dashboard.type import *
from pygamestudio.gui.dashboard.model import DashboardSortFilterProxyModel
import shutil


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
        self._set_layout()
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
        
        self._standard_model.insertRow(0, item)
        self.scrollToBottom()

    def _delete_item(self, row):
        self._standard_model.removeRow(row)

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
            'path': project_path,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self._add_item(project_data)
        
        # Add new project data to PygameStudio dashboard.json.
        add_project_to_dashboard_config(project_data)
    
    def show_create_project_window(self):
        return self._show_create_project_window()

    def _show_create_project_window(self):
        self._create_project_window.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._create_project_window.show()

    def import_project(self):
        return self._import_project()

    def _import_project(self):
        project_path = QFileDialog.getExistingDirectory(self, '请选择项目', '.', QFileDialog.Option.ReadOnly)
        if not project_path:
            return

        if not (Path(project_path) / 'project.json').exists():
            QMessageBox.critical(self, '错误', '项目打开失败，没有找到project.json文件')
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
            QMessageBox.critical(self, '错误', '找不到项目文件')
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
            QMessageBox.critical(self, '错误', '找不到项目文件')
            return
        
        self._rename_project_window.set_index_and_old_project_path(index, project_path)
        self._rename_project_window.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._rename_project_window.show()

    def _rename_project(self, index, old_project_path, new_project_path):
        update_project_name_in_dashboard_config(old_project_path, new_project_path)

        item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index))
        item.setData(Path(new_project_path).name, self.ProjectNameRole)
        item.setData(new_project_path, self.ProjectPathRole)
        
    def _delete_project(self, index):
        chocie = QMessageBox.question(self, '请确认', '是否删除该项目？', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
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
        """重写绘制事件"""
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
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, '目前你还没有任何项目\n请点击按钮创建或导入')
            
            painter.restore()
