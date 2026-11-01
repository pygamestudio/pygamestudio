"""Collision geometry for scene objects.

Every object can carry one collision shape (rect / circle / polygon) defined
in the object's local, unscaled, unrotated space. ``ObjectBase`` is
responsible for turning that local definition into a *world-space descriptor*
(see ``_collision_geometry_world``); this module only knows how to test those
descriptors against each other and against points.

World-space descriptors:
    {'kind': 'rect',   'rect': pygame.Rect}                 axis-aligned rect
    {'kind': 'circle', 'cx': float, 'cy': float, 'r': float} circle
    {'kind': 'poly',   'points': [(x, y), ...]}              polygon (any kind)

Rectangles that are rotated are stored as 'poly' (four transformed corners),
and circles under a non-uniform scale become a sampled 'poly' too, so only the
fast cases keep their exact representation.
"""

import math

import pygame


# --------------------------------------------------------------------------
# point tests
# --------------------------------------------------------------------------
def _point_in_poly(points, x, y):
    """Ray-casting point-in-polygon test (works for concave polygons too)."""
    inside = False
    n = len(points)
    if n < 3:
        return False
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            if x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
    return inside


def _point_on_segment(a, b, p):
    """True when p lies on the segment a-b (collinear check)."""
    return (min(a[0], b[0]) - 1e-9 <= p[0] <= max(a[0], b[0]) + 1e-9
            and min(a[1], b[1]) - 1e-9 <= p[1] <= max(a[1], b[1]) + 1e-9)


def collide_point(shape, x, y):
    """True when the point (x, y) is inside the shape descriptor."""
    kind = shape['kind']
    if kind == 'rect':
        return shape['rect'].collidepoint(x, y)
    if kind == 'circle':
        dx = x - shape['cx']
        dy = y - shape['cy']
        return dx * dx + dy * dy <= shape['r'] * shape['r']
    if kind == 'poly':
        return _point_in_poly(shape['points'], x, y)
    return False


# --------------------------------------------------------------------------
# polygon helpers
# --------------------------------------------------------------------------
def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segments_intersect(p1, p2, p3, p4):
    """True when segment p1-p2 and p3-p4 intersect (touching included)."""
    d1 = _cross(p3, p4, p1)
    d2 = _cross(p3, p4, p2)
    d3 = _cross(p1, p2, p3)
    d4 = _cross(p1, p2, p4)

    if (((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0))
            and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0))):
        return True

    if abs(d1) < 1e-9 and _point_on_segment(p3, p4, p1):
        return True
    if abs(d2) < 1e-9 and _point_on_segment(p3, p4, p2):
        return True
    if abs(d3) < 1e-9 and _point_on_segment(p1, p2, p3):
        return True
    if abs(d4) < 1e-9 and _point_on_segment(p1, p2, p4):
        return True
    return False


def polygon_polygon(a, b):
    """True when two polygons overlap. Handles convex AND concave polygons:
    first any edge crossing, then containment of a vertex either way."""
    points_a = a['points'] if a['kind'] == 'poly' else shape_to_polygon(a)
    points_b = b['points'] if b['kind'] == 'poly' else shape_to_polygon(b)
    if len(points_a) < 3 or len(points_b) < 3:
        return False

    for i in range(len(points_a)):
        p1 = points_a[i]
        p2 = points_a[(i + 1) % len(points_a)]
        for j in range(len(points_b)):
            if _segments_intersect(p1, p2, points_b[j], points_b[(j + 1) % len(points_b)]):
                return True

    return (_point_in_poly(points_b, points_a[0][0], points_a[0][1])
            or _point_in_poly(points_a, points_b[0][0], points_b[0][1]))


# --------------------------------------------------------------------------
# conversion / dispatcher
# --------------------------------------------------------------------------
_CIRCLE_SEGMENTS = 24


def shape_to_polygon(shape):
    """Approximate any shape descriptor as a polygon point list (rect corners,
    sampled circle, or the polygon itself)."""
    kind = shape['kind']
    if kind == 'poly':
        return shape['points']
    if kind == 'rect':
        r = shape['rect']
        return [(r.left, r.top), (r.right, r.top), (r.right, r.bottom),
                (r.left, r.bottom)]
    # circle
    cx, cy, r = shape['cx'], shape['cy'], shape['r']
    return [(cx + r * math.cos(2 * math.pi * i / _CIRCLE_SEGMENTS),
             cy + r * math.sin(2 * math.pi * i / _CIRCLE_SEGMENTS))
            for i in range(_CIRCLE_SEGMENTS)]


def collide(a, b):
    """True when two world-space shape descriptors overlap."""
    ka, kb = a['kind'], b['kind']

    # Fast exact paths first.
    if ka == 'rect' and kb == 'rect':
        return a['rect'].colliderect(b['rect'])
    if ka == 'circle' and kb == 'circle':
        dx = a['cx'] - b['cx']
        dy = a['cy'] - b['cy']
        rr = a['r'] + b['r']
        return dx * dx + dy * dy <= rr * rr
    if (ka == 'rect' and kb == 'circle') or (ka == 'circle' and kb == 'rect'):
        rect = a['rect'] if ka == 'rect' else b['rect']
        circle = a if ka == 'circle' else b
        return rect_circle(rect, circle)

    # Anything involving a polygon: fall back to polygon intersection.
    return polygon_polygon(a, b)


def rect_circle(rect, circle):
    """True when an axis-aligned pygame.Rect and a circle overlap."""
    # Clamp the circle centre to the rect; if the closest point is within the
    # radius the circle touches the rect.
    closest_x = max(rect.left, min(circle['cx'], rect.right))
    closest_y = max(rect.top, min(circle['cy'], rect.bottom))
    dx = circle['cx'] - closest_x
    dy = circle['cy'] - closest_y
    return dx * dx + dy * dy <= circle['r'] * circle['r']


# --------------------------------------------------------------------------
# convenience (used by ObjectBase for its fallback AABB)
# --------------------------------------------------------------------------
def rect_shape(rect):
    return {'kind': 'rect', 'rect': rect}
