import os
from pathlib import Path

# Resources (icons, QSS themes, templates) shipped inside the package.
RES_PATH = Path(__file__).parent.parent / 'res'
# Folder containing the per-language JSON dictionaries (en.json, zh_CN.json...).
LANG_PATH = Path(__file__).parent.parent / 'i18n/languages'


def get_project_path():
    """Resolve the current project root.

    Priority: __PYGAMESTUDIO_PROJECT_PATH (set by the editor) first, then
    PROJECT_PATH (set by the runtime Game). Returns '' when neither is set.
    """
    if os.environ.get('__PYGAMESTUDIO_PROJECT_PATH'):
        return os.environ.get('__PYGAMESTUDIO_PROJECT_PATH')
    
    elif os.environ.get('PROJECT_PATH'):
        return os.environ.get('PROJECT_PATH')
    
    else:
        return ''