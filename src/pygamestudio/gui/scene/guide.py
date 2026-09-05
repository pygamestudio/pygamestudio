"""Photoshop-style smart alignment guides for the scene editor.

While an object (or group) is dragged with the move gizmo, its axis-aligned
bounding box is compared against every other visible object. When one of the
six alignment edges (left / center-x / right / top / center-y / bottom) comes
within ``SNAP_TOLERANCE`` pixels of another object's matching edge, the drag is
corrected so the two edges line up exactly ("snap") and a magenta guide line is
returned so the scene view can draw it.

All coordinates are in world (scene) pixels and are pure math on ``pygame.Rect``
values -- no Qt, no game-manager access, so this module is unit-testable.
"""

import pygame

# How close (in pixels) an edge must be to a matching edge before it snaps.
SNAP_TOLERANCE = 4


def union_rect(rects):
    """Smallest pygame.Rect covering every rect in ``rects`` (or None)."""
    result = None
    for rect in rects:
        if result is None:
            result = rect.copy()
        else:
            result.union_ip(rect)
    return result


def _snap_axis(delta, group, refs, horizontal):
    """Try to snap one axis of the dragged group.

    ``delta``     -- intended movement along this axis (pixels).
    ``group``     -- current world rect of the dragged group.
    ``refs``      -- world rects of the reference objects.
    ``horizontal``-- True aligns x edges, False aligns y edges.

    Returns ``(correction, target, ref_rect)`` where ``correction`` is the
    amount to add to ``delta`` so the nearest matching edge lines up exactly,
    or ``(0, None, None)`` when nothing is close enough.
    """
    if horizontal:
        edges = (group.left, group.centerx, group.right)
    else:
        edges = (group.top, group.centery, group.bottom)

    best = None          # (abs_diff, correction, target, ref_rect)
    for ref in refs:
        if horizontal:
            targets = (ref.left, ref.centerx, ref.right)
        else:
            targets = (ref.top, ref.centery, ref.bottom)
        for edge in edges:
            for target in targets:
                correction = target - (edge + delta)
                abs_diff = abs(correction)
                if abs_diff <= SNAP_TOLERANCE and (best is None or abs_diff < best[0]):
                    best = (abs_diff, correction, target, ref)

    if best is None:
        return 0, None, None
    return best[1], best[2], best[3]


def resolve_drag(dx, dy, allow_x, allow_y, group, refs):
    """Snap ``(dx, dy)`` against ``refs`` and describe the guide lines.

    ``allow_x`` / ``allow_y`` say which axes the current drag may move along
    (a single-axis handle drag only snaps along that axis).

    Returns ``(new_dx, new_dy, guides)``:
    * ``new_dx``/``new_dy`` -- the movement to actually apply (may differ from
      the input by up to ``SNAP_TOLERANCE`` pixels).
    * ``guides`` -- list of lines to draw, each ``(is_vertical, value, a, b)``:
      vertical line at x=``value`` from y ``a`` to ``b``, or horizontal line at
      y=``value`` from x ``a`` to ``b``. The extent spans from the dragged
      group's outer edge to the matched reference's outer edge (the
      Photoshop-style connecting segment).
    """
    # Only snap along an axis that the drag is actually moving along; a locked
    # axis (raw delta 0) must neither snap nor draw a guide.
    if allow_x and dx != 0:
        correction_x, x_target, x_ref = _snap_axis(dx, group, refs, True)
    else:
        correction_x, x_target, x_ref = 0, None, None
    if allow_y and dy != 0:
        correction_y, y_target, y_ref = _snap_axis(dy, group, refs, False)
    else:
        correction_y, y_target, y_ref = 0, None, None

    # Disallowed axes never move (single-axis handle drags stay locked), and
    # allowed axes pick up the snap correction.
    new_dx = (dx + correction_x) if allow_x else 0
    new_dy = (dy + correction_y) if allow_y else 0

    # The group's rect after the snapped movement; guides span the union of the
    # dragged group and the matched reference along the orthogonal axis.
    final_rect = group.move(new_dx, new_dy)

    guides = []
    if allow_x and x_target is not None:
        y0 = min(final_rect.top, x_ref.top)
        y1 = max(final_rect.bottom, x_ref.bottom)
        guides.append((True, x_target, y0, y1))
    if allow_y and y_target is not None:
        x0 = min(final_rect.left, y_ref.left)
        x1 = max(final_rect.right, y_ref.right)
        guides.append((False, y_target, x0, x1))

    return new_dx, new_dy, guides
