import os
import platform
import subprocess
from pathlib import Path
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.console.logger import Logger
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils.config import get_project_config, update_project_config


class DesktopAppBuildWindow(QScrollArea):
    def __init__(self, game_manager):
        super().__init__()
        self._game_manager = game_manager
        self._central_widget = QWidget()
        self._app_name_label = QLabel()
        self._app_name_lineedit = QLineEdit()
        self._app_icon_label = QLabel()
        self._app_icon_lineedit = QLineEdit()
        self._app_icon_browse_button = QPushButton()
        self._output_dir_label = QLabel()
        self._output_dir_lineedit = QLineEdit()
        self._output_dir_browse_button = QPushButton()
        self._clean_cache_label = QLabel()
        self._clean_cache_checkbox = QCheckBox()
        self._progress_bar = QProgressBar()
        self._build_button = QPushButton()
        self._open_output_dir_button = QPushButton()

        self._build_thread = BuildThread(self, self._game_manager)
        self._is_building = False
        
        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self.setWidgetResizable(True)
        self.setWidget(self._central_widget)

        self._app_name_label.setText(T.tr('build.app_name', 'App Name'))
        self._app_name_lineedit.setPlaceholderText(T.tr('build.app_name_placeholder', 'Please enter the app name'))
        self._app_icon_label.setText(T.tr('build.app_icon', 'App Icon'))
        self._app_icon_lineedit.setPlaceholderText(T.tr('build.app_icon_placeholder', 'Please choose the app icon (.png/.ico/.icns)'))
        self._app_icon_browse_button.setIcon(QIcon(':/images/browse.png'))
        self._output_dir_label.setText(T.tr('build.output_dir', 'Output Dir'))
        self._output_dir_lineedit.setPlaceholderText(T.tr('build.output_dir_placeholder', 'Please choose the output dir'))
        self._output_dir_browse_button.setIcon(QIcon(':/images/browse.png'))
        self._clean_cache_label.setText(T.tr('build.clean_cache', 'Clean Cache'))
        self._clean_cache_checkbox.setChecked(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.hide()
        self._build_button.setText(T.tr('build.build', 'Build'))
        self._open_output_dir_button.setText(T.tr('build.open_output_dir', 'Open Output Dir'))
        
    def _set_signal(self):
        self._app_icon_browse_button.clicked.connect(self._browse_app_icon)
        self._output_dir_browse_button.clicked.connect(self._browse_output_dir)
        self._build_button.clicked.connect(self._build)
        self._open_output_dir_button.clicked.connect(self._open_output_dir)

        self._build_thread.stopped_signal.connect(self._on_build_stopped)
        self._build_thread.finished_signal.connect(self._on_build_finished)
        self._build_thread.progress_signal.connect(self._on_progress_updated)

        T.add_observer(self)

    def _set_layout(self):
        app_name_layout = QHBoxLayout()
        app_name_layout.addWidget(self._app_name_lineedit)
        app_icon_layout = QHBoxLayout()
        app_icon_layout.addWidget(self._app_icon_lineedit)
        app_icon_layout.addSpacing(5)
        app_icon_layout.addWidget(self._app_icon_browse_button)
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self._output_dir_lineedit)
        output_dir_layout.addSpacing(5)
        output_dir_layout.addWidget(self._output_dir_browse_button)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self._build_button)
        button_layout.addSpacing(5)
        button_layout.addWidget(self._open_output_dir_button)

        main_g_layout = QGridLayout(self._central_widget)
        main_g_layout.setVerticalSpacing(10)
        main_g_layout.addWidget(self._app_name_label, 0, 0, 1, 1)
        main_g_layout.addLayout(app_name_layout, 0, 1)
        main_g_layout.addWidget(self._app_icon_label, 1, 0, 1, 1)
        main_g_layout.addLayout(app_icon_layout, 1, 1)
        main_g_layout.addWidget(self._output_dir_label, 2, 0, 1, 1)
        main_g_layout.addLayout(output_dir_layout, 2, 1)
        # main_g_layout.addWidget(self._clean_cache_label, 3, 0, 1, 1)
        # main_g_layout.addWidget(self._clean_cache_checkbox, 3, 1, 1, 1)
        main_g_layout.addWidget(self._progress_bar, 3, 0, 1, 2)
        main_g_layout.addLayout(button_layout, 4, 0, 1, 2)
        main_g_layout.setContentsMargins(5, 5, 5, 0)
        
    def _set_object_name(self):
        self._build_button.setObjectName('desktopAppBuildBtn')

    def get_ready_for_project(self):
        project_config = get_project_config()
        try:
            self._app_name_lineedit.setText(project_config['build']['app_name'])
        except Exception as e:
            self._app_name_lineedit.clear()

        try:
            self._app_icon_lineedit.setText(project_config['build']['app_icon'])
        except Exception as e:
            self._app_icon_lineedit.clear()

        try:
            self._output_dir_lineedit.setText(project_config['build']['output_dir'])
        except Exception as e:
            self._output_dir_lineedit.clear()

    def _browse_app_icon(self):
        icon_path, _ = QFileDialog.getOpenFileName(self, T.tr('build.select_app_icon', 'Select App Icon'), self._game_manager.get_project_path(), 'Format (*png *.ico *.icns)')
        if icon_path:
            self._app_icon_lineedit.setText(icon_path)

    def _browse_output_dir(self):
        output_dir = QFileDialog.getExistingDirectory(self, T.tr('build.select_output_dir', 'Select Output Dir'))
        if output_dir:
            self._output_dir_lineedit.setText(output_dir)

    def _check_before_build(self):
        if not (Path(self._game_manager.get_project_path()) / 'main.py').exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_main_not_found', 'main.py is not found'))
            return False
        
        if self._app_icon_lineedit.text().strip() and not Path(self._app_icon_lineedit.text().strip()).exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_app_icon_not_exist', 'App icon does not exist'))
            return False
        
        if not self._output_dir_lineedit.text().strip():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_no_output_dir', 'Please choose the output dir'))
            return False

        if not Path(self._output_dir_lineedit.text().strip()).exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_output_dir_not_exist', 'Output dir does not exist'))
            return False
        
        return True
    
    def _build(self):
        if self._is_building:
            choice = QMessageBox.question(QApplication.activeWindow(), T.tr('message_box.quesiton_title', 'Confirm'), T.tr('message_box.question_stop_build', 'Sure to stop the building?'))
            if choice == QMessageBox.StandardButton.Yes:
                self._build_button.setEnabled(False)
                self._build_thread.stop()
            return
        
        is_ok_to_build = self._check_before_build()
        if not is_ok_to_build:
            return
        
        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._build_thread.start()
        self._is_building = True
        self._build_button.setText(T.tr('build.stop', 'Stop'))

    def _open_output_dir(self):
        if not self._output_dir_lineedit.text().strip():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_no_output_dir', 'Please choose the output dir'))
            return

        output_dir_path = Path(self._output_dir_lineedit.text().strip())
        if not output_dir_path.exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_output_dir_not_exist', 'Output dir does not exist'))
            return
        
        system = platform.system()
        if system == 'Windows':
            os.startfile(output_dir_path)
        elif system == 'Darwin':
            subprocess.Popen(['open', output_dir_path])
        elif system == 'Linux':
            subprocess.Popen(["xdg-open", output_dir_path])
        else:
            QMessageBox.information(QApplication.activeWindow(), T.tr('message_box.information_title', 'Info'), T.tr('message_box.information_os_content', 'Unsupported Operating System'))

    def _on_build_stopped(self):
        self._is_building = False
        self._build_button.setEnabled(True)
        self._build_button.setText(T.tr('build.build', 'Build'))
        
    def _on_build_finished(self, is_successful):
        self._is_building = False
        self._build_button.setText(T.tr('build.build', 'Build'))

        if not is_successful:
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_fail_to_build', 'Failed to build the project. Please check the log.'))
    
    def _on_progress_updated(self, progress):
        self._progress_bar.setValue(progress)

    def get_build_config(self):
        project_config = get_project_config()

        app_name = self._app_name_lineedit.text().strip()
        if not app_name:
            app_name = project_config.get('caption')

        app_icon = self._app_icon_lineedit.text().strip()
        output_dir = self._output_dir_lineedit.text().strip()

        build_config = {
            "app_name": app_name,
            "app_icon": app_icon,
            "output_dir": output_dir
        }
        update_project_config('build', build_config)

        return build_config

    def retranslate(self):
        self._app_name_label.setText(T.tr('build.app_name', 'App Name'))
        self._app_name_lineedit.setPlaceholderText(T.tr('build.app_name_placeholder', 'Please enter the app name'))
        self._app_icon_label.setText(T.tr('build.app_icon', 'App Icon'))
        self._app_icon_lineedit.setPlaceholderText(T.tr('build.app_icon_placeholder', 'Please choose the app icon (.png/.ico/.icns)'))
        self._output_dir_label.setText(T.tr('build.output_dir', 'Output Dir'))
        self._output_dir_lineedit.setPlaceholderText(T.tr('build.output_dir_placeholder', 'Please choose the output dir'))
        self._clean_cache_label.setText(T.tr('build.clean_cache', 'Clean Cache'))
        self._build_button.setText(T.tr('build.build', 'Build'))
        self._open_output_dir_button.setText(T.tr('build.open_output_dir', 'Open Output Dir'))


class BuildThread(QThread):
    stopped_signal = Signal()
    finished_signal = Signal(bool)
    progress_signal = Signal(int)

    def __init__(self, window, game_manager):
        super().__init__()
        self.process = None
        self._window = window
        self._game_manager = game_manager

    def run(self):
        try:
            build_config = self._window.get_build_config()
            cmd = ['pyinstaller', '-w', '-y']
            cmd.extend(['--exclude-module', 'numpy'])

            if build_config.get('app_name'):
                cmd.extend(['-n', build_config.get('app_name')])

            if build_config.get('app_icon'):
                cmd.extend(['-i', build_config.get('app_icon')])

            system = platform.system()
            output_dir = Path(build_config.get('output_dir')) / f'build/{system}'
            output_dir.mkdir(parents=True, exist_ok=True)
            cmd.extend(['--distpath', (output_dir/'dist').as_posix()])
            cmd.extend(['--workpath', (output_dir/'_build').as_posix()])
            cmd.extend(['--specpath', output_dir.as_posix()])
            
            sep = ';' if system == 'Windows' else ':'
            project_path = Path(self._game_manager.get_project_path())
            cmd.append(self._get_add_data_param(project_path/'audio', './audio', sep))
            cmd.append(self._get_add_data_param(project_path/'image', './image', sep))
            cmd.append(self._get_add_data_param(project_path/'scene', './scene', sep))
            cmd.append(self._get_add_data_param(project_path/'project.pygs', '.', sep))

            main_file_path = (project_path / 'main.py').as_posix()
            cmd.append(main_file_path)
            cmd = [c for c in cmd if c]

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors='replace'
            )

            for line in iter(self.process.stdout.readline, ''):
                line_strip = line.strip()
                if not line_strip:
                    continue
                    
                if 'ERROR:' in line_strip or 'pyinstaller: error:' in line_strip:
                    Logger.error(line_strip)
                elif 'WARNING:' in line_strip:
                    Logger.warning(line_strip)
                else:
                    Logger.info(line_strip)

                progress = self._parse_progress(line_strip)
                if progress is not None:
                    self.progress_signal.emit(progress)

            self.process.wait()
            self.progress_signal.emit(100)
            self.finished_signal.emit(True)
        except Exception as e:
            Logger.error(str(e))
            self.finished_signal.emit(False)

    def _get_add_data_param(self, src_path, dest_path, sep):
        src_path = Path(src_path)
        dest_path = Path(dest_path)

        if not src_path.exists():
            return ''
        
        if not src_path.is_dir():
            return f"--add-data={src_path.as_posix()}{sep}{dest_path.as_posix()}"

        if not any(src_path.iterdir()):
            return ''
        else:
            return f"--add-data={(src_path/'*').as_posix()}{sep}{dest_path.as_posix()}"
        
    def _parse_progress(self, line: str):
        line = line.lower()
        if 'module search paths' in line:
            return 10
        elif 'checking analysis' in line:
            return 30
        elif 'processing standard module hook' in line:
            return 55
        elif 'including run-time hook' in line:
            return 70
        elif 'creating base_library.zip' in line:
            return 90
        elif 'checking exe' in line:
            return 95
        elif 'build complete' in line or 'finished' in line:
            return 100
        return None
    
    def stop(self):
        self.stopped_signal.emit()
        try:
            self.process.kill()
            self.terminate()
        except Exception as e:
            pass
