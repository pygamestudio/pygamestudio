from PySide6.QtGui import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *


class AlphaBackground(QWidget):
    def __init__(self):
        super().__init__()
        self._current_color = QColor(255, 0, 0, 255)

    def set_color(self, color):
        self._current_color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        checker_size = 5
        
        light_color = QColor(204, 204, 204)
        dark_color = QColor(153, 153, 153)
        
        for row in range(0, rect.height(), checker_size):
            for col in range(0, rect.width(), checker_size):
                color = light_color if (row // checker_size + col // checker_size) % 2 == 0 else dark_color
                painter.fillRect(
                    col, row,
                    min(checker_size, rect.width() - col),
                    min(checker_size, rect.height() - row),
                    color
                )
        
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0, self._current_color)
        gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(rect, gradient)
        painter.end()


class ColorPicker(QWidget):
    color_changed = Signal(tuple)

    def __init__(self):
        super().__init__()
        self._central_widget = QWidget()
        self._color_layer = QWidget()
        self._black_layer = QWidget()
        self._selector_ring = QLabel()

        self._hue_container = QWidget()
        self._hue_bg = QWidget()
        self._hue_bar = QLabel()
        
        self._alpha_container = QWidget()
        self._alpha_bg = AlphaBackground()
        self._alpha_bar = QLabel()
        
        self._current_color_selection_label = QLabel()
        self._previous_color_selection_label = QLabel()
        self._r_label = QLabel()
        self._g_label = QLabel()
        self._b_label = QLabel()
        self._a_label = QLabel()
        self._r_slider = QSlider()
        self._g_slider = QSlider()
        self._b_slider = QSlider()
        self._a_slider = QSlider()
        self._r_lineedit = QLineEdit()
        self._g_lineedit = QLineEdit()
        self._b_lineedit = QLineEdit()
        self._a_lineedit = QLineEdit()
        self._hex_label = QLabel()
        self._hex_lineedit = QLineEdit()

        self._current_hue = 0
        self._current_saturation = 100
        self._current_value = 100
        self._current_alpha = 255
        self._update_mode = 'all'

        self._start_x = None
        self._start_y = None

        self._set_up()

    def _set_up(self):
        self._set_widget()
        self._set_signal()
        self._set_layout()
        self._set_object_name()

    def _set_widget(self):
        self.resize(286, 356)
        self.setWindowTitle('Pygame Studio')
        self.setWindowIcon(QIcon(':/images/logo.png'))
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._central_widget.setStyleSheet("""
            QWidget#inspectorColorPickerCentralWidget {
                border-radius: 5px;
            }
        """)

        self._color_layer.setMinimumSize(QSize(200, 200))
        self._color_layer.setMaximumSize(QSize(200, 200))
        self._color_layer.setStyleSheet("""
            background-color: qlineargradient(
                x1:1, x2:0,
                stop:0 hsl(0%, 100%, 50%),
                stop:1 rgba(255, 255, 255, 255)
            );
        """)

        self._black_layer.setMinimumSize(QSize(200, 200))
        self._black_layer.setMaximumSize(QSize(200, 200))
        self._black_layer.setStyleSheet("""
            background-color: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(0, 0, 0, 0),
                stop:1 rgba(0, 0, 0, 255)
            );
        """)

        self._selector_ring.resize(12, 12)
        self._selector_ring.move(194, 0)
        self._selector_ring.setStyleSheet("""
            background-color: none;
            border: 2px solid #3a3a3a;
            border-radius: 6px;
        """)

        self._hue_container.setMinimumSize(QSize(26, 200))
        self._hue_container.setMaximumSize(QSize(26, 200))
        self._hue_bg.setMinimumSize(QSize(20, 200))
        self._hue_bg.setMaximumSize(QSize(20, 200))
        self._hue_bg.setStyleSheet("""
            background-color: qlineargradient(
                x1:0, y1:1, x2:0, y2:0, 
                stop:0 rgba(255, 0, 0, 255), 
                stop:0.166 rgba(255, 0, 255, 255), 
                stop:0.333 rgba(0, 0, 255, 255), 
                stop:0.5 rgba(0, 255, 255, 255), 
                stop:0.666 rgba(0, 255, 0, 255), 
                stop:0.833 rgba(255, 255, 0, 255), 
                stop:1 rgba(255, 0, 0, 255)
            );
        """)

        self._hue_bar.move(0, 0)
        self._hue_bar.setMinimumSize(QSize(26, 4))
        self._hue_bar.setMaximumSize(QSize(26, 4))
        self._hue_bar.setStyleSheet("background-color: #cccccc;")

        self._alpha_container.setMinimumSize(QSize(26, 200))
        self._alpha_container.setMaximumSize(QSize(26, 200))

        self._alpha_bg.setMinimumSize(QSize(20, 200))
        self._alpha_bg.setMaximumSize(QSize(20, 200))

        self._alpha_bar.move(0, 0)
        self._alpha_bar.setMinimumSize(QSize(26, 4))
        self._alpha_bar.setMaximumSize(QSize(26, 4))
        self._alpha_bar.setStyleSheet("background-color: #cccccc;")

        self._r_label.setText('R')
        self._g_label.setText('G')
        self._b_label.setText('B')
        self._a_label.setText('A')
        
        for slider in [self._r_slider, self._g_slider, self._b_slider, self._a_slider]:
            slider.setOrientation(Qt.Orientation.Horizontal)
            slider.setRange(0, 255)
        
        self._r_slider.setValue(255)
        self._g_slider.setValue(0)
        self._b_slider.setValue(0)
        self._a_slider.setValue(255)

        for lineedit in [self._r_lineedit, self._g_lineedit, self._b_lineedit, self._a_lineedit]:
            lineedit.setMaximumWidth(60)
            lineedit.setValidator(QIntValidator(0, 255))
        
        self._r_lineedit.setText('255')
        self._g_lineedit.setText('0')
        self._b_lineedit.setText('0')
        self._a_lineedit.setText('255')

        self._hex_label.setText('HEX')
        self._hex_lineedit.setText('#FF0000')
        
        self._current_color_selection_label.setMinimumSize(QSize(24, 24))
        self._current_color_selection_label.setMaximumSize(QSize(24, 24))
        self._previous_color_selection_label.setMinimumSize(QSize(24, 24))
        self._previous_color_selection_label.setMaximumSize(QSize(24, 24))
        self._current_color_selection_label.setStyleSheet("background-color: #FF0000;")
        self._previous_color_selection_label.setStyleSheet("background-color: #FF0000;")

        self._update_color_preview(255, 0, 0, 255)

        self.focusOutEvent = self._on_focus_out
        for slider in [self._r_slider, self._g_slider, self._b_slider, self._a_slider]:
            slider.focusOutEvent = self._on_focus_out
        for lineedit in [self._r_lineedit, self._g_lineedit, self._b_lineedit, self._a_lineedit]:
            lineedit.focusOutEvent = self._on_focus_out

        self._hex_lineedit.focusOutEvent = self._on_focus_out

    def _set_signal(self):
        self._r_slider.valueChanged.connect(self._on_slider_changed)
        self._g_slider.valueChanged.connect(self._on_slider_changed)
        self._b_slider.valueChanged.connect(self._on_slider_changed)
        self._a_slider.valueChanged.connect(self._on_slider_changed)
        
        self._r_lineedit.textChanged.connect(self._on_rgb_changed)
        self._g_lineedit.textChanged.connect(self._on_rgb_changed)
        self._b_lineedit.textChanged.connect(self._on_rgb_changed)
        self._a_lineedit.textChanged.connect(self._on_rgb_changed)
        self._hex_lineedit.textChanged.connect(self._on_hex_changed)

        self._black_layer.mousePressEvent = self._on_color_layer_press
        self._black_layer.mouseMoveEvent = self._on_color_layer_move

        self._hue_bg.mousePressEvent = self._on_hue_press
        self._hue_bg.mouseMoveEvent = self._on_hue_move

        self._alpha_bg.mousePressEvent = self._on_alpha_press
        self._alpha_bg.mouseMoveEvent = self._on_alpha_move

    def _set_layout(self):
        color_layer_v_layout = QVBoxLayout(self._color_layer)
        color_layer_v_layout.addWidget(self._black_layer)
        color_layer_v_layout.setContentsMargins(0, 0, 0, 0)
        self._selector_ring.setParent(self._black_layer)

        hue_container_v_layout = QVBoxLayout(self._hue_container)
        hue_container_v_layout.addWidget(self._hue_bg)
        hue_container_v_layout.setContentsMargins(0, 0, 0, 0)
        hue_container_v_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._hue_bar.setParent(self._hue_container)

        alpha_container_v_layout = QVBoxLayout(self._alpha_container)
        alpha_container_v_layout.addWidget(self._alpha_bg)
        alpha_container_v_layout.setContentsMargins(0, 0, 0, 0)
        alpha_container_v_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._alpha_bar.setParent(self._alpha_container)

        color_hue_alpha_h_layout = QHBoxLayout()
        color_hue_alpha_h_layout.addWidget(self._color_layer)
        color_hue_alpha_h_layout.addWidget(self._hue_container)
        color_hue_alpha_h_layout.addWidget(self._alpha_container)

        r_h_layout = QHBoxLayout()
        g_h_layout = QHBoxLayout()
        b_h_layout = QHBoxLayout()
        a_h_layout = QHBoxLayout()
        
        r_h_layout.addWidget(self._r_label)
        r_h_layout.addWidget(self._r_slider)
        r_h_layout.addWidget(self._r_lineedit)
        
        g_h_layout.addWidget(self._g_label)
        g_h_layout.addWidget(self._g_slider)
        g_h_layout.addWidget(self._g_lineedit)
        
        b_h_layout.addWidget(self._b_label)
        b_h_layout.addWidget(self._b_slider)
        b_h_layout.addWidget(self._b_lineedit)
        
        a_h_layout.addWidget(self._a_label)
        a_h_layout.addWidget(self._a_slider)
        a_h_layout.addWidget(self._a_lineedit)

        hex_selection_h_layout = QHBoxLayout()
        hex_selection_h_layout.addWidget(self._hex_label)
        hex_selection_h_layout.addWidget(self._hex_lineedit)
        hex_selection_h_layout.addWidget(self._current_color_selection_label)
        hex_selection_h_layout.addWidget(self._previous_color_selection_label)

        central_v_layout = QVBoxLayout(self._central_widget)
        central_v_layout.addLayout(color_hue_alpha_h_layout)
        central_v_layout.addLayout(r_h_layout)
        central_v_layout.addLayout(g_h_layout)
        central_v_layout.addLayout(b_h_layout)
        central_v_layout.addLayout(a_h_layout)
        central_v_layout.addLayout(hex_selection_h_layout)

        main_v_layout = QVBoxLayout(self)
        main_v_layout.addWidget(self._central_widget)
        main_v_layout.setContentsMargins(0, 0, 0, 0)

    def _set_object_name(self):
        self._central_widget.setObjectName('inspectorColorPickerCentralWidget')

    def _rgb2hex(self, r, g, b, a=255):
        if a < 255:
            return f'#{a:02X}{r:02X}{g:02X}{b:02X}'
        return f'#{r:02X}{g:02X}{b:02X}'

    def _hex2rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        try:
            if len(hex_color) == 6:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return (r, g, b, 255)
            elif len(hex_color) == 8:
                a = int(hex_color[0:2], 16)
                r = int(hex_color[2:4], 16)
                g = int(hex_color[4:6], 16)
                b = int(hex_color[6:8], 16)
                return (r, g, b, a)
            else:
                return None
        except Exception:
            return None

    def _rgb2hsv(self, rgb):
        r, g, b = [x / 255.0 for x in rgb[:3]]
        cmax = max(r, g, b)
        cmin = min(r, g, b)
        delta = cmax - cmin

        if delta == 0:
            h = 0
        elif cmax == r:
            h = ((g - b) / delta) % 6
        elif cmax == g:
            h = (b - r) / delta + 2
        else:
            h = (r - g) / delta + 4
        h = round(h * 60)

        s = 0 if cmax == 0 else (delta / cmax) * 100
        v = cmax * 100
        return (h, s, v)

    def _hsv2rgb(self, h, s, v):
        h = h / 360.0
        s = s / 100.0
        v = v / 100.0

        i = int(h * 6)
        f = h * 6 - i
        p = v * (1 - s)
        q = v * (1 - f * s)
        t = v * (1 - (1 - f) * s)

        i %= 6
        if i == 0:
            r, g, b = v, t, p
        elif i == 1:
            r, g, b = q, v, p
        elif i == 2:
            r, g, b = p, v, t
        elif i == 3:
            r, g, b = p, q, v
        elif i == 4:
            r, g, b = t, p, v
        else:
            r, g, b = v, p, q

        return (round(r * 255), round(g * 255), round(b * 255))

    def _update_color_preview(self, r, g, b, a=255):
        if a < 255:
            self._current_color_selection_label.setStyleSheet(
                f"background-color: rgba({r}, {g}, {b}, {a/255.0:.2f});"
            )
        else:
            hex_color = self._rgb2hex(r, g, b)
            self._current_color_selection_label.setStyleSheet(
                f"background-color: {hex_color};"
            )

    def _update_color_layer_gradient(self, hue):
        if hue == 360:
            hue = 0
        self._color_layer.setStyleSheet(f"""
            background-color: qlineargradient(
                x1:1, x2:0,
                stop:0 hsl({hue}, 100%, 50%),
                stop:1 rgba(255, 255, 255, 255)
            );
        """)

    def _update_alpha_bg_gradient(self, r, g, b):
        self._alpha_bg.set_color(QColor(r, g, b, 255))

    def _update_selector_ring_position(self, saturation, value):
        x = int(saturation * 200 / 100)
        y = int((100 - value) * 200 / 100)
        x = max(0, min(200, x))
        y = max(0, min(200, y))
        offset = 6
        self._selector_ring.move(x - offset, y - offset)

    def _update_hue_bar_position(self, hue):
        bg_height = self._hue_bg.height()
        bar_height = self._hue_bar.height()
        if bg_height <= 0:
            return
        max_y = bg_height - bar_height
        y = int(hue * max_y / 360)
        y = max(0, min(max_y, y))
        self._hue_bar.move(0, y)

    def _update_alpha_bar_position(self, alpha):
        bg_height = self._alpha_bg.height()
        bar_height = self._alpha_bar.height()
        if bg_height <= 0:
            return
        max_y = bg_height - bar_height
        y = int((255 - alpha) * max_y / 255)
        y = max(0, min(max_y, y))
        self._alpha_bar.move(0, y)

    def _update_all_visuals(self, r, g, b, a=None, h=None, s=None, v=None):
        if a is None:
            a = self._current_alpha

        if not h and not s and not v:
            h, s, v = self._rgb2hsv((r, g, b))
        self._current_hue = h
        self._current_saturation = s
        self._current_value = v
        self._current_alpha = a

        self._update_color_preview(r, g, b, a)
        self._update_alpha_bg_gradient(r, g, b)

        if self._update_mode == 'all':
            self._update_color_layer_gradient(h)
            self._update_selector_ring_position(s, v)
            self._update_hue_bar_position(h)
            self._update_alpha_bar_position(a)
        elif self._update_mode == 'hue_only':
            self._update_color_layer_gradient(h)
            self._update_hue_bar_position(h)
        elif self._update_mode == 'sv_only':
            self._update_selector_ring_position(s, v)
        elif self._update_mode == 'alpha_only':
            self._update_alpha_bar_position(a)

        self.color_changed.emit((r, g, b, a))

    def _on_color_layer_press(self, event):
        self._update_color_from_pos(event.position())

    def _on_color_layer_move(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._update_color_from_pos(event.position())

    def _update_color_from_pos(self, pos):
        self._update_mode = 'sv_only'

        x = max(0, min(200, int(pos.x())))
        y = max(0, min(200, int(pos.y())))
        saturation = int(x * 100 / 200)
        value = int((200 - y) * 100 / 200)

        h = self._current_hue
        r, g, b = self._hsv2rgb(h, saturation, value)
        self._current_saturation = saturation
        self._current_value = value

        self._set_rgba((r, g, b, self._current_alpha))
        hex_color = self._rgb2hex(r, g, b, self._current_alpha)
        self._set_hex(hex_color)
        self._update_all_visuals(r, g, b)
        self._update_mode = 'all'

    def _on_hue_press(self, event):
        self._update_hue_from_pos(event.position())

    def _on_hue_move(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._update_hue_from_pos(event.position())

    def _update_hue_from_pos(self, pos):
        self._update_mode = 'hue_only'

        bg_height = self._hue_bg.height()
        bar_height = self._hue_bar.height()
        if bg_height <= 0:
            return

        max_y = bg_height - bar_height
        pos_y = max(0, min(max_y, pos.y()))
        hue = int(pos_y * 360 / max_y) if max_y > 0 else 0
        hue = max(0, min(360, hue))
        saturation = self._current_saturation if self._current_saturation > 0 else 100
        value = self._current_value if self._current_value > 0 else 100

        r, g, b = self._hsv2rgb(hue, saturation, value)
        self._current_hue = hue
        self._current_saturation = saturation
        self._current_value = value

        hex_color = self._rgb2hex(r, g, b, self._current_alpha)
        self._set_hex(hex_color)
        self._update_all_visuals(r, g, b, self._current_alpha, hue, saturation, value)
        self._update_mode = 'all'

    def _on_alpha_press(self, event):
        self._update_alpha_from_pos(event.position())

    def _on_alpha_move(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._update_alpha_from_pos(event.position())

    def _update_alpha_from_pos(self, pos):
        self._update_mode = 'alpha_only'

        bg_height = self._alpha_bg.height()
        bar_height = self._alpha_bar.height()
        if bg_height <= 0:
            return

        max_y = bg_height - bar_height
        pos_y = max(0, min(max_y, pos.y()))
        alpha = 255 - int(pos_y * 255 / max_y) if max_y > 0 else 255
        alpha = max(0, min(255, alpha))

        self._current_alpha = alpha
        r = self._r_slider.value()
        g = self._g_slider.value()
        b = self._b_slider.value()

        self._a_slider.blockSignals(True)
        self._a_lineedit.blockSignals(True)
        self._a_slider.setValue(alpha)
        self._a_lineedit.setText(str(alpha))
        self._a_slider.blockSignals(False)
        self._a_lineedit.blockSignals(False)

        hex_color = self._rgb2hex(r, g, b, alpha)
        self._set_hex(hex_color)
        self._update_all_visuals(r, g, b, alpha)
        self._update_mode = 'all'

    def _on_slider_changed(self):
        self._update_mode = 'all'
        r = self._r_slider.value()
        g = self._g_slider.value()
        b = self._b_slider.value()
        a = self._a_slider.value()

        self._r_lineedit.setText(str(r))
        self._g_lineedit.setText(str(g))
        self._b_lineedit.setText(str(b))
        self._a_lineedit.setText(str(a))

        hex_color = self._rgb2hex(r, g, b, a)
        self._set_hex(hex_color)
        self._update_all_visuals(r, g, b, a)

    def _on_rgb_changed(self):
        self._update_mode = 'all'
        r = self._r_lineedit.text()
        g = self._g_lineedit.text()
        b = self._b_lineedit.text()
        a = self._a_lineedit.text()

        r = 0 if not r else (255 if int(r) > 255 else int(r))
        g = 0 if not g else (255 if int(g) > 255 else int(g))
        b = 0 if not b else (255 if int(b) > 255 else int(b))
        a = 255 if not a else (255 if int(a) > 255 else int(a))

        self._r_slider.setValue(r)
        self._g_slider.setValue(g)
        self._b_slider.setValue(b)
        self._a_slider.setValue(a)

        hex_color = self._rgb2hex(r, g, b, a)
        self._set_hex(hex_color)
        self._update_all_visuals(r, g, b, a)

    def _on_hex_changed(self, text):
        self._update_mode = 'all'
        rgba = self._hex2rgb(text)
        if not rgba:
            return
        self._set_rgba(rgba)
        self._update_all_visuals(*rgba)

    def _set_rgba(self, rgba):
        r, g, b, a = rgba
        
        for slider in [self._r_slider, self._g_slider, self._b_slider, self._a_slider]:
            slider.blockSignals(True)
        for lineedit in [self._r_lineedit, self._g_lineedit, self._b_lineedit, self._a_lineedit]:
            lineedit.blockSignals(True)

        self._r_slider.setValue(r)
        self._g_slider.setValue(g)
        self._b_slider.setValue(b)
        self._a_slider.setValue(a)
        self._r_lineedit.setText(str(r))
        self._g_lineedit.setText(str(g))
        self._b_lineedit.setText(str(b))
        self._a_lineedit.setText(str(a))

        for slider in [self._r_slider, self._g_slider, self._b_slider, self._a_slider]:
            slider.blockSignals(False)
        for lineedit in [self._r_lineedit, self._g_lineedit, self._b_lineedit, self._a_lineedit]:
            lineedit.blockSignals(False)

    def set_rgba(self, rgba):
        self._set_rgba(rgba)
        self._update_all_visuals(*rgba)

    def _set_hex(self, hex_color):
        self._hex_lineedit.blockSignals(True)
        self._hex_lineedit.setText(hex_color)
        self._hex_lineedit.blockSignals(False)

    def _on_focus_out(self, event):
        pos = QCursor.pos()
        x = pos.x()
        y = pos.y()

        if x < self.geometry().x() or y < self.geometry().y() or x > self.geometry().x() + self.geometry().width() or y > self.geometry().y() + self.geometry().height():
            self.close()
    
    def closeEvent(self, event):
        r = int(self._r_lineedit.text())
        g = int(self._g_lineedit.text())
        b = int(self._b_lineedit.text())
        a = int(self._a_lineedit.text())
        self._previous_color_selection_label.setStyleSheet(f"background-color: rgba({r}, {g}, {b}, {a/255.0:.2f});")
        return super().closeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:       
            self._start_x = event.x()
            self._start_y = event.y()
    
    def mouseMoveEvent(self, event):
        if not self._start_x or not self._start_y:
                return
    
        dis_x = event.x() - self._start_x
        dis_y = event.y() - self._start_y
        self.move(self.x() + dis_x, self.y() + dis_y)
    
    def mouseReleaseEvent(self, event):
        self._start_x = None
        self._start_y = None