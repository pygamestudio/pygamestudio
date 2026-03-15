import os
import json
from pathlib import Path
from pygamestudio.common.utils.path import RES_PATH


def get_project_config() -> dict:
    project_path = Path(os.environ.get('PROJECT_PATH'))
    project_config_json_path = project_path / 'project.json'

    if not project_config_json_path.exists():
        project_config_json_path.touch()
        with open(RES_PATH/'templates/project.json', 'r', encoding='utf-8') as f:
            project_config_template_content = f.read()
        
        with open(project_config_json_path, 'w', encoding='utf-8') as f:
            f.write(project_config_template_content)

        return project_config_template_content
    
    with open(project_config_json_path, 'r', encoding='utf-8') as f:
        return json.loads(f.read())


def get_env(key: str) -> str:
    return os.environ.get(key)


def set_env(key: str, value: str) -> bool:
    try:
        os.environ[key] = value
        return True
    except Exception as e:
        return False