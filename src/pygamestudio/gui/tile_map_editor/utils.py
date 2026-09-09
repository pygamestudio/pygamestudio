import pygame
from PySide6.QtGui import QColor, QImage, QPainter


def surface_to_qimage(surface):
    """pygame SRCALPHA surface -> QImage (RGBA, top-down like pygame)."""
    data = pygame.image.tostring(surface, 'RGBA', False)
    img = QImage(data, surface.get_width(), surface.get_height(),
                 surface.get_width() * 4, QImage.Format.Format_RGBA8888)
    return img.copy()


def make_checker_image(cell=8, c1=(58, 58, 58), c2=(46, 46, 46)):
    """Small checkerboard image shown behind transparent/empty map cells."""
    img = QImage(cell * 2, cell * 2, QImage.Format.Format_ARGB32)
    img.fill(QColor(*c2))
    painter = QPainter(img)
    painter.fillRect(0, 0, cell, cell, QColor(*c1))
    painter.fillRect(cell, cell, cell, cell, QColor(*c1))
    painter.end()
    return img
