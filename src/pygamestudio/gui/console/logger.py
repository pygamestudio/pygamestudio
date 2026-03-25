from PySide6.QtCore import QObject


class Logger(QObject):
    instance = None
    
    def __new__(cls):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            super().__init__()
            self.initialized = True
            self.log_widget = None
    
    @staticmethod
    def get_instance():
        if Logger.instance is None:
            Logger.instance = Logger()
        return Logger.instance
    
    @staticmethod
    def set_log_widget(widget):
        instance = Logger.get_instance()
        instance.log_widget = widget
    
    @staticmethod
    def info(message):
        instance = Logger.get_instance()
        print(instance)
        print(instance.log_widget)
        if instance.log_widget:
            instance.log_widget.info(message)
    
    @staticmethod
    def error(message):
        instance = Logger.get_instance()
        if instance.log_widget:
            instance.log_widget.error(message)
    
    @staticmethod
    def warning(message):
        instance = Logger.get_instance()
        if instance.log_widget:
            instance.log_widget.warning(message)