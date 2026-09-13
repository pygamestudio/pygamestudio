import ast
import importlib.util
import os
import platform
import subprocess
import sys
import sysconfig
from pathlib import Path
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.console.logger import Logger
from pygamestudio.gui.build import obfuscation
from pygamestudio.gui.build import assets as asset_build
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils.config import get_project_config, update_project_config
from pygamestudio.common.utils.path import LANG_PATH, RES_PATH


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

        self._build_thread = BuildThread(self._game_manager)
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
        self._clean_cache_checkbox.setToolTip(T.tr('build.clean_cache_tooltip', 'Clear the PyInstaller cache and temporary files before building'))
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._build_button.setText(T.tr('build.build', 'Build'))
        self._open_output_dir_button.setText(T.tr('build.open_output_dir', 'Open Output Dir'))
        self._update_button_widths()
        
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
        button_layout.addStretch()
        button_layout.addWidget(self._clean_cache_label)
        button_layout.addSpacing(5)
        button_layout.addWidget(self._clean_cache_checkbox)

        main_g_layout = QGridLayout(self._central_widget)
        main_g_layout.setHorizontalSpacing(10)
        main_g_layout.setVerticalSpacing(10)
        main_g_layout.addWidget(self._app_name_label, 0, 0, 1, 1)
        main_g_layout.addLayout(app_name_layout, 0, 1)
        main_g_layout.addWidget(self._app_icon_label, 1, 0, 1, 1)
        main_g_layout.addLayout(app_icon_layout, 1, 1)
        main_g_layout.addWidget(self._output_dir_label, 2, 0, 1, 1)
        main_g_layout.addLayout(output_dir_layout, 2, 1)
        main_g_layout.addWidget(self._progress_bar, 3, 0, 1, 2)
        main_g_layout.addLayout(button_layout, 4, 0, 1, 2)
        main_g_layout.setColumnStretch(1, 1)
        main_g_layout.setContentsMargins(5, 5, 5, 0)
        
    def _set_object_name(self):
        self._build_button.setObjectName('desktopAppBuildBtn')

    def _update_button_widths(self):
        """Give both buttons one width, wide enough for the longer label."""
        button_width = max(self._build_button.sizeHint().width(), self._open_output_dir_button.sizeHint().width())
        self._build_button.setMinimumWidth(button_width)
        self._open_output_dir_button.setMinimumWidth(button_width)

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

        try:
            self._clean_cache_checkbox.setChecked(bool(project_config['build']['clean_cache']))
        except Exception as e:
            self._clean_cache_checkbox.setChecked(False)

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

        try:
            has_pyinstaller = importlib.util.find_spec('PyInstaller') is not None
        except (ImportError, ValueError):
            has_pyinstaller = False

        if not has_pyinstaller:
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_no_pyinstaller', 'PyInstaller is not installed. Please install it with "pip install pyinstaller" and build again.'))
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
        self._build_thread.set_build_config(self.get_build_config())
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
        self._progress_bar.hide()
        
    def _on_build_finished(self, is_successful):
        self._is_building = False
        self._build_button.setEnabled(True)
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
            "output_dir": output_dir,
            "clean_cache": self._clean_cache_checkbox.isChecked()
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
        self._clean_cache_checkbox.setToolTip(T.tr('build.clean_cache_tooltip', 'Clear the PyInstaller cache and temporary files before building'))
        self._build_button.setText(T.tr('build.build', 'Build'))
        self._open_output_dir_button.setText(T.tr('build.open_output_dir', 'Open Output Dir'))
        self._update_button_widths()


class BuildThread(QThread):
    stopped_signal = Signal()
    finished_signal = Signal(bool)
    progress_signal = Signal(int)

    #: Directories that never belong in a build (caches, virtual envs, VCS data).
    _IGNORED_DIR_NAMES = {'__pycache__', 'node_modules', 'venv', 'env', 'dist', 'build'}
    #: PyInstaller log fragments (lower case) mapped to build progress values.
    #: The pipeline only ever moves forward, see _emit_progress().
    _PROGRESS_STAGES = (
        ('module search paths', 5),
        ('checking analysis', 10),
        ('initializing module dependency graph', 12),
        ('caching module graph hooks', 15),
        ('analyzing', 20),
        ('loading module hook', 30),
        ('processing standard module hook', 30),
        ('including run-time hook', 45),
        ('processing run-time hook', 45),
        ('checking pyz', 55),
        ('building pyz', 60),
        ('checking pkg', 65),
        ('building pkg', 70),
        ('checking exe', 75),
        ('building exe', 80),
        ('copying icon', 85),
        ('embedding manifest', 85),
        ('appending pkg archive', 88),
        ('checking collect', 90),
        ('building collect', 93),
        ('build complete', 99),
    )

    def __init__(self, game_manager):
        super().__init__()
        self.process = None
        self._game_manager = game_manager
        self._build_config = {}
        self._progress_value = 0
        self._stop_requested = False

    def set_build_config(self, build_config):
        """Take a snapshot of the build configuration.

        It is filled in by the window on the UI thread, so the worker never
        touches a widget and the values stay stable while the build runs.
        """
        self._build_config = dict(build_config or {})

    def run(self):
        try:
            self._progress_value = 0
            self._stop_requested = False

            build_config = self._build_config
            project_path = Path(self._game_manager.get_project_path())
            output_dir = Path(build_config.get('output_dir')) / f'build/{platform.system()}'
            output_dir.mkdir(parents=True, exist_ok=True)

            environment = dict(os.environ)
            environment['PYTHONIOENCODING'] = 'utf-8'
            environment['PYTHONUTF8'] = '1'
            creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == 'Windows' else 0

            self.process = subprocess.Popen(
                self._build_command(build_config, project_path, output_dir),
                cwd=project_path.as_posix(),
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=creation_flags
            )
            if self._stop_requested:
                self.process.kill()

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
                    self._emit_progress(progress)

            return_code = self.process.wait()

            if self._stop_requested:
                Logger.info(T.tr('build.build_stopped', 'Build stopped'))
                self.stopped_signal.emit()
                return

            is_successful = return_code == 0
            if not is_successful:
                Logger.error(T.tr('build.build_fail_return_code', 'PyInstaller exited with code {}').format(return_code))
            else:
                executable_path = self._get_executable_path(build_config.get('app_name'), output_dir)
                if executable_path is None:
                    Logger.error(T.tr('build.build_exe_not_found', 'The build completed but the executable was not found: {}').format((output_dir / 'dist').as_posix()))
                    is_successful = False
                else:
                    Logger.info(T.tr('build.build_output', 'Build output: {}').format(executable_path.parent.as_posix()))
                    self._emit_progress(100)

            self.finished_signal.emit(is_successful)
        except Exception as e:
            Logger.error(str(e))
            self.finished_signal.emit(False)

    def _build_command(self, build_config, project_path, output_dir):
        """Assemble the complete PyInstaller command line."""
        cmd = [sys.executable, '-m', 'PyInstaller', '-w', '-y']

        if build_config.get('clean_cache'):
            cmd.append('--clean')

        # Project scripts are loaded at runtime, so their imports have to be
        # collected up front - PyInstaller's static analysis cannot see them.
        hidden_imports, missing_imports = self._scan_project_imports(project_path)
        if hidden_imports:
            Logger.info(T.tr('build.build_hidden_imports', 'Imports found in the project: {}').format(', '.join(hidden_imports)))
        for name in hidden_imports:
            cmd.append(f'--hidden-import={name}')
        if missing_imports:
            Logger.warning(T.tr('build.build_import_missing', 'Modules that could not be found, skipped: {}').format(', '.join(missing_imports)))

        # Qt is only needed by the editor, a game does not use it at all, so
        # PySide6 stays out of the build (unless a project script imports it).
        if 'PySide6' not in hidden_imports:
            cmd.append('--exclude-module=PySide6')
        if 'numpy' not in hidden_imports:
            cmd.append('--exclude-module=numpy')

        app_name = build_config.get('app_name')
        if app_name:
            cmd.extend(['-n', app_name])

        icon_path = self._prepare_icon(build_config.get('app_icon'), output_dir)
        if icon_path:
            cmd.extend(['-i', icon_path])

        cmd.extend(['--distpath', (output_dir / 'dist').as_posix()])
        cmd.extend(['--workpath', (output_dir / '_build').as_posix()])
        cmd.extend(['--specpath', output_dir.as_posix()])

        # The build packages a staging copy of the project: the code of that
        # copy loses every comment/docstring (and is obfuscated when pyobfus is
        # available) and its assets are encrypted. The project stays untouched.
        build_project_path = self._prepare_build_project(project_path, output_dir)

        sep = ';' if platform.system() == 'Windows' else ':'
        cmd.extend(self._get_project_data_params(build_project_path, output_dir, sep))
        # Engine data that is read from the file system at runtime; PyInstaller
        # only collects the .py files of the engine on its own.
        cmd.append(self._get_add_data_param(RES_PATH / 'images', 'pygamestudio/common/res/images', sep))
        cmd.append(self._get_add_data_param(LANG_PATH, 'pygamestudio/common/i18n/languages', sep))

        cmd.append((build_project_path / 'main.py').as_posix())
        return [part for part in cmd if part]

    def _prepare_build_project(self, project_path, output_dir):
        """Create the protected staging copy that gets packaged.

        :return: the staged project folder; the project itself is never touched.
        """
        Logger.info(T.tr('build.protection_running', 'Preparing the project code and assets ...'))
        try:
            result = obfuscation.prepare(project_path, output_dir)
        except asset_build.AssetBuildError as e:
            Logger.error(T.tr('build.assets_failed', 'Encrypting the project assets failed, the build is stopped: {}').format(e))
            raise
        except obfuscation.ObfuscationError as e:
            # Never ship readable code silently when obfuscation was expected -
            # the user would not notice the difference.
            Logger.error(T.tr('build.obfuscation_failed', 'Code obfuscation failed, the build is stopped: {}').format(e))
            raise
        except obfuscation.ProtectionError as e:
            Logger.error(T.tr('build.staging_failed', 'The project could not be prepared for the build, the build is stopped: {}').format(e))
            raise

        if result['obfuscation_summary'] is None:
            Logger.warning(T.tr('build.obfuscation_unavailable', 'pyobfus was not found: the code is stripped but not name-obfuscated'))
        else:
            Logger.info(T.tr('build.obfuscation_enabled', 'Obfuscated {} python file(s), no comment or docstring left').format(result['obfuscation_summary']['files']))
        summary = result['asset_summary']['summary']
        Logger.info(T.tr('build.assets_encrypted', 'Encrypted {} asset file(s) ({} KB)').format(summary['files'], round(summary['bytes'] / 1024)))
        return result['project_dir']

    def _get_project_data_params(self, project_path, output_dir, sep):
        """One --add-data per top level project entry (build outputs excluded)."""
        params = []
        skipped = []
        output_resolved = output_dir.resolve()

        for entry in sorted(project_path.iterdir()):
            if entry.name in self._IGNORED_DIR_NAMES or entry.name.startswith('.'):
                skipped.append(entry.name)
                continue

            entry_resolved = entry.resolve()
            if entry_resolved == output_resolved or output_resolved.is_relative_to(entry_resolved):
                # never package the build output itself: the output dir may be
                # inside the project folder
                skipped.append(entry.name)
                continue

            param = self._get_add_data_param(entry, f'./{entry.name}' if entry.is_dir() else '.', sep)
            if param:
                params.append(param)

        if skipped:
            Logger.info(T.tr('build.build_entries_skipped', 'Excluded from the package: {}').format(', '.join(skipped)))
        return params

    def _get_add_data_param(self, src_path, dest_path, sep):
        src_path = Path(src_path)
        if not src_path.exists():
            return ''
        # an empty directory would add nothing, PyInstaller cannot copy it
        if src_path.is_dir() and not any(src_path.iterdir()):
            return ''
        return f"--add-data={src_path.as_posix()}{sep}{dest_path}"

    def _prepare_icon(self, app_icon, output_dir):
        """Return a usable icon path; PyInstaller wants .ico on Windows."""
        if not app_icon:
            return ''
        icon_path = Path(app_icon)
        if platform.system() != 'Windows' or icon_path.suffix.lower() == '.ico':
            return icon_path.as_posix()

        icon_image = QImage(icon_path.as_posix())
        if not icon_image.isNull() and max(icon_image.width(), icon_image.height()) > 256:
            icon_image = icon_image.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        icon_file_path = output_dir / f'{icon_path.stem}.ico'
        if icon_image.isNull() or not icon_image.save(icon_file_path.as_posix(), 'ICO'):
            Logger.warning(T.tr('build.build_icon_convert_failed', 'Failed to convert the icon {}, the original file is used').format(icon_path.name))
            return icon_path.as_posix()
        return icon_file_path.as_posix()

    def _scan_project_imports(self, project_path):
        """Top level imports of the project scripts.

        :return: a tuple of (imports to keep, imports that could not be found)
        """
        imported_names = set()
        for script_path in self._iter_project_scripts(project_path):
            try:
                script_tree = ast.parse(script_path.read_text(encoding='utf-8'))
            except (OSError, SyntaxError, UnicodeDecodeError) as e:
                Logger.warning(f'{script_path.name}: {e}')
                continue

            for node in ast.walk(script_tree):
                if isinstance(node, ast.Import):
                    imported_names.update(alias.name.split('.')[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported_names.add(node.module.split('.')[0])

        local_modules = {script_path.stem for script_path in self._iter_project_scripts(project_path)}
        stdlib_path = Path(sysconfig.get_paths()['stdlib']).resolve()

        hidden_imports = []
        missing_imports = []
        for name in sorted(imported_names):
            if name == 'pygamestudio' or name in local_modules:
                continue

            module_spec = self._find_module(name)
            if module_spec is None:
                missing_imports.append(name)
                continue

            origin = getattr(module_spec, 'origin', None)
            if origin in ('built-in', 'frozen'):
                continue
            if origin is not None:
                origin_path = Path(origin)
                is_site_package = 'site-packages' in origin_path.parts or 'dist-packages' in origin_path.parts
                if not is_site_package and origin_path.resolve().is_relative_to(stdlib_path):
                    continue
            hidden_imports.append(name)

        return hidden_imports, missing_imports

    def _iter_project_scripts(self, project_path):
        """Python files of the project, skipping caches and virtual envs."""
        for script_path in sorted(project_path.rglob('*.py')):
            parents = script_path.relative_to(project_path).parts[:-1]
            if any(parent in self._IGNORED_DIR_NAMES or parent.startswith('.') for parent in parents):
                continue
            yield script_path

    @staticmethod
    def _find_module(name):
        try:
            return importlib.util.find_spec(name)
        except (AttributeError, ImportError, ValueError):
            return None

    @staticmethod
    def _get_executable_path(app_name, output_dir):
        """Path of the built executable, or None when it was not created."""
        if not app_name:
            return None
        executable_name = f'{app_name}.exe' if platform.system() == 'Windows' else app_name
        executable_path = output_dir / 'dist' / app_name / executable_name
        return executable_path if executable_path.exists() else None

    def _emit_progress(self, progress):
        """Progress only ever moves forward, no matter in which order the log arrives."""
        if progress > self._progress_value:
            self._progress_value = progress
            self.progress_signal.emit(progress)

    def _parse_progress(self, line: str):
        line = line.lower()
        for keyword, progress in self._PROGRESS_STAGES:
            if keyword in line:
                return progress
        return None

    def stop(self):
        """Ask the running build to stop (called from the UI thread)."""
        self._stop_requested = True
        process = self.process
        if process is not None and process.poll() is None:
            try:
                process.kill()
            except OSError as e:
                Logger.error(str(e))
