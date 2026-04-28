from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *

from pygamestudio.gui.base.window import WindowBase
from pygamestudio.gui.dashboard.list import DashboardListView
from pygamestudio.gui.dashboard.search import SearchLineEdit
from pygamestudio.gui.dashboard.widget import SortTypeComboBox, CreateProjectButton, ImportProjectButton
from pygamestudio.common.i18n.translator import Translator as T


class DashboardWindow(WindowBase):
    open_project_signal = Signal(str)
    
    def __init__(self):
        super().__init__() 
        self._sort_label = QLabel()
        self._dashboard_list_view = DashboardListView(self)

        self._create_project_button = CreateProjectButton()
        self._import_project_button = ImportProjectButton()
        self._search_line_edit = SearchLineEdit()
        self._sort_type_combobox = SortTypeComboBox()

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self.resize(640, 460)
        self._center()
        self.set_window_body(self._dashboard_list_view)
        self.window_title.set_title_name('Pygame Studio Dashboard')

        self._sort_label.setText(T.tr('dashboard.sort', 'Sort:'))

    def _set_signal(self):
        self._create_project_button.clicked.connect(self._dashboard_list_view.show_create_project_window)
        self._import_project_button.clicked.connect(self._dashboard_list_view.import_project)
        self._search_line_edit.textChanged.connect(self._dashboard_list_view.search)
        self._sort_type_combobox.currentIndexChanged.connect(self._dashboard_list_view.set_sort_type)
        self._dashboard_list_view.open_project_signal.connect(self.open_project_signal.emit)
        T.add_observer(self)

    def _set_layout(self):
        widget_h_layout = QHBoxLayout()
        widget_h_layout.addWidget(self._create_project_button)
        widget_h_layout.addWidget(self._import_project_button)
        widget_h_layout.addWidget(self._search_line_edit)
        widget_h_layout.addWidget(self._sort_label)
        widget_h_layout.addWidget(self._sort_type_combobox)
        self.central_v_layout.insertLayout(1, widget_h_layout)

    def _set_object_name(self):
        self.setObjectName('dashboard')
        
    def _center(self):
        screen = QApplication.primaryScreen()
        screen_width = screen.availableGeometry().width()
        screen_height = screen.availableGeometry().height()
 
        pos_x = screen_width/2 - self.frameGeometry().width()/2
        pos_y = screen_height/2 - self.frameGeometry().height()/2
 
        self.move(int(pos_x), int(pos_y))

    @property
    def dashboard_list_view(self):
        return self._dashboard_list_view
    
    def retranslate(self):
        self._sort_label.setText(T.tr('dashboard.sort', 'Sort'))