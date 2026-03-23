from platformdirs import user_config_dir
from pathlib import Path
import json


DASHBOARD_PROJECTS_FILE_NAME = 'dashboard.json'
DASHBOARD_CONFIG_DIR_PATH = Path(user_config_dir()) / 'PygameStudio'
DASHBOARD_PROJECTS_FILE_PATH = DASHBOARD_CONFIG_DIR_PATH / DASHBOARD_PROJECTS_FILE_NAME


def ensure_config_dir_exists():
    if not DASHBOARD_CONFIG_DIR_PATH.exists():
        DASHBOARD_CONFIG_DIR_PATH.mkdir(parents=True)


def save_projects_to_dashbaord_config(project_list):
    ensure_config_dir_exists()

    try:
        DASHBOARD_PROJECTS_FILE_PATH.write_text(
            json.dumps(project_list, indent=4, ensure_ascii=False),
            encoding='utf-8'
        )
    except Exception as e:
        print(f"保存最近项目列表时出错: {e}")


def add_project_to_dashboard_config(project_data):
    project_list = load_projects_from_dashboard_config()

    # 如果是导入已经存在的项目的话，那就要把这个项目移到最顶上
    for i, data in enumerate(project_list):
        if data['path'] == project_data['path']:
            del project_list[i]
            break

    project_list.append(project_data)
    save_projects_to_dashbaord_config(project_list)

def delete_project_from_dashboard_config(project_path):
    project_list = load_projects_from_dashboard_config()
    for i, project_data in enumerate(project_list):
        if project_data['path'] == project_path:
            del project_list[i]
            break

    save_projects_to_dashbaord_config(project_list)


def load_projects_from_dashboard_config():
    if not DASHBOARD_PROJECTS_FILE_PATH.exists():
        return []

    try:
        project_list = json.loads(DASHBOARD_PROJECTS_FILE_PATH.read_text(encoding='utf-8'))
        if isinstance(project_list, list):
            return project_list
        else:
            print("配置文件格式错误，预期是一个列表。")
            return []
    except json.JSONDecodeError:
        print("配置文件损坏，无法解析 JSON。")
        return []
    except Exception as e:
        print(f"加载最近项目列表时出错: {e}")
        return []
    
def update_project_date_in_dashboard_config(project_path, new_project_date):
    project_list = load_projects_from_dashboard_config()
    for i, project_data in enumerate(project_list):
        if project_data['path'] == project_path:
            project_list[i]['date'] = new_project_date
            break
            
    save_projects_to_dashbaord_config(project_list)

def update_project_name_in_dashboard_config(old_project_path, new_project_path):
    project_list = load_projects_from_dashboard_config()
    for i, project_data in enumerate(project_list):
        if project_data['path'] == old_project_path:
            project_list[i]['name'] = Path(new_project_path).name
            project_list[i]['path'] = new_project_path
            break
        
    save_projects_to_dashbaord_config(project_list)
