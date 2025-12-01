from PySide6.QtWidgets import QStyledItemDelegate, QLineEdit, QStyleOptionButton, QStyle,QStyleOptionViewItem
from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QMouseEvent, QPixmap, QPainter, QBrush, QColor, QPen, QDragMoveEvent
from pygamestudio.common.utils.path import RES_PATH


class AssetTreeWidgetDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__parent = parent
    
    def __draw_frame(self, painter, cell_rect):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen()
        pen.setColor(QColor(0, 255, 0))
        painter.setPen(pen)
        painter.drawRect(cell_rect)

        painter.restore()

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            text = index.data(Qt.ItemDataRole.DisplayRole)
            last_dot = text.rfind('.')
            if last_dot > 0:
                QTimer.singleShot(0, lambda: editor.setSelection(0, last_dot))
                        
        return editor

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        item = self.__parent.itemFromIndex(index)
        if item == self.__parent.get_hover_item_in_drag_move():
            self.__draw_frame(painter, option.rect)