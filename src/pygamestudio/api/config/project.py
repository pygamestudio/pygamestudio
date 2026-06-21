import os
import json
from pathlib import Path
from pygamestudio.common.i18n.translator import Translator as T


def get_project_config():
    project_path = Path(os.environ.get('PROJECT_PATH'))
    project_config_file_path = project_path / 'project.pygs'

    if not project_config_file_path.exists():
        raise RuntimeError(T.tr('api.no_project_pygs', 'Failed to find config file project.pygs in the project root directory.'))

    try:
        with open(project_config_file_path, 'r', encoding='utf-8') as f:
            project_config = json.load(f)
            return project_config
    except Exception as e:
        raise RuntimeError(T.tr('api.fail_to_load_project_pygs', 'Failed to load config file project.pygs: {}').format(str(e)))