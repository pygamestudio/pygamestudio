"""Offscreen check of the Android UI: the build tab and the settings page.

No display and no real configuration: ``APPDATA``/``LOCALAPPDATA`` (and the XDG
equivalents) point at a temporary folder, so the editor config the widgets read
and write is a throw-away copy and the user's own settings stay untouched.

    py -3.10 tools/android_spike/check_android_ui.py
"""
import os
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPIKE_APP = REPO_ROOT / 'tools' / 'android_spike' / 'app'

TEMP = tempfile.mkdtemp(prefix='pygs-android-ui-')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
for variable in ('APPDATA', 'LOCALAPPDATA', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME',
                 'XDG_DATA_HOME', 'HOME'):
    os.environ[variable] = TEMP
# platformdirs asks the shell on Windows and ignores APPDATA, so the editor
# config folder is pointed somewhere throw-away explicitly.
os.environ['PYGAMESTUDIO_EDITOR_DIR'] = str(Path(TEMP) / 'editor')

PROJECT_DIR = Path(TEMP) / 'project'
shutil.copytree(SPIKE_APP, PROJECT_DIR,
                ignore=shutil.ignore_patterns('pygamestudio', '__pycache__', '*.pyc'))
os.environ['__PYGAMESTUDIO_PROJECT_PATH'] = str(PROJECT_DIR)
os.environ['PROJECT_PATH'] = str(PROJECT_DIR)

sys.path.insert(0, str(REPO_ROOT / 'src'))

from PySide6.QtWidgets import QApplication                        # noqa: E402
from PySide6.QtWidgets import QLineEdit                           # noqa: E402

from pygamestudio.common.res import resources_rc                   # noqa: E402,F401 - registers :/images
from pygamestudio.gui.build.android import AndroidAppBuildWindow, is_valid_package  # noqa: E402
import pygamestudio.gui.build.android as android_module                # noqa: E402
from pygamestudio.gui.build.window import BuildWindow, BuildWindowBody      # noqa: E402
from pygamestudio.gui.settings.editor import EditorSettingsBody    # noqa: E402
from pygamestudio.gui.settings.project import ProjectSettingsBody  # noqa: E402
from pygamestudio.common.utils.path import RES_PATH                 # noqa: E402
from pygamestudio.gui.build import web                              # noqa: E402

results = []


def check(name, condition, detail=''):
    results.append((name, bool(condition), detail))
    print(f'  [{"ok  " if condition else "FAIL"}] {name}'
          f'{(" - " + str(detail)) if detail else ""}')


class GameManager:
    """What the build tabs ask of the editor's scene/asset manager."""

    def get_project_path(self):
        return str(PROJECT_DIR)


def main():
    app = QApplication.instance() or QApplication([])
    manager = GameManager()

    print('1) android tab')
    window = AndroidAppBuildWindow(manager)
    window.get_ready_for_project()
    config = window.get_build_config()
    check('app name from project.pygs', config['app_name'] == 'PyGS Engine Spike',
          config['app_name'])
    check('output dir starts empty', config['output_dir'] == '')
    check('package derived from the app name',
          config['package'].startswith('org.pygamestudio.'), config['package'])
    check('package is valid', is_valid_package(config['package']))
    check('invalid package refused', not is_valid_package('My Game'))
    check('version name default', config['version_name'] == '1.0.0')
    check('version code default', str(config['version_code']) == '1')
    check('orientation default', config['orientation'] == 'landscape', config['orientation'])
    check('build type default', config['build_type'] == 'debug', config['build_type'])
    check('five orientation choices', window._orientation_combobox.count() == 5)
    check('signing rows hidden for debug', window._keystore_label.isHidden()
          and window._keystore_row.isHidden())
    check('keystore creator exists', window._keystore_create_button.text() != '')
    window._build_type_combobox.setCurrentIndex(window._build_type_combobox.findData('release'))
    window._update_signing_enabled()
    check('signing rows shown for release', not window._keystore_label.isHidden()
          and not window._keystore_row.isHidden())
    window._build_type_combobox.setCurrentIndex(window._build_type_combobox.findData('debug'))
    window._update_signing_enabled()
    window.retranslate()
    check('retranslate keeps the orientation pick',
          window._orientation_combobox.currentData() == 'landscape')

    print('1b) the password fields have an eye')
    for name, field in (('keystore', window._store_password_lineedit),
                        ('key', window._key_password_lineedit)):
        actions = field.actions()
        check(f'the {name} password starts hidden',
              field.echoMode() == QLineEdit.EchoMode.Password, field.echoMode())
        check(f'the {name} password has one action with a real icon',
              len(actions) == 1 and not actions[0].icon().isNull(), len(actions))
        actions[0].trigger()
        check(f'clicking the eye shows the {name} password',
              field.echoMode() == QLineEdit.EchoMode.Normal)
        check(f'the {name} eye still has an icon when open',
              not actions[0].icon().isNull())
        actions[0].trigger()
        check(f'clicking again hides the {name} password',
              field.echoMode() == QLineEdit.EchoMode.Password)

    print('1c) the APK name says which build type it is')
    thread = window._build_thread
    check('a debug build is named <app>-debug.apk',
          thread.output_file_name('My Game', False) == 'My Game-debug.apk',
          thread.output_file_name('My Game', False))
    check('a release build is named <app>-release.apk',
          thread.output_file_name('My Game', True) == 'My Game-release.apk',
          thread.output_file_name('My Game', True))
    check('a dangerous name is still a file name',
          thread.output_file_name('a/b:c*?', False) == 'abc-debug.apk',
          thread.output_file_name('a/b:c*?', False))

    print('2) build window tabs')
    body = BuildWindowBody(manager)
    check('three tabs', body.count() == 3, body.count())
    check('desktop tab first', body.tabText(0) != '')
    check('android tab named Android App',
          body.tabText(2) in ('Android App', '安卓应用'), body.tabText(2))
    body.get_ready_for_project()
    check('project data reaches every tab', body.count() == 3)
    body.retranslate()
    check('tab titles survive retranslate', all(body.tabText(i) for i in range(3)))

    print('2b) the window follows the tab height')
    window = BuildWindow(manager)
    window.get_ready_for_project()
    window.show()
    app.processEvents()
    window._build_window_body.setCurrentIndex(0)
    window._fit_height()
    desktop_height = window.height()
    window._build_window_body.setCurrentIndex(2)
    window._fit_height()
    android_height = window.height()
    check('the android tab is taller', android_height > desktop_height,
          f'{desktop_height} -> {android_height}')
    window.close()

    print('2c) "New..." without a JDK')
    # The reported bug: with an empty JDK path the button asked for a file, an
    # alias and a password and only then failed with "keytool not found in ".
    # It has to refuse up front, and without opening a dialog.
    class _NoDialog:
        @staticmethod
        def getSaveFileName(*args, **kwargs):
            raise AssertionError('a file dialog was opened without a JDK')

    class _RecordingLogger:
        errors = []

        @classmethod
        def error(cls, message, *args, **kwargs):
            cls.errors.append(str(message))

        @staticmethod
        def info(*args, **kwargs):
            pass

        warning = info

    build_window = AndroidAppBuildWindow(manager)
    build_window.get_ready_for_project()
    original_dialog, original_logger = android_module.QFileDialog, android_module.Logger
    android_module.QFileDialog, android_module.Logger = _NoDialog, _RecordingLogger
    try:
        build_window._create_keystore()
    finally:
        android_module.QFileDialog, android_module.Logger = original_dialog, original_logger
    check('no dialog before the JDK is known', bool(_RecordingLogger.errors))
    check('the message names the setting, not "keytool not found in "',
          _RecordingLogger.errors and 'Android Build' in _RecordingLogger.errors[0],
          (_RecordingLogger.errors[0].replace('\n', ' ')[:70] if _RecordingLogger.errors else ''))

    print('3) settings page')
    settings = EditorSettingsBody(manager)
    check('three settings pages', settings._list_widget.count() == 3,
          settings._list_widget.count())
    check('android page is in the stack', settings._main_stacked_widget.count() == 3)
    check('an empty path stays empty in the field',
          settings._android_jdk_lineedit.text() == ''
          and settings._android_sdk_lineedit.text() == '',
          [settings._android_jdk_lineedit.text(), settings._android_sdk_lineedit.text()])
    check('the placeholder asks for a folder instead of guessing one',
          'Auto-detected' not in settings._android_jdk_lineedit.placeholderText()
          and settings._android_jdk_lineedit.placeholderText() != '',
          settings._android_jdk_lineedit.placeholderText())
    check('permission list keeps its width',
          settings._list_widget.minimumWidth() == 170
          == settings._list_widget.maximumWidth(),
          settings._list_widget.minimumWidth())
    check('no runtime pack row', not hasattr(settings, '_android_pack_label'))
    check('only jdk and sdk fields', not hasattr(settings, '_android_gradle_lineedit'))
    settings.retranslate()
    check('labels survive retranslate', settings._android_jdk_label.text() != '')

    print('4) display fit settings')
    project_settings = ProjectSettingsBody(manager)
    project_settings.get_ready_for_project()
    check('mobile fit picker offers no "no fit"',
          project_settings._screen_fit_combobox.count() == 6
          and project_settings._screen_fit_combobox.findData('none') == -1,
          project_settings._screen_fit_combobox.count())
    check('desktop picker = windowed + the modes, no "no fit"',
          project_settings._desktop_display_combobox.count() == 7
          and project_settings._desktop_display_combobox.findData('none') == -1,
          project_settings._desktop_display_combobox.count())
    check('web picker = the three page modes, no "no fit"',
          project_settings._web_fit_combobox.count() == 3
          and project_settings._web_fit_combobox.findData('none') == -1,
          project_settings._web_fit_combobox.count())
    check('mobile defaults to letterboxed',
          project_settings._screen_fit_combobox.currentData() == 'show_all',
          project_settings._screen_fit_combobox.currentData())
    check('desktop defaults to windowed',
          project_settings._desktop_display_combobox.currentData() == 'window',
          project_settings._desktop_display_combobox.currentData())
    check('web defaults to letterboxed',
          project_settings._web_fit_combobox.currentData() == 'show_all',
          project_settings._web_fit_combobox.currentData())

    project_settings._desktop_display_combobox.setCurrentIndex(
        project_settings._desktop_display_combobox.findData('exact_fit'))
    project_settings._web_fit_combobox.setCurrentIndex(
        project_settings._web_fit_combobox.findData('integer'))
    stored = json.loads((PROJECT_DIR / 'project.pygs').read_text(encoding='utf-8'))
    check('desktop mode written to project.pygs',
          stored.get('desktop_display_mode') == 'exact_fit',
          stored.get('desktop_display_mode'))
    check('web mode written to project.pygs',
          stored.get('web_scale_mode') == 'integer', stored.get('web_scale_mode'))

    project_settings.retranslate()
    check('pickers keep their value across a language switch',
          project_settings._desktop_display_combobox.currentData() == 'exact_fit'
          and project_settings._web_fit_combobox.currentData() == 'integer')
    check('desktop labels are translated',
          project_settings._desktop_display_combobox.itemText(0) != '')
    check('web labels are translated',
          project_settings._web_fit_combobox.itemText(1) != '')

    print('5) web page honours the fit mode')
    check('the page template has the fit placeholder',
          '__PYGS_WEB_FIT__' in (RES_PATH / 'templates' / 'web_index_template.html')
          .read_text(encoding='utf-8'))
    web_modes = {value for value, _key, _fallback in ProjectSettingsBody.WEB_FIT_MODES}
    check('every picker value is understood by the web build',
          web_modes <= set(web.WEB_FIT_MODES), sorted(web_modes))
    check('the web default is a pickable value',
          web.DEFAULT_WEB_FIT in web_modes, web.DEFAULT_WEB_FIT)
    page_source = (RES_PATH / 'templates' / 'web_index_template.html').read_text(encoding='utf-8')
    page_css = page_source.split('<style>')[1].split('</style>')[0]
    check('the page never scales the canvas with object-fit',
          'object-fit' not in page_css)
    check('the page shows a splash image while loading',
          '__PYGS_SPLASH_TAG__' in page_source
          and (RES_PATH / 'images' / web.SPLASH_IMAGE_NAME).is_file(),
          web.SPLASH_IMAGE_NAME)
    check('the canvas is hidden until the game starts',
          'visibility: hidden' in page_css and 'body.running canvas#canvas' in page_css)
    check('the loading stage keeps title, splash and bar',
          all(token in page_source
              for token in ('id="title"', 'id="loader"', '__PYGS_SPLASH_TAG__')))
    check('the running stage keeps nothing but the canvas',
          'body.running #splash, body.running h1#title, body.running #loader { display: none; }'
          in page_css)

    app.processEvents()

    shutil.rmtree(TEMP, ignore_errors=True)

    passed = sum(1 for _name, ok, _detail in results if ok)
    failed = [name for name, ok, _detail in results if not ok]
    print(f'\n{passed}/{len(results)} check(s) passed')
    if failed:
        print('FAILED: ' + ', '.join(failed))
        print('RESULT : the Android UI is broken')
        return 1
    print('RESULT : build tab and settings page work without touching user settings')
    return 0


if __name__ == '__main__':
    sys.exit(main())
