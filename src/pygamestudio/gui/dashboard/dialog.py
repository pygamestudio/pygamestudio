
import json
from pathlib import Path
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.gui.base.window import WindowBase
from pygamestudio.common.i18n.translator import Translator as T


class CreateProjectBody(QWidget):
    close_window_signal = Signal()
    create_project_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self._project_name_label = QLabel()
        self._project_name_edit = QLineEdit()

        self._project_dir_path_label = QLabel()
        self._project_dir_path_edit = QLineEdit()
        self._browse_button = QPushButton()

        self._error_label = QLabel()
        self._create_button = QPushButton()
        self._cancel_button = QPushButton()

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self._project_name_label.setText(T.tr('dashboard.project_name', 'Project Name:'))
        self._project_name_edit.setPlaceholderText(T.tr('dashboard.project_name_edit_placeholder', 'Please enter the project name'))
    
        self._project_dir_path_label.setText(T.tr('dashboard.project_path', 'Project Path:'))
        self._project_dir_path_edit.setPlaceholderText(T.tr('dashboard.project_path_edit_placeholder', 'Please select or enter the project path'))

        self._browse_button.setText(T.tr('dashboard.browse', 'Browse'))
        self._create_button.setText(T.tr('dashboard.create', 'Create'))
        self._create_button.setEnabled(False)
        self._cancel_button.setText(T.tr('dashboard.cancel', 'Cancel'))

        self._error_label.hide()

    def _set_signal(self):
        self._project_name_edit.textChanged.connect(self._validate_project)
        self._project_dir_path_edit.textChanged.connect(self._validate_project)
        self._create_button.clicked.connect(self._create_project)
        self._browse_button.clicked.connect(self._browse)
        self._cancel_button.clicked.connect(self.close_window_signal.emit)
        T.add_observer(self)

    def _set_layout(self):
        h_layout1 = QHBoxLayout()
        h_layout2 = QHBoxLayout()
        h_layout3 = QHBoxLayout()
        main_v_layout = QVBoxLayout(self)

        h_layout1.addWidget(self._project_name_label)
        h_layout1.addWidget(self._project_name_edit)
        h_layout2.addWidget(self._project_dir_path_label)
        h_layout2.addWidget(self._project_dir_path_edit)
        h_layout2.addWidget(self._browse_button)

        h_layout3.addWidget(self._create_button)
        h_layout3.addSpacing(10)
        h_layout3.addWidget(self._cancel_button)
        main_v_layout.addLayout(h_layout1)
        main_v_layout.addSpacing(5)
        main_v_layout.addLayout(h_layout2)
        main_v_layout.addSpacing(2.5)
        main_v_layout.addWidget(self._error_label)
        main_v_layout.addSpacing(2.5)
        main_v_layout.addLayout(h_layout3)

    def _set_object_name(self):
        self._error_label.setObjectName('dashboardCreateProjectErrorLabel')
        
    def _validate_project(self):
        project_name = self._project_name_edit.text().strip()
        project_dir_path = self._project_dir_path_edit.text().strip()
        project_path = Path(project_dir_path) / project_name

        self._hide_error()
        if not project_name or not project_dir_path:
            self._create_button.setEnabled(False)
            return
        
        if project_path.exists():
            self._show_error(T.tr('dashboard.project_exist_error', 'The project already exists. Please change the project name.'))
            self._create_button.setEnabled(False)
        else:
            self._create_button.setEnabled(True)

    def _create_project(self):
        project_name = self._project_name_edit.text().strip()
        project_dir_path = self._project_dir_path_edit.text().strip()
        project_path = Path(project_dir_path) / project_name
        audio_folder_path = project_path / 'audio'
        image_folder_path = project_path / 'image'
        scene_folder_path = project_path / 'scene'
        script_folder_path = project_path / 'script'
        main_py_path = project_path / 'main.py'
        project_json_path = project_path / 'project.pygs'

        try:
            project_path.mkdir(parents=True, exist_ok=False)
            audio_folder_path.mkdir(parents=True, exist_ok=False)
            image_folder_path.mkdir(parents=True, exist_ok=False)
            scene_folder_path.mkdir(parents=True, exist_ok=False)
            script_folder_path.mkdir(parents=True, exist_ok=False)
            with open(RES_PATH / 'templates/main_template.py', 'r', encoding='utf-8') as f:
                main_py_path.write_text(f.read(), encoding='utf-8')
            with open(RES_PATH / 'templates/project_template.pygs', 'r', encoding='utf-8') as f:
                project_config = json.loads(f.read())
                project_config['caption'] = project_name
                project_json_path.write_text(json.dumps(project_config, indent=4, ensure_ascii=False), encoding='utf-8')
            
            self._project_name_edit.clear()
            self._project_dir_path_edit.clear()
            self.close_window_signal.emit()
            self.create_project_signal.emit(str(project_path))
        except FileExistsError:
            self._show_error(T.tr('dashboard.project_exist_error', 'The project already exists. Please change the project name.'))
            self._create_button.setEnabled(False)
        except Exception as e:
            self._show_error(T.tr('dashboard.create_project_error', 'Failed to create project: {}').format(e))
            self._create_button.setEnabled(False)

    def _hide_error(self):
        self._error_label.setText('')
        self._error_label.hide()

    def _show_error(self, err):
        self._error_label.setText(err)
        self._error_label.show()

    def _browse(self):
        project_dir_path = QFileDialog.getExistingDirectory(self, T.tr('dashboard.select_project_path', 'Select Project Path'))
        if project_dir_path:
            self._project_dir_path_edit.setText(project_dir_path)

    def clean_up(self):
        self._project_name_edit.clear()
        self._project_dir_path_edit.clear()
        self._hide_error()

    def retranslate(self):
        self._project_name_label.setText(T.tr('dashboard.project_name', 'Project Name:'))
        self._project_name_edit.setPlaceholderText(T.tr('dashboard.project_name_edit_placeholder', 'Please enter the project name'))
        self._project_dir_path_label.setText(T.tr('dashboard.project_path', 'Project Path:'))
        self._project_dir_path_edit.setPlaceholderText(T.tr('dashboard.project_path_edit_placeholder', 'Please select or enter the project path'))
        self._browse_button.setText(T.tr('dashboard.browse', 'Browse'))
        self._create_button.setText(T.tr('dashboard.create', 'Create'))
        self._cancel_button.setText(T.tr('dashboard.cancel', 'Cancel'))

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().enterEvent(event)


class CreatePorjectWindow(WindowBase):
    create_project_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self._create_project_body = CreateProjectBody()
        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.resize(410, 150)
        self.setMinimumWidth(300)
        self.setMaximumWidth(500)
        self.set_window_body(self._create_project_body)
        self.layout().setVerticalSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        self.window_title.set_title_name(T.tr('dashboard.create', 'Create'))
        self.window_title.set_maximize_button_disabled()

    def _set_signal(self):
        self._create_project_body.create_project_signal.connect(self.create_project_signal.emit)
        self._create_project_body.close_window_signal.connect(self.close)
        T.add_observer(self)

    def retranslate(self):
        self.window_title.set_title_name(T.tr('dashboard.create', 'Create'))

    def closeEvent(self, event):
        self._create_project_body.clean_up()
        return super().closeEvent(event)
    
class RenameProjectBody(QWidget):
    close_window_signal = Signal()
    rename_project_signal = Signal(QModelIndex, str, str)

    def __init__(self):
        super().__init__()
        self._index = None
        self._old_project_path = ''

        self._project_name_label = QLabel()
        self._project_name_edit = QLineEdit()
        self._error_label = QLabel()
        self._rename_button = QPushButton()
        self._cancel_button = QPushButton()

        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self._project_name_label.setText(T.tr('dashboard.project_name', 'Project Name:'))
        self._project_name_edit.setPlaceholderText(T.tr('dashboard.project_rename_edit_placeholder', 'Please enter the new project name'))

        self._rename_button.setText(T.tr('dashboard.rename', 'Rename'))
        self._rename_button.setEnabled(False)
        self._cancel_button.setText(T.tr('dashboard.cancel', 'Cancel'))

        self._error_label.hide()

    def _set_signal(self):
        self._project_name_edit.textChanged.connect(self._validate_project)
        self._rename_button.clicked.connect(self._rename)
        self._cancel_button.clicked.connect(self.close_window_signal.emit)
        T.add_observer(self)

    def _set_layout(self):
        h_layout1 = QHBoxLayout()
        h_layout2 = QHBoxLayout()
        main_v_layout = QVBoxLayout(self)

        h_layout1.addWidget(self._project_name_label)
        h_layout1.addWidget(self._project_name_edit)
        h_layout2.addWidget(self._rename_button)
        h_layout2.addSpacing(10)
        h_layout2.addWidget(self._cancel_button)
        main_v_layout.addLayout(h_layout1)
        main_v_layout.addSpacing(2.5)
        main_v_layout.addWidget(self._error_label)
        main_v_layout.addSpacing(2.5)
        main_v_layout.addLayout(h_layout2)

    def _set_object_name(self):
        self._error_label.setObjectName('dashboardRenameProjectErrorLabel')

    def _validate_project(self):
        new_project_name = self._project_name_edit.text().strip()
        new_project_path = Path(self._old_project_path).parent / new_project_name

        self._hide_error()
        if not new_project_name:
            self._rename_button.setEnabled(False)
            return
        
        if new_project_name == Path(self._old_project_path).name:
            self._show_error(T.tr('dashboard.same_name', 'Same name as the original.'))
            self._rename_button.setEnabled(False)
            return
        
        if new_project_path.exists():
            self._show_error(T.tr('dashboard.project_exist_error', 'The project already exists. Please change the project name.'))
            self._rename_button.setEnabled(False)
        else:
            self._rename_button.setEnabled(True)
    
    def _rename(self):        
        project_name = self._project_name_edit.text().strip()
        new_project_path = str(Path(self._old_project_path).parent / project_name)

        try:
            Path(self._old_project_path).rename(new_project_path)
            self._project_name_edit.clear()
            self.close_window_signal.emit()
        except Exception as e:
            QMessageBox.critical(self, T.tr('message_box.critical_title'), T.tr('message_box.critical_rename_content', 'Failed to rename: {}').format(e))
        else:
            self.rename_project_signal.emit(self._index, self._old_project_path, new_project_path)

    def _hide_error(self):
        self._error_label.setText('')
        self._error_label.hide()

    def _show_error(self, err):
        self._error_label.setText(err)
        self._error_label.show()

    def set_index_and_old_project_path(self, index, old_project_path):
        self._index = index
        self._old_project_path = old_project_path

    def clean_up(self):
        self._project_name_edit.clear()
        self._hide_error()

    def retranslate(self):
        self._project_name_label.setText(T.tr('dashboard.project_name', 'Project Name:'))
        self._project_name_edit.setPlaceholderText(T.tr('dashboard.project_rename_edit_placeholder', 'Please enter the new project name'))
        self._rename_button.setText(T.tr('dashboard.rename', 'Rename'))
        self._cancel_button.setText(T.tr('dashboard.cancel', 'Cancel'))


class RenameProjectWindow(WindowBase):
    rename_project_signal = Signal(QModelIndex, str, str)

    def __init__(self):
        super().__init__()
        self._rename_project_body = RenameProjectBody()
        self._setup()

    def _setup(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.resize(370, 80)
        self.setMinimumWidth(300)
        self.setMaximumWidth(410)
        self.set_window_body(self._rename_project_body)
        self.layout().setVerticalSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        self.window_title.set_title_name(T.tr('dashboard.rename', 'Rename'))
        self.window_title.set_maximize_button_disabled()

    def _set_signal(self):
        self._rename_project_body.rename_project_signal.connect(self.rename_project_signal.emit)
        self._rename_project_body.close_window_signal.connect(self.close)
        T.add_observer(self)

    def set_index_and_old_project_path(self, index, old_project_path):
        self._rename_project_body.set_index_and_old_project_path(index, old_project_path)

    def retranslate(self):
        self.window_title.set_title_name(T.tr('menu.rename', 'Rename'))

    def closeEvent(self, event):
        self._rename_project_body.clean_up()
        return super().closeEvent(event)