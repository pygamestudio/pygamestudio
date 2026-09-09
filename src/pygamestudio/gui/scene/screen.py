import pygame
from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from pygamestudio.game.object.type import *
from pygamestudio.game.core.collision import shape_to_polygon
from pygamestudio.gui.scene.gizmo import MoveGizmo
from pygamestudio.gui.scene.guide import resolve_drag, union_rect
from pygamestudio.common.utils.config import get_project_config


class PygameScreen(QWidget):
    """Editor canvas view, drawn over the whole grid scene.

    The widget is a TRANSPARENT overlay that covers the entire
    ``GridGraphicsScene`` area (like the grid itself), so the developer can
    park objects at any position around the game screen and still see and edit
    them (they simply sit on the grid, outside the screen rectangle). The
    actual game screen is drawn as an opaque rect (the canvas); everything
    else is left transparent so the background grid shows through. At runtime
    only the screen area is ever rendered, so off-screen objects never appear
    in the game.
    """

    # Ring of editable/visible space around the game screen. The overlay
    # widget must stay MODEST: a full-grid-sized (64000) widget makes Windows
    # allocate a 64000*devicePixelRatio backing store (CreateDIBSection) and
    # crashes. Within this ring objects are visible over the transparent grid;
    # pan/zoom (middle-drag / wheel) reach anything farther away.
    _WORKSPACE_MARGIN = 2000

    def __init__(self, game_manager=None, scene=None):
        super().__init__()
        self._game_manager = game_manager
        self._scene = scene
        self._screen_width = 800
        self._screen_height = 600
        self._workspace_margin = self._WORKSPACE_MARGIN
        self._consuming_press = False
        self._object_images = {}   # object uuid -> QImage (baked surface)
        self._move_gizmo = MoveGizmo(self, game_manager)

        self._mouse_x = None
        self._mouse_y = None
        self._is_ctrl_pressed = False
        self._final_selected_object = None
        self._alignment_guides = []   # lines to draw: (is_vertical, value, a, b)

        self._setup()

    def scene_offset(self):
        """(ox, oy) such that widget-local = world + offset. The proxy is
        parked at scene (-margin, -margin), so the canvas (world 0..W, 0..H)
        sits centred inside the widget and everything else maps by +margin."""
        return (self._workspace_margin, self._workspace_margin)

    def canvas_size(self):
        """The game screen (canvas) size, without any surrounding workspace."""
        return (self._screen_width, self._screen_height)

    def _setup(self):
        self._set_widget()
        self._set_signal()

    def _set_widget(self):
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self._screen_width + 2 * self._workspace_margin,
                          self._screen_height + 2 * self._workspace_margin)
        self.installEventFilter(self)

    def _set_signal(self):
        # Content-affecting changes rebuild the rendered images.
        self._game_manager.object_added.connect(self._update_scene)
        self._game_manager.object_deleted.connect(self._on_object_deleted)
        self._game_manager.object_selected.connect(self._on_object_selected)
        self._game_manager.object_deselected.connect(self._on_object_deselected)
        # Moving an object only changes its place, not its pixels.
        self._game_manager.object_moved.connect(self._on_object_moved)
        self._game_manager.object_scaled.connect(self._update_scene)
        self._game_manager.object_rotated.connect(self._update_scene)
        self._game_manager.object_resized.connect(self._on_object_resized)
        self._game_manager.object_showed.connect(self._update_scene)
        self._game_manager.object_hidden.connect(self._update_scene)
        self._game_manager.object_color_changed.connect(self._update_scene)
        self._game_manager.object_rect_border_radius_changed.connect(self._update_scene)
        self._game_manager.object_line_start_point_changed.connect(self._update_scene)
        self._game_manager.object_line_end_point_changed.connect(self._update_scene)
        self._game_manager.object_line_thickness_changed.connect(self._update_scene)
        self._game_manager.object_text_changed.connect(self._update_scene)
        self._game_manager.object_font_size_changed.connect(self._update_scene)
        self._game_manager.object_font_family_changed.connect(self._update_scene)
        self._game_manager.object_bold_state_changed.connect(self._update_scene)
        self._game_manager.object_italic_state_changed.connect(self._update_scene)
        self._game_manager.object_underline_state_changed.connect(self._update_scene)
        self._game_manager.object_strikethrough_state_changed.connect(self._update_scene)
        self._game_manager.object_image_path_changed.connect(self._update_scene)
        self._game_manager.object_font_path_changed.connect(self._update_scene)
        self._game_manager.object_points_changed.connect(self._update_scene)
        self._game_manager.object_particle_parameter_changed.connect(self._update_scene)
        self._game_manager.object_text_input_parameter_changed.connect(self._update_scene)
        self._game_manager.object_frame_sequence_parameter_changed.connect(self._update_scene)
        self._game_manager.object_tile_map_parameter_changed.connect(self._update_scene)
        self._game_manager.object_progress_bar_parameter_changed.connect(self._update_scene)
        self._game_manager.object_slider_parameter_changed.connect(self._update_scene)
        self._game_manager.object_collision_parameter_changed.connect(self._update_scene)

    def get_ready_for_project(self):
        self._screen_width = get_project_config()['screen_width']
        self._screen_height = get_project_config()['screen_height']
        self.setFixedSize(self._screen_width + 2 * self._workspace_margin,
                          self._screen_height + 2 * self._workspace_margin)
        self._update_scene()

    def clean_up(self):
        self._final_selected_object = None
        self._mouse_x = None
        self._mouse_y = None
        self._alignment_guides = []
        self._is_ctrl_pressed = False
        self._consuming_press = False
        self._object_images = {}
        self._screen_width = 800
        self._screen_height = 600
        self.setFixedSize(self._screen_width + 2 * self._workspace_margin,
                          self._screen_height + 2 * self._workspace_margin)

    def _delete(self):
        # Delete all selected objects.
        selected_uuids = self._game_manager.get_selected_objects_uuids()
        self._game_manager.delete(selected_uuids)

    def _on_object_deleted(self, object_uuid):
        move_gizmo_object = self._move_gizmo.get_object()
        if not move_gizmo_object or not self._game_manager.get_object(move_gizmo_object.uuid):
            self._move_gizmo.remove_object()
            self._move_gizmo.hide()

        # A deleted object must never linger: clear the collision-overlay
        # reference when the selected object is gone (directly or because a
        # parent it lived under was removed), so its green outline disappears.
        if (self._final_selected_object is not None
                and not self._game_manager.get_object(self._final_selected_object.uuid)):
            self._final_selected_object = None

        self._update_scene()

    def _on_object_selected(self, object_uuid):
        if object_uuid == self._game_manager.canvas_object_uuid:
            self._move_gizmo.hide()
        else:
            obj = self._game_manager.get_object(object_uuid)
            self._final_selected_object = obj
            self._move_gizmo.set_object(obj)

        self._update_scene()

    def _on_object_deselected(self, object_uuid):
        if self._move_gizmo.get_object() and self._move_gizmo.get_object().uuid == object_uuid:
            self._move_gizmo.remove_object()
            self._move_gizmo.hide()
        self._update_scene()

    def _on_object_moved(self, object_uuid):
        """A pure move only changes where the object sits, not its pixels, so
        skip the expensive image rebuild (keeps gizmo drags smooth)."""
        obj = self._game_manager.get_object(object_uuid)
        parent = self._game_manager.get_parent_object(object_uuid) if obj is not None else None
        if parent is not None and parent.type != OBJECT_CANVAS:
            # A nested object moved inside its parent: that parent's baked
            # image (which contains the child) is now stale.
            self._update_scene()
            return
        self.update()

    def _on_object_resized(self, object_uuid):
        if object_uuid == self._game_manager.canvas_object_uuid:
            obj = self._game_manager.get_object(object_uuid)
            self._screen_width = int(obj.width)
            self._screen_height = int(obj.height)
            self.setFixedSize(self._screen_width + 2 * self._workspace_margin,
                              self._screen_height + 2 * self._workspace_margin)

        self._update_scene()

    # ------------------------------------------------------------- render
    @staticmethod
    def _surface_to_qimage(surface):
        """pygame SRCALPHA surface -> QImage (RGBA, top-down like pygame)."""
        data = pygame.image.tostring(surface, 'RGBA', False)
        img = QImage(data, surface.get_width(), surface.get_height(),
                     surface.get_width() * 4, QImage.Format.Format_RGBA8888)
        return img.copy()

    def _root_value(self):
        return list(self._game_manager.all_object_tree_struct.values())[0]

    def _bake_subtree(self, node):
        """Update every surface in ``node`` and composite the children into
        their parent's surface (children clip to their parent, like always).
        Returns the top object of the subtree."""
        value = list(node.values())[0]
        obj = value['object']
        obj._update_surface()
        if obj.visible:
            for child_node in value['children']:
                self._bake_subtree(child_node)
                child_obj = list(child_node.values())[0]['object']
                if child_obj.visible:
                    child_obj._draw(obj._get_surface())
        return obj

    def _update_scene(self):
        """Rebuild the cached QImages (canvas + each visible top-level object,
        children baked in) and schedule a repaint."""
        self._object_images = {}
        if self._game_manager.is_empty():
            self.update()
            return

        root_value = self._root_value()
        canvas = root_value['object']
        canvas._update_surface()
        self._object_images[canvas.uuid] = self._surface_to_qimage(canvas._get_surface())

        for child_node in root_value['children']:
            obj = self._bake_subtree(child_node)
            if obj.visible:
                if obj.selected:
                    # The generic selection outline lives in ObjectBase._draw
                    # (drawn when blitting onto a parent), but top-level objects
                    # are painted straight from their own surface here, so bake
                    # the outline in explicitly.
                    pygame.draw.rect(obj._get_surface(), (0, 122, 204),
                                     obj._get_surface().get_rect(), width=2)
                self._object_images[obj.uuid] = self._surface_to_qimage(obj._get_surface())

        # Stale guides must never linger: they only exist during a gizmo drag.
        if not self._move_gizmo.is_dragging and self._alignment_guides:
            self._alignment_guides = []
        self.update()
        self._move_gizmo.update_pos()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing
                               | QPainter.RenderHint.SmoothPixmapTransform)
        if self._game_manager.is_empty():
            painter.end()
            return

        if self._game_manager.is_current_canvas_visible():
            self._paint_scene(painter)
        else:
            self._paint_border_only(painter)

        # Photoshop-style alignment guides, drawn above the scene while the
        # move gizmo is dragging near an aligned position.
        self._draw_alignment_guides(painter)
        painter.end()

    def _paint_scene(self, painter):
        ox, oy = self.scene_offset()
        root_value = self._root_value()

        canvas = root_value['object']
        img = self._object_images.get(canvas.uuid)
        if img is not None:
            painter.drawImage(QRectF(ox, oy, img.width(), img.height()), img)

        for child_node in root_value['children']:
            value = list(child_node.values())[0]
            obj = value['object']
            if not obj.visible:
                continue
            img = self._object_images.get(obj.uuid)
            if img is None:
                continue
            rect = obj._get_world_rect()
            painter.drawImage(QRectF(rect.x + ox, rect.y + oy,
                                     rect.width, rect.height), img)

        self._draw_collision_overlay(painter)

    def _paint_border_only(self, painter):
        """Canvas hidden: draw only the screen outline (mirrors old look)."""
        ox, oy = self.scene_offset()
        painter.save()
        pen = QPen(Qt.GlobalColor.white)
        pen.setWidth(5)
        painter.setPen(pen)
        painter.drawRect(QRectF(ox, oy, self._screen_width, self._screen_height))
        painter.restore()

    # ------------------------------------------------------- smart guides
    def _alignment_group_rect(self, moving_objects):
        """World-space bounding box of every object being dragged together."""
        return union_rect([obj._get_world_rect() for obj in moving_objects])

    def _collect_alignment_refs(self, moving_uuids):
        """World rects of the objects the dragged group can align against.

        Objects that are themselves being dragged are skipped, and so is any
        descendant of a dragged object (it moves along implicitly). Hidden
        objects are ignored; the canvas is included so edges/center can align
        to the scene/stage itself."""
        refs = []

        def walk(object_tree_struct, under_mover):
            value = list(object_tree_struct.values())[0]
            obj = value['object']
            is_mover = obj.uuid in moving_uuids
            if not under_mover and not is_mover and obj.visible:
                refs.append(obj._get_world_rect())
            for child_tree in value['children']:
                walk(child_tree, under_mover or is_mover)

        walk(self._game_manager.all_object_tree_struct, False)
        return refs

    def resolve_move_delta(self, dx, dy, allow_x=True, allow_y=True):
        """Snap a gizmo drag step and record the guides to draw.

        Called by the move gizmo while dragging, BEFORE the objects are moved:
        returns the (possibly corrected) movement to apply and stores the guide
        lines that match the final position on ``self._alignment_guides`` so the
        next paint draws them."""
        moving_objects = self._game_manager.get_objects_to_move()
        if not moving_objects:
            self._alignment_guides = []
            return dx, dy

        group = self._alignment_group_rect(moving_objects)
        moving_uuids = {obj.uuid for obj in moving_objects}
        refs = self._collect_alignment_refs(moving_uuids)
        if group is None or not refs:
            self._alignment_guides = []
            return dx, dy

        new_dx, new_dy, guides = resolve_drag(
            dx, dy, allow_x, allow_y, group, refs)
        self._alignment_guides = guides
        # Repaint even when the movement collapsed to zero (object snapped to
        # an alignment and the cursor is still within snapping distance), so
        # the guides stay visible without a scene change.
        self.update()
        return new_dx, new_dy

    def clear_alignment_guides(self):
        """Hide any guide lines (called when a drag ends)."""
        if self._alignment_guides:
            self._alignment_guides = []
            self.update()

    def _draw_alignment_guides(self, painter):
        """Paint the smart guides as thin magenta dashed lines."""
        if not self._alignment_guides:
            return
        painter.save()
        pen = QPen(QColor(255, 0, 255, 230), 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        ox, oy = self.scene_offset()
        for vertical, value, start, end in self._alignment_guides:
            if vertical:
                painter.drawLine(int(value + ox), int(start + oy),
                                 int(value + ox), int(end + oy))
            else:
                painter.drawLine(int(start + ox), int(value + oy),
                                 int(end + ox), int(value + oy))
        painter.restore()

    def _draw_collision_overlay(self, painter):
        """Outline the selected object's collision body in green. Only drawn
        while collision is enabled on that object."""
        obj = self._final_selected_object
        if obj is None or getattr(obj, 'type', '') == OBJECT_CANVAS:
            return
        if not hasattr(obj, '_collision_geometry_world'):
            return
        if not getattr(obj, 'collision_enabled', False):
            return

        shape = obj._collision_geometry_world()
        if shape is None:
            return
        ox, oy = self.scene_offset()
        points = [QPointF(x + ox, y + oy) for (x, y) in shape_to_polygon(shape)]
        if len(points) < 3:
            return
        painter.save()
        pen = QPen(QColor(0, 255, 0), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(QPolygonF(points))
        painter.restore()

    # ------------------------------------------------------------- events
    def _on_mouse_left_button_pressed(self, event):
        """Returns True when the press was consumed (object/canvas click) and
        False when it fell on empty grid (so the rubber band can run)."""
        pos = event.position()
        self._mouse_x = pos.x()
        self._mouse_y = pos.y()
        if self._game_manager.is_empty():
            return False
        ox, oy = self.scene_offset()
        return self._update_object_selection(QPointF(pos.x() - ox, pos.y() - oy))

    def _on_mouse_move(self, event):
        # Should move the object by gizmo. Otherwise, the rubber band will show up.
        # self._move_selected_objects(event.position())
        pass

    def _on_mouse_left_button_released(self, event):
        self._mouse_x = None
        self._mouse_y = None

    def _object_at(self, world_pos):
        """Topmost visible object (not the canvas) under ``world_pos``."""
        found = None

        def _find(node, pos):
            nonlocal found
            value = list(node.values())[0]
            obj = value['object']
            if obj.type != OBJECT_CANVAS and obj.visible \
                    and obj._check_click_collision((pos.x(), pos.y())):
                found = obj
                return
            for child_node in reversed(value['children']):
                _find(child_node, pos)
                if found:
                    return

        _find(self._game_manager.all_object_tree_struct, world_pos)
        return found

    def _update_object_selection(self, world_pos):
        """Select the object under the click; return True if consumed."""
        obj = self._object_at(world_pos)
        canvas = self._root_value()['object']
        in_canvas = (canvas.visible
                     and 0 <= world_pos.x() <= self._screen_width
                     and 0 <= world_pos.y() <= self._screen_height)

        if obj is not None:
            if not self._is_ctrl_pressed:
                self._game_manager.deselect_all()
            self._game_manager.select(obj.uuid)
            return True

        if in_canvas:
            # Clicking empty canvas keeps the canvas selected (no gizmo).
            if not self._is_ctrl_pressed:
                self._game_manager.deselect_all()
            self._game_manager.select(self._game_manager.canvas_object_uuid)
            return True

        # Empty grid: clear the selection and let the rubber band take over.
        if not self._is_ctrl_pressed:
            self._game_manager.deselect_all()
        return False

    def _move_selected_objects(self, pos):
        if not self._final_selected_object:
            return

        self._game_manager.undo_stack.beginMacro('Move')
        selected_objects = self._game_manager.get_objects_to_move()
        for obj in selected_objects:
            new_x = obj.x + pos.x() - self._mouse_x
            new_y = obj.y + pos.y() - self._mouse_y
            self._game_manager.move(obj.uuid, (new_x, new_y))

        self._game_manager.undo_stack.endMacro()
        self._mouse_x = pos.x()
        self._mouse_y = pos.y()

    def update_selection_by_rubber_band(self, rect_pyside6):
        def _set(object_tree_struct, rect_pyside6):
            value = list(object_tree_struct.values())[0]

            for child_object_tree_struct in value['children']:
                _set(child_object_tree_struct, rect_pyside6)

            rect_pygame = pygame.FRect(rect_pyside6.x(), rect_pyside6.y(),
                                       rect_pyside6.width(), rect_pyside6.height())
            obj = value['object']
            if obj.type != OBJECT_CANVAS and obj._check_rect_collision(rect_pygame):
                self._game_manager.select(obj.uuid)
            else:
                self._game_manager.deselect(obj.uuid)

        self._game_manager.deselect(self._game_manager.canvas_object_uuid)
        root_value = self._root_value()
        for child_object_tree_struct in root_value['children']:
            _set(child_object_tree_struct, rect_pyside6)

    def is_dragging_by_move_gizmo(self):
        return self._move_gizmo.is_dragging

    def eventFilter(self, obj, event):
        """Handle clicks inside the overlay widget.

        Left clicks that land on an object or on the canvas are consumed here;
        clicks on empty grid return False so the grid view's rubber-band
        selection keeps working. (Gizmo presses are handled by the gizmo child
        widget itself; Qt routes them correctly on both sides of the canvas
        since the grid view's deselect check compares in scene space.)"""
        dragging = False
        try:
            if self._scene and self._scene.views():
                dragging = self._scene.views()[0].is_dragging()
        except Exception:
            dragging = False

        if obj == self and not dragging:
            etype = event.type()
            if etype == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton or etype == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.RightButton:
                self._consuming_press = self._on_mouse_left_button_pressed(event)
                return self._consuming_press
            elif etype == QEvent.Type.MouseMove and event.buttons() == Qt.MouseButton.LeftButton:
                self._on_mouse_move(event)
                return self._consuming_press
            elif etype == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self._on_mouse_left_button_released(event)
                consumed = self._consuming_press
                self._consuming_press = False
                return consumed
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self._is_ctrl_pressed = True

        elif event.key() == Qt.Key.Key_Delete:
            self._delete()

        return super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self._is_ctrl_pressed = False

        return super().keyReleaseEvent(event)

    def resizeEvent(self, event):
        return super().resizeEvent(event)
