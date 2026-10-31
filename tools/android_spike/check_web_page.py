"""Check the page a web build produces (no browser, no Pyodide run).

The page is generated from ``common/res/templates/web_index_template.html``
plus the project's ``web_scale_mode``, so the checks are about that output:
every placeholder replaced, the splash shown while loading, the canvas hidden
until the game starts, and the fit mode taken from the project.

    py -3.10 tools/android_spike/check_web_page.py
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

TEMP = Path(tempfile.mkdtemp(prefix='pygs-web-page-'))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['PYGAMESTUDIO_EDITOR_DIR'] = str(TEMP / 'editor')

sys.path.insert(0, str(REPO_ROOT / 'src'))

from PySide6.QtWidgets import QApplication                        # noqa: E402

from pygamestudio.gui.build.web import (WebAppBuilder, DEFAULT_WEB_FIT,
                                        SPLASH_BAR_RATIO_FALLBACK)    # noqa: E402
from pygamestudio.common.utils.path import RES_PATH                   # noqa: E402

results = []

PROJECT_CONFIG = {
    'caption': 'Web Page Check',
    'screen_width': 800,
    'screen_height': 600,
    'screen_size': [800, 600],
    'screen_scaled': True,
    'screen_scale_mode': 'show_all',
    'screen_scale_filter': 'nearest',
    'desktop_display_mode': 'window',
    'asset': {'current_scene': '', 'sort_type': 1},
    'build': {},
}
MAIN_SOURCE = '''import pygamestudio as studio


class Game(studio.Game):
    pass
'''


def check(name, condition, detail=''):
    results.append((name, bool(condition), detail))
    print(f'  [{"ok  " if condition else "FAIL"}] {name}'
          f'{(" - " + str(detail)) if detail else ""}')


def make_project(config_extra):
    """A minimal project plus the folders a web build reads."""
    project = TEMP / f'project-{len(results)}'
    project.mkdir()
    config = dict(PROJECT_CONFIG, **config_extra)
    (project / 'project.pygs').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
    (project / 'main.py').write_text(MAIN_SOURCE, encoding='utf-8')
    return project


def build(project, output_name):
    builder = WebAppBuilder(project, {'app_name': 'Web Page Check',
                                      'output_dir': str(TEMP / output_name)})
    bundle = builder.build()
    return bundle, (bundle / 'index.html').read_text(encoding='utf-8')


def main():
    app = QApplication.instance() or QApplication([])      # noqa: F841 - QImage in the builder

    print('1) a project that chose a fit mode')
    project = make_project({'web_scale_mode': 'show_all'})
    bundle, page = build(project, 'out-show-all')

    check('every template placeholder is replaced',
          not re.findall(r'__PYGS_[A-Z_]+__', page),
          re.findall(r'__PYGS_[A-Z_]+__', page))
    check('the fit mode comes from the project',
          'const CANVAS_FIT = "show_all";' in page,
          re.search(r'const CANVAS_FIT = "\w+";', page).group(0))
    check('the splash is bundled next to the page',
          (bundle / 'presplash_logo.png').is_file())
    check('the page shows that splash while loading',
          '<img id="splash" src="presplash_logo.png"' in page)
    check('title, splash and bar are the loading stage',
          'id="title"' in page and 'id="loader"' in page
          and 'body.running #splash, body.running h1#title, body.running #loader { display: none; }'
          in page)
    check('the canvas is hidden until the game starts',
          'visibility: hidden' in page and 'body.running canvas#canvas' in page)
    check('the game archive is next to the page', (bundle / 'game.zip').is_file())
    check('the canvas keeps the project size',
          'width="800" height="600"' in page)

    print('2) the progress bar matches the wordmark on the splash')
    splash = RES_PATH / 'images' / 'presplash_logo.png'
    ratio = WebAppBuilder._measure_splash_text(splash)
    # The wordmark of the shipped logo spans x=20..381 of 400 px.
    check('the wordmark width is measured from the picture',
          0.85 <= ratio <= 0.95, round(ratio, 3))
    check('the page gets that ratio',
          f'const SPLASH_BAR_RATIO = {ratio:.3f};' in page)
    check('a missing splash falls back instead of failing',
          WebAppBuilder._measure_splash_text(TEMP / 'nope.png') == SPLASH_BAR_RATIO_FALLBACK)

    print('3) a project without a fit mode')
    project = make_project({})
    _bundle, page = build(project, 'out-default')
    check('the page falls back to letterbox',
          f'const CANVAS_FIT = "{DEFAULT_WEB_FIT}";' in page,
          re.search(r'const CANVAS_FIT = "\w+";', page).group(0))

    print('4) a project that still stores the retired "none"')
    project = make_project({'web_scale_mode': 'none'})
    _bundle, page = build(project, 'out-retired')
    check('a retired no-fit is read as letterbox',
          'const CANVAS_FIT = "show_all";' in page,
          re.search(r'const CANVAS_FIT = "\w+";', page).group(0))

    app.processEvents()

    passed = sum(1 for _name, ok, _detail in results if ok)
    failed = [name for name, ok, _detail in results if not ok]
    print(f'\n{passed}/{len(results)} check(s) passed')
    if failed:
        print('FAILED: ' + ', '.join(failed))
        print('RESULT : the generated web page is broken')
        return 1
    print('RESULT : the web page shows splash + progress, then only the canvas')
    return 0


if __name__ == '__main__':
    sys.exit(main())
