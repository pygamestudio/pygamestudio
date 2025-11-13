from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionButton, QStyle
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QIcon, QMouseEvent, QPixmap, QPainter, QBrush, QColor, QPen
from pygamestudio.common.utils.path import RES_PATH


class ObjectTreeWidgetDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.__parent = parent
        self.__pixmap_size = QSize(16, 16)
        self.__open_eye_pixmap = QPixmap(RES_PATH/'images/open_eye.png')
        self.__open_eye_gray_pixmap = QPixmap(RES_PATH/'images/open_eye_gray.png')
        self.__closed_eye_pixmap = QPixmap(RES_PATH/'images/closed_eye.png')

        self.__hovered_index = None

    def __draw_eye_pixmap(self, painter, cell_rect, is_hovered, is_item_visible, is_ancestor_visible):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pixmap_rect = QRect(0, 0, self.__pixmap_size.width(), self.__pixmap_size.height())
        pixmap_rect.moveCenter(cell_rect.center())
        pixmap_rect.moveRight(cell_rect.right()-int(self.__pixmap_size.width()/5))

        if is_hovered:
            pixmap_rect.adjust(-1, -1, 1, 1)

        # If current item is visible but its ancestor is not, 
        # then draw a gray open eye to indicate the ancestor of this item is invisible.
        if is_item_visible and is_ancestor_visible:
            painter.drawPixmap(pixmap_rect, self.__open_eye_pixmap)
        elif is_item_visible and not is_ancestor_visible:
            painter.drawPixmap(pixmap_rect, self.__open_eye_gray_pixmap)
        else:
            painter.drawPixmap(pixmap_rect, self.__closed_eye_pixmap)

        painter.restore()

    def __is_click_on_eye_pixmap(self, pos, cell_rect):
        pixmap_rect = QRect(0, 0, self.__pixmap_size.width(), self.__pixmap_size.height())
        pixmap_rect.moveCenter(cell_rect.center())
        pixmap_rect.moveRight(cell_rect.right()-int(self.__pixmap_size.width()/5))
        return pixmap_rect.contains(pos)

    def paint(self, painter, option, index):
        if index.column() == 1:
            super().paint(painter, option, index)

            # Get the visibility of target item and that of its ancestor.
            item = self.__parent.itemFromIndex(index)
            if not item:
                return
            
            is_hovered = index == self.__hovered_index
            is_item_visible = item.data(0, Qt.ItemDataRole.UserRole).get('isVisible')
            is_ancestor_visible = self.__parent.is_ancestor_item_visible(item)
            self.__draw_eye_pixmap(painter, option.rect, is_hovered, is_item_visible, is_ancestor_visible)

        else:
            super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        # Toggle item's visibility.
        if event.type() == QMouseEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton and index.column() == 1:
            item = self.__parent.itemFromIndex(index)
            if item and self.__is_click_on_eye_pixmap(event.pos(), option.rect):
                self.__parent.toggle_item_visibility(item)
                return True

        # Increate hovered item's size.
        elif event.type() == QMouseEvent.Type.MouseMove and index.column() == 1:
            old_hovered_index = self.__hovered_index
            if self.__is_click_on_eye_pixmap(event.pos(), option.rect):
                self.__hovered_index = index
            else:
                self.__hovered_index = None
            
            # If mouse hovers on a different index, then repaint.
            if old_hovered_index != self.__hovered_index:
                self.__parent.viewport().update()
            return True
        
        # Prevent the expand and collapse event when toggling item's visibility.
        elif event.type() == QMouseEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton and index.column() == 1 and self.__is_click_on_eye_pixmap(event.pos(), option.rect):
            return True

        return super().editorEvent(event, model, option, index)