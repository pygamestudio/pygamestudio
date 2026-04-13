import json

with open('D:\\Github\\pygamestudio\\src\\pygamestudio\\common\\res\\templates\\project_template.json', 'r', encoding='utf-8') as f:
    project_config = json.load(f)
    print(project_config)