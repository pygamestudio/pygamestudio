import json
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.gui.console.logger import Logger
from pygamestudio.common.utils.path import LANG_PATH


class Translator:
    """Singleton i18n helper. Translations live in JSON dictionaries under
    common/i18n/languages (e.g. en.json), keyed by dot paths like
    'message_box.critical_title'. Use T.tr('key.path', 'fallback') anywhere;
    the fallback is returned when the key is missing. Widgets can register
    themselves via add_observer() to get retranslated on language switch.
    """
    instance = None
    
    def __new__(cls):
        # Singleton: every caller shares the same loaded language dictionary.
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance
    
    def __init__(self):
        # __new__ returns the same instance, so guard against re-init.
        if not hasattr(self, 'initialized'):
            super().__init__()
            self.initialized = True
            self.current_lang = 'en'
            self.observers = []
            self.lang_dict = {}

    @staticmethod
    def load_language(lang_code):
        """Load a language JSON file (e.g. 'zh_CN') into the singleton."""
        instance = Translator.get_instance()
        lang_file = LANG_PATH / f'{lang_code}.json'
        
        if not lang_file.exists():
            Logger.error(instance.tr('translator.no_lang_code_json', "Couldn't find {}.json").format(lang_code))
            return

        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                instance.lang_dict = json.load(f)
                instance.current_language = lang_code
        except Exception as e:
            Logger.error(instance.tr('translator.fail_to_load_lang_code_json', 'Failed to load {}.json: {}').format(lang_code, e))

    @staticmethod
    def toggle_language(lang_code):
        """Switch language and retranslate every registered observer widget."""
        instance = Translator.get_instance()
        instance.load_language(lang_code)
        for observer in instance.observers:
            observer.retranslate()

    @staticmethod
    def get_instance():
        """Return the shared Translator singleton."""
        if Translator.instance is None:
            Translator.instance = Translator()
        return Translator.instance
    
    @staticmethod
    def tr(key, default='') -> str:
        """Look up a dotted key in the loaded dictionary; return default when
        the key (or an intermediate level) does not exist."""
        instance = Translator.get_instance()
        
        keys = key.split('.')
        value = instance.lang_dict
        
        try:
            for k in keys:
                value = value[k]
            return value
        except Exception:
            return default
    
    @staticmethod
    def get_available_languages():
        """List available language codes by scanning the languages folder."""
        return [f.stem for f in LANG_PATH.glob('*.json')]
    
    @staticmethod
    def add_observer(target):
        """Register a widget with a retranslate() method for live language
        switching."""
        instance = Translator.get_instance()
        instance.observers.append(target)