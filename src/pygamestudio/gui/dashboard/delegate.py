import platform
from pathlib import Path
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.i18n.translator import Translator as T


class DashboardDelegate(QStyledItemDelegate):
    menuRequested = Signal(QPoint)

    def __init__(self, list_view=None):
        super().__init__(list_view)
        self._list_view = list_view
        self._padding = 10
        self._icon_size = QSize(60, 60)

        self._placeholder_text = ''

        self._hovered_index = None
        self._button_margin = 5
        self._button_size = QSize(18, 18)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        project_icon = index.data(self._list_view.ProjectIconRole)
        project_name = index.data(self._list_view.ProjectNameRole)
        project_path = index.data(self._list_view.ProjectPathRole)
        project_date = index.data(self._list_view.ProjectDateRole)

        is_project_existed = True
        if not Path(project_path).exists():
            is_project_existed = False

        icon_rect = QRect(option.rect.x() + self._padding, option.rect.y() + (option.rect.height() - self._icon_size.height()) // 2,
                    self._icon_size.width(), self._icon_size.height())
        icon = QPixmap(project_icon).scaled(self._icon_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap(icon_rect, icon)

        name_x = icon_rect.right() + self._padding
        name_width = option.rect.width() - name_x - self._padding - 80
        name_rect = QRect(name_x, icon_rect.y()+self._icon_size.height()//8, name_width, option.rect.height())

        name_font = QFont()
        name_font.setBold(True)
        font_size = 15 if platform.system() == 'Darwin' else 12
        name_font.setPointSize(font_size)
        painter.setFont(name_font)
        if is_project_existed:
            painter.setPen(QColor(255, 255, 255))
        else:
            painter.setPen(QColor(255, 0, 0))
            project_name += T.tr('dashboard.not_found', ' (Not Found)')

        painter.drawText(name_rect, Qt.AlignmentFlag.AlignTop, 
                         painter.fontMetrics().elidedText(project_name, Qt.TextElideMode.ElideRight, name_width))
        
        path_rect = QRect(name_x, icon_rect.y()+self._icon_size.height()//8*5, name_width, option.rect.height())
        path_font = QFont()
        font_size = 12 if platform.system() == 'Darwin' else 8
        path_font.setPointSize(font_size)
        painter.setFont(path_font)
        painter.setPen(QColor(204, 204, 204))
        painter.drawText(path_rect, Qt.AlignmentFlag.AlignTop, 
                         painter.fontMetrics().elidedText(project_path, Qt.TextElideMode.ElideRight, name_width))
        
        date_rect = QRect(option.rect.right() - 110, icon_rect.y(), 100, 20)
        date_font = QFont()
        font_size = 9 if platform.system() == 'Darwin' else 7
        date_font.setPointSize(font_size)
        painter.setFont(date_font)
        painter.setPen(QColor(204, 204, 204))
        painter.drawText(date_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, project_date)
        

        button_x = option.rect.right() - self._button_size.width() - self._button_margin
        button_y = option.rect.bottom() - self._button_size.height() - self._button_margin
        button_rect = QRect(button_x, button_y, self._button_size.width(), self._button_size.height())
        
        if self._hovered_index == index:
            # painter.setBrush(QColor(204, 204, 204))
            painter.setPen(QPen(QColor(150, 150, 150), 1))
            painter.drawRoundedRect(button_rect, 5, 5)

        button_text_font = QFont()
        button_text_font.setPointSize(16)
        button_text_font.setBold(True)
        painter.setFont(button_text_font)
        painter.setPen(QColor(80, 80, 80))
        painter.drawText(button_rect, Qt.AlignmentFlag.AlignCenter, "⋮")
    
    def editorEvent(self, event, model, option, index):
        button_x = option.rect.right() - self._button_size.width() - self._button_margin
        button_y = option.rect.bottom() - self._button_size.height() - self._button_margin
        button_rect = QRect(button_x, button_y, self._button_size.width(), self._button_size.height())

        if event.type() == QMouseEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if button_rect.contains(event.pos()):
                self._hovered_index = index
                self._list_view.setCurrentIndex(index)
                self.menuRequested.emit(event.pos())
                self._hovered_index = None
                return True

        elif event.type() == QMouseEvent.Type.MouseMove:
            if button_rect.contains(event.pos()):
                self._hovered_index = index
            else:
                self._hovered_index = None
            return True

        return super().editorEvent(event, model, option, index)