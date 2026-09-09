"""UI input box (single-line text field) scene object.

Renders as a box that holds a single line of editable text. In the editor it
displays the configured text / placeholder; at runtime the game routes mouse
and keyboard events to it (see api/core/scene.py focus handling), so clicking
the box focuses it and typed characters land in ``self.text`` (password mode
masks the display with '*').
"""

import math
import uuid
import pygame
from pathlib import Path
from pygamestudio.game.object.type import *
from pygamestudio.game.object.base import ObjectBase
from pygamestudio.common.utils.path import get_project_path


class ObjectTextInput(ObjectBase):
    """Single-line input box UI object (see module docstring)."""

    # Horizontal padding between the box border and the text.
    _TEXT_MARGIN = 8
    # Blink period of the runtime caret in milliseconds.
    _CARET_BLINK_MS = 500

    def __init__(self, game_manager, object_data={}, is_for_api=False):
        super().__init__(game_manager, object_data, is_for_api)
        self._is_initialized = False

        if hasattr(self, 'icon'):
            self.icon = ':/images/text_input.png'

        common_properties = {
            'name': 'TextInput',
            'type': OBJECT_TEXT_INPUT,
            'uuid': str(uuid.uuid4()),
            'x': 20,
            'y': 20,
            'pos': (20, 20),
            'width': 180,
            'height': 36,
            'size': (180, 36),
            'scale_x': 1,
            'scale_y': 1,
            'scale': (1, 1),
            'angle': 0,
            'visible': True,
            # Text + placeholder content.
            'text': '',
            'placeholder': '',
            'password': False,
            'max_length': 0,           # 0 = unlimited
            # Enter key behaviour: True -> Enter inserts a newline (multi-line
            # content); False (default) -> Enter stops editing.
            'enter_newline': False,
            # Text alignment inside the box: 'left'|'center'|'right' and
            # 'top'|'middle'|'bottom' (applies when the text fits the box).
            'text_align': 'left',
            'text_valign': 'middle',
            # Font of the field content (same options as a Text object).
            'font_size': 24,
            'font_path': './font/SIMHEI.ttf',
            'bold': False,
            'italic': False,
            'underline': False,
            'strikethrough': False,
            # Appearance: 'color' is the TEXT color (kept on the base field so
            # existing color plumbing works), plus box colors below.
            'color': (30, 30, 30, 255),
            'background_color': (255, 255, 255, 255),
            'border_color': (150, 150, 150, 255),
            # Rounded box corners (0 = sharp), same as the Rect object.
            'border_top_left_radius': 6,
            'border_top_right_radius': 6,
            'border_bottom_left_radius': 6,
            'border_bottom_right_radius': 6,
            # Runtime-only editing state (never serialized).
            '_runtime_focused': False,
            '_runtime_caret': 0,
        }

        for key, value in common_properties.items():
            setattr(self, key, object_data.get(key, value))

        # Migration: scenes saved with the old 'submit_on_enter' flag (True =
        # Enter submits) map onto enter_newline (True = Enter inserts '\n').
        if 'enter_newline' not in object_data and 'submit_on_enter' in object_data:
            self.enter_newline = not bool(object_data.get('submit_on_enter'))

        # Keep colors as tuples even when a .scene file handed us lists.
        self.color = tuple(self.color)
        self.background_color = tuple(self.background_color)
        self.border_color = tuple(self.border_color)

        self.surface = pygame.Surface(self.size, pygame.SRCALPHA)
        self._is_initialized = True

        self._start()

    # ---------------------------------------------------------------- API
    def get_text(self) -> str:
        """The current text of the input box."""
        return self.text

    def set_text(self, text: str):
        self.text = text

    def get_placeholder(self) -> str:
        """Hint text shown while the box is empty."""
        return self.placeholder

    def set_placeholder(self, placeholder: str):
        self.placeholder = placeholder

    def is_password_mode(self) -> bool:
        """True when the content is masked as dots (password box)."""
        return bool(self.password)

    def set_password_mode(self, password: bool):
        self.password = bool(password)

    def get_max_length(self) -> int:
        """Maximum number of characters (0 = unlimited)."""
        return self.max_length

    def set_max_length(self, max_length: int):
        self.max_length = max(0, int(max_length))

    def get_text_align(self) -> str:
        """Horizontal text alignment: 'left', 'center' or 'right'."""
        return self.text_align

    def set_text_align(self, align: str):
        if align in ('left', 'center', 'right'):
            self.text_align = align

    def get_text_valign(self) -> str:
        """Vertical text alignment: 'top', 'middle' or 'bottom'."""
        return self.text_valign

    def set_text_valign(self, align: str):
        if align in ('top', 'middle', 'bottom'):
            self.text_valign = align

    def is_enter_newline(self) -> bool:
        """True: Enter inserts a newline. False (default): Enter stops editing."""
        return bool(self.enter_newline)

    def set_enter_newline(self, enabled: bool):
        self.enter_newline = bool(enabled)

    def get_border_radius(self) -> tuple:
        """All four corner radii as (top_left, top_right, bottom_left,
        bottom_right)."""
        return (self.border_top_left_radius, self.border_top_right_radius,
                self.border_bottom_left_radius, self.border_bottom_right_radius)

    def set_border_radius(self, radius):
        """Set all four corners at once: a single int or a 4-item tuple."""
        if isinstance(radius, (tuple, list)):
            (self.border_top_left_radius, self.border_top_right_radius,
             self.border_bottom_left_radius, self.border_bottom_right_radius) = radius
        else:
            self.border_top_left_radius = radius
            self.border_top_right_radius = radius
            self.border_bottom_left_radius = radius
            self.border_bottom_right_radius = radius

    def get_font_size(self) -> int:
        return self.font_size

    def set_font_size(self, font_size: int):
        self.font_size = font_size

    def get_font_path(self) -> str:
        return self.font_path

    def set_font_path(self, font_path: str):
        self.font_path = font_path

    def get_background_color(self):
        """Box fill color as an (r, g, b, a) tuple."""
        return tuple(self.background_color)

    def set_background_color(self, color):
        self.background_color = tuple(color)

    def get_border_color(self):
        """Box border color as an (r, g, b, a) tuple."""
        return tuple(self.border_color)

    def set_border_color(self, color):
        self.border_color = tuple(color)

    def get_text_color(self):
        """Color of the typed text ((r, g, b, a) tuple)."""
        return tuple(self.color)

    def set_text_color(self, color):
        self.color = tuple(color)

    # --------------------------------------------------- runtime editing
    def _runtime_display(self) -> str:
        """What to draw: the real text, or '*' masking in password mode."""
        if self.password:
            return '*' * len(self.text)
        return self.text

    def _runtime_clamp_caret(self):
        self._runtime_caret = max(0, min(len(self.text), self._runtime_caret))

    def _runtime_insert(self, text: str):
        """Insert ``text`` at the caret (respects max_length). Returns True
        when something was inserted."""
        if not text:
            return False
        chars = list(self.text)
        remaining = None
        if self.max_length > 0:
            remaining = self.max_length - len(chars)
            if remaining <= 0:
                return False
            text = text[:remaining]
            if not text:
                return False
        chars[self._runtime_caret:self._runtime_caret] = list(text)
        self.text = ''.join(chars)
        self._runtime_caret += len(text)
        return True

    def _runtime_backspace(self) -> bool:
        """Delete the character before the caret."""
        if self._runtime_caret <= 0:
            return False
        chars = list(self.text)
        del chars[self._runtime_caret - 1]
        self.text = ''.join(chars)
        self._runtime_caret -= 1
        return True

    def _runtime_delete(self) -> bool:
        """Delete the character at the caret."""
        if self._runtime_caret >= len(self.text):
            return False
        chars = list(self.text)
        del chars[self._runtime_caret]
        self.text = ''.join(chars)
        return True

    def _runtime_caret_move(self, delta: int):
        self._runtime_caret = max(0, min(len(self.text), self._runtime_caret + delta))

    def _runtime_caret_home(self):
        self._runtime_caret = 0

    def _runtime_caret_end(self):
        self._runtime_caret = len(self.text)

    # -------------------------------------------------------------- render
    @staticmethod
    def _rgba(color):
        """Normalize a possibly-list color to an (r, g, b, a) tuple."""
        color = tuple(int(c) for c in color)
        if len(color) == 3:
            return color + (255,)
        return color

    def _init_font(self):
        font_absolute_path = Path(get_project_path()) / self.font_path
        if self.font_path == '' or not font_absolute_path.exists():
            font = pygame.font.Font(None, size=self.font_size)
        else:
            font = pygame.font.Font(str(font_absolute_path), size=self.font_size)
        font.set_bold(self.bold)
        font.set_italic(self.italic)
        font.set_underline(self.underline)
        font.set_strikethrough(self.strikethrough)
        return font

    @staticmethod
    def _layout_rows(text, font, content_w):
        """Split ``text`` into visual rows as (start, end, line_text) spans.

        Each span is a contiguous slice over the whole string so a caret (a
        global character index) maps to exactly one row. A '\n' only
        terminates its line (no phantom empty row); an empty logical line
        (consecutive '\n') is still its own row, and a trailing '\n' leaves
        one empty caret row.
        """
        spans = []
        n = len(text)
        line_start = 0
        while line_start < n:
            nl = text.find('\n', line_start)
            segment_end = n if nl == -1 else nl
            # Greedy character wrap of text[line_start:segment_end].
            start = line_start
            buffer_text = ''
            for char in text[line_start:segment_end]:
                trial = buffer_text + char
                if buffer_text and font.size(trial)[0] > content_w:
                    spans.append((start, start + len(buffer_text), buffer_text))
                    start += len(buffer_text)
                    buffer_text = char
                else:
                    buffer_text = trial
            if buffer_text:
                spans.append((start, start + len(buffer_text), buffer_text))
            elif nl != -1:
                # An empty logical line (two consecutive '\n') is its own row.
                spans.append((line_start, line_start, ''))
            if nl == -1:
                break
            line_start = nl + 1
        # A trailing newline leaves one empty (caret) row after the last line.
        if n and text[-1] == '\n':
            spans.append((n, n, ''))
        if not spans:
            spans = [(0, 0, '')]
        return spans

    @staticmethod
    def _nearest_col(line_text, font, x):
        """Column (0..len(line_text)) whose caret boundary x is nearest to ``x``."""
        best, prefix = 0, ''
        best_diff = float('inf')
        for i in range(len(line_text) + 1):
            diff = abs((font.size(prefix)[0] if prefix else 0) - x)
            if diff < best_diff:
                best_diff, best = diff, i
            if i < len(line_text):
                prefix += line_text[i]
        return best

    def _content_coords_from_world(self, world_pos):
        """Map a world-space point back onto the unscaled content surface."""
        rect = self._get_world_rect()
        lx = float(world_pos[0] - rect.x)
        ly = float(world_pos[1] - rect.y)
        sx = float(getattr(self, 'scale_x', 1) or 1)
        sy = float(getattr(self, 'scale_y', 1) or 1)
        angle = float(getattr(self, 'angle', 0) or 0)
        if angle:
            # Undo the rotation pygame applied. pygame spins the content
            # around the SCALED image centre (c_orig) and places the result
            # so that centre lands on the ROTATED rect's centre (c_new) --
            # these differ numerically whenever the rotated bounding box is
            # not the same size as the scaled image.
            rad = math.radians(angle)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            c_ox = int(self.width) * sx / 2.0
            c_oy = int(self.height) * sy / 2.0
            c_nx = rect.width / 2.0
            c_ny = rect.height / 2.0
            vx = lx - c_nx
            vy = ly - c_ny
            # Inverse of pygame's forward map (vx,vy)->(vx*cos+vy*sin, -vx*sin+vy*cos).
            ux = vx * cos_a - vy * sin_a
            uy = vx * sin_a + vy * cos_a
            lx = ux + c_ox
            ly = uy + c_oy
        return (lx / sx, ly / sy)

    def _caret_index_single_line(self, display, font, content_w, cx_rel,
                                 align_h):
        """Caret index for single-line content under a content x position."""
        text_w = font.size(display)[0]
        caret = max(0, min(len(display), self._runtime_caret))
        if text_w > content_w:
            # Mirror the render: text is scrolled so the caret stays visible.
            caret_px = font.size(display[:caret])[0] if caret else 0
            shift = max(0, caret_px - content_w)
            if caret_px < shift:
                shift = caret_px
            text_x_rel = -shift
        elif align_h == 'right':
            text_x_rel = content_w - text_w
        elif align_h == 'center':
            text_x_rel = (content_w - text_w) // 2
        else:
            text_x_rel = 0
        return self._nearest_col(display, font, cx_rel - text_x_rel)

    def _caret_index_multiline(self, display, font, content_w, width, height,
                               cx_rel, cy, align_h, align_v):
        """Caret index for multi-line content under a content position."""
        line_h = font.size('Ag')[1]
        spans = self._layout_rows(display, font, content_w)
        row_count = len(spans)
        block_height = row_count * line_h
        max_rows = max(1, (height - 4) // max(1, line_h))

        # Current caret row -> the same scroll state the renderer uses.
        caret = max(0, min(len(display), self._runtime_caret))
        caret_row = 0
        for i, (s, e, _) in enumerate(spans):
            if caret < e:
                caret_row = i
                break
            caret_row = i

        if block_height <= height - 2:
            if align_v == 'top':
                base_y = 2
            elif align_v == 'bottom':
                base_y = max(0, height - 2 - block_height)
            else:
                base_y = max(0, (height - block_height) // 2)
            row_offset = 0
        else:
            base_y = 2
            row_offset = max(0, caret_row - max_rows + 1)

        # Which visible row was clicked.
        visible = int((cy - base_y) // line_h) if line_h else 0
        visible = max(0, min(max_rows - 1, visible))
        row = max(0, min(row_count - 1, row_offset + visible))

        _, _, line_text = spans[row]
        line_w = font.size(line_text)[0]
        if align_h == 'right':
            origin_rel = content_w - line_w
        elif align_h == 'center':
            origin_rel = (content_w - line_w) // 2
        else:
            origin_rel = 0
        col = self._nearest_col(line_text, font, cx_rel - origin_rel)
        return spans[row][0] + col

    def set_caret_from_world_point(self, world_pos):
        """Place the runtime caret at the character under ``world_pos`` (a
        mouse click in world coordinates), mirroring the current rendering
        (alignment, horizontal scroll, soft-wrapped rows, vertical scroll)."""
        display = self._runtime_display()
        width, height = int(self.width), int(self.height)
        margin = self._TEXT_MARGIN
        content_w = max(0, width - 2 * margin)
        cx, cy = self._content_coords_from_world(world_pos)
        cx_rel = cx - margin
        font = self._init_font()
        align_h = str(getattr(self, 'text_align', 'left') or 'left')
        align_v = str(getattr(self, 'text_valign', 'middle') or 'middle')

        if not display:
            self._runtime_caret = 0
        elif '\n' in display:
            self._runtime_caret = self._caret_index_multiline(
                display, font, content_w, width, height, cx_rel, cy,
                align_h, align_v)
        else:
            self._runtime_caret = self._caret_index_single_line(
                display, font, content_w, cx_rel, align_h)

    def _draw_multiline(self, surface, font, text, color, margin, content_w,
                        width, height, caret, focused, align_h, align_v,
                        line_h):
        """Render content that contains newlines.

        Soft-wraps every logical line to ``content_w`` (character-level, so
        CJK text works), aligns each line horizontally and the whole block
        vertically, and auto-scrolls vertically so the caret line stays
        visible. The caret is drawn on its own (wrapped) row.
        """
        # Visual rows as (start, end, line_text) spans, shared with the
        # click->caret mapping so both always agree on the layout.
        spans = self._layout_rows(text, font, content_w)
        n = len(text)

        # Caret -> (row, column in that row).
        caret = max(0, min(n, caret))
        row = 0
        for row_index, (span_start, span_end, _) in enumerate(spans):
            if caret < span_end:
                row = row_index
                break
            row = row_index
        col = caret - spans[row][0]

        row_count = len(spans)
        block_height = row_count * line_h
        max_rows = max(1, (height - 4) // max(1, line_h))

        if block_height <= height - 2:
            if align_v == 'top':
                base_y = 2
            elif align_v == 'bottom':
                base_y = max(0, height - 2 - block_height)
            else:
                base_y = max(0, (height - block_height) // 2)
            row_offset = 0
        else:
            # Tall content: pin to the top and scroll so the caret stays seen.
            base_y = 2
            row_offset = max(0, row - max_rows + 1)

        def line_x(line_text):
            text_w = font.size(line_text)[0]
            if align_h == 'right':
                return width - margin - text_w
            if align_h == 'center':
                return margin + (content_w - text_w) // 2
            return margin

        surface.set_clip(pygame.Rect(margin, 0, content_w, height))
        for row_index, (span_start, span_end, line_text) in enumerate(spans):
            y = base_y + (row_index - row_offset) * line_h
            if y + line_h < 0 or y > height:
                continue
            if line_text:
                rendered = font.render(line_text, True, color[:4])
                surface.blit(rendered, (int(line_x(line_text)), int(y)))
        surface.set_clip(None)

        # Caret on its row, sized to the font.
        if focused:
            blink_visible = (pygame.time.get_ticks() // self._CARET_BLINK_MS) % 2 == 0
            if blink_visible:
                line_text = spans[row][2]
                caret_x = line_x(line_text) + font.size(line_text[:col])[0]
                caret_y = base_y + (row - row_offset) * line_h
                pygame.draw.line(surface, color[:3],
                                 (int(caret_x), int(caret_y)),
                                 (int(caret_x), int(caret_y + line_h)), width=2)

    def _update_surface(self):
        width, height = int(self.width), int(self.height)
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        bg = self._rgba(self.background_color)
        border = self._rgba(self.border_color)

        # Box background + 2px border (rounded via the per-corner radii, same
        # look as the Rect object).
        box_rect = surface.get_rect()
        radii = (int(getattr(self, 'border_top_left_radius', 0) or 0),
                 int(getattr(self, 'border_top_right_radius', 0) or 0),
                 int(getattr(self, 'border_bottom_right_radius', 0) or 0),
                 int(getattr(self, 'border_bottom_left_radius', 0) or 0))
        fill_color = bg if bg[3] < 255 else bg[:3]
        pygame.draw.rect(surface, fill_color, box_rect, border_radius=-1,
                         border_top_left_radius=radii[0],
                         border_top_right_radius=radii[1],
                         border_bottom_right_radius=radii[2],
                         border_bottom_left_radius=radii[3])
        pygame.draw.rect(surface, border[:3], box_rect, width=2,
                         border_radius=-1,
                         border_top_left_radius=radii[0],
                         border_top_right_radius=radii[1],
                         border_bottom_right_radius=radii[2],
                         border_bottom_left_radius=radii[3])

        # Content / placeholder text. Alignment only applies while the text
        # fits the box; an overflowing line scrolls (input-box style) so the
        # caret never gets pushed out of view.
        font = self._init_font()
        margin = self._TEXT_MARGIN
        content_w = max(0, width - 2 * margin)
        focused = bool(getattr(self, '_runtime_focused', False))

        caret = max(0, min(len(self.text), getattr(self, '_runtime_caret', 0)))
        text_to_draw = ''
        text_color = self._rgba(self.color)
        show_placeholder = (not self.text and self.placeholder and not focused)
        if show_placeholder:
            text_to_draw = self.placeholder
            # Placeholder is drawn faded so it reads as a hint.
            text_color = (150, 150, 150, min(255, text_color[3]))
        elif self.text:
            text_to_draw = self._runtime_display()

        align_h = str(getattr(self, 'text_align', 'left') or 'left')
        align_v = str(getattr(self, 'text_valign', 'middle') or 'middle')
        text_h = font.size('Ag')[1]

        def vertical_y():
            if align_v == 'top':
                return 2
            if align_v == 'bottom':
                return max(0, height - 2 - text_h)
            return max(0, (height - text_h) // 2)

        if text_to_draw and '\n' in text_to_draw:
            # Multi-line content (Enter inserts newlines when enter_newline
            # is on): soft-wrap each line to the box width and align the
            # whole paragraph vertically.
            self._draw_multiline(surface, font, text_to_draw, text_color,
                                 margin, content_w, width, height, caret,
                                 focused, align_h, align_v, text_h)
            surface.set_clip(None)
        elif text_to_draw:
            rendered = font.render(text_to_draw, True, text_color[:4])
            text_w = rendered.get_width()
            overflow = text_w > content_w

            if overflow:
                # Scroll long text so the caret stays visible while typing.
                prefix = text_to_draw[:caret] if not show_placeholder else ''
                caret_px = font.size(prefix)[0] if prefix else 0
                shift = max(0, caret_px - content_w)
                if caret_px < shift:
                    shift = caret_px
                text_x = margin - shift
                # Caret sits at the caret's text position relative to the
                # (scrolled) text origin; the text was already shifted by
                # ``shift``, so do NOT subtract it again here.
                caret_dx = caret_px
            else:
                if align_h == 'right':
                    text_x = width - margin - text_w
                elif align_h == 'center':
                    text_x = margin + (content_w - text_w) // 2
                else:
                    text_x = margin
                prefix_w = font.size(text_to_draw[:caret])[0] if caret else 0
                caret_dx = prefix_w

            text_y = vertical_y()
            # Clip with a DESTINATION clip (pygame's blit ``area`` is a source
            # rect and would chop off the first glyphs).
            surface.set_clip(pygame.Rect(margin, 0, content_w, height))
            surface.blit(rendered, (int(text_x), int(text_y)))
            surface.set_clip(None)

            # Runtime caret: a blinking vertical bar as TALL AS THE FONT (not
            # the whole box), aligned with the text it edits.
            if focused and not show_placeholder:
                blink_visible = (pygame.time.get_ticks() // self._CARET_BLINK_MS) % 2 == 0
                if blink_visible:
                    caret_screen_x = int(text_x + caret_dx)
                    pygame.draw.line(surface, text_color[:3],
                                     (caret_screen_x, int(text_y)),
                                     (caret_screen_x, int(text_y + text_h)), width=2)
        elif focused:
            # Empty focused box: draw a font-sized caret at the text position.
            blink_visible = (pygame.time.get_ticks() // self._CARET_BLINK_MS) % 2 == 0
            if blink_visible:
                text_y = vertical_y()
                pygame.draw.line(surface, text_color[:3],
                                 (margin, int(text_y)),
                                 (margin, int(text_y + text_h)), width=2)

        # Scale / rotate like the other objects (content is unscaled).
        scaled_size = (max(1, int(surface.get_width() * self.scale_x)),
                       max(1, int(surface.get_height() * self.scale_y)))
        scaled_surface = pygame.transform.scale(surface, scaled_size)
        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        self.surface = rotated_surface

        if not self._is_for_api and self.selected:
            pygame.draw.rect(self.surface, (0, 122, 204), self.surface.get_rect(), width=2)

        super()._update_surface()

    def _to_dict(self):
        """Serialize the config, excluding runtime-only editing state."""
        data = super()._to_dict()
        for key in ('_runtime_focused', '_runtime_caret'):
            data.pop(key, None)
        return data

    def __setattr__(self, name, value):
        if not hasattr(self, '_is_initialized') or not self._is_initialized:
            super().__setattr__(name, value)
            return

        if name == 'font_path':
            if value == '':
                super().__setattr__('font_path', '')
            else:
                project_path = Path(get_project_path())
                new_font_path = Path(value).absolute()
                try:
                    super().__setattr__('font_path', new_font_path.relative_to(project_path).as_posix())
                except ValueError:
                    super().__setattr__('font_path', new_font_path.as_posix())
        elif name in ('color', 'background_color', 'border_color'):
            # Keep colors as tuples (JSON may hand us lists).
            super().__setattr__(name, tuple(value))
        else:
            super().__setattr__(name, value)
