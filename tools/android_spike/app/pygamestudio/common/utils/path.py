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
    PROJECT_PATH (set by the runtime Game). Before the game has run its
    start-up the variable is still missing, but a game's main.py may import
    its own modules at the very top - those imports need the root (and the
    build key next to it) already, so a frozen build falls back to the
    PyInstaller bundle folder and a source run to the folder of main.py.
    Returns '' when none of these applies (e.g. a tool without a project).
    """
    if os.environ.get('__PYGAMESTUDIO_PROJECT_PATH'):
        return os.environ.get('__PYGAMESTUDIO_PROJECT_PATH')

    elif os.environ.get('PROJECT_PATH'):
        return os.environ.get('PROJECT_PATH')

    elif getattr(sys, 'frozen', False):
        bundle = getattr(sys, '_MEIPASS', None)
        return Path(bundle or Path(sys.executable).parent).resolve().as_posix()

    else:
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