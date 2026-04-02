import os
import json
from pathlib import Path
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.gui.console.logger import Logger


def get_project_config() -> dict:
    project_config_json_path = Path(get_env('__PYGAMESTUDIO_PROJECT_PATH')) / 'project.json'

    if not project_config_json_path.exists():
        project_config_json_path.touch()
        with open(RES_PATH/'templates/project.json', 'r', encoding='utf-8') as f:
            project_config_template_content = f.read()
        
        with open(project_config_json_path, 'w', encoding='utf-8') as f:
            f.write(project_config_template_content)

        return project_config_template_content
    
    with open(project_config_json_path, 'r', encoding='utf-8') as f:
        return json.loads(f.read())
    

def save_project_config(config) -> None:
    try:
        project_config_json_path = Path(get_env('__PYGAMESTUDIO_PROJECT_PATH')) / 'project.json'
        with open(project_config_json_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        Logger.error(f'项目配置保存失败：{e}')


def get_current_scene_from_project_config() -> str:
    project_config = get_project_config()
    try:
        return project_config['asset']['current_scene']
    except Exception as e:
        Logger.error(f'读取project.json错误：{e}')


def set_current_scene_to_projec_config(current_scene_file_path):
    try:
        current_scene_file_relative_path = Path(current_scene_file_path).relative_to(get_env('__PYGAMESTUDIO_PROJECT_PATH')).as_posix()
    except ValueError:
        current_scene_file_relative_path = current_scene_file_path

    project_config = get_project_config()
    project_config['asset']['current_scene'] = current_scene_file_relative_path
    save_project_config(project_config)


def get_env(key: str) -> str:
    return os.environ.get(key)


def set_env(key: str, value: str) -> bool:
    try:
        os.environ[key] = value
        return True
    except Exception as e:
        return False