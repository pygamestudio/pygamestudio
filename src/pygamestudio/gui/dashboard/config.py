import json
from pathlib import Path
from platformdirs import user_config_dir
from PySide6.QtWidgets import QApplication, QMessageBox
from pygamestudio.common.i18n.translator import Translator as T


DASHBOARD_PROJECTS_FILE_NAME = 'dashboard.pygs'
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
        QMessageBox.critical(QApplication.activeWindow(), T.tr('message_box.critical_title', 'Error'),  T.tr('message_box.critical_save_project_list_content', 'Failed to save project list: {}').format(e))


def add_project_to_dashboard_config(project_data):
    project_list = load_projects_from_dashboard_config()

    # If importing an existing project, move it to the top.
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
            QMessageBox.critical(QApplication.activeWindow(), T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_not_list_content', 'Invalid configuration file format. Expected a list.'))
            return []
    except json.JSONDecodeError:
        QMessageBox.critical(QApplication.activeWindow(), T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_corrupted_json_content', 'The configuration file is corrupted. Failed to parse JSON.'))
        return []
    except Exception as e:
        QMessageBox.critical(QApplication.activeWindow(), T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_failed_to_load_content', 'Failed to load projects: {}').format(e))
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
