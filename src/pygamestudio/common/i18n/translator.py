import json
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.console.logger import Logger
from pygamestudio.common.utils.path import LANG_PATH


# 设计成单例
class Translator:
    toggle_language_signal = Signal()
    instance = None
    
    def __new__(cls):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            super().__init__()
            self.initialized = True
            self.current_lang = 'en'
            self.lang_dict = {}

    @staticmethod
    def load_language(lang_code):
        lang_file = LANG_PATH / f'{lang_code}.json'
        
        if not lang_file.exists():
            Logger.error('找不到对应的语言文件，请检查下是否被删除了？')
            return
        
        instance = Translator.get_instance()

        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                instance.lang_dict = json.load(f)
                instance.current_language = lang_code
        except Exception as e:
            Logger.error(f'语言文件加载失败: {e}')

    @staticmethod
    def toggle_language(lang_code):
        instance = Translator.get_instance()
        instance.load_language(lang_code)
        instance.toggle_language_signal.emit()

    @staticmethod
    def get_instance():
        if Translator.instance is None:
            Translator.instance = Translator()
        return Translator.instance
    
    @staticmethod
    def tr(key, default=''):
        instance = Translator.get_instance()
        return instance.lang_dict.get(key, default)

    