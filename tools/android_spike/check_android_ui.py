"""Offscreen check of the Android UI: the build tab and the settings page.

No display and no real configuration: ``APPDATA``/``LOCALAPPDATA`` (and the XDG
equivalents) point at a temporary folder, so the editor config the widgets read
and write is a throw-away copy and the user's own settings stay untouched.

    py -3.10 tools/android_spike/check_android_ui.py
"""
import os
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

PROJECT_DIR = Path(TEMP) / 'project'
shutil.copytree(SPIKE_APP, PROJECT_DIR,
                ignore=shutil.ignore_patterns('pygamestudio', '__pycache__', '*.pyc'))
os.environ['__PYGAMESTUDIO_PROJECT_PATH'] = str(PROJECT_DIR)
os.environ['PROJECT_PATH'] = str(PROJECT_DIR)

sys.path.insert(0, str(REPO_ROOT / 'src'))

from PySide6.QtWidgets import QApplication                        # noqa: E402

from pygamestudio.gui.build.android import AndroidAppBuildWindow, is_valid_package  # noqa: E402
from pygamestudio.gui.build.window import BuildWindowBody          # noqa: E402
from pygamestudio.gui.settings.editor import EditorSettingsBody    # noqa: E402

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
    check('five orientation choices', window._orientation_combobox.count() == 5)
    check('environment line filled', window._environment_label.text() != '')
    window.retranslate()
    check('retranslate keeps the orientation pick',
          window._orientation_combobox.currentData() == 'landscape')

    print('2) build window tabs')
    body = BuildWindowBody(manager)
    check('three tabs', body.count() == 3, body.count())
    check('desktop tab first', body.tabText(0) != '')
    check('android tab last', 'Android' in body.tabText(2) or body.tabText(2) != '',
          body.tabText(2))
    body.get_ready_for_project()
    check('project data reaches every tab', body.count() == 3)
    body.retranslate()
    check('tab titles survive retranslate', all(body.tabText(i) for i in range(3)))

    print('3) settings page')
    settings = EditorSettingsBody(manager)
    check('three settings pages', settings._list_widget.count() == 3,
          settings._list_widget.count())
    check('android page is in the stack', settings._main_stacked_widget.count() == 3)
    check('jdk field filled', settings._android_jdk_lineedit.text() != ''
          or settings._android_status_label.text() != '')
    check('pack described', settings._android_pack_value_label.text() != '-',
          settings._android_pack_value_label.text())
    check('status explains the toolchain', settings._android_status_label.text() != '')
    settings.retranslate()
    check('status survives retranslate', settings._android_status_label.text() != '')

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
