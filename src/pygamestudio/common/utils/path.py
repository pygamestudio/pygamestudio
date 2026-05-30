import os
from pathlib import Path

RES_PATH = Path(__file__).parent.parent / 'res'
LANG_PATH = Path(__file__).parent.parent / 'i18n/languages'


def get_project_path():
    if os.environ.get('__PYGAMESTUDIO_PROJECT_PATH'):
        return os.environ.get('__PYGAMESTUDIO_PROJECT_PATH')
    
    elif os.environ.get('PROJECT_PATH'):
        return os.environ.get('PROJECT_PATH')
    
    else:
        return ''