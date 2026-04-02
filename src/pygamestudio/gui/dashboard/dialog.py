from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from pathlib import Path
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.gui.base.window import WindowBase


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

    def _set_widget(self):
        self._project_name_label.setText('项目名称:')
        self._project_name_edit.setPlaceholderText('请输入项目名称')
    
        self._project_dir_path_label.setText('项目路径:')
        self._project_dir_path_edit.setPlaceholderText('请选择或输入项目路径')

        self._browse_button.setText('浏览')
        self._error_label.setStyleSheet("""
        QLabel {
            color: red;
        }
        """)

        self._create_button.setText('创建')
        self._create_button.setEnabled(False)
        self._cancel_button.setText('取消')

    def _set_signal(self):
        self._project_name_edit.textChanged.connect(self._validate_project)
        self._project_dir_path_edit.textChanged.connect(self._validate_project)
        self._create_button.clicked.connect(self._create_project)
        self._browse_button.clicked.connect(self._browse)
        self._cancel_button.clicked.connect(self._close_window)

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
        main_v_layout.addWidget(self._error_label)
        main_v_layout.addStretch()
        main_v_layout.addLayout(h_layout3)
        
    def _validate_project(self):
        project_name = self._project_name_edit.text().strip()
        project_dir_path = self._project_dir_path_edit.text().strip()
        project_path = Path(project_dir_path) / project_name

        self._hide_error()
        if not project_name or not project_dir_path:
            self._create_button.setEnabled(False)
            return
        
        if project_path.exists():
            self._show_error('目标文件夹已存在，请修改项目名称')
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
        project_json_path = project_path / 'project.json'

        try:
            project_path.mkdir(parents=True, exist_ok=False)
            audio_folder_path.mkdir(parents=True, exist_ok=False)
            image_folder_path.mkdir(parents=True, exist_ok=False)
            scene_folder_path.mkdir(parents=True, exist_ok=False)
            script_folder_path.mkdir(parents=True, exist_ok=False)
            main_py_path.touch(exist_ok=False)
            with open(RES_PATH / 'templates/project.json', 'r', encoding='utf-8') as f:
                project_json_path.write_text(f.read(), encoding='utf-8')
            
            self._project_name_edit.clear()
            self._project_dir_path_edit.clear()
            self.close_window_signal.emit()
            self.create_project_signal.emit(str(project_path))
        except FileExistsError:
            self._show_error('目标文件夹已存在，请修改项目名称')
            self._create_button.setEnabled(False)
        except Exception as e:
            self._show_error(f'目录创建失败: {e}')
            self._create_button.setEnabled(False)

    def _close_window(self):
        self._project_name_edit.clear()
        self._project_dir_path_edit.clear()
        self.close_window_signal.emit()

    def _hide_error(self):
        self._error_label.setText('')
        self._error_label.hide()

    def _show_error(self, err):
        self._error_label.setText(err)
        self._error_label.show()

    def _browse(self):
        project_dir_path = QFileDialog.getExistingDirectory(self, '选择项目路径')
        if project_dir_path:
            self._project_dir_path_edit.setText(project_dir_path)

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
        self.resize(350, 150)
        self.set_window_body(self._create_project_body)

    def _set_signal(self):
        self._create_project_body.create_project_signal.connect(self.create_project_signal.emit)
        self._create_project_body.close_window_signal.connect(self.close)


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

    def _set_widget(self):
        self._project_name_label.setText('项目名称:')
        self._project_name_edit.setPlaceholderText('请输入新的项目名称')

        self._error_label.setStyleSheet("""
        QLabel {
            color: red;
        }
        """)

        self._rename_button.setText('重命名')
        self._rename_button.setEnabled(False)
        self._cancel_button.setText('取消')

    def _set_signal(self):
        self._project_name_edit.textChanged.connect(self._validate_project)
        self._rename_button.clicked.connect(self._rename)
        self._cancel_button.clicked.connect(self._close_window)

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
        main_v_layout.addWidget(self._error_label)
        main_v_layout.addStretch()
        main_v_layout.addLayout(h_layout2)

    def _validate_project(self):
        new_project_name = self._project_name_edit.text().strip()
        new_project_path = Path(self._old_project_path).parent / new_project_name

        self._hide_error()
        if not new_project_name:
            self._rename_button.setEnabled(False)
            return
        
        if new_project_name == Path(self._old_project_path).name:
            self._show_error('项目名称与原来的一样')
            return
        
        if new_project_path.exists():
            self._show_error('目标文件夹已存在，请修改项目名称')
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
            QMessageBox.critical(self, '错误', f'重命名失败!\n{e}')
        else:
            self.rename_project_signal.emit(self._index, self._old_project_path, new_project_path)

    def _close_window(self):
        self._project_name_edit.clear()
        self.close_window_signal.emit()

    def _hide_error(self):
        self._error_label.setText('')
        self._error_label.hide()

    def _show_error(self, err):
        self._error_label.setText(err)
        self._error_label.show()

    def set_index_and_old_project_path(self, index, old_project_path):
        self._index = index
        self._old_project_path = old_project_path


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
        self.resize(350, 80)
        self.set_window_body(self._rename_project_body)

    def _set_signal(self):
        self._rename_project_body.rename_project_signal.connect(self.rename_project_signal.emit)
        self._rename_project_body.close_window_signal.connect(self.close)

    def set_index_and_old_project_path(self, index, old_project_path):
        self._rename_project_body.set_index_and_old_project_path(index, old_project_path)