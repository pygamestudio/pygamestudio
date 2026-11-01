import os
import sys
from pathlib import Path

# Resources (icons, QSS themes, templates) shipped inside the package.
RES_PATH = Path(__file__).parent.parent / 'res'
# Folder containing the per-language JSON dictionaries (en.json, zh_CN.json...).
LANG_PATH = Path(__file__).parent.parent / 'i18n/languages'


def get_project_path():
    """Resolve the current project root.

    Priority: __PYGAMESTUDIO_PROJECT_PATH (set by the editor) first, then
    PROJECT_PATH (set by the runtime Game, and by the ``sitecustomize.py`` of an
    Android payload before main.py runs), then the frozen bundle, then the p4a
    export (``ANDROID_ARGUMENT`` / ``ANDROID_PRIVATE``) and finally the folder of
    main.py for a plain source run. Before the game has run its start-up the
    variable may still be missing, but a game's main.py may import its own
    modules at the very top - those imports need the root (and the build key
    next to it) already.
    Returns '' when none of these applies (e.g. a tool without a project).
    """
    if os.environ.get('__PYGAMESTUDIO_PROJECT_PATH'):
        return os.environ.get('__PYGAMESTUDIO_PROJECT_PATH')

    if os.environ.get('PROJECT_PATH'):
        return os.environ.get('PROJECT_PATH')

    if getattr(sys, 'frozen', False):
        bundle = getattr(sys, '_MEIPASS', None)
        return Path(bundle or Path(sys.executable).parent).resolve().as_posix()

    # A python-for-android build: the app folder (main.py, project.pygs,
    # resources.cache) is what the bootstrap exports, while sys.argv[0] is a
    # bare "main.py" there, so the main.py fallback below cannot find it.
    for candidate in (os.environ.get('ANDROID_ARGUMENT'),
                      os.environ.get('ANDROID_PRIVATE')):
        if candidate and (Path(candidate) / 'project.pygs').is_file():
            return Path(candidate).as_posix()

    try:
        entry = Path(sys.argv[0] or '').resolve()
        if entry.suffix.lower() == '.py' and (entry.parent / 'project.pygs').is_file():
            return entry.parent.as_posix()
    except (OSError, ValueError):
        pass
    return ''


def followed_path(current, old_root, new_root):
    """Where ``current`` points after ``old_root`` was renamed/moved.

    Returns the new path when ``current`` IS ``old_root`` or lives below it
    (a file inside a moved folder follows too), otherwise None. Paths are
    compared case-insensitively on Windows (normcase).
    """
    current_text = str(Path(current))
    old_text = str(Path(old_root))
    current_key = os.path.normcase(current_text)
    old_key = os.path.normcase(old_text)
    if current_key == old_key:
        return Path(new_root)
    if current_key.startswith(old_key + os.sep):
        tail = current_text[len(old_text) + 1:]
        return Path(new_root) / tail
    return None