import uuid
import pygame
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase


class ObjectPolygon(ObjectBase):
    """A polygon object rendered as a filled shape from a list of vertices.

    The vertices in ``points`` are scene (canvas) coordinates, so a vertex at
    (0, 0) sits at the canvas origin — exactly like ObjectLine's endpoints.
    The object's x/y (the surface top-left) and width/height are derived from
    the vertex bounding box: x/y/pos = the min vertex, width/height = the
    vertex extent. At least 3 points are required to draw; the shape is then
    scaled / rotated / alpha-blended like the other objects.
    """

    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/polygon.png'

        common_properties = {
            'name': 'Polygon',
            'type': OBJECT_POLYGON,
            'uuid': str(uuid.uuid4()),
            'x': 20,
            'y': 20,
            'pos': (20, 20),
            'width': 60,
            'height': 60,
            'size': (60, 60),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'color': (255, 255, 255, 255),
            'visible': True,
            'points': [(30, 4), (54, 24), (45, 52), (15, 52), (6, 24)],
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self._is_initialized = True

        self._start()

    def get_points(self):
        """Return the polygon's vertex list (scene/canvas coordinates)."""
        return self.points

    def set_points(self, points):
        """Set the polygon's vertices (scene coordinates), e.g.
        [(0, 0), (100, 0), (50, 80)] — a vertex at (0, 0) sits at the canvas
        origin."""
        self.points = points

    def _get_points_bounds(self):
        """Return (min_x, min_y, max_x, max_y) of the vertices, or None when
        the polygon has no vertices."""
        if not self.points:
            return None
        xs = [point[0] for point in self.points]
        ys = [point[1] for point in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def _update_bounding_box(self):
        """Derive position and size from the vertex bounding box.

        x/y/pos = the min vertex (the surface's top-left in scene coords) and
        width/height = the vertex extent, exactly like ObjectLine derives its
        box from its endpoints.
        """
        bounds = self._get_points_bounds()
        if bounds is None:
            return
        min_x, min_y, max_x, max_y = bounds
        width = max(max_x - min_x, 1)
        height = max(max_y - min_y, 1)
        super().__setattr__('x', min_x)
        super().__setattr__('y', min_y)
        super().__setattr__('pos', (min_x, min_y))
        super().__setattr__('width', width)
        super().__setattr__('height', height)
        super().__setattr__('size', (width, height))

    def _update_surface(self):
        self._update_bounding_box()

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        if len(self.points) >= 3:
            min_x, min_y, _, _ = self._get_points_bounds()
            normalized_points = [(point[0] - min_x, point[1] - min_y) for point in self.points]
            pygame.draw.polygon(self.surface, self.color[0:3], normalized_points)

        scaled_size = (self.surface.width * self.scale_x, self.surface.height * self.scale_y)
        scaled_surface = pygame.transform.scale(self.surface, scaled_size)
        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self.surface = self._apply_alpha(rotated_surface)

        super()._update_surface()

    def __setattr__(self, name, value):
        """Mirror ObjectLine: moving the object translates every vertex.

        x/y/pos are derived from the vertices in _update_bounding_box(), so a
        pos write shifts all vertices by the same delta and the box follows on
        the next surface update.
        """
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return

        if name == 'pos':
            # Recompute the current box first so the delta stays correct even
            # when no redraw happened since the last change.
            self._update_bounding_box()
            dx = value[0] - self.x
            dy = value[1] - self.y
            super().__setattr__('points', [(point[0] + dx, point[1] + dy) for point in self.points])
        else:
            super().__setattr__(name, value)
