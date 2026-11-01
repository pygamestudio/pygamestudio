import os
import json
from pathlib import Path
from pygamestudio.common.i18n.translator import Translator as T
from pygamestudio.common.utils import assets


def get_project_config():
    project_path = Path(os.environ.get('PROJECT_PATH'))
    project_config_file_path = project_path / 'project.pygs'

    if not project_config_file_path.exists():
        raise RuntimeError(T.tr('api.no_project_pygs', 'Failed to find config file project.pygs in the project root directory.'))

    try:
        # Plain when the game runs from source, decrypted in a protected build.
        return json.loads(assets.read_text(project_config_file_path))
    except Exception as e:
        raise RuntimeError(T.tr('api.fail_to_load_project_pygs', 'Failed to load config file project.pygs: {}').format(str(e)))