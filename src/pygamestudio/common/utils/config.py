import os
import json
from typing import Union
from pathlib import Path
from platformdirs import user_config_dir
from pygamestudio.gui.console.logger import Logger
from pygamestudio.common.utils.path import RES_PATH


def get_editor_config() -> dict:
    editor_config_dir_path =  Path(user_config_dir()) / 'PygameStudio'
    if not editor_config_dir_path.exists():
        editor_config_dir_path.mkdir(parents=True)
    
    editor_config_file_path = editor_config_dir_path / 'editor.pygs'
    if not editor_config_file_path.exists():
        editor_config_file_path.touch()
        with open(RES_PATH/'templates/editor_template.pygs', 'r', encoding='utf-8') as f:
            editor_config_template_content = f.read()
    
        with open(editor_config_file_path, 'w', encoding='utf-8') as f:
            f.write(editor_config_template_content)

        return json.loads(editor_config_template_content)
    
    with open(editor_config_file_path, 'r', encoding='utf-8') as f:
        return json.loads(f.read())

    
def update_editor_config(key:str, value:Union[str, int, float, list, tuple]) -> None:
    editor_config = get_editor_config()
    editor_config[key] = value
    try:
        editor_config_json_path = Path(user_config_dir()) / 'PygameStudio/editor.pygs'
        with open(editor_config_json_path, 'w', encoding='utf-8') as f:
            json.dump(editor_config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        Logger.error(f'Failed to save editor config: {e}')


def get_project_config() -> dict:
    project_config_json_path = Path(get_env('__PYGAMESTUDIO_PROJECT_PATH')) / 'project.pygs'

    if not project_config_json_path.exists():
        project_config_json_path.touch()
        with open(RES_PATH/'templates/project_template.pygs', 'r', encoding='utf-8') as f:
            project_config_template_content = f.read()
        
        with open(project_config_json_path, 'w', encoding='utf-8') as f:
            f.write(project_config_template_content)

        return json.loads(project_config_template_content)
    
    with open(project_config_json_path, 'r', encoding='utf-8') as f:
        return json.loads(f.read())
    

def save_project_config(config:dict) -> None:
    try:
        project_config_json_path = Path(get_env('__PYGAMESTUDIO_PROJECT_PATH')) / 'project.pygs'
        with open(project_config_json_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        Logger.error(f'Failed to save project config: {e}')


def get_current_scene_from_project_config() -> str:
    project_config = get_project_config()
    try:
        return project_config['asset']['current_scene']
    except Exception as e:
        Logger.error(f'Failed to read project.pygs: {e}')


def set_current_scene_to_project_config(current_scene_file_path) -> None:
    try:
        current_scene_file_relative_path = Path(current_scene_file_path).relative_to(get_env('__PYGAMESTUDIO_PROJECT_PATH')).as_posix()
    except ValueError:
        current_scene_file_relative_path = current_scene_file_path

    project_config = get_project_config()
    project_config['asset']['current_scene'] = current_scene_file_relative_path
    save_project_config(project_config)


def update_project_config(key:str, value:Union[str, int, float, list, tuple]) -> None:
    project_config = get_project_config()
    keys = key.split('.')
    target = project_config
        
    try:
        for k in keys[:-1]:
            target = target[k]
        last_key = keys[-1]
        target[last_key] = value
        save_project_config(project_config)
    except Exception as e:
        Logger.error(f'Failed to update project config key {key}: {e}')


def get_env(key: str) -> str:
    return os.environ.get(key)


def set_env(key: str, value: str) -> bool:
    try:
        os.environ[key] = value
        return True
    except Exception as e:
        return False