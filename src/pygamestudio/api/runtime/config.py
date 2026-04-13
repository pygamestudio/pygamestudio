import os
import json
from pathlib import Path


def get_project_config():
    project_path = Path(os.environ.get('PROJECT_PATH'))
    project_config_file_path = project_path / 'project.pygs'

    if not project_config_file_path.exists():
        raise RuntimeError('没有在项目根目录下找到project.pygs配置文件')

    try:
        with open(project_config_file_path, 'r', encoding='utf-8') as f:
            project_config = json.load(f)
            return project_config
    except Exception as e:
        raise RuntimeError(f'project.pygs配置加载失败：{e}')