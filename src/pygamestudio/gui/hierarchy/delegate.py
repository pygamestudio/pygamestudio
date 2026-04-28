from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.common.utils.path import RES_PATH


class HierarchyTreeViewDelegate(QStyledItemDelegate):
    def __init__(self, tree_view=None, proxy_model=None, standard_model=None):
        super().__init__(tree_view)
        self._tree_view = tree_view
        self._proxy_model = proxy_model
        self._standard_model = standard_model

        self._pixmap_size = QSize(16, 16)
        self._eye_open_pixmap = QPixmap(RES_PATH/'images/eye_open.png')
        self._eye_off_pixmap = QPixmap(RES_PATH/'images/eye_off.png')
        self._eye_closed_pixmap = QPixmap(RES_PATH/'images/eye_closed.png')

        self._hovered_index = None

    def _draw_eye_pixmap(self, painter, cell_rect, is_hovered, is_item_visible, is_ancestor_visible):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pixmap_rect = QRect(0, 0, self._pixmap_size.width(), self._pixmap_size.height())
        pixmap_rect.moveCenter(cell_rect.center())
        pixmap_rect.moveRight(cell_rect.right()-int(self._pixmap_size.width()/5))

        if is_hovered:
            pixmap_rect.adjust(-1, -1, 1, 1)

        # If current item is visible but its ancestor is not, 
        # then draw an eye (off) to indicate the ancestor of this item is invisible.
        if is_item_visible and is_ancestor_visible:
            painter.drawPixmap(pixmap_rect, self._eye_open_pixmap)
        elif is_item_visible and not is_ancestor_visible:
            painter.drawPixmap(pixmap_rect, self._eye_off_pixmap)
        else:
            painter.drawPixmap(pixmap_rect, self._eye_closed_pixmap)

        painter.restore()

    def _draw_index_foreground(self, index, is_item_visible, is_ancestor_visible):
        item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index))
        if is_item_visible and is_ancestor_visible:
            item.setForeground(QColor(0, 0, 0))
        else:
            item.setForeground(QColor(200, 200, 200))

    def _is_click_on_eye_pixmap(self, pos, cell_rect):
        pixmap_rect = QRect(0, 0, self._pixmap_size.width(), self._pixmap_size.height())
        pixmap_rect.moveCenter(cell_rect.center())
        pixmap_rect.moveRight(cell_rect.right()-int(self._pixmap_size.width()/5))
        return pixmap_rect.contains(pos)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        # Get the visibility of target item and the visibility of its ancestor.
        item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index))
        if not item:
            return
        
        is_hovered = index == self._hovered_index
        is_item_visible = self._tree_view.is_item_visible(item)
        is_ancestor_visible = self._tree_view.is_ancestor_item_visible(item)
        self._draw_eye_pixmap(painter, option.rect, is_hovered, is_item_visible, is_ancestor_visible)

    def editorEvent(self, event, model, option, index):
        # Toggle item's visibility.
        if event.type() == QMouseEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            item = self._standard_model.itemFromIndex(self._proxy_model.mapToSource(index))
            if item and self._is_click_on_eye_pixmap(event.pos(), option.rect):
                self._tree_view.toggle_item_visibility(item)
                return True

        # Increate hovered item's size.
        elif event.type() == QMouseEvent.Type.MouseMove:
            old_hovered_index = self._hovered_index
            if self._is_click_on_eye_pixmap(event.pos(), option.rect):
                self._hovered_index = index
            else:
                self._hovered_index = None
            
            # If mouse hovers on a different index, then repaint.
            if old_hovered_index != self._hovered_index:
                self._tree_view.viewport().update()
            return True
        
        # Prevent the expand and collapse event when toggling item's visibility.
        elif event.type() == QMouseEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton and self._is_click_on_eye_pixmap(event.pos(), option.rect):
            return True

        return super().editorEvent(event, model, option, index)