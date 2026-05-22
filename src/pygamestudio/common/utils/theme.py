from PySide6.QtWidgets import *
from pygamestudio.common.utils.path import RES_PATH
from pygamestudio.common.utils.config import get_editor_config
from pygamestudio.common.i18n.translator import Translator as T


def set_editor_theme(theme: str=''):
    if not theme:
        theme = get_editor_config().get('theme')
        theme = 'dark' if not theme else theme

    theme_qss_path = RES_PATH / f'qss/{theme}.qss'
    if not theme_qss_path.exists():
        QMessageBox.critical(QApplication.activeWindow(), T.tr('message_box.critical_title', 'Error'), T.tr('message_box.critical_read_qss_content', 'The theme QSS file {}.qss does not exist!').format(theme))
        return
    
    with open(theme_qss_path, 'r', encoding='utf-8') as f:
        QApplication.instance().setStyleSheet(f.read())