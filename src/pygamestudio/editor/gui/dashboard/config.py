from platformdirs import user_config_dir
from pathlib import Path
import json


DASHBOARD_CONFIG_DIR_PATH = Path(user_config_dir(appname='PygameStudio'))
DASHBOARD_PROJECTS_FILE_NAME = 'projects.json'
DASHBOARD_PROJECTS_FILE_PATH = DASHBOARD_CONFIG_DIR_PATH / DASHBOARD_PROJECTS_FILE_NAME


def ensure_config_dir_exists():
    if not DASHBOARD_CONFIG_DIR_PATH.exists():
        DASHBOARD_CONFIG_DIR_PATH.mkdir(parents=True)


def save_projects(projects_list):
    ensure_config_dir_exists()

    try:
        DASHBOARD_PROJECTS_FILE_PATH.write_text(
            json.dumps(projects_list, indent=4, ensure_ascii=False),
            encoding='utf-8'
        )
    except Exception as e:
        print(f"保存最近项目列表时出错: {e}")


def load_projects():
    if not DASHBOARD_PROJECTS_FILE_PATH.exists():
        return []

    try:
        projects_list = json.loads(DASHBOARD_PROJECTS_FILE_PATH.read_text(encoding='utf-8'))
        if isinstance(projects_list, list):
            return projects_list
        else:
            print("配置文件格式错误，预期是一个列表。")
            return []
    except json.JSONDecodeError:
        print("配置文件损坏，无法解析 JSON。")
        return []
    except Exception as e:
        print(f"加载最近项目列表时出错: {e}")
        return []