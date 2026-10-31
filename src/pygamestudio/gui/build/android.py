"""Android build tab: package the project into an APK, without a toolchain.

The compile-once part (Python, pygame-ce, pymunk, SDL2, the Java bootstrap)
ships inside the editor as the frozen runtime pack, so this tab only has to:

* unpack the pack (once, into the user cache),
* protect the project the same way the desktop/web builds do,
* stage the engine and write ``assets/private.tar``,
* run Gradle (debug, or release with the user's keystore) and copy the APK out.

The work folder lives in the cache on purpose: Gradle keeps its incremental
state there, so the second build of a project takes seconds instead of minutes.
"""
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *

import pygamestudio
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils import android_runtime
from pygamestudio.common.utils.config import (get_editor_config,
                                              get_project_config,
                                              update_editor_config,
                                              update_project_config)
from pygamestudio.gui.build import android_dist
from pygamestudio.gui.build import protection
from pygamestudio.gui.build import runtime_payload
from pygamestudio.gui.console.logger import Logger

#: Output sub folder of the tab (``<output>/build/Android``).
OUTPUT_SUBDIR = ('build', 'Android')
#: Orientation picker: value stored in project.pygs -> translation key.
ORIENTATION_CHOICES = (
    ('landscape', 'build.orientation_landscape'),
    ('portrait', 'build.orientation_portrait'),
    ('sensor_landscape', 'build.orientation_sensor_landscape'),
    ('sensor_portrait', 'build.orientation_sensor_portrait'),
    ('full_sensor', 'build.orientation_full_sensor'),
)
#: Build type picker: value for Gradle -> translation key.
BUILD_TYPES = (
    ('debug', 'build.android_debug'),
    ('release', 'build.android_release'),
)


def default_package(app_name):
    """The package name shown when the project has none yet."""
    return android_dist.package_name_for(app_name)


#: Kept here so the window and the thread validate the same way.
is_valid_package = android_dist.is_valid_package


class AndroidAppBuildWindow(QScrollArea):
    """The Android page of the build window."""

    #: The app icon and name are one setting shared with the other tabs
    #: (build.app_icon / build.app_name); the build window saves and mirrors them.
    app_icon_changed_signal = Signal(str)
    app_name_changed_signal = Signal(str)

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
        self._package_label = QLabel()
        self._package_lineedit = QLineEdit()
        self._version_name_label = QLabel()
        self._version_name_lineedit = QLineEdit()
        self._version_code_label = QLabel()
        self._version_code_lineedit = QLineEdit()
        self._orientation_label = QLabel()
        self._orientation_combobox = QComboBox()
        self._build_type_label = QLabel()
        self._build_type_combobox = QComboBox()
        # Signing (release builds): the two secrets stay on this machine, the
        # keystore path and the alias belong to the project.
        self._keystore_label = QLabel()
        self._keystore_lineedit = QLineEdit()
        self._keystore_browse_button = QPushButton()
        self._keystore_create_button = QPushButton()
        self._key_alias_label = QLabel()
        self._key_alias_lineedit = QLineEdit()
        self._store_password_label = QLabel()
        self._store_password_lineedit = QLineEdit()
        self._key_password_label = QLabel()
        self._key_password_lineedit = QLineEdit()
        self._progress_bar = QProgressBar()
        self._build_button = QPushButton()
        self._open_output_dir_button = QPushButton()

        self._build_thread = AndroidBuildThread(game_manager)
        self._is_building = False

        self._set_up()

    # ------------------------------------------------------------- set up
    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()

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
        self._package_label.setText(T.tr('build.android_package', 'Package Name'))
        self._package_lineedit.setPlaceholderText(T.tr('build.android_package_placeholder', 'org.pygamestudio.mygame'))
        self._version_name_label.setText(T.tr('build.android_version_name', 'Version Name'))
        self._version_code_label.setText(T.tr('build.android_version_code', 'Version Code'))
        self._version_name_lineedit.setPlaceholderText('1.0.0')
        self._version_code_lineedit.setPlaceholderText('1')
        self._orientation_label.setText(T.tr('build.android_orientation', 'Screen Orientation'))
        self._build_type_label.setText(T.tr('build.android_build_type', 'Build Type'))
        self._keystore_label.setText(T.tr('build.android_keystore', 'Keystore'))
        self._keystore_lineedit.setPlaceholderText(T.tr(
            'build.android_keystore_placeholder', 'Select the signing key (.jks/.keystore)'))
        self._keystore_browse_button.setIcon(QIcon(':/images/browse.png'))
        self._keystore_create_button.setText(T.tr('build.android_keystore_new', 'New...'))
        self._key_alias_label.setText(T.tr('build.android_key_alias', 'Key Alias'))
        self._store_password_label.setText(T.tr('build.android_store_password', 'Keystore Password'))
        self._key_password_label.setText(T.tr('build.android_key_password', 'Key Password'))
        for field in (self._store_password_lineedit, self._key_password_lineedit):
            field.setEchoMode(QLineEdit.EchoMode.Password)
        self._set_orientation_texts()
        self._set_build_type_texts()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._build_button.setText(T.tr('build.build', 'Build'))
        self._open_output_dir_button.setText(T.tr('build.open_output_dir', 'Open Output Dir'))
        self._update_button_widths()
        self._update_signing_enabled()

    def _set_signal(self):
        self._app_name_lineedit.editingFinished.connect(self._on_app_name_edited)
        self._app_icon_browse_button.clicked.connect(self._browse_app_icon)
        self._app_icon_lineedit.editingFinished.connect(self._on_app_icon_edited)
        self._output_dir_browse_button.clicked.connect(self._browse_output_dir)
        self._package_lineedit.editingFinished.connect(self._on_package_edited)
        self._version_name_lineedit.editingFinished.connect(self._on_version_name_edited)
        self._version_code_lineedit.editingFinished.connect(self._on_version_code_edited)
        self._orientation_combobox.activated.connect(self._on_orientation_activated)
        self._build_type_combobox.activated.connect(self._on_build_type_activated)
        self._keystore_browse_button.clicked.connect(self._browse_keystore)
        self._keystore_create_button.clicked.connect(self._create_keystore)
        self._keystore_lineedit.editingFinished.connect(self._on_signing_edited)
        self._key_alias_lineedit.editingFinished.connect(self._on_signing_edited)
        self._store_password_lineedit.editingFinished.connect(self._on_signing_edited)
        self._key_password_lineedit.editingFinished.connect(self._on_signing_edited)
        self._build_button.clicked.connect(self._build)
        self._open_output_dir_button.clicked.connect(self._open_output_dir)

        self._build_thread.stopped_signal.connect(self._on_build_stopped)
        self._build_thread.finished_signal.connect(self._on_build_finished)
        self._build_thread.progress_signal.connect(self._on_progress_updated)

        T.add_observer(self)

    def _set_layout(self):
        icon_layout = QHBoxLayout()
        icon_layout.addWidget(self._app_icon_lineedit)
        icon_layout.addSpacing(5)
        icon_layout.addWidget(self._app_icon_browse_button)
        output_layout = QHBoxLayout()
        output_layout.addWidget(self._output_dir_lineedit)
        output_layout.addSpacing(5)
        output_layout.addWidget(self._output_dir_browse_button)
        version_layout = QHBoxLayout()
        version_layout.addWidget(self._version_name_lineedit, 2)
        version_layout.addWidget(self._version_code_label)
        version_layout.addWidget(self._version_code_lineedit, 1)
        orientation_layout = QHBoxLayout()
        orientation_layout.addWidget(self._orientation_combobox, 1)
        orientation_layout.addSpacing(10)
        orientation_layout.addWidget(self._build_type_label)
        orientation_layout.addWidget(self._build_type_combobox, 1)
        keystore_layout = QHBoxLayout()
        keystore_layout.addWidget(self._keystore_lineedit)
        keystore_layout.addSpacing(5)
        keystore_layout.addWidget(self._keystore_browse_button)
        keystore_layout.addWidget(self._keystore_create_button)
        signing_layout = QHBoxLayout()
        signing_layout.addWidget(self._key_alias_lineedit, 2)
        signing_layout.addWidget(self._store_password_label)
        signing_layout.addWidget(self._store_password_lineedit, 2)
        signing_layout.addWidget(self._key_password_label)
        signing_layout.addWidget(self._key_password_lineedit, 2)
        button_layout = QHBoxLayout()
        button_layout.addWidget(self._build_button)
        button_layout.addSpacing(1)
        button_layout.addWidget(self._open_output_dir_button)
        button_layout.addStretch()

        layout = QGridLayout(self._central_widget)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)
        layout.addWidget(self._app_name_label, 0, 0)
        layout.addWidget(self._app_name_lineedit, 0, 1)
        layout.addWidget(self._app_icon_label, 1, 0)
        layout.addLayout(icon_layout, 1, 1)
        layout.addWidget(self._output_dir_label, 2, 0)
        layout.addLayout(output_layout, 2, 1)
        layout.addWidget(self._package_label, 3, 0)
        layout.addWidget(self._package_lineedit, 3, 1)
        layout.addWidget(self._version_name_label, 4, 0)
        layout.addLayout(version_layout, 4, 1)
        layout.addWidget(self._orientation_label, 5, 0)
        layout.addLayout(orientation_layout, 5, 1)
        layout.addWidget(self._keystore_label, 6, 0)
        layout.addLayout(keystore_layout, 6, 1)
        layout.addWidget(self._key_alias_label, 7, 0)
        layout.addLayout(signing_layout, 7, 1)
        layout.addWidget(self._progress_bar, 8, 0, 1, 2)
        layout.addLayout(button_layout, 9, 0, 1, 2)
        layout.setColumnStretch(1, 1)
        layout.setContentsMargins(5, 5, 5, 0)

    def _set_orientation_texts(self):
        selected = self._orientation_combobox.currentData()
        self._orientation_combobox.blockSignals(True)
        self._orientation_combobox.clear()
        for value, key in ORIENTATION_CHOICES:
            self._orientation_combobox.addItem(T.tr(key, value.replace('_', ' ').title()), value)
        index = self._orientation_combobox.findData(selected)
        self._orientation_combobox.setCurrentIndex(index if index >= 0 else 0)
        self._orientation_combobox.blockSignals(False)

    def _set_build_type_texts(self):
        selected = self._build_type_combobox.currentData() or 'debug'
        self._build_type_combobox.blockSignals(True)
        self._build_type_combobox.clear()
        for value, key in BUILD_TYPES:
            self._build_type_combobox.addItem(T.tr(key, value.title()), value)
        index = self._build_type_combobox.findData(selected)
        self._build_type_combobox.setCurrentIndex(index if index >= 0 else 0)
        self._build_type_combobox.blockSignals(False)

    def _update_signing_enabled(self):
        """Signing only matters for a release build (debug uses its own key)."""
        is_release = self.get_build_type() == 'release'
        for widget in (self._keystore_lineedit, self._keystore_browse_button,
                       self._keystore_create_button,
                       self._key_alias_lineedit, self._store_password_lineedit,
                       self._key_password_lineedit):
            widget.setEnabled(is_release)

    def _update_button_widths(self):
        width = max(self._build_button.sizeHint().width(),
                    self._open_output_dir_button.sizeHint().width())
        self._build_button.setMinimumWidth(width)
        self._open_output_dir_button.setMinimumWidth(width)

    # ------------------------------------------------------------ project
    def get_ready_for_project(self):
        project_config = get_project_config()
        build_config = project_config.get('build') or {}
        editor_config = get_editor_config()

        self._app_name_lineedit.setText(str(build_config.get('app_name') or ''))
        self._app_icon_lineedit.setText(str(build_config.get('app_icon') or ''))
        self._output_dir_lineedit.setText(str(build_config.get('output_dir') or ''))
        self._package_lineedit.setText(str(build_config.get('android_package') or ''))
        if not self._package_lineedit.text():
            self._package_lineedit.setText(default_package(self._app_name_lineedit.text()))
        self._version_name_lineedit.setText(str(build_config.get('android_version_name') or '1.0.0'))
        self._version_code_lineedit.setText(str(build_config.get('android_version_code') or 1))
        orientation = str(build_config.get('android_orientation') or '')
        index = self._orientation_combobox.findData(orientation)
        self._orientation_combobox.setCurrentIndex(index if index >= 0 else 0)
        index = self._build_type_combobox.findData(str(build_config.get('android_build_type') or 'debug'))
        self._build_type_combobox.setCurrentIndex(index if index >= 0 else 0)

        self._keystore_lineedit.setText(str(build_config.get('android_keystore') or ''))
        self._key_alias_lineedit.setText(str(build_config.get('android_key_alias') or ''))
        self._store_password_lineedit.setText(str(editor_config.get('android_store_password') or ''))
        self._key_password_lineedit.setText(str(editor_config.get('android_key_password') or ''))
        self._update_signing_enabled()

    # --------------------------------------------------------------- edits
    def _browse_app_icon(self):
        icon_path, _ = QFileDialog.getOpenFileName(
            self, T.tr('build.select_app_icon', 'Select App Icon'),
            self._game_manager.get_project_path(), 'Format (*png *.ico *.icns)')
        if icon_path:
            self._app_icon_lineedit.setText(icon_path)
            self._on_app_icon_edited()

    def _on_app_icon_edited(self):
        self.app_icon_changed_signal.emit(self._app_icon_lineedit.text().strip())

    def set_app_icon(self, icon_path):
        icon_path = str(icon_path or '')
        if self._app_icon_lineedit.text() != icon_path:
            self._app_icon_lineedit.setText(icon_path)

    def _on_app_name_edited(self):
        self.app_name_changed_signal.emit(self._app_name_lineedit.text().strip())

    def set_app_name(self, app_name):
        app_name = str(app_name or '')
        if self._app_name_lineedit.text() != app_name:
            self._app_name_lineedit.setText(app_name)

    def _browse_output_dir(self):
        output_dir = QFileDialog.getExistingDirectory(
            self, T.tr('build.select_output_dir', 'Select Output Dir'))
        if output_dir:
            self._output_dir_lineedit.setText(output_dir)

    def _on_package_edited(self):
        package = self._package_lineedit.text().strip()
        if package and not is_valid_package(package):
            Logger.warning(T.tr('build.android_package_invalid',
                                'A package name must be two or more lowercase segments, e.g. org.pygamestudio.mygame'))
            return
        update_project_config('build.android_package', package)

    def _on_version_name_edited(self):
        update_project_config('build.android_version_name',
                              self._version_name_lineedit.text().strip() or '1.0.0')

    def _on_version_code_edited(self):
        text = self._version_code_lineedit.text().strip()
        update_project_config('build.android_version_code',
                              int(text) if text.isdigit() else 1)

    def _on_orientation_activated(self, index):
        update_project_config('build.android_orientation',
                              str(self._orientation_combobox.currentData() or ''))

    def _on_build_type_activated(self, index):
        update_project_config('build.android_build_type', self.get_build_type())
        self._update_signing_enabled()

    def get_build_type(self):
        """``debug`` or ``release``."""
        return str(self._build_type_combobox.currentData() or 'debug')

    def _browse_keystore(self):
        start = self._keystore_lineedit.text().strip() or self._game_manager.get_project_path()
        keystore_path, _ = QFileDialog.getOpenFileName(
            self, T.tr('build.android_select_keystore', 'Select the keystore'),
            start, 'Keystore (*.jks *.keystore *.p12)')
        if keystore_path:
            self._keystore_lineedit.setText(Path(keystore_path).as_posix())
            self._on_signing_edited()

    def _create_keystore(self):
        """Create a self-signed release key with the JDK's keytool."""
        title = T.tr('build.android_keystore_new_title', 'Create a signing key')
        output_dir = (self._output_dir_lineedit.text().strip()
                      or self._game_manager.get_project_path())
        app_name = self._app_name_lineedit.text().strip() or 'game'
        default = Path(output_dir) / f'{app_name}-release.jks'
        path, _ = QFileDialog.getSaveFileName(self, title, default.as_posix(),
                                              'Keystore (*.jks)')
        if not path:
            return

        alias, accepted = QInputDialog.getText(
            self, title, T.tr('build.android_key_alias', 'Key Alias'), text='release')
        if not accepted or not alias.strip():
            return
        password, accepted = QInputDialog.getText(
            self, title, T.tr('build.android_store_password', 'Keystore Password'),
            QLineEdit.EchoMode.Password)
        if not accepted or not password:
            return

        try:
            config = get_editor_config()
            toolchain = android_runtime.check_toolchain(config.get('android_jdk') or '',
                                                        config.get('android_sdk') or '')
            android_dist.create_keystore(toolchain.get('jdk') or '', path,
                                         alias.strip(), password, common_name=app_name)
        except Exception as error:                        # noqa: BLE001 - report in the console
            Logger.error(T.tr('build.android_keystore_create_failed',
                              'Could not create the signing key: {}').format(error))
            return

        self._keystore_lineedit.setText(Path(path).as_posix())
        self._key_alias_lineedit.setText(alias.strip())
        self._store_password_lineedit.setText(password)
        self._key_password_lineedit.setText(password)
        self._on_signing_edited()
        Logger.info(T.tr('build.android_keystore_created',
                         'Signing key created: {}').format(Path(path).as_posix()))

    def _on_signing_edited(self):
        """Keystore/alias belong to the project, the passwords to this machine."""
        update_project_config('build.android_keystore',
                              self._keystore_lineedit.text().strip())
        update_project_config('build.android_key_alias',
                              self._key_alias_lineedit.text().strip())
        update_editor_config('android_store_password', self._store_password_lineedit.text())
        update_editor_config('android_key_password', self._key_password_lineedit.text())

    # --------------------------------------------------------------- build
    def get_build_config(self):
        output_dir = self._output_dir_lineedit.text().strip()
        editor_config = get_editor_config()
        return {
            'project_path': self._game_manager.get_project_path(),
            'output_dir': output_dir,
            'app_name': self._app_name_lineedit.text().strip(),
            'app_icon': self._app_icon_lineedit.text().strip(),
            'package': self._package_lineedit.text().strip(),
            'orientation': str(self._orientation_combobox.currentData() or ''),
            'version_name': self._version_name_lineedit.text().strip() or '1.0.0',
            'version_code': self._version_code_lineedit.text().strip() or '1',
            'build_type': self.get_build_type(),
            'keystore': self._keystore_lineedit.text().strip(),
            'key_alias': self._key_alias_lineedit.text().strip(),
            'store_password': self._store_password_lineedit.text(),
            'key_password': self._key_password_lineedit.text(),
            'jdk': str(editor_config.get('android_jdk') or ''),
            'sdk': str(editor_config.get('android_sdk') or ''),
            'gradle': str(editor_config.get('android_gradle') or ''),
        }

    def _check_before_build(self):
        if not (Path(self._game_manager.get_project_path()) / 'main.py').exists():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'),
                                 T.tr('message_box.critical_main_not_found', 'main.py is not found'))
            return False

        if not self._app_name_lineedit.text().strip():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'),
                                 T.tr('build.android_no_app_name', 'Please enter the app name'))
            return False

        icon = self._app_icon_lineedit.text().strip()
        if icon and not Path(icon).is_file():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'),
                                 T.tr('message_box.critical_app_icon_not_exist', 'App icon does not exist'))
            return False

        output_dir = self._output_dir_lineedit.text().strip()
        if not output_dir:
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'),
                                 T.tr('message_box.critical_no_output_dir', 'Please choose the output dir'))
            return False
        if not Path(output_dir).is_dir():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'),
                                 T.tr('message_box.critical_output_dir_not_exist', 'Output dir does not exist'))
            return False

        if not is_valid_package(self._package_lineedit.text().strip()):
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'),
                                 T.tr('build.android_package_invalid',
                                      'A package name must be two or more lowercase segments, e.g. org.pygamestudio.mygame'))
            return False

        if self.get_build_type() == 'release':
            keystore = self._keystore_lineedit.text().strip()
            if not keystore or not Path(keystore).is_file():
                QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'),
                                     T.tr('build.android_keystore_missing',
                                          'A release build needs a keystore: choose the .jks file first'))
                return False
            if not self._key_alias_lineedit.text().strip():
                QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'),
                                     T.tr('build.android_alias_missing', 'Please enter the key alias'))
                return False

        try:
            android_runtime.find_pack()
        except android_runtime.AndroidRuntimeError as error:
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'),
                                 T.tr('build.android_pack_missing',
                                      'The Android runtime is missing from the editor: {}').format(error.detail))
            return False
        return True

    def _build(self):
        if self._is_building:
            choice = QMessageBox.question(
                QApplication.activeWindow(), T.tr('message_box.quesiton_title', 'Confirm'),
                T.tr('message_box.question_stop_build', 'Sure to stop the building?'))
            if choice == QMessageBox.StandardButton.Yes:
                self._build_button.setEnabled(False)
                self._build_thread.stop()
            return

        if not self._check_before_build():
            return

        self._progress_bar.setValue(0)
        self._build_thread.set_build_config(self.get_build_config())
        self._build_thread.start()
        self._is_building = True
        self._build_button.setText(T.tr('build.stop', 'Stop'))

    def _open_output_dir(self):
        output_dir = self._output_dir_lineedit.text().strip()
        if not output_dir:
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'),
                                 T.tr('message_box.critical_no_output_dir', 'Please choose the output dir'))
            return
        if not Path(output_dir).is_dir():
            QMessageBox.critical(self, T.tr('message_box.critical_title', 'Error'),
                                 T.tr('message_box.critical_output_dir_not_exist', 'Output dir does not exist'))
            return
        target = Path(output_dir).joinpath(*OUTPUT_SUBDIR)
        target.mkdir(parents=True, exist_ok=True)

        system = platform.system()
        if system == 'Windows':
            os.startfile(target)
        elif system == 'Darwin':
            subprocess.Popen(['open', target])
        elif system == 'Linux':
            subprocess.Popen(['xdg-open', target])
        else:
            QMessageBox.information(QApplication.activeWindow(),
                                    T.tr('message_box.information_title', 'Info'),
                                    T.tr('message_box.information_os_content', 'Unsupported Operating System'))

    # -------------------------------------------------------------- events
    def _on_build_stopped(self):
        self._is_building = False
        self._progress_bar.setValue(0)
        self._build_button.setEnabled(True)
        self._build_button.setText(T.tr('build.build', 'Build'))

    def _on_build_finished(self, is_successful):
        self._is_building = False
        self._build_button.setEnabled(True)
        self._build_button.setText(T.tr('build.build', 'Build'))
        if is_successful:
            self._progress_bar.setValue(100)

    def _on_progress_updated(self, progress):
        self._progress_bar.setValue(max(0, min(100, int(progress))))

    def retranslate(self):
        self._app_name_label.setText(T.tr('build.app_name', 'App Name'))
        self._app_name_lineedit.setPlaceholderText(T.tr('build.app_name_placeholder', 'Please enter the app name'))
        self._app_icon_label.setText(T.tr('build.app_icon', 'App Icon'))
        self._app_icon_lineedit.setPlaceholderText(T.tr('build.app_icon_placeholder', 'Please choose the app icon (.png/.ico/.icns)'))
        self._output_dir_label.setText(T.tr('build.output_dir', 'Output Dir'))
        self._output_dir_lineedit.setPlaceholderText(T.tr('build.output_dir_placeholder', 'Please choose the output dir'))
        self._package_label.setText(T.tr('build.android_package', 'Package Name'))
        self._package_lineedit.setPlaceholderText(T.tr('build.android_package_placeholder', 'org.pygamestudio.mygame'))
        self._version_name_label.setText(T.tr('build.android_version_name', 'Version Name'))
        self._version_code_label.setText(T.tr('build.android_version_code', 'Version Code'))
        self._orientation_label.setText(T.tr('build.android_orientation', 'Screen Orientation'))
        self._build_type_label.setText(T.tr('build.android_build_type', 'Build Type'))
        self._keystore_label.setText(T.tr('build.android_keystore', 'Keystore'))
        self._keystore_create_button.setText(T.tr('build.android_keystore_new', 'New...'))
        self._key_alias_label.setText(T.tr('build.android_key_alias', 'Key Alias'))
        self._store_password_label.setText(T.tr('build.android_store_password', 'Keystore Password'))
        self._key_password_label.setText(T.tr('build.android_key_password', 'Key Password'))
        self._set_orientation_texts()
        self._set_build_type_texts()
        self._build_button.setText(T.tr('build.build', 'Build') if not self._is_building
                                   else T.tr('build.stop', 'Stop'))
        self._open_output_dir_button.setText(T.tr('build.open_output_dir', 'Open Output Dir'))
        self._update_signing_enabled()

    def enterEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().enterEvent(event)


class AndroidBuildThread(QThread):
    """The worker: unpack, protect, stage, inject, Gradle, copy the APK."""

    stopped_signal = Signal()
    finished_signal = Signal(bool)
    progress_signal = Signal(int)

    def __init__(self, game_manager):
        super().__init__()
        self._game_manager = game_manager
        self._build_config = {}
        self._stop_requested = False
        self.apk_path = None

    def set_build_config(self, build_config):
        """Take a snapshot (filled in on the UI thread, read by the worker)."""
        self._build_config = dict(build_config or {})

    def stop(self):
        self._stop_requested = True

    # ---------------------------------------------------------- utilities
    def _emit(self, start, end):
        def report(percent):
            self.progress_signal.emit(int(start + (end - start) * max(0, min(100, percent)) / 100))
        return report

    def _check_stop(self):
        return self._stop_requested

    # ---------------------------------------------------------------- run
    def run(self):
        try:
            self._stop_requested = False
            self.apk_path = None
            self.progress_signal.emit(0)

            config = self._build_config
            project_path = Path(config.get('project_path') or
                                self._game_manager.get_project_path())
            output_dir = Path(config.get('output_dir')) / Path(*OUTPUT_SUBDIR)
            output_dir.mkdir(parents=True, exist_ok=True)
            app_name = str(config.get('app_name') or '').strip() or 'game'
            is_release = str(config.get('build_type') or 'debug') == 'release'

            Logger.info(T.tr('build.android_start', 'Packaging the APK...'))
            runtime_dir = android_runtime.ensure_unpacked(self._emit(0, 20))

            toolchain = android_runtime.check_toolchain(config.get('jdk') or '',
                                                        config.get('sdk') or '')
            if not toolchain['ok']:
                raise android_dist.AndroidBuildError(
                    T.tr('build.android_toolchain_problem',
                         'Missing build tools - open Editor Settings > Android Build:\n{}').format(
                        '\n'.join(T.tr(key, key) for key in toolchain['problems'])),
                    toolchain['problems'][0])

            Logger.info(T.tr('build.android_staging', 'Protecting the project and staging the engine...'))
            payload_root = android_runtime.cache_root() / 'payload'
            prepared = protection.prepare(project_path, payload_root)
            payload_dir = prepared['project_dir']
            engine_root = Path(pygamestudio.__file__).parent
            staged = runtime_payload.stage(engine_root, payload_dir)
            Logger.info(T.tr('build.android_payload', 'Payload: {} project file(s), {} engine file(s)').format(
                prepared['stage_summary']['files'], staged['files']))
            self.progress_signal.emit(35)
            if self._check_stop():
                self._finish_stopped()
                return

            signing = None
            if is_release:
                signing = {'keystore': config.get('keystore') or '',
                           'alias': config.get('key_alias') or ''}
                if not signing['keystore'] or not signing['alias']:
                    raise android_dist.AndroidBuildError(
                        T.tr('build.android_keystore_missing',
                             'A release build needs a keystore: choose the .jks file first'),
                        'android.error_keystore')

            dist_dir = android_runtime.cache_root() / 'dist'
            Logger.info(T.tr('build.android_assets', 'Writing icon, splash and manifest...'))
            android_dist.prepare_dist(
                runtime_dir, dist_dir,
                app_name=app_name,
                package=config.get('package') or default_package(app_name),
                version_code=int(config.get('version_code') or 1),
                version_name=str(config.get('version_name') or '1.0.0'),
                orientation=config.get('orientation') or android_dist.DEFAULT_ORIENTATION,
                min_sdk=android_runtime.MIN_SDK,
                compile_sdk=android_runtime.COMPILE_SDK,
                sdk_dir=toolchain['sdk'],
                icon=config.get('app_icon') or '',
                presplash=config.get('app_icon') or '',
                signing=signing,
                on_progress=self._emit(35, 70))

            Logger.info(T.tr('build.android_payload_tar', 'Writing assets/private.tar...'))
            tar_summary = android_dist.write_payload(
                payload_dir, dist_dir / 'src' / 'main' / 'assets' / 'private.tar',
                numeric_version=int(config.get('version_code') or 1),
                min_sdk=android_runtime.MIN_SDK)
            Logger.info(T.tr('build.android_payload_tar_done',
                             'private.tar: {} file(s), {}').format(
                tar_summary['files'], self._size(tar_summary['bytes'])))
            self.progress_signal.emit(75)
            if self._check_stop():
                self._finish_stopped()
                return

            Logger.info(T.tr('build.android_gradle',
                             'Running Gradle (the first build downloads its dependencies)...'))
            task = android_dist.RELEASE_TASK if is_release else android_dist.DEBUG_TASK
            codes = []
            gradle_home = android_runtime.default_gradle_home()
            gradle_dir = config.get('gradle') or ''
            secrets_env = android_dist.signing_environment(signing, config)
            code = android_dist.run_gradle(
                dist_dir, toolchain['jdk'], toolchain['sdk'], gradle_home,
                task=task,
                on_line=lambda line: self._on_gradle_line(line, codes),
                on_progress=self._emit(75, 95),
                stop_check=self._check_stop,
                gradle_dir=gradle_dir,
                extra_environment=secrets_env)

            # A machine behind a proxy (the usual Clash/v2ray setup) reaches the
            # internet in the browser but not from Java, which has no system
            # proxy support: the very first download times out. Retry once with
            # the proxy Java ignores.
            if code != 0 and not self._stop_requested:
                proxy = android_dist.windows_proxy()
                if proxy and android_dist.is_network_failure('\n'.join(codes[-80:])):
                    Logger.info(T.tr('build.android_proxy_retry',
                                     'The download failed; retrying through the system proxy {}:{}').format(*proxy))
                    android_dist.use_proxy(dist_dir, proxy)
                    codes.clear()
                    code = android_dist.run_gradle(
                        dist_dir, toolchain['jdk'], toolchain['sdk'], gradle_home,
                        task=task,
                        on_line=lambda line: self._on_gradle_line(line, codes),
                        on_progress=self._emit(75, 95),
                        stop_check=self._check_stop,
                        gradle_dir=gradle_dir,
                        extra_environment=secrets_env,
                        proxy=proxy)

            if self._stop_requested:
                self._finish_stopped()
                return
            if code != 0:
                hint = android_dist.translate_error('\n'.join(codes[-80:]))
                raise android_dist.AndroidBuildError(
                    T.tr('build.android_gradle_failed',
                         'Gradle failed (exit code {}). See the console for the full log.').format(code),
                    hint or 'android.error_build')

            apk = android_dist.find_apk(dist_dir)
            if apk is None:
                raise android_dist.AndroidBuildError(
                    T.tr('build.android_apk_missing',
                         'Gradle finished but no APK was produced.'),
                    'android.error_apk_missing')

            suffix = '-release' if is_release else ''
            target = output_dir / f'{self._safe_file_name(app_name)}{suffix}.apk'
            shutil.copy2(apk, target)
            self.apk_path = target
            self.progress_signal.emit(100)
            Logger.info(T.tr('build.android_apk_done', 'APK: {}').format(target.as_posix()))
            self.finished_signal.emit(True)
        except android_runtime.AndroidRuntimeError as error:
            Logger.error(T.tr(error.reason, str(error)))
            self.finished_signal.emit(False)
        except android_dist.AndroidBuildError as error:
            Logger.error(T.tr(error.reason, str(error)))
            self.finished_signal.emit(False)
        except protection.ProtectionError as error:
            Logger.error(T.tr('android.error_protection',
                              'The project could not be prepared: {}').format(error))
            self.finished_signal.emit(False)
        except Exception as error:                        # noqa: BLE001 - report, never crash
            Logger.error(str(error))
            self.finished_signal.emit(False)

    def _finish_stopped(self):
        Logger.info(T.tr('build.build_stopped', 'Build stopped'))
        self.stopped_signal.emit()

    def _on_gradle_line(self, line, codes):
        codes.append(line)
        lowered = line.lower()
        if 'error' in lowered or line.startswith('FAILURE'):
            Logger.error(line)
        elif 'warning' in lowered:
            Logger.warning(line)
        else:
            Logger.info(line)

    @staticmethod
    def _size(count):
        for unit in ('B', 'KB', 'MB', 'GB'):
            if count < 1024 or unit == 'GB':
                return f'{count:.1f} {unit}'
            count /= 1024

    @staticmethod
    def _safe_file_name(name):
        cleaned = re.sub(r'[\\/:*?"<>|]+', '', str(name or 'game')).strip()
        return cleaned or 'game'
