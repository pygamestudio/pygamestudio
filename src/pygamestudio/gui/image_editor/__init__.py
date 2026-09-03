"""Image editor package.

A simple but complete raster image editor that lives as a tab next to the
code editor: open an image, draw with brushes/shapes, flood-fill, pick
colors, undo/redo, transform (flip/rotate), zoom and save.
"""

from .canvas import ImageCanvas
from .window import ImageEditorWindow

__all__ = ['ImageCanvas', 'ImageEditorWindow']
