import os
import json
from typing import Union
from pathlib import Path
from platformdirs import user_config_dir
from pygamestudio.gui.console.logger import Logger
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.common.utils.system import get_system_lang
from PySide6.QtWidgets import *

#: Layout version of editor.pygs. Bumped whenever a file written by an older
#: version has to be adjusted once (see _migrate_editor_config).
EDITOR_CONFIG_VERSION = 2

#: Settings every project.pygs should carry. An older project gets the missing
#: ones added once when the editor opens it; values already present are kept.
PROJECT_CONFIG_DEFAULTS = {
    # TapTap PC SDK keys (empty = not configured; fill them in from the TapTap
    # developer center). studio.sdk.taptap.pc reads them from here.
    'taptap': {'client_id': '', 'public_key': ''},
}


def get_editor_data_dir() -> Path:
    """Machine-local data folder of the editor (``editor.pygs`` and friends)."""
    return Path(user_config_dir()) / 'PygameStudio'


def _editor_config_file_path() -> Path:
    return get_editor_data_dir() / 'editor.pygs'


def _write_editor_config(editor_config: dict) -> None:
    try:
        editor_config_json_path = _editor_config_file_path()
        with open(editor_config_json_path, 'w', encoding='utf-8') as f:
            json.dump(editor_config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        Logger.error(f'Failed to save editor config: {e}')


def _migrate_editor_config(editor_config: dict) -> dict:
    """Adjust an editor.pygs written by an older version (once per version).

    Version 2 lets the language follow the system one until the user picks a
    language in the settings. Older versions wrote the template default "en"
    into the file without anybody choosing it, so a file from before version 2
    with exactly that value becomes "automatic" again; a language the user had
    switched to in the settings is kept.
    """
    if editor_config.get('settings_version', 1) >= EDITOR_CONFIG_VERSION:
        return editor_config

    if editor_config.get('lang') == 'en':
        editor_config['lang'] = ''
    editor_config['settings_version'] = EDITOR_CONFIG_VERSION
    _write_editor_config(editor_config)
    return editor_config


def get_editor_config() -> dict:
    editor_config_file_path = _editor_config_file_path()
    editor_config_dir_path = editor_config_file_path.parent
    if not editor_config_dir_path.exists():
        editor_config_dir_path.mkdir(parents=True)

    if not editor_config_file_path.exists():
        with open(RES_PATH/'templates/editor_template.pygs', 'r', encoding='utf-8') as f:
            editor_config_template_content = f.read()

        with open(editor_config_file_path, 'w', encoding='utf-8') as f:
            f.write(editor_config_template_content)

        return json.loads(editor_config_template_content)

    with open(editor_config_file_path, 'r', encoding='utf-8') as f:
        return _migrate_editor_config(json.load(f))


def get_editor_language() -> str:
    """The language the editor UI should use.

    The language picked in the editor settings wins; while nothing has been
    picked yet the editor follows the language of the operating system.
    """
    return get_editor_config().get('lang') or get_system_lang()


def update_editor_config(key:str, value:Union[str, int, float, list, tuple]) -> None:
    editor_config = get_editor_config()
    editor_config[key] = value
    _write_editor_config(editor_config)


def get_project_config() -> dict:
    project_config_json_path = Path(get_env('__PYGAMESTUDIO_PROJECT_PATH')) / 'project.pygs'

    if not project_config_json_path.exists():
        project_config_json_path.touch()
        with open(RES_PATH/'templates/project_template.pygs', 'r', encoding='utf-8') as f:
            project_config_template_content = f.read()
        
        with open(project_config_json_path, 'w', encoding='utf-8') as f:
            f.write(project_config_template_content)

        return _migrate_project_config(json.loads(project_config_template_content),
                                       project_config_json_path)
    
    with open(project_config_json_path, 'r', encoding='utf-8') as f:
        project_config = json.loads(f.read())
    return _migrate_project_config(project_config, project_config_json_path)


def _migrate_project_config(project_config: dict, path: Path) -> dict:
    """Add the project settings an older project.pygs does not have yet.

    Only missing keys are added (a value the user already set is never
    touched), and the file is rewritten once so the new settings are visible
    in project.pygs right away.
    """
    changed = False
    for key, default in PROJECT_CONFIG_DEFAULTS.items():
        if not isinstance(project_config.get(key), dict):
            project_config[key] = dict(default)
            changed = True
            continue
        section = project_config[key]
        for field, value in default.items():
            if field not in section:
                section[field] = value
                changed = True
    if changed:
        try:
            path.write_text(json.dumps(project_config, indent=4, ensure_ascii=False),
                            encoding='utf-8')
        except OSError as error:
            Logger.error(f'Failed to update project config: {error}')
    return project_config
    

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


def update_project_config(key:str, value:Union[str, int, float, list, tuple, dict]) -> None:
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